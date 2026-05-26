"""
core.services.crm_campaign_analytics_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Campaign delivery analytics. Pure functions — read-only, no mutations.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)


@dataclass(frozen=True)
class DeliveryMetrics:
    total_attempts: int = 0
    proposed: int = 0
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    blocked_rate: float = 0.0
    unique_contacts: int = 0
    duplicate_blocked: int = 0


@dataclass(frozen=True)
class CanaryMetrics:
    canary_sent: int = 0
    canary_failed: int = 0
    non_canary_skipped: int = 0


@dataclass(frozen=True)
class ReplyMetrics:
    reply_count: int = 0
    reply_rate: float = 0.0
    contacts_replied: int = 0
    first_reply_avg_minutes: float = 0.0
    hot_replies: int = 0


@dataclass(frozen=True)
class StatusChangeMetrics:
    status_changes: int = 0
    status_change_rate: float = 0.0
    by_status: list[tuple[str, int]] = field(default_factory=list)


@dataclass(frozen=True)
class CampaignRecommendation:
    priority: str = "medium"
    title: str = ""
    description: str = ""


@dataclass(frozen=True)
class CampaignAnalytics:
    campaign_id: int = 0
    delivery: DeliveryMetrics = field(default_factory=DeliveryMetrics)
    blocked_reasons: list[tuple[str, int]] = field(default_factory=list)
    failure_reasons: list[tuple[str, int]] = field(default_factory=list)
    canary: CanaryMetrics = field(default_factory=CanaryMetrics)
    replies: ReplyMetrics = field(default_factory=ReplyMetrics)
    status_changes: StatusChangeMetrics = field(default_factory=StatusChangeMetrics)
    recommendations: list[CampaignRecommendation] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=True)
class DashboardSummary:
    total_campaigns: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_blocked: int = 0
    overall_success_rate: float = 0.0
    overall_reply_rate: float = 0.0
    top_segments: list[tuple[str, int]] = field(default_factory=list)


class CRMCampaignAnalyticsService:
    """Campaign delivery analytics. Read-only, pure functions."""

    @staticmethod
    def get_delivery_metrics(attempts: list[dict[str, Any]]) -> DeliveryMetrics:
        if not attempts:
            return DeliveryMetrics()
        total = len(attempts)
        proposed = sum(1 for a in attempts if a.get("status") == "proposed")
        sent = sum(1 for a in attempts if a.get("status") == "sent")
        failed = sum(1 for a in attempts if a.get("status") == "failed")
        blocked = sum(1 for a in attempts if a.get("status") == "blocked")
        skipped = sum(1 for a in attempts if a.get("status") == "skipped")
        contacts = {a.get("contact_id") for a in attempts if a.get("contact_id")}
        dup_blocked = sum(1 for a in attempts if a.get("blocked_reason") == "duplicate_send")
        sr = sent / total if total > 0 else 0.0
        fr = failed / total if total > 0 else 0.0
        br = blocked / total if total > 0 else 0.0
        return DeliveryMetrics(
            total_attempts=total, proposed=proposed, sent=sent, failed=failed,
            blocked=blocked, skipped=skipped,
            success_rate=round(sr, 3), failure_rate=round(fr, 3), blocked_rate=round(br, 3),
            unique_contacts=len(contacts), duplicate_blocked=dup_blocked,
        )

    @staticmethod
    def get_blocked_reason_metrics(attempts: list[dict[str, Any]]) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for a in attempts:
            if a.get("status") == "blocked" and a.get("blocked_reason"):
                reason = a["blocked_reason"]
                counts[reason] = counts.get(reason, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)

    @staticmethod
    def get_failure_reason_metrics(attempts: list[dict[str, Any]]) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for a in attempts:
            if a.get("status") == "failed":
                err = a.get("error_message", "unknown")[:50] or "unknown"
                err = _TOKEN_RE.sub("[REDACTED]", err)
                counts[err] = counts.get(err, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)

    @staticmethod
    def get_canary_metrics(attempts: list[dict[str, Any]]) -> CanaryMetrics:
        canary_sent = sum(1 for a in attempts if a.get("status") == "sent" and a.get("metadata_json", {}).get("is_canary"))
        canary_failed = sum(1 for a in attempts if a.get("status") == "failed" and a.get("metadata_json", {}).get("is_canary"))
        non_canary_skip = sum(1 for a in attempts if a.get("blocked_reason") == "not_in_canary")
        return CanaryMetrics(canary_sent=canary_sent, canary_failed=canary_failed, non_canary_skipped=non_canary_skip)

    @staticmethod
    def get_reply_metrics(
        sent_attempts: list[dict[str, Any]],
        inbound_messages: list[dict[str, Any]],
        window_hours: int = 72,
    ) -> ReplyMetrics:
        if not sent_attempts:
            return ReplyMetrics()
        sent_contacts: dict[int, str] = {}
        for a in sent_attempts:
            if a.get("status") == "sent" and a.get("contact_id"):
                sent_contacts[a["contact_id"]] = a.get("sent_at", "")
        if not sent_contacts:
            return ReplyMetrics()
        replied_contacts: set[int] = set()
        reply_minutes: list[float] = []
        hot_count = 0
        for msg in inbound_messages:
            cid = msg.get("contact_id", 0)
            if cid not in sent_contacts:
                continue
            if msg.get("direction") != "inbound":
                continue
            replied_contacts.add(cid)
            if msg.get("lead_status") in ("hot", "operator_needed"):
                hot_count += 1
        reply_count = len(replied_contacts)
        total_sent = len(sent_contacts)
        rate = reply_count / total_sent if total_sent > 0 else 0.0
        avg_min = sum(reply_minutes) / len(reply_minutes) if reply_minutes else 0.0
        return ReplyMetrics(
            reply_count=reply_count, reply_rate=round(rate, 3),
            contacts_replied=reply_count, first_reply_avg_minutes=round(avg_min, 1),
            hot_replies=hot_count,
        )

    @staticmethod
    def get_status_change_metrics(
        sent_attempts: list[dict[str, Any]],
        contact_status_changes: list[dict[str, Any]],
    ) -> StatusChangeMetrics:
        if not sent_attempts:
            return StatusChangeMetrics()
        sent_ids = {a.get("contact_id") for a in sent_attempts if a.get("status") == "sent"}
        changes = [c for c in contact_status_changes if c.get("contact_id") in sent_ids]
        if not changes:
            return StatusChangeMetrics()
        by_status: dict[str, int] = {}
        for c in changes:
            new_status = c.get("new_status", "unknown")
            by_status[new_status] = by_status.get(new_status, 0) + 1
        total_sent = len(sent_ids)
        total_changes = len(changes)
        rate = total_changes / total_sent if total_sent > 0 else 0.0
        return StatusChangeMetrics(
            status_changes=total_changes, status_change_rate=round(rate, 3),
            by_status=sorted(by_status.items(), key=lambda x: x[1], reverse=True),
        )

    @staticmethod
    def build_recommendations(
        delivery: DeliveryMetrics,
        blocked_reasons: list[tuple[str, int]],
        canary: CanaryMetrics,
        replies: ReplyMetrics,
    ) -> list[CampaignRecommendation]:
        recs: list[CampaignRecommendation] = []
        blocked_dict = dict(blocked_reasons)
        if blocked_dict.get("no_telegram_id", 0) > 3:
            recs.append(CampaignRecommendation(
                priority="medium", title="Contact data quality",
                description="Ko'p contact telegram ID yo'q — data quality yaxshilang",
            ))
        if blocked_dict.get("marketing_disabled", 0) > 5:
            recs.append(CampaignRecommendation(
                priority="medium", title="Marketing opt-out ko'p",
                description="Opt-out segmentlarni tekshiring",
            ))
        if canary.canary_failed > 0:
            recs.append(CampaignRecommendation(
                priority="high", title="Canary failure mavjud",
                description="Live sendni yoqmang — canary xatolik bor",
            ))
        if delivery.sent > 0 and replies.reply_rate < 0.05:
            recs.append(CampaignRecommendation(
                priority="medium", title="Reply rate past",
                description="Message CTA yoki content yaxshilang",
            ))
        if blocked_dict.get("duplicate_send", 0) > 2:
            recs.append(CampaignRecommendation(
                priority="low", title="Duplicate dedup ishlayapti",
                description="Takroriy send blocker to'g'ri ishlayapti",
            ))
        if delivery.failure_rate > 0.2 and delivery.sent > 0:
            recs.append(CampaignRecommendation(
                priority="high", title="Yuqori failure rate",
                description="Telegram API xatoliklarini tekshiring",
            ))
        if not recs:
            recs.append(CampaignRecommendation(
                priority="low", title="Holat yaxshi",
                description="Hozircha muammo aniqlanmadi",
            ))
        return recs

    @staticmethod
    def build_campaign_analytics(
        campaign_id: int,
        attempts: list[dict[str, Any]],
        inbound_messages: list[dict[str, Any]] | None = None,
        status_changes: list[dict[str, Any]] | None = None,
    ) -> CampaignAnalytics:
        now = datetime.now(timezone.utc)
        delivery = CRMCampaignAnalyticsService.get_delivery_metrics(attempts)
        blocked = CRMCampaignAnalyticsService.get_blocked_reason_metrics(attempts)
        failures = CRMCampaignAnalyticsService.get_failure_reason_metrics(attempts)
        canary = CRMCampaignAnalyticsService.get_canary_metrics(attempts)
        sent_attempts = [a for a in attempts if a.get("status") == "sent"]
        replies = CRMCampaignAnalyticsService.get_reply_metrics(sent_attempts, inbound_messages or [])
        sc = CRMCampaignAnalyticsService.get_status_change_metrics(sent_attempts, status_changes or [])
        recs = CRMCampaignAnalyticsService.build_recommendations(delivery, blocked, canary, replies)
        return CampaignAnalytics(
            campaign_id=campaign_id,
            delivery=delivery, blocked_reasons=blocked, failure_reasons=failures,
            canary=canary, replies=replies, status_changes=sc,
            recommendations=recs, generated_at=now.isoformat(),
        )

    @staticmethod
    def build_dashboard_summary(
        campaigns: list[dict[str, Any]],
        all_attempts: list[dict[str, Any]],
    ) -> DashboardSummary:
        if not campaigns:
            return DashboardSummary()
        total_sent = sum(1 for a in all_attempts if a.get("status") == "sent")
        total_failed = sum(1 for a in all_attempts if a.get("status") == "failed")
        total_blocked = sum(1 for a in all_attempts if a.get("status") == "blocked")
        total = len(all_attempts)
        sr = total_sent / total if total > 0 else 0.0
        seg_counts: dict[str, int] = {}
        for c in campaigns:
            seg = c.get("segment_key", "unknown")
            seg_counts[seg] = seg_counts.get(seg, 0) + 1
        return DashboardSummary(
            total_campaigns=len(campaigns),
            total_sent=total_sent, total_failed=total_failed, total_blocked=total_blocked,
            overall_success_rate=round(sr, 3),
            top_segments=sorted(seg_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        )

    @staticmethod
    def sanitize_output(data: dict[str, Any]) -> dict[str, Any]:
        safe = dict(data)
        for key in list(safe.keys()):
            val = safe[key]
            if isinstance(val, str) and _TOKEN_RE.search(val):
                safe[key] = "[REDACTED]"
        return safe
