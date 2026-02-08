"""Signal normalisation — unit mapping and label canonicalisation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from universal_gear.core.contracts import RawEvent


class UnitMapping(BaseModel):
    """Maps one unit to another with a conversion factor."""

    from_unit: str
    to_unit: str
    factor: float


class NormalizerConfig(BaseModel):
    """Configuration for the normaliser processor."""

    unit_mappings: list[UnitMapping] = Field(default_factory=list)
    label_synonyms: dict[str, str] = Field(default_factory=dict)
    default_unit: str = "unit"


class Normalizer:
    """Normalises raw event data in-place: unit conversion + label canonicalisation."""

    def __init__(self, config: NormalizerConfig) -> None:
        self.config = config
        self._unit_map: dict[str, UnitMapping] = {m.from_unit: m for m in config.unit_mappings}
        self._log: list[str] = []

    def normalise_events(self, events: list[RawEvent]) -> tuple[list[dict[str, Any]], list[str]]:
        """Return normalised data dicts (one per event) and a log of actions taken."""
        self._log = []
        normalised: list[dict[str, Any]] = []

        for event in events:
            norm = dict(event.data)
            norm = self._apply_label_synonyms(norm)
            norm = self._apply_unit_conversions(norm)
            normalised.append(norm)

        return normalised, list(self._log)

    def _apply_label_synonyms(self, data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            canonical = self.config.label_synonyms.get(key, key)
            if canonical != key:
                self._log.append(f"label: '{key}' -> '{canonical}'")
            result[canonical] = value
        return result

    def _apply_unit_conversions(self, data: dict[str, Any]) -> dict[str, Any]:
        for key, value in data.items():
            if isinstance(value, (int, float)) and key in self._unit_map:
                mapping = self._unit_map[key]
                data[key] = value * mapping.factor
                self._log.append(
                    f"unit: '{key}' {mapping.from_unit} -> {mapping.to_unit} (x{mapping.factor})"
                )
        return data
