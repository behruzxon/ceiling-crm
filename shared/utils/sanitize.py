"""
shared.utils.sanitize
~~~~~~~~~~~~~~~~~~~~~~
Pure sanitization utilities for LLM prompt construction and reply validation.

These functions contain **no framework dependencies** (no aiogram, no Redis,
no database).  They are safe to call from any layer: ``core/``, ``apps/``,
``infrastructure/``, or tests.

Three functions are provided:

* ``detect_prompt_injection(text)`` — returns True if the text matches known
  prompt-injection / jailbreak patterns (English, Russian, Uzbek).
* ``sanitize_user_text_for_prompt(text, ...)`` — truncates and scrubs
  user-authored text before it is injected into an LLM prompt.
* ``sanitize_ai_reply(reply)`` — returns None if the LLM reply appears to
  leak system-prompt internals.
"""
from __future__ import annotations

import re

# ── Prompt-injection firewall ────────────────────────────────────────────────

# Patterns that indicate a prompt-injection or jailbreak attempt.
# Checked against the raw user input (patterns use re.I for case-insensitivity).
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # ── English ───────────────────────────────────────────────────────────
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above|system)\s+"
        r"(instructions?|prompts?|rules?|context)",
        re.I,
    ),
    re.compile(
        r"(reveal|show|display|print|output|repeat|tell\s+me|give\s+me)"
        r"\s+(your\s+|the\s+)?"
        r"(system\s+prompt|hidden\s+(rules?|instructions?)|"
        r"initial\s+instructions?|secret\s+(prompt|instructions?)|"
        r"internal\s+(rules?|instructions?))",
        re.I,
    ),
    re.compile(
        r"(forget|disregard|discard|drop)\s+(all\s+)?"
        r"(previous|prior|above|system)\s+"
        r"(instructions?|prompts?|rules?|context)",
        re.I,
    ),
    re.compile(
        r"(you\s+are|act\s+as|pretend\s+to\s+be|roleplay\s+as|become)\s+"
        r"(now\s+)?(a\s+|an\s+)?"
        r"(different|new|evil|unrestricted|unfiltered|unlocked)",
        re.I,
    ),
    re.compile(r"\b(system|developer|admin)\s*:\s*", re.I),
    re.compile(r"new\s+(system\s+)?instructions?\s*:", re.I),
    re.compile(r"override\s+(all\s+)?(previous|system|safety)", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bDAN\b\s*(mode)?"),
    re.compile(
        r"bypass\s+(safety|filter|restriction|guardrail|content\s+policy)",
        re.I,
    ),
    re.compile(
        r"(what|tell|show|print)\s+(is|me|are)\s+(your|the)\s+"
        r"(system\s+)?(prompt|instructions?|rules?|guidelines?)\b",
        re.I,
    ),
    re.compile(r"output\s+(everything|all|the\s+text)\s+(above|before)", re.I),
    re.compile(r"translate\s+(your\s+)?(system\s+)?(prompt|instructions?)", re.I),
    # ── Russian ───────────────────────────────────────────────────────────
    re.compile(
        r"(игнорируй|забудь|отмени)\s+(все\s+)?"
        r"(предыдущие|системные)\s+(инструкции|правила|промпт)",
        re.I,
    ),
    re.compile(
        r"(покажи|выведи|повтори)\s+(системный\s+)?(промпт|инструкции)",
        re.I,
    ),
    # ── Uzbek ─────────────────────────────────────────────────────────────
    re.compile(
        r"(oldingi|tizim)\s+(ko.?rsatma|qoida)larni\s+"
        r"(e.?tiborsiz|unut|bekor)",
        re.I,
    ),
    re.compile(r"(tizim\s+)?prompt(ni|ingni)\s+(ko.?rsat|ayt|chiqar)", re.I),
)

# Phrases from the system prompt that must NEVER leak into user-facing replies.
_LEAK_MARKERS: tuple[str, ...] = (
    "asosiy qoidalar",
    "javob formati",
    "closing_confidence",
    "lead_temperature",
    "intent",
    "extracted",
    "salomlashish",
    "lead scoring",
    "cta rotatsiya",
    "savdo strategiyasi",
    "shaxsiylashtirish",
    "foydalanuvchi konteksti",
    "xavfsizlik (hech qachon buzilmasin)",
    "ko'rsatmalar ierarxiyasi",
    "bilimlar bazasi",
)


def detect_prompt_injection(text: str) -> bool:
    """Return True if *text* looks like a prompt-injection attempt."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def sanitize_user_text_for_prompt(
    text: str,
    *,
    max_length: int = 300,
    placeholder: str = "[blocked]",
) -> str:
    """Sanitize user-sourced text before injecting it into an LLM prompt.

    Returns the (truncated) text if clean, or *placeholder* if the text
    looks like a prompt-injection attempt.  This is the **single reusable
    guard** that every OpenAI call-site should use on user-authored fields
    (messages, names, summaries, etc.) instead of copy-pasting
    ``detect_prompt_injection`` checks.
    """
    if not text or not text.strip():
        return ""
    if detect_prompt_injection(text):
        return placeholder
    return text[:max_length]


def sanitize_ai_reply(reply: str) -> str | None:
    """Return None if the reply appears to leak system-prompt internals.

    Otherwise returns the reply unchanged.  Callers should substitute a
    safe fallback when None is returned.
    """
    lowered = reply.lower()
    for marker in _LEAK_MARKERS:
        if marker in lowered:
            return None
    return reply
