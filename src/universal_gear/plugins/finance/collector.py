"""BCB collector -- fetches real macroeconomic data from Banco Central do Brasil APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from universal_gear.core.contracts import (
    CollectionResult,
    DataQualityReport,
    QualityFlag,
    RawEvent,
    SourceMeta,
    SourceReliability,
    SourceType,
)
from universal_gear.core.interfaces import BaseCollector
from universal_gear.core.registry import register_collector
from universal_gear.plugins.finance.config import SGS_SERIES, FinanceConfig

logger = structlog.get_logger()

# BCB PTAX endpoint for USD/BRL exchange rates
_PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
    "/CotacaoDolarPeriodo(dataInicial=@di,dataFinalCotacao=@df)"
)

# BCB SGS endpoint for time-series (SELIC, IPCA, etc.)
_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series}/dados"

_REQUEST_TIMEOUT = 30.0


@register_collector("bcb")
class BCBCollector(BaseCollector[FinanceConfig]):
    """Collects real macroeconomic data from Banco Central do Brasil open APIs."""

    async def collect(self) -> CollectionResult:
        events: list[RawEvent] = []
        flags: list[QualityFlag] = []

        for indicator in self.config.indicators:
            match indicator:
                case "usd_brl":
                    ind_events, ind_flags = await self._collect_ptax()
                case "selic" | "ipca":
                    ind_events, ind_flags = await self._collect_sgs(indicator)
                case _:
                    logger.warning("indicator.unknown", indicator=indicator)
                    continue
            events.extend(ind_events)
            flags.extend(ind_flags)

        total = len(events)
        valid = sum(1 for e in events if self._is_valid_event(e))

        source_meta = SourceMeta(
            source_id="bcb-finance",
            source_type=SourceType.API,
            url_or_path="https://olinda.bcb.gov.br",
            reliability=SourceReliability.HIGH,
        )

        quality_report = DataQualityReport(
            source=source_meta,
            total_records=total,
            valid_records=valid,
            flags=flags,
            schema_match=not flags or all(f.severity != "critical" for f in flags),
            reliability_score=valid / total if total > 0 else 0.0,
        )

        return CollectionResult(events=events, quality_report=quality_report)

    async def _collect_ptax(self) -> tuple[list[RawEvent], list[QualityFlag]]:
        """Fetch USD/BRL exchange rates from the BCB PTAX endpoint."""
        events: list[RawEvent] = []
        flags: list[QualityFlag] = []

        source = SourceMeta(
            source_id="bcb-ptax-usd_brl",
            source_type=SourceType.API,
            url_or_path=_PTAX_URL,
            reliability=SourceReliability.HIGH,
        )

        di = _to_bcb_date(self.config.date_start)
        df = _to_bcb_date(self.config.date_end)

        params: dict[str, str] = {
            "@di": f"'{di}'",
            "@df": f"'{df}'",
            "$format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(_PTAX_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("ptax.http_error", status=exc.response.status_code)
            flags.append(
                QualityFlag(
                    field_name="ptax_fetch",
                    issue="http_error",
                    severity="critical",
                    details=f"HTTP {exc.response.status_code}",
                )
            )
            return events, flags
        except Exception as exc:
            logger.error("ptax.fetch_failed", error=str(exc))
            flags.append(
                QualityFlag(
                    field_name="ptax_fetch",
                    issue="collection_error",
                    severity="critical",
                    details=str(exc),
                )
            )
            return events, flags

        records = payload.get("value", [])
        for record in records:
            row_flags = self._validate_ptax_record(record)
            flags.extend(row_flags)

            timestamp = _parse_ptax_timestamp(record.get("dataHoraCotacao"))
            if timestamp is None:
                flags.append(
                    QualityFlag(
                        field_name="dataHoraCotacao",
                        issue="missing",
                        severity="error",
                        details=f"Could not parse timestamp: {record}",
                    )
                )
                continue

            events.append(
                RawEvent(
                    source=source,
                    timestamp=timestamp,
                    data={
                        "indicator": "usd_brl",
                        "cotacao_compra": record.get("cotacaoCompra"),
                        "cotacao_venda": record.get("cotacaoVenda"),
                        "data_hora_cotacao": record.get("dataHoraCotacao"),
                    },
                    schema_version="ptax-v1",
                )
            )

        logger.info("ptax.collected", records=len(events), flags=len(flags))
        return events, flags

    async def _collect_sgs(self, indicator: str) -> tuple[list[RawEvent], list[QualityFlag]]:
        """Fetch time-series data from the BCB SGS endpoint (SELIC, IPCA, etc.)."""
        events: list[RawEvent] = []
        flags: list[QualityFlag] = []

        series = SGS_SERIES.get(indicator)
        if series is None:
            flags.append(
                QualityFlag(
                    field_name="indicator",
                    issue="unknown_series",
                    severity="critical",
                    details=f"No SGS series mapped for indicator '{indicator}'",
                )
            )
            return events, flags

        source = SourceMeta(
            source_id=f"bcb-sgs-{indicator}",
            source_type=SourceType.API,
            url_or_path=_SGS_URL.format(series=series),
            reliability=SourceReliability.HIGH,
        )

        di = _to_sgs_date(self.config.date_start)
        df = _to_sgs_date(self.config.date_end)

        url = _SGS_URL.format(series=series)
        params: dict[str, str] = {
            "formato": "json",
            "dataInicial": di,
            "dataFinal": df,
        }

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                records: list[dict[str, Any]] = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "sgs.http_error",
                indicator=indicator,
                status=exc.response.status_code,
            )
            flags.append(
                QualityFlag(
                    field_name=f"{indicator}_fetch",
                    issue="http_error",
                    severity="critical",
                    details=f"HTTP {exc.response.status_code}",
                )
            )
            return events, flags
        except Exception as exc:
            logger.error("sgs.fetch_failed", indicator=indicator, error=str(exc))
            flags.append(
                QualityFlag(
                    field_name=f"{indicator}_fetch",
                    issue="collection_error",
                    severity="critical",
                    details=str(exc),
                )
            )
            return events, flags

        for record in records:
            timestamp = _parse_sgs_timestamp(record.get("data"))
            valor = record.get("valor")

            if timestamp is None:
                flags.append(
                    QualityFlag(
                        field_name="data",
                        issue="missing",
                        severity="error",
                        details=f"Could not parse timestamp: {record}",
                    )
                )
                continue

            if valor is None:
                flags.append(
                    QualityFlag(
                        field_name="valor",
                        issue="missing",
                        severity="warning",
                        details=f"Null value for {indicator} on {record.get('data')}",
                    )
                )
                continue

            try:
                parsed_valor = float(str(valor).replace(",", "."))
            except (ValueError, TypeError):
                flags.append(
                    QualityFlag(
                        field_name="valor",
                        issue="type_mismatch",
                        severity="error",
                        details=f"Cannot parse '{valor}' as float",
                    )
                )
                continue

            events.append(
                RawEvent(
                    source=source,
                    timestamp=timestamp,
                    data={
                        "indicator": indicator,
                        "valor": parsed_valor,
                        "data_referencia": record.get("data"),
                    },
                    schema_version=f"sgs-{indicator}-v1",
                )
            )

        logger.info(
            "sgs.collected",
            indicator=indicator,
            records=len(events),
            flags=len(flags),
        )
        return events, flags

    def _validate_ptax_record(self, record: dict[str, Any]) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        for field in ("cotacaoCompra", "cotacaoVenda"):
            val = record.get(field)
            if val is None:
                flags.append(
                    QualityFlag(
                        field_name=field,
                        issue="missing",
                        severity="warning",
                        details=f"{field} is null",
                    )
                )
            elif not isinstance(val, int | float):
                flags.append(
                    QualityFlag(
                        field_name=field,
                        issue="type_mismatch",
                        severity="error",
                        details=f"Expected numeric, got {type(val).__name__}",
                    )
                )
        return flags

    def _is_valid_event(self, event: RawEvent) -> bool:
        indicator = event.data.get("indicator")
        if indicator == "usd_brl":
            buy = event.data.get("cotacao_compra")
            sell = event.data.get("cotacao_venda")
            return (
                buy is not None
                and sell is not None
                and isinstance(buy, int | float)
                and isinstance(sell, int | float)
            )
        valor = event.data.get("valor")
        return valor is not None and isinstance(valor, int | float)


def _to_bcb_date(iso_date: str) -> str:
    """Convert ISO date (YYYY-MM-DD) to BCB PTAX format (MM-DD-YYYY)."""
    dt = datetime.fromisoformat(iso_date)
    return dt.strftime("%m-%d-%Y")


def _to_sgs_date(iso_date: str) -> str:
    """Convert ISO date (YYYY-MM-DD) to BCB SGS format (DD/MM/YYYY)."""
    dt = datetime.fromisoformat(iso_date)
    return dt.strftime("%d/%m/%Y")


def _parse_ptax_timestamp(value: Any) -> datetime | None:
    """Parse PTAX timestamp format (e.g. '2026-01-15 13:04:23.456')."""
    if value is None:
        return None
    try:
        raw = str(value)
        # PTAX returns ISO-like format: "2026-01-15 13:04:23.456"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_sgs_timestamp(value: Any) -> datetime | None:
    """Parse SGS date format (DD/MM/YYYY)."""
    if value is None:
        return None
    try:
        dt = datetime.strptime(str(value), "%d/%m/%Y")
        return dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None
