"""Configuration for the finance domain plugin."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _today() -> str:
    return date.today().isoformat()


class FinanceConfig(BaseModel):
    """Shared configuration for all finance pipeline stages."""

    indicators: list[str] = Field(
        default_factory=lambda: ["usd_brl"],
    )
    date_start: str = Field(default_factory=lambda: _days_ago(90))
    date_end: str = Field(default_factory=_today)
    granularity: str = "weekly"
    base_currency: str = "BRL"


# BCB SGS series codes for each indicator
SGS_SERIES: dict[str, int] = {
    "selic": 11,
    "ipca": 433,
}

# Human-readable labels and units
INDICATOR_LABELS: dict[str, str] = {
    "usd_brl": "USD/BRL Exchange Rate",
    "selic": "SELIC Target Rate",
    "ipca": "IPCA Inflation Index",
}

INDICATOR_UNITS: dict[str, str] = {
    "usd_brl": "BRL/USD",
    "selic": "% p.a.",
    "ipca": "% m/m",
}
