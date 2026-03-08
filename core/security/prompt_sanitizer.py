"""
core.security.prompt_sanitizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Prompt injection detection and sanitization for AI inputs.

Detects social-engineering phrases that attempt to override the system
prompt, reveal hidden instructions, or switch the model persona.
Works alongside ``shared.utils.prompt_safety`` which handles low-level
control-char stripping and role-boundary neutralisation.

Usage::

    from core.security.prompt_sanitizer import scan_prompt

    result = scan_prompt(user_text)
    if result.blocked:
        # log + reject
    sanitized = result.sanitized_text
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


# ── Risk levels ──────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"        # suspicious but may be benign
    MEDIUM = "medium"  # likely injection attempt
    HIGH = "high"      # blatant injection / system prompt extraction


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScanResult:
    """Outcome of scanning a user prompt."""

    sanitized_text: str
    risk_level: RiskLevel = RiskLevel.NONE
    blocked: bool = False
    matched_patterns: tuple[str, ...] = ()


# ── Injection phrase patterns ────────────────────────────────────────────────
# Each entry: (compiled regex, human-readable label, risk level).
# Patterns are checked case-insensitively against the full message.

_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str, RiskLevel]] = [
    # Direct instruction override
    (re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above|earlier|system)\s+"
        r"(instructions?|prompts?|rules?|directives?|guidelines?)",
        re.IGNORECASE,
    ), "instruction_override", RiskLevel.HIGH),

    # System prompt extraction
    (re.compile(
        r"(reveal|show|print|display|output|repeat|echo|leak|dump|give\s+me)"
        r"\s+(me\s+)?(the\s+)?(your\s+)?(system\s+prompt|hidden\s+prompt|initial\s+prompt"
        r"|original\s+prompt|system\s+message|instructions?|your\s+rules?)",
        re.IGNORECASE,
    ), "prompt_extraction", RiskLevel.HIGH),

    # Persona / mode switching
    (re.compile(
        r"(enter|switch\s+to|activate|enable|you\s+are\s+now\s+in)"
        r"\s+(developer|debug|admin|root|god|sudo|dan|jailbreak"
        r"|unrestricted|unfiltered)\s*(mode)?",
        re.IGNORECASE,
    ), "mode_switch", RiskLevel.HIGH),

    # "Pretend" / role-play override
    (re.compile(
        r"(pretend|act\s+as\s+if|imagine|suppose|assume)"
        r"\s+(you\s+are|you\'?re|that\s+you)"
        r"\s+(a\s+different|another|not\s+a|an?\s+unrestricted)",
        re.IGNORECASE,
    ), "persona_hijack", RiskLevel.HIGH),

    # "Do anything now" / DAN
    (re.compile(
        r"\bDAN\b|do\s+anything\s+now",
        re.IGNORECASE,
    ), "dan_jailbreak", RiskLevel.HIGH),

    # "Forget" instructions
    (re.compile(
        r"forget\s+(all\s+)?(your\s+)?(previous|prior|system)?\s*"
        r"(instructions?|prompts?|rules?|context|training)",
        re.IGNORECASE,
    ), "forget_instructions", RiskLevel.HIGH),

    # "New instructions" / "from now on"
    (re.compile(
        r"(new\s+instructions?|from\s+now\s+on|henceforth|going\s+forward)"
        r".{0,30}(you\s+(will|must|should|shall)|respond|answer|behave|act)",
        re.IGNORECASE,
    ), "instruction_injection", RiskLevel.MEDIUM),

    # "What are your instructions"
    (re.compile(
        r"what\s+(are|is)\s+(your|the)\s+"
        r"(instructions?|system\s+prompt|rules?|guidelines?|directives?)",
        re.IGNORECASE,
    ), "prompt_probing", RiskLevel.MEDIUM),

    # Base64 / encoded payload attempts
    (re.compile(
        r"(decode|base64|eval|exec)\s*\(",
        re.IGNORECASE,
    ), "encoded_payload", RiskLevel.MEDIUM),

    # "You are a" reprogramming (short, direct)
    (re.compile(
        r"^you\s+are\s+(a|an|now|no\s+longer)\s+",
        re.IGNORECASE | re.MULTILINE,
    ), "identity_override", RiskLevel.LOW),
]


# ── Hidden prompt markers to strip ───────────────────────────────────────────
# These extend the role-boundary markers in prompt_safety.py.

_HIDDEN_PROMPT_RE = re.compile(
    r"(<<\s*SYSTEM\s*>>|<\s*SYSTEM_PROMPT\s*>|<\s*/SYSTEM_PROMPT\s*>"
    r"|<<\s*HIDDEN\s*>>|<<\s*/HIDDEN\s*>>"
    r"|<\s*INSTRUCTIONS?\s*>|<\s*/INSTRUCTIONS?\s*>"
    r"|###\s*SYSTEM\s*:?\s*###"
    r"|\[SYSTEM\]|\[/SYSTEM\]"
    r"|\[HIDDEN\]|\[/HIDDEN\])",
    re.IGNORECASE,
)


# ── Markdown code fence role injection ───────────────────────────────────────
# Prevents ``` system, ``` assistant, ``` developer from being
# interpreted as role boundaries in models that parse markdown fences.

_CODE_FENCE_ROLE_RE = re.compile(
    r"```\s*(system|assistant|developer|user|tool)\b",
    re.IGNORECASE,
)


# ── Constants ────────────────────────────────────────────────────────────────

MAX_USER_MESSAGE_LEN = 2000


# ── Public API ───────────────────────────────────────────────────────────────

def scan_prompt(text: str) -> ScanResult:
    """Scan and sanitize a user prompt for injection attempts.

    Returns a ``ScanResult`` with:
    - ``sanitized_text``: safe version of the input
    - ``risk_level``: overall risk assessment
    - ``blocked``: True if the message should be rejected
    - ``matched_patterns``: labels of detected patterns
    """
    if not text:
        return ScanResult(sanitized_text="")

    # 1. Enforce max length
    text = text[:MAX_USER_MESSAGE_LEN]

    # 2. Strip hidden prompt markers
    text = _HIDDEN_PROMPT_RE.sub("", text)

    # 3. Neutralize code fence role injection
    text = _CODE_FENCE_ROLE_RE.sub("``` ", text)

    # 4. Detect injection patterns
    matched: list[str] = []
    highest_risk = RiskLevel.NONE

    for pattern, label, risk in _INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(label)
            if _risk_ord(risk) > _risk_ord(highest_risk):
                highest_risk = risk

    # 5. Determine blocking: HIGH risk = block, MEDIUM/LOW = allow but flag
    blocked = highest_risk == RiskLevel.HIGH

    return ScanResult(
        sanitized_text=text,
        risk_level=highest_risk,
        blocked=blocked,
        matched_patterns=tuple(matched),
    )


def _risk_ord(level: RiskLevel) -> int:
    """Numeric ordering for risk levels."""
    return {"none": 0, "low": 1, "medium": 2, "high": 3}[level.value]
