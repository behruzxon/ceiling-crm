"""
core.services.lead_notification_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin-group notification service for new and HOT leads.

This service manages its own Bot lifecycle and DB sessions so it can be
called fire-and-forget after the main transaction has committed.

Public API
----------
  is_hot_lead(lead) -> bool               — pure predicate
  LeadNotificationService.notify_new_lead(lead)   — "🆕 Yangi lid" card
  LeadNotificationService.notify_hot_lead(lead_id) — "🔥 HOT LEAD" alert (deduped)
"""
from __future__ import annotations

from core.domain.lead import Lead
from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.database.repositories.audit_log_repo import PostgresAuditLogRepository
from infrastructure.database.repositories.lead_action_repo import PostgresLeadActionRepository
from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.session import get_session_factory
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

HOT_SCORE_THRESHOLD = 7


def is_hot_lead(lead: Lead) -> bool:
    """Return True if the lead should trigger a HOT admin alert."""
    return lead.lead_status == "hot" or (lead.score or 0) >= HOT_SCORE_THRESHOLD


class LeadNotificationService:
    """
    Sends admin-group notifications for new and HOT leads.

    Each public method creates its own Bot instance + DB session so the
    caller never needs to worry about session state or Bot lifecycle.
    Methods never raise — all exceptions are caught and logged.
    """

    def __init__(self, admin_user_id: int, bot_token: str) -> None:
        self._admin_user_id = admin_user_id
        self._bot_token = bot_token

    # ── Public API ─────────────────────────────────────────────────────────────

    @staticmethod
    def _lead_status_keyboard(lead_id: int) -> "InlineKeyboardMarkup":
        """Build the quick-action inline keyboard appended to every lead card."""
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📌 Kanban'da ochish",
                    callback_data=f"kanban:lead:{lead_id}:new",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Bog'landim",
                    callback_data=f"lead:{lead_id}:status:contacted",
                ),
                InlineKeyboardButton(
                    text="📅 O'lchov",
                    callback_data=f"lead:{lead_id}:status:measurement",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Narx yuborildi",
                    callback_data=f"lead:{lead_id}:status:quoted",
                ),
                InlineKeyboardButton(
                    text="🧾 Zakaz",
                    callback_data=f"lead:{lead_id}:status:deal",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="\u274c Yo'qotildi",
                    callback_data=f"lead:{lead_id}:status:lost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="\U0001f4a1 Operator yordam",
                    callback_data=f"op:menu:{lead_id}",
                ),
            ],
        ])

    async def notify_new_lead(self, lead: Lead) -> None:
        """Send a NEW lead card to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        text = self._new_lead_text(lead)
        keyboard = self._lead_status_keyboard(lead.id)

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, keyboard)
            await self._log_new_lead_action(lead.id)
        except Exception:
            log.exception("notify_new_lead_error", lead_id=lead.id)
        finally:
            await bot.session.close()

    async def notify_hot_lead(self, lead_id: int) -> None:
        """Send a HOT lead alert once, deduped by last_action. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        factory = get_session_factory()
        async with factory() as session:
            try:
                lead_repo = PostgresLeadRepository(session)
                lead = await lead_repo.get_by_id(lead_id)
                if lead is None:
                    log.warning("notify_hot_lead_not_found", lead_id=lead_id)
                    return
                if lead.last_action == "hot_alert_sent":
                    log.debug("notify_hot_lead_skipped_dedupe", lead_id=lead_id)
                    return

                text = self._hot_lead_text(lead)
                keyboard = self._lead_status_keyboard(lead_id)

                bot = Bot(
                    token=self._bot_token,
                    default=DefaultBotProperties(parse_mode="HTML"),
                )
                try:
                    await self._send_to_groups_and_dm(bot, text, keyboard)

                    # Dedupe marker + audit trail (same session — atomic)
                    await lead_repo.update_last_action(lead_id, "hot_alert_sent")
                    await PostgresLeadActionRepository(session).insert(
                        lead_id, self._admin_user_id, "admin_notify_hot"
                    )
                    await PostgresAuditLogRepository(session).insert(
                        actor_id=self._admin_user_id,
                        action="lead.hot_alert_sent",
                        entity_type="lead",
                        entity_id=lead_id,
                        new_value={"last_action": "hot_alert_sent"},
                    )
                    await session.commit()
                except Exception:
                    log.exception("notify_hot_lead_error", lead_id=lead_id)
                    await session.rollback()
                finally:
                    await bot.session.close()

            except Exception:
                log.exception("notify_hot_lead_outer_error", lead_id=lead_id)

    # ── Internals ──────────────────────────────────────────────────────────────

    @staticmethod
    def _new_lead_text(lead: Lead) -> str:
        dims = ""
        if lead.room_length and lead.room_width:
            dims = f"\n📐 O'lcham: {lead.room_length} × {lead.room_width} m"
        temp_tag = f"\n🌡 Holat: {lead.lead_temperature}" if lead.lead_temperature else ""
        conf_tag = (
            f"\n💡 Ishonch: {lead.closing_confidence:.0%}"
            if lead.closing_confidence is not None
            else ""
        )
        category_str = lead.category.value if lead.category else "—"
        return (
            f"🆕 <b>Yangi lid keldi!</b>\n\n"
            f"📋 Lid #{lead.id}\n"
            f"👤 {lead.name}\n"
            f"📱 {lead.phone}\n"
            f"📍 {lead.district}\n"
            f"🏷 {category_str}{dims}{temp_tag}{conf_tag}\n\n"
            f"/lead_{lead.id}"
        )

    @staticmethod
    def _hot_lead_text(lead: Lead) -> str:
        score_tag = f" ⭐{lead.score}" if lead.score else ""
        pkg_tag = f"\n📦 Paket: {lead.package_type}" if lead.package_type else ""
        return (
            f"🔥 <b>HOT LEAD!</b>{score_tag}\n\n"
            f"📋 Lid #{lead.id}\n"
            f"👤 {lead.name}\n"
            f"📱 {lead.phone}\n"
            f"📍 {lead.district}{pkg_tag}\n\n"
            f"/lead_{lead.id}"
        )

    async def _send_to_groups_and_dm(self, bot: object, text: str, keyboard: object) -> None:
        """Deliver *text*+*keyboard* to admin DM and all tracked admin groups."""
        # Admin DM
        try:
            await bot.send_message(self._admin_user_id, text, reply_markup=keyboard)  # type: ignore[union-attr]
        except Exception as exc:
            log.warning("notify_admin_dm_failed", error=str(exc))

        # Admin groups
        try:
            factory = get_session_factory()
            async with factory() as session:
                group_ids = await PostgresAdminGroupRepository(session).list_all_chat_ids()
        except Exception:
            log.exception("notify_get_groups_error")
            return

        admin_group_id = get_settings().bot.admin_group_id
        for gid in group_ids:
            # Hard whitelist: only send to the designated admin group.
            # Prevents the main customer group (BOT_MAIN_GROUP_ID) from
            # receiving lead cards even if it was previously recorded.
            if gid != admin_group_id:
                log.warning("notify_skip_non_admin_group", chat_id=gid)
                continue
            try:
                await bot.send_message(gid, text, reply_markup=keyboard)  # type: ignore[union-attr]
            except Exception as exc:
                log.warning("notify_group_failed", chat_id=gid, error=str(exc))

    async def notify_measurement_lead(
        self,
        lead: "Lead",
        *,
        time_pref: str | None,
        dimensions: str | None,
        lead_temperature: str | None,
        closing_confidence: float | None,
        chat_type: str,
        chat_id: int,
        tg_user_id: int,
        username: str | None,
    ) -> None:
        """Send a measurement-lead card to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        conf_str = f"{closing_confidence:.0%}" if closing_confidence is not None else "—"
        uname_str = f"@{username}" if username else "—"
        time_str = time_pref or "Ko'rsatilmagan"

        text = (
            f"📐 <b>Bepul o'lchov so'rovi!</b>\n\n"
            f"📋 Lid #{lead.id}\n"
            f"👤 Ism: {lead.name}\n"
            f"📱 Telefon: {lead.phone}\n"
            f"📍 Manzil: {lead.district}\n"
            f"🕐 Vaqt: {time_str}\n"
            f"📐 O'lcham: {dimensions or '—'}\n"
            f"🌡 Holat: {lead_temperature or '—'}\n"
            f"💡 Ishonch: {conf_str}\n\n"
            f"🔗 {chat_type} | {uname_str} | /lead_{lead.id}"
        )
        keyboard = self._lead_status_keyboard(lead.id)

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, keyboard)
            await self._log_new_lead_action(lead.id)
        except Exception:
            log.exception("notify_measurement_lead_error", lead_id=lead.id)
        finally:
            await bot.session.close()

    async def notify_draft_lead(
        self,
        *,
        phone: str,
        name: str | None,
        username: str | None,
        user_id: int | None,
        chat_type: str,
        chat_id: int,
    ) -> None:
        """Send a draft phone-capture alert to admin DM only. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        uname_str = f"@{username}" if username else "—"
        name_str = name or "Noma'lum"
        uid_str = str(user_id) if user_id else "—"

        text = (
            f"📞 <b>Telefon raqam aniqlandi!</b>\n\n"
            f"📱 {phone}\n"
            f"👤 {name_str}\n"
            f"🔗 {uname_str} | #{uid_str} | {chat_type}"
        )

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await bot.send_message(self._admin_user_id, text)
        except Exception as exc:
            log.warning("notify_draft_lead_failed", error=str(exc))
        finally:
            await bot.session.close()

    # Shared score badges used by several notification methods
    _SCORE_BADGES: dict[str, str] = {
        "hot":  "🔥 HOT LEAD",
        "warm": "🟡 WARM LEAD",
        "cold": "⚪ COLD LEAD",
    }

    async def notify_ai_lead_collected(
        self,
        *,
        phone: str,
        district: str,
        area: float | None,
        room: str | None,
        design: str | None = None,
        name: str | None,
        username: str | None,
        user_id: int | None,
        score: int = 0,
        last_message: str = "",
        lead_id: int | None = None,
        last_objection: str | None = None,
        closing_attempted: bool = False,
        closing_action: str | None = None,
        deal_probability: object | None = None,
        buyer_profile: object | None = None,
        revenue_estimate: object | None = None,
        negotiation_tactic: str | None = None,
        negotiation_escalated: bool = False,
        conversation_graph: object | None = None,
        followup_decision: object | None = None,
        sales_brain: object | None = None,
    ) -> None:
        """Send AI-collected lead card to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        if score >= 60:
            badge = "\U0001f525 HOT LEAD"
        elif score >= 30:
            badge = "\U0001f7e1 WARM LEAD"
        else:
            badge = "\u2744\ufe0f COLD LEAD"

        # Recommended action: prefer probability engine, fallback to simple rules
        if deal_probability is not None:
            rec_action = deal_probability.recommended_action  # type: ignore[union-attr]
        elif score >= 60:
            rec_action = "\U0001f4de Zudlik bilan qo'ng'iroq qiling!"
        elif last_objection == "expensive":
            rec_action = "\U0001f4b0 Byudjet variantini taklif qiling"
        elif last_objection == "delay":
            rec_action = "\u23f0 24 soatdan keyin follow-up"
        elif score >= 30:
            rec_action = "\U0001f4cb O'lchov taklif qiling"
        else:
            rec_action = "\U0001f4e8 Ma'lumot yuboring"

        name_str = name or "Noma'lum"
        lines = [f"<b>{badge}</b> (score: {score})\n", f"Ism: {name_str}"]
        if username:
            lines.append(f"Username: @{username}")
        elif user_id:
            lines.append(f"Telegram: <a href='tg://user?id={user_id}'>{user_id}</a>")
        lines.append(f"Tel: {phone}")
        if district:
            lines.append(f"Tuman: {district}")
        if area is not None:
            lines.append(f"Maydon: {area:g} m\u00b2")
        if design:
            lines.append(f"Dizayn: {design}")
        if room:
            lines.append(f"Xona: {room}")
        if last_objection:
            _obj_labels = {
                "expensive": "\U0001f4b8 Qimmat",
                "trust": "\U0001f914 Ishonch",
                "compare": "\u2696\ufe0f Taqqoslash",
                "delay": "\u23f3 Keyinroq",
                "angry": "\U0001f624 Norozilik",
            }
            lines.append(f"E'tiroz: {_obj_labels.get(last_objection, last_objection)}")
        if closing_attempted:
            _action_labels = {
                "measurement": "Bepul o'lchov",
                "call": "Menejer qo'ng'iroq",
                "catalog": "Katalog yuborish",
            }
            action_label = _action_labels.get(closing_action or "", closing_action or "\u2014")
            lines.append(f"Closing: Ha \u2705 ({action_label})")

        # ── Deal probability + revenue section (concise) ─────────────────
        if deal_probability is not None:
            dp = deal_probability
            _conf_labels = {"high": "yuqori", "medium": "o'rtacha", "low": "past"}
            conf_label = _conf_labels.get(dp.confidence_level, dp.confidence_level)  # type: ignore[union-attr]
            lines.append("")
            lines.append(
                f"\U0001f4ca Ehtimol: {dp.deal_probability_percent}%"  # type: ignore[union-attr]
                f" ({conf_label})"
            )
            # Revenue range (preferred) or simple expected value
            if revenue_estimate is not None and revenue_estimate.predicted_revenue_best is not None:  # type: ignore[union-attr]
                re = revenue_estimate
                lines.append(
                    f"\U0001f4b0 Daromad: {re.predicted_revenue_min:,}"  # type: ignore[union-attr]
                    f" \u2013 {re.predicted_revenue_max:,} UZS"  # type: ignore[union-attr]
                )
                lines.append(
                    f"\U0001f4b5 Eng yaxshi: {re.predicted_revenue_best:,} UZS"  # type: ignore[union-attr]
                )
                _upsell_labels = {"high": "yuqori", "medium": "o'rtacha", "low": "past"}
                lines.append(
                    f"\U0001f4e6 Upsell: {_upsell_labels.get(re.upsell_potential, re.upsell_potential)}"  # type: ignore[union-attr]
                    f" \u2014 {re.recommended_upsell}"  # type: ignore[union-attr]
                )
            elif dp.expected_deal_value is not None:  # type: ignore[union-attr]
                lines.append(
                    f"\U0001f4b0 Kutilgan: {dp.expected_deal_value:,} UZS"  # type: ignore[union-attr]
                )
            lines.append(f"Tavsiya: {rec_action}")
        else:
            lines.append(f"Tavsiya: {rec_action}")

        # ── Buyer type section (concise) ──────────────────────────────
        if buyer_profile is not None:
            bp = buyer_profile
            _bt_labels = {
                "price_sensitive": "\U0001f4b2 Narxga sezgir",
                "quality_buyer": "\u2b50 Sifat xaridori",
                "fast_buyer": "\u26a1 Tez qaror",
                "research_buyer": "\U0001f50d Tadqiqotchi",
            }
            bt_label = _bt_labels.get(bp.buyer_type, bp.buyer_type)  # type: ignore[union-attr]
            lines.append(
                f"\U0001f9e0 Xaridor: {bt_label}"
                f" ({bp.confidence:.0%})"  # type: ignore[union-attr]
            )
            lines.append(f"\U0001f4de Strategiya: {bp.strategy}")  # type: ignore[union-attr]

        # ── Negotiation section (concise) ───────────────────────────
        if negotiation_tactic and negotiation_tactic != "none":
            from core.services.negotiation_engine_service import TACTIC_LABELS
            tactic_label = TACTIC_LABELS.get(negotiation_tactic, negotiation_tactic)
            esc_flag = " \u26a0\ufe0f ESCALATE" if negotiation_escalated else ""
            lines.append(f"\U0001f91d Muzokara: {tactic_label}{esc_flag}")

        # ── Conversation graph section (concise) ──────────────────
        if conversation_graph is not None:
            from core.services.conversation_memory_graph_service import (
                STAGE_LABELS,
                TREND_LABELS,
            )
            cg = conversation_graph
            stage_label = STAGE_LABELS.get(
                cg.current_decision_stage, cg.current_decision_stage  # type: ignore[union-attr]
            )
            trend_label = TREND_LABELS.get(
                cg.engagement_trend, cg.engagement_trend  # type: ignore[union-attr]
            )
            lines.append(
                f"\U0001f4cd Bosqich: {stage_label} | {trend_label}"
            )
            if cg.recommended_next_step:  # type: ignore[union-attr]
                lines.append(f"\u27a1 Keyingi: {cg.recommended_next_step}")  # type: ignore[union-attr]

        # ── Follow-up decision section (concise) ──────────────────
        if followup_decision is not None and followup_decision.should_follow_up:  # type: ignore[union-attr]
            from core.services.followup_brain_service import FU_TYPE_LABELS
            fd = followup_decision
            fd_label = FU_TYPE_LABELS.get(
                fd.follow_up_type, fd.follow_up_type  # type: ignore[union-attr]
            )
            _dm = fd.follow_up_delay_minutes  # type: ignore[union-attr]
            if _dm and _dm < 60:
                delay_str = f"{_dm} daqiqa"
            elif _dm:
                delay_str = f"{_dm // 60} soat"
            else:
                delay_str = "\u2014"
            lines.append(f"\u23f0 FU: {fd_label} | {delay_str}")

        # ── Sales Brain unified section (replaces standalone radar) ──
        if sales_brain is not None:
            from core.services.deal_radar_service import BUCKET_LABELS
            _bl = BUCKET_LABELS.get(
                sales_brain.priority, sales_brain.priority  # type: ignore[union-attr]
            )
            lines.append(
                f"\U0001f9e0 Brain: {_bl} | "
                f"{sales_brain.win_probability}% ehtimol"  # type: ignore[union-attr]
            )
            lines.append(
                f"\u27a1 {sales_brain.recommended_action}"  # type: ignore[union-attr]
            )
            if sales_brain.risk_flags:  # type: ignore[union-attr]
                lines.append(
                    f"\u26a0\ufe0f {sales_brain.risk_flags[0]}"  # type: ignore[union-attr]
                )
        else:
            # Fallback: inline radar for callers that don't pass sales_brain
            try:
                from core.services.deal_radar_service import (
                    BUCKET_LABELS as _BL,
                    rank_lead_for_radar,
                )
                _radar = rank_lead_for_radar(
                    score=score,
                    deal_probability_percent=(
                        deal_probability.deal_probability_percent  # type: ignore[union-attr]
                        if deal_probability else None
                    ),
                    predicted_revenue_best=(
                        revenue_estimate.predicted_revenue_best  # type: ignore[union-attr]
                        if revenue_estimate else None
                    ),
                    buyer_type=(
                        buyer_profile.buyer_type  # type: ignore[union-attr]
                        if buyer_profile else None
                    ),
                    negotiation_escalated=negotiation_escalated,
                    decision_stage=(
                        conversation_graph.current_decision_stage  # type: ignore[union-attr]
                        if conversation_graph else None
                    ),
                    engagement_trend=(
                        conversation_graph.engagement_trend  # type: ignore[union-attr]
                        if conversation_graph else None
                    ),
                    phone_captured=bool(phone),
                    has_area=area is not None,
                    has_district=bool(district),
                    closing_attempted=closing_attempted,
                    closing_confidence=None,
                    lead_status=None,
                )
                _bl2 = _BL.get(_radar.radar_bucket, _radar.radar_bucket)
                lines.append(
                    f"\U0001f4e1 Radar: {_bl2} | {_radar.radar_priority_score}%"
                )
            except Exception:
                pass

        if last_message:
            lines.append(f"So'nggi xabar: {last_message[:120]}")
        text = "\n".join(lines)

        keyboard = self._lead_status_keyboard(lead_id) if lead_id else None

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, keyboard)
        except Exception as exc:
            log.warning("notify_ai_lead_failed", error=str(exc))
        finally:
            await bot.session.close()

    async def notify_lead_interest(
        self,
        *,
        score: str,
        name: str | None,
        username: str | None,
        user_id: int | None,
        topic: str,
    ) -> None:
        """Send a WARM/COLD interest signal to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        badge = self._SCORE_BADGES.get(score, "🟡 WARM LEAD")
        lines = [f"<b>{badge}</b>\n"]
        if name:
            lines.append(f"Ism: {name}")
        if username:
            lines.append(f"Username: @{username}")
        elif user_id:
            lines.append(f"Telegram: <a href='tg://user?id={user_id}'>{user_id}</a>")
        lines.append(f"Savol: {topic}")
        text = "\n".join(lines)

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, None)
        except Exception as exc:
            log.warning("notify_lead_interest_failed", error=str(exc))
        finally:
            await bot.session.close()

    async def _log_new_lead_action(self, lead_id: int) -> None:
        """Insert lead_action + audit_log for a new-lead notification."""
        factory = get_session_factory()
        async with factory() as session:
            try:
                await PostgresLeadActionRepository(session).insert(
                    lead_id, self._admin_user_id, "admin_notify_new"
                )
                await PostgresAuditLogRepository(session).insert(
                    actor_id=self._admin_user_id,
                    action="lead.admin_notify_new",
                    entity_type="lead",
                    entity_id=lead_id,
                )
                await session.commit()
            except Exception:
                log.exception("notify_log_new_lead_error", lead_id=lead_id)
