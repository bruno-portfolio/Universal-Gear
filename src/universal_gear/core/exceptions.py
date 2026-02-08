"""Hierarchy of domain exceptions for Universal Gear."""

from __future__ import annotations


class UniversalGearError(Exception):
    """Base exception for all Universal Gear errors."""


class SchemaValidationError(UniversalGearError):
    """Data schema does not match the expected contract."""


class CollectionError(UniversalGearError):
    """Collection stage failure (timeout, HTTP error, parse error)."""


class DegradedSourceError(UniversalGearError):
    """Source available but quality is below the configured threshold."""


class StageTransitionError(UniversalGearError):
    """Stage output does not meet transition criteria for the next stage."""


class PipelineError(UniversalGearError):
    """Pipeline orchestration failure."""


class PluginNotFoundError(UniversalGearError):
    """Referenced plugin is not registered."""
