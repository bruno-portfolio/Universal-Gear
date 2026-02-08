"""Plugin registry with decorator-based registration."""

from __future__ import annotations

from typing import Any

from universal_gear.core.exceptions import PluginNotFoundError

_VALID_STAGES = frozenset({"collector", "processor", "analyzer", "model", "action", "monitor"})

_REGISTRY: dict[str, dict[str, type[Any]]] = {stage: {} for stage in _VALID_STAGES}


def register(stage: str, name: str):
    """Decorator that registers a plugin class under *stage*/*name*."""

    def decorator(cls: type[Any]) -> type[Any]:
        if stage not in _VALID_STAGES:
            msg = f"Unknown stage '{stage}'. Valid: {sorted(_VALID_STAGES)}"
            raise ValueError(msg)
        _REGISTRY[stage][name] = cls
        return cls

    return decorator


def get_plugin(stage: str, name: str) -> type[Any]:
    """Retrieve a registered plugin class."""
    try:
        return _REGISTRY[stage][name]
    except KeyError:
        available = list(_REGISTRY.get(stage, {}).keys())
        raise PluginNotFoundError(
            f"Plugin '{name}' not found in stage '{stage}'. Available: {available}"
        ) from None


def list_plugins(stage: str | None = None) -> dict[str, list[str]]:
    """List registered plugins, optionally filtered by stage."""
    if stage:
        return {stage: list(_REGISTRY.get(stage, {}).keys())}
    return {s: list(plugins.keys()) for s, plugins in _REGISTRY.items()}


def register_collector(name: str):
    return register("collector", name)


def register_processor(name: str):
    return register("processor", name)


def register_analyzer(name: str):
    return register("analyzer", name)


def register_model(name: str):
    return register("model", name)


def register_action(name: str):
    return register("action", name)


def register_monitor(name: str):
    return register("monitor", name)
