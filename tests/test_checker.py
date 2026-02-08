"""Tests for the plugin checker (check-plugin command)."""

from __future__ import annotations

import shutil

import pytest

from universal_gear.cli.checker import check_plugin
from universal_gear.cli.scaffold import PLUGIN_BASE, TEST_BASE, generate_plugin

CHECKER_NAME = "_test_checker_tmp"


@pytest.fixture()
def _cleanup():
    yield
    plugin_dir = PLUGIN_BASE / CHECKER_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    test_file = TEST_BASE / f"test_{CHECKER_NAME}_plugin.py"
    if test_file.exists():
        test_file.unlink()


@pytest.mark.offline()
@pytest.mark.usefixtures("_cleanup")
class TestCheckPlugin:
    def test_valid_scaffold_passes(self):
        generate_plugin(CHECKER_NAME)
        errors = check_plugin(CHECKER_NAME)
        assert errors == []

    def test_missing_directory_returns_error(self):
        errors = check_plugin("nonexistent_plugin_xyz")
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_missing_module_detected(self):
        generate_plugin(CHECKER_NAME)
        (PLUGIN_BASE / CHECKER_NAME / "collector.py").unlink()
        errors = check_plugin(CHECKER_NAME)
        assert any("collector.py" in e for e in errors)

    def test_existing_plugins_pass(self):
        for name in ("agro", "finance"):
            errors = check_plugin(name)
            assert errors == [], f"Plugin '{name}' failed: {errors}"
