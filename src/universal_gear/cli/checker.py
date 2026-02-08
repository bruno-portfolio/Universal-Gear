"""Plugin validation — checks that a plugin implements all required interfaces."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from universal_gear.core.interfaces import (
    BaseAnalyzer,
    BaseCollector,
    BaseDecider,
    BaseMonitor,
    BaseProcessor,
    BaseSimulator,
)

PLUGIN_BASE = Path("src/universal_gear/plugins")

EXPECTED_MODULES = ("config", "collector", "processor", "analyzer", "model", "action", "monitor")

STAGE_BASE_CLASSES: dict[str, type] = {
    "collector": BaseCollector,
    "processor": BaseProcessor,
    "analyzer": BaseAnalyzer,
    "model": BaseSimulator,
    "action": BaseDecider,
    "monitor": BaseMonitor,
}


def check_plugin(name: str) -> list[str]:
    """Validate plugin structure and return a list of error messages."""
    errors: list[str] = []

    plugin_dir = PLUGIN_BASE / name
    if not plugin_dir.is_dir():
        return [f"Plugin directory not found: {plugin_dir}"]

    for module_name in EXPECTED_MODULES:
        module_path = plugin_dir / f"{module_name}.py"
        if not module_path.exists():
            errors.append(f"Missing module: {module_name}.py")

    _check_interfaces(name, errors)

    return errors


def _check_interfaces(name: str, errors: list[str]) -> None:
    """Import each stage module and verify it contains a class with the right ABC."""
    for stage, base_cls in STAGE_BASE_CLASSES.items():
        module_key = f"universal_gear.plugins.{name}.{stage}"
        try:
            mod = importlib.import_module(module_key)
        except (ImportError, ModuleNotFoundError) as exc:
            errors.append(f"{stage}: import failed — {exc}")
            continue

        implementations = [
            cls
            for _, cls in inspect.getmembers(mod, inspect.isclass)
            if issubclass(cls, base_cls) and cls is not base_cls
        ]

        if not implementations:
            errors.append(f"{stage}: no class inheriting {base_cls.__name__}")

    _check_config(name, errors)


def _check_config(name: str, errors: list[str]) -> None:
    """Verify the config module exports a Pydantic BaseModel subclass."""
    module_key = f"universal_gear.plugins.{name}.config"
    try:
        mod = importlib.import_module(module_key)
    except (ImportError, ModuleNotFoundError) as exc:
        errors.append(f"config: import failed — {exc}")
        return

    from pydantic import BaseModel

    configs = [
        cls
        for _, cls in inspect.getmembers(mod, inspect.isclass)
        if issubclass(cls, BaseModel) and cls is not BaseModel
    ]

    if not configs:
        errors.append("config: no Pydantic BaseModel subclass found")
