"""SQLAlchemy ORM model for tenants table.

Each tenant represents a separate business that uses the bot platform.
Stores per-business configuration: bot credentials, AI prompts, pricing,
menu layout, social links, and service areas.
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.session import Base


class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    business_type: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, server_default="other",
    )

    # ── Bot credentials ────────────────────────────────────────────────────
    bot_token: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)
    bot_username: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    webhook_set: Mapped[bool] = mapped_column(sa.Boolean, server_default="false")
    last_health_check: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )

    # ── Telegram group/user IDs ────────────────────────────────────────────
    admin_group_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    main_group_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    admin_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)

    # ── AI configuration ───────────────────────────────────────────────────
    ai_system_prompt: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    knowledge_base: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # ── Business configuration (JSON) ──────────────────────────────────────
    pricing_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    menu_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    social_links: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    districts: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # ── Status ─────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true")

    # ── Billing ───────────────────────────────────────────────────────────
    billing_status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="trial",
    )
    billing_plan: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, server_default="basic",
    )
    monthly_price_uzs: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default="0",
        comment="Monthly subscription price in UZS (so'm), integer",
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True,
    )

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_tenants_slug", "slug", unique=True),
        sa.Index("ix_tenants_is_active", "is_active"),
        sa.Index("ix_tenants_billing_status", "billing_status"),
    )
