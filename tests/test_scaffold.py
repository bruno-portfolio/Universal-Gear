"""Tests for plugin scaffold generation and validation."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from universal_gear.cli.scaffold import PLUGIN_BASE, TEST_BASE, generate_plugin

SCAFFOLD_NAME = "_test_scaffold_tmp"
EXPECTED_PLUGIN_FILES = 8
EXPECTED_TOTAL_FILES = 9


@pytest.fixture
def _cleanup():
    yield
    plugin_dir = PLUGIN_BASE / SCAFFOLD_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    test_file = TEST_BASE / f"test_{SCAFFOLD_NAME}_plugin.py"
    if test_file.exists():
        test_file.unlink()


@pytest.mark.offline
@pytest.mark.usefixtures("_cleanup")
class TestGeneratePlugin:
    def test_creates_expected_files(self):
        created = generate_plugin(SCAFFOLD_NAME)
        assert len(created) == EXPECTED_TOTAL_FILES

    def test_plugin_directory_structure(self):
        generate_plugin(SCAFFOLD_NAME)
        plugin_dir = PLUGIN_BASE / SCAFFOLD_NAME

        expected = {
            "__init__.py",
            "config.py",
            "collector.py",
            "processor.py",
            "analyzer.py",
            "model.py",
            "action.py",
            "monitor.py",
        }
        actual = {p.name for p in plugin_dir.iterdir()}
        assert actual == expected

    def test_generates_test_file(self):
        generate_plugin(SCAFFOLD_NAME)
        test_file = TEST_BASE / f"test_{SCAFFOLD_NAME}_plugin.py"
        assert test_file.exists()

        content = test_file.read_text(encoding="utf-8")
        assert "TestScaffoldTmpConfig" in content

    def test_config_contains_pydantic_model(self):
        generate_plugin(SCAFFOLD_NAME)
        config_file = PLUGIN_BASE / SCAFFOLD_NAME / "config.py"
        content = config_file.read_text(encoding="utf-8")
        assert "BaseModel" in content
        assert "ScaffoldTmpConfig" in content

    def test_collector_has_register_decorator(self):
        generate_plugin(SCAFFOLD_NAME)
        collector = PLUGIN_BASE / SCAFFOLD_NAME / "collector.py"
        content = collector.read_text(encoding="utf-8")
        assert f'@register_collector("{SCAFFOLD_NAME}")' in content
        assert "BaseCollector" in content

    def test_model_has_register_decorator(self):
        generate_plugin(SCAFFOLD_NAME)
        model = PLUGIN_BASE / SCAFFOLD_NAME / "model.py"
        content = model.read_text(encoding="utf-8")
        assert f'@register_model("{SCAFFOLD_NAME}")' in content
        assert "BaseSimulator" in content

    def test_raises_on_duplicate(self):
        generate_plugin(SCAFFOLD_NAME)
        with pytest.raises(FileExistsError, match="already exists"):
            generate_plugin(SCAFFOLD_NAME)

    def test_all_files_are_valid_python(self):
        generate_plugin(SCAFFOLD_NAME)
        plugin_dir = PLUGIN_BASE / SCAFFOLD_NAME
        for py_file in plugin_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            compile(content, str(py_file), "exec")

    def test_returns_path_objects(self):
        created = generate_plugin(SCAFFOLD_NAME)
        assert all(isinstance(p, Path) for p in created)

    def test_all_stages_use_correct_base_class(self):
        generate_plugin(SCAFFOLD_NAME)
        plugin_dir = PLUGIN_BASE / SCAFFOLD_NAME

        stage_bases = {
            "collector.py": "BaseCollector",
            "processor.py": "BaseProcessor",
            "analyzer.py": "BaseAnalyzer",
            "model.py": "BaseSimulator",
            "action.py": "BaseDecider",
            "monitor.py": "BaseMonitor",
        }

        for filename, base_class in stage_bases.items():
            content = (plugin_dir / filename).read_text(encoding="utf-8")
            assert base_class in content, f"{filename} missing {base_class}"
