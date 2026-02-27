"""
Celery tasks for the "Tayyor paketlar" funnel.

check_package_followup(lead_id)
    Fires 15 minutes after a user selects a package.
    Checks whether the lead is still at PACKAGE_SELECTED stage.
    If yes → operator has not acted yet → notify admin groups + admin DM.
    If no  → operator already moved the lead forward → no-op.

Engine lifetime
---------------
Same pattern as broadcast_tasks: each asyncio.run() creates a new event
loop, so a locally-created AsyncEngine (disposed in finally) is required.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import sqlalchemy as sa
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models.lead import LeadModel
from infrastructure.database.models.pipeline_stage import PipelineStageModel
from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.queue.app import celery_app
from shared.config import get_settings
from shared.constants.enums import PipelineStage
from shared.logging import get_logger

log = get_logger(__name__)


# ── Local session helpers (same safe-engine pattern as broadcast_tasks) ────────


def _make_session_factory() -> tuple[object, async_sessionmaker[AsyncSession]]:
    settings = get_settings()
    engine = create_async_engine(
        settings.db.async_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        connect_args={"server_settings": {"jit": "off"}, "command_timeout": 30},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return engine, factory


@asynccontextmanager
async def _ro_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# ── Celery task ────────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    max_retries=0,
    name="packages.check_followup",
    ignore_result=True,
)
def check_package_followup(self, lead_id: int) -> None:
    """Check if operator has contacted the lead 15 minutes after package selection.

    Idempotent: safe to call multiple times — only notifies when stage is still
    PACKAGE_SELECTED.
    """
    try:
        asyncio.run(_async_check_followup(lead_id))
    except Exception as exc:
        log.error("pkg_followup_task_error", lead_id=lead_id, error=str(exc))


# ── Async implementation ───────────────────────────────────────────────────────


async def _async_check_followup(lead_id: int) -> None:
    engine, Session = _make_session_factory()
    try:
        # 1. Check current stage
        async with _ro_session(Session) as session:
            latest_stage_result = await session.execute(
                sa.select(PipelineStageModel.stage)
                .where(PipelineStageModel.lead_id == lead_id)
                .order_by(PipelineStageModel.created_at.desc())
                .limit(1)
            )
            current_stage = latest_stage_result.scalar_one_or_none()

        if current_stage != PipelineStage.PACKAGE_SELECTED.value:
            log.info(
                "pkg_followup_skip_already_handled",
                lead_id=lead_id,
                stage=current_stage,
            )
            return

        # 2. Load lead info for notification text
        async with _ro_session(Session) as session:
            lead_model = await session.get(LeadModel, lead_id)

        if lead_model is None:
            log.warning("pkg_followup_lead_not_found", lead_id=lead_id)
            return

        # 3. Send follow-up alerts
        settings = get_settings()
        bot = Bot(
            token=settings.bot.token.get_secret_value(),
            default=DefaultBotProperties(parse_mode="HTML"),
        )

        pkg = lead_model.package_type or "noma'lum"
        name = lead_model.name or "—"
        phone = lead_model.phone or "—"
        text = (
            f"⚠️ <b>Diqqat! 15 daqiqa o'tdi</b>\n\n"
            f"Lead #{lead_id} uchun hali operator bog'lanmadi!\n\n"
            f"👤 Mijoz: <b>{name}</b>\n"
            f"📱 Telefon: <code>{phone}</code>\n"
            f"📦 Paket: <b>{pkg.upper()}</b>\n"
            f"📅 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC\n\n"
            f"/lead_{lead_id}"
        )

        try:
            # Admin DM
            try:
                await bot.send_message(settings.bot.admin_user_id, text)
            except Exception as exc:
                log.warning("pkg_followup_admin_dm_failed", error=str(exc))

            # All admin groups
            async with _ro_session(Session) as session:
                ag_repo = PostgresAdminGroupRepository(session)
                group_ids = await ag_repo.list_all_chat_ids()

            for gid in group_ids:
                try:
                    await bot.send_message(gid, text)
                except Exception as exc:
                    log.warning("pkg_followup_group_failed", chat_id=gid, error=str(exc))

            log.info(
                "pkg_followup_notified",
                lead_id=lead_id,
                groups=len(group_ids),
            )
        finally:
            await bot.session.close()

    finally:
        await engine.dispose()
