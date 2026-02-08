"""Configuration for the agro domain plugin."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _today() -> str:
    return date.today().isoformat()


class AgroConfig(BaseModel):
    """Shared configuration for all agro pipeline stages."""

    commodity: str = "soja"
    region: str | None = None
    date_start: str = Field(default_factory=lambda: _days_ago(90))
    date_end: str = Field(default_factory=_today)
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
