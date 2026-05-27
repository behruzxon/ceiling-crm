"""Tests for Step CD — final_ui_stage1_check.py script."""
from __future__ import annotations

from pathlib import Path


class TestScriptExists:
    def test_script_file(self):
        assert Path("scripts/final_ui_stage1_check.py").exists()


class TestImports:
    def test_importable(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert mod is not None

    def test_main_callable(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.main)

    def test_check_critical_docs(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.check_critical_docs)

    def test_check_templates(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.check_templates)

    def test_check_dangerous_flags(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.check_dangerous_flags)

    def test_check_login_no_sidebar(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.check_login_no_sidebar)

    def test_check_sidebar_routes(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.check_sidebar_routes)

    def test_check_no_secrets(self):
        import importlib
        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.check_no_secrets_in_templates)


class TestCheckResults:
    def test_docs_green(self):
        from scripts.final_ui_stage1_check import check_critical_docs
        results = check_critical_docs()
        assert all(r[0] == "[OK]" for r in results)

    def test_templates_green(self):
        from scripts.final_ui_stage1_check import check_templates
        results = check_templates()
        assert all(r[0] == "[OK]" for r in results)

    def test_login_standalone_green(self):
        from scripts.final_ui_stage1_check import check_login_no_sidebar
        results = check_login_no_sidebar()
        assert all(r[0] == "[OK]" for r in results)

    def test_sidebar_routes_green(self):
        from scripts.final_ui_stage1_check import check_sidebar_routes
        results = check_sidebar_routes()
        assert all(r[0] == "[OK]" for r in results)

    def test_no_secrets_green(self):
        from scripts.final_ui_stage1_check import check_no_secrets_in_templates
        results = check_no_secrets_in_templates()
        assert all(r[0] == "[OK]" for r in results)

    def test_flags_no_red(self):
        from scripts.final_ui_stage1_check import check_dangerous_flags
        results = check_dangerous_flags()
        assert all(r[0] != "[FAIL]" for r in results)

    def test_main_returns_zero(self, capsys):
        from scripts.final_ui_stage1_check import main
        rc = main()
        assert rc == 0
        captured = capsys.readouterr()
        assert "[FAIL]" not in captured.out
