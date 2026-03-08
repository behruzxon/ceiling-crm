"""
shared.utils.prompt_safety
~~~~~~~~~~~~~~~~~~~~~~~~~~
Sanitisation utilities for AI prompt assembly.

Prevents prompt injection by:
- Stripping control characters
- Neutralising role-boundary markers (``<|im_start|>``, ``[INST]``, etc.)
- Truncating fields to safe lengths
- Fencing user-data blocks with clear delimiters

Usage:
    from shared.utils.prompt_safety import sanitize_field, fence_data_block
"""
from __future__ import annotations

import re

# ── Compiled patterns ──────────────────────────────────────────────────────

# ASCII control characters (except \t \n \r which are useful)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Patterns that simulate OpenAI / Llama / Anthropic role boundaries
_ROLE_BOUNDARY_RE = re.compile(
    r"(<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>"
    r"|<<\s*SYS\s*>>|<<\s*/SYS\s*>>"
    r"|\[INST\]|\[/INST\]"
    r"|<<\s*SYSTEM\s*>>|<\s*SYSTEM_PROMPT\s*>|<\s*/SYSTEM_PROMPT\s*>"
    r"|<\s*INSTRUCTIONS?\s*>|<\s*/INSTRUCTIONS?\s*>"
    r"|\[SYSTEM\]|\[/SYSTEM\])",
    re.IGNORECASE,
)

# Markdown code fences that could be parsed as role boundaries
_CODE_FENCE_ROLE_RE = re.compile(
    r"```\s*(system|assistant|developer|user|tool)\b",
    re.IGNORECASE,
)


# ── Public API ─────────────────────────────────────────────────────────────

def sanitize_field(text: str | None, *, max_len: int = 200) -> str:
    """Sanitise a single data field destined for a prompt context block.

    - Strips control characters
    - Collapses whitespace to single spaces (no newlines)
    - Neutralises role-boundary markers
    - Truncates to *max_len*
    """
    if not text:
        return ""
    text = _CONTROL_CHARS_RE.sub("", text)
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = _ROLE_BOUNDARY_RE.sub("", text)
    return text[:max_len]


def sanitize_user_message(text: str, *, max_len: int = 2000) -> str:
    """Sanitise a user message before sending to the model.

    Preserves newlines for readability but strips control characters,
    role-boundary markers, and code-fence role injections.
    """
    if not text:
        return ""
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _ROLE_BOUNDARY_RE.sub("", text)
    text = _CODE_FENCE_ROLE_RE.sub("``` ", text)
    return text[:max_len]


def sanitize_history(
    messages: list[dict[str, str]],
    *,
    max_msg_len: int = 1000,
) -> list[dict[str, str]]:
    """Sanitise a conversation history list.

    Validates roles, strips boundary markers, and truncates each message.
    """
    _valid_roles = frozenset({"user", "assistant"})
    safe: list[dict[str, str]] = []
    for msg in messages:
        role = msg.get("role", "user")
        if role not in _valid_roles:
            role = "user"
        text = sanitize_user_message(msg.get("text", ""), max_len=max_msg_len)
        if text:
            safe.append({"role": role, "text": text})
    return safe


def fence_data_block(label: str, content: str) -> str:
    """Wrap *content* in delimiters that signal non-instruction status.

    The model is instructed (via a safety suffix in the system prompt)
    to treat everything between ``[DATA:...]`` and ``[/DATA:...]`` as
    passive data, never as commands.
    """
    return f"[DATA:{label}]\n{content}\n[/DATA:{label}]"


def sanitize_tenant_prompt(
    text: str | None, *, max_len: int = 8000,
) -> str | None:
    """Sanitise a tenant-provided system prompt.

    Tenants are semi-trusted (admin-level access), so this is lighter:
    strips control characters and enforces length limit.
    """
    if not text:
        return None
    text = _CONTROL_CHARS_RE.sub("", text)
    return text[:max_len] or None


def sanitize_knowledge_base(
    text: str | None, *, max_len: int = 16000,
) -> str | None:
    """Sanitise a tenant-provided knowledge base."""
    if not text:
        return None
    text = _CONTROL_CHARS_RE.sub("", text)
    return text[:max_len] or None
