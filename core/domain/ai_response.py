"""Pydantic models for validating AI response payloads.

All fields have permissive defaults so that malformed responses degrade
gracefully instead of crashing handlers.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


# ── Valid value sets ──────────────────────────────────────────────────────────

_VALID_INTENTS = frozenset({
    "greeting", "price", "catalog", "operator",
    "measurement", "faq", "objection", "other",
})

_VALID_TEMPS = frozenset({"hot", "warm", "cold"})


# ── Extracted fields sub-model ────────────────────────────────────────────────

class AIExtractedFields(BaseModel):
    """Fields the AI may extract from the conversation."""

    interested_design: str | None = None
    last_dimensions: str | None = None
    location: str | None = None

    model_config = {"extra": "allow"}


# ── Main AI reply payload ────────────────────────────────────────────────────

class AIReplyPayload(BaseModel):
    """Validated shape of an AI JSON reply.

    All fields are optional with safe defaults so that partial or
    malformed responses never crash the handler.
    """

    intent: str = "other"
    reply: str = ""
    lead_temperature: str | None = None
    closing_confidence: float | None = None
    extracted: AIExtractedFields = AIExtractedFields()

    @field_validator("intent", mode="before")
    @classmethod
    def _normalise_intent(cls, v: Any) -> str:
        s = str(v).strip().lower() if v is not None else "other"
        return s if s in _VALID_INTENTS else "other"

    @field_validator("lead_temperature", mode="before")
    @classmethod
    def _normalise_temp(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        return s if s in _VALID_TEMPS else None

    @field_validator("closing_confidence", mode="before")
    @classmethod
    def _normalise_confidence(cls, v: Any) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @field_validator("extracted", mode="before")
    @classmethod
    def _normalise_extracted(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return v
        return {}


# ── Helper: parse raw dict into validated payload ────────────────────────────

_PARSE_FAIL_FALLBACK = AIReplyPayload(
    intent="other",
    reply="",
    lead_temperature=None,
    closing_confidence=None,
)


def parse_ai_response(raw: dict[str, Any]) -> AIReplyPayload:
    """Validate a raw AI response dict into an ``AIReplyPayload``.

    Never raises — returns a fallback payload on any validation error.
    """
    try:
        return AIReplyPayload.model_validate(raw)
    except Exception:
        return _PARSE_FAIL_FALLBACK
