"""Configuration for the agro domain plugin."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgroConfig(BaseModel):
    """Shared configuration for all agro pipeline stages."""

    commodity: str = "soja"
    region: str | None = None
    date_start: str = "2025-01-01"
    date_end: str = "2025-12-31"
    sources: list[str] = Field(default_factory=lambda: ["cepea"])
    currency: str = "BRL"
    granularity: str = "weekly"
    safra: str | None = None
    uf: str | None = None


SACA_60KG_TO_TON = 1000 / 60

COMMODITY_UNITS: dict[str, str] = {
    "soja": "BRL/sc60kg",
    "milho": "BRL/sc60kg",
    "cafe": "BRL/sc60kg",
    "boi": "BRL/arroba",
    "trigo": "BRL/ton",
    "algodao": "BRL/arroba",
    "arroz": "BRL/sc50kg",
}

COMMODITY_CANONICAL_UNIT: dict[str, str] = {
    "soja": "BRL/ton",
    "milho": "BRL/ton",
    "cafe": "BRL/ton",
    "boi": "BRL/arroba",
    "trigo": "BRL/ton",
    "algodao": "BRL/arroba",
    "arroz": "BRL/ton",
}
