"""Phase 4 — exception/log redaction.

Shadow test found a raw phone (`'price_phone': '+998908866666'`) in a dev-mode
traceback's local-variable dump from the OpenAI-failure path. Fix:
  * tracebacks render with show_locals=False (dev RichTracebackFormatter + prod
    ExceptionDictTransformer) — local vars never appear;
  * a scrub_sensitive processor redacts secrets/phones from every string value.

Pure / offline: no network, Redis, DB, OpenAI, Telegram.
"""

from __future__ import annotations

import sys

from shared.logging.setup import (
    _build_console_renderer,
    _redact_str,
    scrub_sensitive,
)

_PHONE = "+998908866666"
_KEY = "sk-ABCD1234efgh5678ijkl"
_TG_TOKEN = "123456789:AAEdef_ghIJKlmnopQRstuvWXyz12345678"


def _raise_with_locals():
    # Local vars mirror the real handler frame that leaked the phone.
    price_phone = _PHONE  # noqa: F841 — intentionally a local
    bot_token = _TG_TOKEN  # noqa: F841
    raise ValueError("boom while processing")


def _exc_info():
    try:
        _raise_with_locals()
    except Exception:
        return sys.exc_info()


# ── _redact_str ───────────────────────────────────────────────────────────


class TestRedactStr:
    def test_phone(self) -> None:
        assert _PHONE not in _redact_str(f"price_phone={_PHONE}")
        assert "[redacted_phone]" in _redact_str(f"price_phone={_PHONE}")

    def test_phone_without_plus(self) -> None:
        assert "998908866666" not in _redact_str("998908866666")

    def test_openai_key(self) -> None:
        assert _KEY not in _redact_str(f"key={_KEY}")
        assert "[redacted_key]" in _redact_str(f"key={_KEY}")

    def test_bot_token_pattern(self) -> None:
        assert _TG_TOKEN not in _redact_str(f"token {_TG_TOKEN} end")

    def test_bearer(self) -> None:
        out = _redact_str("Authorization: Bearer abcdef123456.gh")
        assert "abcdef123456" not in out
        assert "[redacted_bearer]" in out

    def test_postgres_url(self) -> None:
        out = _redact_str("conn postgres://user:pass@host:5432/db now")
        assert "user:pass@host" not in out
        assert "[redacted_db_url]" in out

    def test_redis_url(self) -> None:
        assert "[redacted_redis_url]" in _redact_str("redis://localhost:6379/0")

    def test_database_url_env(self) -> None:
        out = _redact_str("DATABASE_URL=postgres://u:p@h/d")
        assert "u:p@h" not in out

    def test_bot_token_env(self) -> None:
        out = _redact_str("BOT_TOKEN=123456789:AAEdefghIJKlmnopQRstuvWX")
        assert "AAEdefghIJKl" not in out

    def test_openai_key_env(self) -> None:
        out = _redact_str("OPENAI_API_KEY=sk-verysecretvalue123456")
        assert "verysecretvalue" not in out

    def test_clean_text_unchanged(self) -> None:
        assert _redact_str("gulli 20 kv qancha") == "gulli 20 kv qancha"

    def test_short_number_kept(self) -> None:
        # short ids / areas must not be over-redacted
        assert _redact_str("area 20 m2") == "area 20 m2"


# ── scrub_sensitive processor ──────────────────────────────────────────────


class TestScrubProcessor:
    def test_redacts_string_values(self) -> None:
        ed = scrub_sensitive(None, "info", {"event": "x", "phone": _PHONE, "key": _KEY})
        assert _PHONE not in ed["phone"]
        assert _KEY not in ed["key"]

    def test_leaves_non_strings(self) -> None:
        ed = scrub_sensitive(None, "info", {"event": "x", "user_id": 8273579378, "n": 3.5})
        assert ed["user_id"] == 8273579378
        assert ed["n"] == 3.5

    def test_redacts_event_message(self) -> None:
        ed = scrub_sensitive(None, "error", {"event": f"failed for {_PHONE}"})
        assert _PHONE not in ed["event"]

    def test_returns_same_dict_shape(self) -> None:
        ed = scrub_sensitive(None, "info", {"event": "ok", "a": "clean"})
        assert ed["a"] == "clean"
        assert ed["event"] == "ok"

    def test_user_id_int_not_touched(self) -> None:
        # raw user_id (int) is intentionally kept for correlation
        ed = scrub_sensitive(None, "info", {"event": "e", "user_id": 998908866666})
        assert ed["user_id"] == 998908866666


# ── show_locals disabled in renderers ──────────────────────────────────────


class TestTracebackNoLocals:
    def test_dev_console_renderer_omits_locals(self) -> None:
        renderer = _build_console_renderer()
        out = renderer(None, "error", {"event": "boom", "level": "error", "exc_info": _exc_info()})
        assert isinstance(out, str)
        assert _PHONE not in out, "phone leaked from traceback locals"
        assert _TG_TOKEN not in out

    def test_prod_exception_transformer_omits_locals(self) -> None:
        from structlog.tracebacks import ExceptionDictTransformer

        transformer = ExceptionDictTransformer(show_locals=False)
        result = transformer(_exc_info())
        blob = str(result)
        assert _PHONE not in blob
        assert _TG_TOKEN not in blob
        # no frame carries a 'locals' mapping
        for exc in result:
            for frame in exc.get("frames", []):
                assert not frame.get("locals"), "locals present despite show_locals=False"

    def test_console_renderer_still_renders_event(self) -> None:
        renderer = _build_console_renderer()
        out = renderer(None, "info", {"event": "hello_world", "level": "info"})
        assert "hello_world" in out


# ── End-to-end: configure_logging wires the scrub processor ────────────────


class TestProcessorChainWired:
    def test_scrub_in_shared_processors(self) -> None:
        from shared.logging.setup import _build_shared_processors

        procs = _build_shared_processors(is_dev=True)
        assert scrub_sensitive in procs

    def test_scrub_in_prod_chain_too(self) -> None:
        from shared.logging.setup import _build_shared_processors

        procs = _build_shared_processors(is_dev=False)
        assert scrub_sensitive in procs
