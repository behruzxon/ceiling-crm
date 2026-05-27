"""
apps.api.routes.admin_agent_settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin endpoints for agent settings mutation.

GET  /api/v1/admin/agent/settings
POST /api/v1/admin/agent/settings/preview
POST /api/v1/admin/agent/settings/apply
POST /api/v1/admin/agent/settings/rollback
GET  /api/v1/admin/agent/settings/audit
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/agent/settings",
    tags=["agent-settings"],
    dependencies=[Depends(require_api_token)],
)


def _check_mutation_enabled() -> None:
    from shared.config import get_settings

    if not get_settings().business.agent_settings_mutation_enabled:
        raise HTTPException(status_code=403, detail="Settings mutation disabled")


class PreviewRequest(BaseModel):
    key: str = Field(..., max_length=100)
    value: object
    reason: str = Field(default="", max_length=500)


class ApplyRequest(BaseModel):
    key: str = Field(..., max_length=100)
    value: object
    confirmation_token: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=500)


class RollbackRequest(BaseModel):
    setting_key: str = Field(..., max_length=100)
    audit_log_id: int = Field(default=0)
    reason: str = Field(default="", max_length=500)


@router.get("")
async def get_settings_list() -> dict:
    from core.services.agent_settings_service import _ALLOWED_KEYS, AgentSettingsService
    from shared.config import get_settings

    biz = get_settings().business
    effective = {k: getattr(biz, k, None) for k in sorted(_ALLOWED_KEYS)}
    items = AgentSettingsService.sanitize_settings_for_api(effective)
    dangers = AgentSettingsService.detect_dangerous_combinations(effective)
    mutation_enabled = getattr(biz, "agent_settings_mutation_enabled", False)
    return {
        "settings": [asdict(s) for s in items],
        "dangerous_combinations": dangers,
        "mutation_enabled": mutation_enabled,
    }


@router.post("/preview")
async def preview_change(body: PreviewRequest) -> dict:
    _check_mutation_enabled()
    from core.services.agent_settings_service import AgentSettingsService
    from shared.config import get_settings

    biz = get_settings().business
    from core.services.agent_settings_service import _ALLOWED_KEYS

    current = {k: getattr(biz, k, None) for k in _ALLOWED_KEYS}
    allow_live = getattr(biz, "agent_settings_allow_live_flags", False)

    result = AgentSettingsService.validate_change(
        body.key,
        body.value,
        current,
        allow_live_flags=allow_live,
    )
    return asdict(result)


@router.post("/apply")
async def apply_change(
    body: ApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_mutation_enabled()
    from core.services.agent_settings_service import AgentSettingsService
    from shared.config import get_settings

    biz = get_settings().business
    from core.services.agent_settings_service import _ALLOWED_KEYS

    current = {k: getattr(biz, k, None) for k in _ALLOWED_KEYS}
    allow_live = getattr(biz, "agent_settings_allow_live_flags", False)

    validation = AgentSettingsService.validate_change(
        body.key,
        body.value,
        current,
        allow_live_flags=allow_live,
    )
    if not validation.allowed:
        raise HTTPException(status_code=400, detail=validation.blockers)

    if validation.requires_confirmation and not body.confirmation_token:
        raise HTTPException(
            status_code=400,
            detail="confirmation_token_required",
        )

    if validation.requires_confirmation and not AgentSettingsService.verify_confirmation_token(
        body.confirmation_token,
    ):
        raise HTTPException(status_code=400, detail="invalid_token")

    from datetime import UTC, datetime

    import sqlalchemy as sa

    from infrastructure.database.models.agent_runtime_setting import (
        AgentRuntimeSettingModel,
    )
    from infrastructure.database.models.agent_setting_audit_log import (
        AgentSettingAuditLogModel,
    )

    stmt = sa.select(AgentRuntimeSettingModel).where(
        AgentRuntimeSettingModel.key == body.key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    old_value = existing.value_json if existing else None

    now = datetime.now(UTC)
    if existing:
        existing.value_json = {"value": body.value}
        existing.updated_by = 0
        existing.updated_at = now
        existing.risk_level = validation.risk_level
    else:
        vtype = (
            "bool"
            if isinstance(body.value, bool)
            else ("int" if isinstance(body.value, int) else "string")
        )
        record = AgentRuntimeSettingModel(
            key=body.key,
            value_json={"value": body.value},
            value_type=vtype,
            risk_level=validation.risk_level,
            updated_by=0,
            updated_at=now,
        )
        db.add(record)

    snapshot = AgentSettingsService.build_rollback_snapshot(current)
    token_hash = (
        hashlib.sha256(body.confirmation_token.encode()).hexdigest()[:16]
        if body.confirmation_token
        else None
    )

    audit = AgentSettingAuditLogModel(
        setting_key=body.key,
        old_value_json=old_value,
        new_value_json={"value": body.value},
        changed_by=0,
        action="apply",
        risk_level=validation.risk_level,
        confirmation_token_hash=token_hash,
        rollback_snapshot_json=snapshot,
        validation_result_json=asdict(validation),
        reason=body.reason[:500] if body.reason else None,
    )
    db.add(audit)
    await db.commit()

    from core.services.agent_effective_settings_service import AgentEffectiveSettingsService

    AgentEffectiveSettingsService.clear_cache()

    return {"status": "applied", "key": body.key, "risk_level": validation.risk_level}


@router.post("/rollback")
async def rollback_setting(
    body: RollbackRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_mutation_enabled()
    from datetime import UTC, datetime

    import sqlalchemy as sa

    from infrastructure.database.models.agent_runtime_setting import (
        AgentRuntimeSettingModel,
    )
    from infrastructure.database.models.agent_setting_audit_log import (
        AgentSettingAuditLogModel,
    )

    stmt = sa.select(AgentRuntimeSettingModel).where(
        AgentRuntimeSettingModel.key == body.setting_key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="setting_not_found")

    old_value = existing.value_json
    existing.is_active = False
    existing.updated_at = datetime.now(UTC)

    audit = AgentSettingAuditLogModel(
        setting_key=body.setting_key,
        old_value_json=old_value,
        new_value_json=None,
        changed_by=0,
        action="rollback",
        risk_level="low",
        reason=body.reason[:500] if body.reason else None,
    )
    db.add(audit)
    await db.commit()

    from core.services.agent_effective_settings_service import AgentEffectiveSettingsService

    AgentEffectiveSettingsService.clear_cache()

    return {"status": "rolled_back", "key": body.setting_key}


@router.get("/audit")
async def get_audit_log(
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    import sqlalchemy as sa

    from infrastructure.database.models.agent_setting_audit_log import (
        AgentSettingAuditLogModel,
    )

    stmt = (
        sa.select(AgentSettingAuditLogModel)
        .order_by(AgentSettingAuditLogModel.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "setting_key": r.setting_key,
                "action": r.action,
                "risk_level": r.risk_level,
                "reason": r.reason,
                "changed_by": r.changed_by,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )

    return {"items": items, "count": len(items)}


# ── Preset endpoints ─────────────────────────────────────────────────────────


class PresetApplyRequest(BaseModel):
    confirmation_token: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=500)


@router.get("/presets")
async def list_presets() -> dict:
    from core.services.agent_rollout_preset_service import (
        AgentRolloutPresetService,
    )

    presets = AgentRolloutPresetService.list_presets()
    return {
        "presets": [
            {
                "name": p.name,
                "label": p.label,
                "description": p.description,
                "risk_level": p.risk_level,
            }
            for p in presets
        ],
    }


@router.post("/presets/{preset}/preview")
async def preview_preset(preset: str) -> dict:
    from core.services.agent_rollout_preset_service import (
        AgentRolloutPresetService,
    )
    from shared.config import get_settings

    biz = get_settings().business
    from core.services.agent_settings_service import _ALLOWED_KEYS

    current = {k: getattr(biz, k, None) for k in _ALLOWED_KEYS}
    allow_live = getattr(biz, "agent_settings_allow_live_flags", False)

    result = AgentRolloutPresetService.preview_preset(
        preset,
        current,
        allow_live,
    )
    return {
        "preset": result.preset,
        "allowed": result.allowed,
        "risk_level": result.risk_level,
        "blockers": result.blockers,
        "warnings": result.warnings,
        "diff": [
            {
                "key": d.key,
                "current": d.current_value,
                "target": d.target_value,
                "risk": d.risk_level,
            }
            for d in result.diff
        ],
        "requires_confirmation": result.requires_confirmation,
        "confirmation_token": result.confirmation_token,
    }


@router.post("/presets/{preset}/apply")
async def apply_preset(
    preset: str,
    body: PresetApplyRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_mutation_enabled()
    from core.services.agent_rollout_preset_service import (
        AgentRolloutPresetService,
    )
    from core.services.agent_settings_service import AgentSettingsService
    from shared.config import get_settings

    target = AgentRolloutPresetService.build_preset_settings(preset)
    if target is None:
        raise HTTPException(status_code=400, detail=f"unknown_preset:{preset}")

    biz = get_settings().business
    from core.services.agent_settings_service import _ALLOWED_KEYS

    current = {k: getattr(biz, k, None) for k in _ALLOWED_KEYS}
    allow_live = getattr(biz, "agent_settings_allow_live_flags", False)

    preview = AgentRolloutPresetService.preview_preset(
        preset,
        current,
        allow_live,
    )
    if not preview.allowed:
        raise HTTPException(status_code=400, detail=preview.blockers)

    token = (body.confirmation_token if body else "") or ""
    if preview.requires_confirmation and not token:
        raise HTTPException(status_code=400, detail="confirmation_required")

    from datetime import UTC, datetime

    import sqlalchemy as sa

    from infrastructure.database.models.agent_runtime_setting import (
        AgentRuntimeSettingModel,
    )
    from infrastructure.database.models.agent_setting_audit_log import (
        AgentSettingAuditLogModel,
    )

    snapshot = AgentSettingsService.build_rollback_snapshot(current)
    reason = f"preset:{preset}" + (f" — {body.reason}" if body and body.reason else "")
    now = datetime.now(UTC)

    for key, val in target.items():
        stmt = sa.select(AgentRuntimeSettingModel).where(
            AgentRuntimeSettingModel.key == key,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        vtype = "bool" if isinstance(val, bool) else ("int" if isinstance(val, int) else "string")
        if existing:
            existing.value_json = {"value": val}
            existing.updated_at = now
            existing.is_active = True
        else:
            db.add(
                AgentRuntimeSettingModel(
                    key=key,
                    value_json={"value": val},
                    value_type=vtype,
                    risk_level=preview.risk_level,
                    updated_at=now,
                )
            )

    audit = AgentSettingAuditLogModel(
        setting_key=f"preset:{preset}",
        old_value_json={"snapshot": snapshot},
        new_value_json={"preset": preset, "settings": target},
        changed_by=0,
        action="preset_apply",
        risk_level=preview.risk_level,
        rollback_snapshot_json=snapshot,
        reason=reason[:500],
    )
    db.add(audit)
    await db.commit()

    from core.services.agent_effective_settings_service import (
        AgentEffectiveSettingsService,
    )

    AgentEffectiveSettingsService.clear_cache()

    return {"status": "applied", "preset": preset, "risk_level": preview.risk_level}
