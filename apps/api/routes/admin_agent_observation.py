"""
apps.api.routes.admin_agent_observation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only Stage 1 observation report endpoint.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/agent/observation",
    tags=["agent-observation"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/stage1-report")
async def get_stage1_report(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage1_observation_report_service import (
        Stage1ObservationReportService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    svc = Stage1ObservationReportService(db)
    report = await svc.build_report(since, now, environment="production")
    return asdict(report)


@router.get("/stage1-dryrun-gate")
async def get_dryrun_gate(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage1_observation_report_service import (
        Stage1ObservationReportService,
    )
    from core.services.stage_transition_gate_service import (
        StageTransitionGateService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    report_svc = Stage1ObservationReportService(db)
    report = await report_svc.build_report(since, now)
    gate = StageTransitionGateService.evaluate_stage1_to_dry_run(report)
    return asdict(gate)


@router.get("/stage2-dryrun-report")
async def get_stage2_dryrun_report(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage2_dryrun_report_service import (
        Stage2DryRunReportService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    svc = Stage2DryRunReportService(db)
    report = await svc.build_report(since, now, environment="production")
    return asdict(report)


@router.get("/stage2-canary-gate")
async def get_canary_gate(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage2_dryrun_report_service import (
        Stage2DryRunReportService as S2Svc,
    )
    from core.services.stage3_canary_readiness_service import (
        Stage3CanaryReadinessService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    report_svc = S2Svc(db)
    report = await report_svc.build_report(since, now)
    gate = Stage3CanaryReadinessService.evaluate_dryrun_to_canary(report)
    return asdict(gate)


@router.get("/stage3-canary-report")
async def get_stage3_canary_report(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage3_canary_report_service import (
        Stage3CanaryReportService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    svc = Stage3CanaryReportService(db)
    report = await svc.build_report(since, now, environment="production")
    return asdict(report)


@router.get("/stage3-approval-gate")
async def get_approval_gate(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage3_canary_report_service import (
        Stage3CanaryReportService as S3Svc,
    )
    from core.services.stage4_approval_readiness_service import (
        Stage4ApprovalReadinessService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    report = await S3Svc(db).build_report(since, now)
    gate = Stage4ApprovalReadinessService.evaluate_canary_to_approval(report)
    return asdict(gate)


@router.get("/stage4-approval-report")
async def get_stage4_approval_report(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage4_approval_report_service import (
        Stage4ApprovalReportService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    svc = Stage4ApprovalReportService(db)
    report = await svc.build_report(since, now, environment="production")
    return asdict(report)


@router.get("/stage4-live-send-gate")
async def get_live_send_gate(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.stage4_approval_report_service import (
        Stage4ApprovalReportService as S4Svc,
    )
    from core.services.stage5_live_send_readiness_service import (
        Stage5LiveSendReadinessService,
    )

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    report = await S4Svc(db).build_report(since, now)
    gate = Stage5LiveSendReadinessService.evaluate_approval_to_live_send(report)
    return asdict(gate)
