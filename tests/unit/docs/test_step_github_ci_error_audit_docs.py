"""Tests for 121_GITHUB_CI_ERROR_AUDIT_AND_FIXES.md documentation."""

from pathlib import Path

DOC_PATH = Path("docs/AI_AGENT_SYSTEM/121_GITHUB_CI_ERROR_AUDIT_AND_FIXES.md")


def _read_doc() -> str:
    assert DOC_PATH.exists(), f"Doc not found: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def test_doc_exists() -> None:
    assert DOC_PATH.exists()


def test_doc_not_empty() -> None:
    content = _read_doc()
    assert len(content) > 500


def test_doc_contains_workflow_jobs() -> None:
    content = _read_doc()
    assert "Workflow Jobs" in content or "workflow" in content.lower()


def test_doc_contains_local_reproduction_commands() -> None:
    content = _read_doc()
    assert "Local Reproduction" in content or "local reproduction" in content.lower()


def test_doc_contains_ruff_check() -> None:
    content = _read_doc()
    assert "ruff check" in content


def test_doc_contains_black_check() -> None:
    content = _read_doc()
    assert "black --check" in content or "black" in content.lower()


def test_doc_contains_mypy() -> None:
    content = _read_doc()
    assert "mypy" in content.lower()


def test_doc_contains_pytest() -> None:
    content = _read_doc()
    assert "pytest" in content


def test_doc_contains_docker_reference() -> None:
    content = _read_doc()
    assert "docker" in content.lower()


def test_doc_contains_errors_found() -> None:
    content = _read_doc()
    assert "Errors Found" in content or "errors found" in content.lower()


def test_doc_contains_fixes_applied() -> None:
    content = _read_doc()
    assert "Fixes Applied" in content or "fixes applied" in content.lower()


def test_doc_contains_remaining_risks() -> None:
    content = _read_doc()
    assert "Remaining Risks" in content or "remaining risks" in content.lower()


def test_doc_says_no_deploy() -> None:
    content = _read_doc()
    assert "NO deploy" in content or "no deploy" in content.lower()


def test_doc_says_no_vps() -> None:
    content = _read_doc()
    assert "NO VPS" in content or "no vps" in content.lower()


def test_doc_says_no_flags_enabled() -> None:
    content = _read_doc()
    assert "NO flags enabled" in content or "no flags" in content.lower()


def test_doc_says_no_stage1_applied() -> None:
    content = _read_doc()
    assert "NO Stage 1" in content or "no stage 1" in content.lower()


def test_doc_says_no_force_push() -> None:
    content = _read_doc()
    assert "NO force push" in content or "no force push" in content.lower()


def test_doc_contains_rollback_or_restore_note() -> None:
    content = _read_doc()
    has_rollback = "rollback" in content.lower()
    has_restore = "restore" in content.lower()
    has_revert = "revert" in content.lower()
    has_mitigation = "mitigation" in content.lower()
    assert has_rollback or has_restore or has_revert or has_mitigation


def test_doc_has_no_bot_token() -> None:
    content = _read_doc()
    assert "AAF" not in content or "Fake" in content
    lines = content.split("\n")
    for line in lines:
        if "BOT_TOKEN" in line:
            assert "fake" in line.lower() or "ci" in line.lower() or "not" in line.lower()


def test_doc_has_no_openai_key() -> None:
    content = _read_doc()
    assert "sk-" not in content or "fake" in content.lower()


def test_doc_has_no_database_url() -> None:
    content = _read_doc()
    assert "postgresql://" not in content
    assert "postgres://" not in content


def test_doc_contains_branch_info() -> None:
    content = _read_doc()
    assert "feature/vash-ai-hardening-session" in content


def test_doc_contains_commit_info() -> None:
    content = _read_doc()
    assert "bdea967" in content


def test_doc_contains_do_not_do_list() -> None:
    content = _read_doc()
    assert "Do-Not-Do" in content or "do not" in content.lower()


def test_doc_contains_next_steps() -> None:
    content = _read_doc()
    assert "Next Steps" in content or "next step" in content.lower()


def test_doc_mentions_continue_on_error() -> None:
    content = _read_doc()
    assert "continue-on-error" in content


def test_doc_mentions_strict_mode_removal() -> None:
    content = _read_doc()
    assert "strict" in content.lower()
