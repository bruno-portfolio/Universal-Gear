"""Agrobr collector — fetches real commodity data from CEPEA/CONAB via agrobr."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from typing import Any

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
from universal_gear.core.exceptions import CollectionError
from universal_gear.core.interfaces import BaseCollector
from universal_gear.core.registry import register_collector
from universal_gear.plugins.agro.config import AgroConfig

logger = structlog.get_logger()

EXPECTED_COLUMNS_CEPEA = {"data", "produto", "praca", "valor", "unidade", "fonte"}


@register_collector("agrobr")
class AgrobrCollector(BaseCollector[AgroConfig]):
    """Collects real market data using the agrobr library."""

    async def collect(self) -> CollectionResult:
        events: list[RawEvent] = []
        flags: list[QualityFlag] = []

        if self.config.sample:
            return self._load_sample()

        for source_name in self.config.sources:
            match source_name:
                case "cepea":
                    src_events, src_flags = await self._collect_cepea()
                case "conab":
                    src_events, src_flags = await self._collect_conab()
                case _:
                    logger.warning("source.unknown", source=source_name)
                    continue
            events.extend(src_events)
            flags.extend(src_flags)

        total = len(events)
        valid = sum(1 for e in events if self._is_valid_event(e))

        source_meta = SourceMeta(
            source_id=f"agrobr-{self.config.commodity}",
            source_type=SourceType.API,
            url_or_path="https://cepea.esalq.usp.br",
            reliability=SourceReliability.HIGH,
        )

        quality_report = DataQualityReport(
            source=source_meta,
            total_records=total,
            valid_records=valid,
            flags=flags,
            schema_match=len(flags) == 0 or all(f.severity != "critical" for f in flags),
            reliability_score=valid / total if total > 0 else 0.0,
        )

        return CollectionResult(events=events, quality_report=quality_report)

    def _load_sample(self) -> CollectionResult:
        """Load cached sample data from bundled fixture for offline use."""
        fixture_path = resources.files("universal_gear.plugins.agro.fixtures").joinpath(
            "sample_cepea.json"
        )

        raw_records: list[dict[str, Any]] = json.loads(fixture_path.read_text("utf-8"))

        source = SourceMeta(
            source_id=f"cepea-{self.config.commodity}-sample",
            source_type=SourceType.FILE,
            url_or_path="bundled://sample_cepea.json",
            reliability=SourceReliability.MEDIUM,
        )

        events: list[RawEvent] = []
        for record in raw_records:
            timestamp = _parse_timestamp(record.get("data"))
            if timestamp is None:
                continue
            events.append(
                RawEvent(
                    source=source,
                    timestamp=timestamp,
                    data=record,
                    schema_version="cepea-v1",
                )
            )

        logger.info(
            "agro.sample_loaded",
            records=len(events),
            commodity=self.config.commodity,
        )

        quality_report = DataQualityReport(
            source=source,
            total_records=len(events),
            valid_records=len(events),
            reliability_score=0.85,
            notes="Sample data from bundled fixture (offline mode)",
        )

        return CollectionResult(events=events, quality_report=quality_report)

    async def _collect_cepea(self) -> tuple[list[RawEvent], list[QualityFlag]]:
        try:
            from agrobr import cepea
        except ImportError as exc:
            raise CollectionError(
                "agrobr not installed. Run: pip install universal-gear[agro]"
            ) from exc

        events: list[RawEvent] = []
        flags: list[QualityFlag] = []

        source = SourceMeta(
            source_id=f"cepea-{self.config.commodity}",
            source_type=SourceType.API,
            url_or_path="https://cepea.esalq.usp.br",
            reliability=SourceReliability.HIGH,
        )

        try:
            df = await cepea.indicador(
                produto=self.config.commodity,
                praca=self.config.region,
                inicio=self.config.date_start,
                fim=self.config.date_end,
                _moeda=self.config.currency,
            )
        except Exception as exc:
            logger.error("cepea.fetch_failed", error=str(exc))
            flags.append(
                QualityFlag(
                    field_name="cepea_fetch",
                    issue="collection_error",
                    severity="critical",
                    details=str(exc),
                )
            )
            return events, flags

        actual_columns = set(df.columns)
        missing_columns = EXPECTED_COLUMNS_CEPEA - actual_columns
        if missing_columns:
            flags.append(
                QualityFlag(
                    field_name="schema",
                    issue="schema_changed",
                    severity="warning",
                    details=f"Missing expected columns: {missing_columns}",
                )
            )

        for _, row in df.iterrows():
            data: dict[str, Any] = row.to_dict()

            row_flags = self._validate_cepea_row(data)
            flags.extend(row_flags)

            timestamp = _parse_timestamp(data.get("data"))
            if timestamp is None:
                flags.append(
                    QualityFlag(
                        field_name="data",
                        issue="missing",
                        severity="error",
                        details=f"Could not parse timestamp from row: {data}",
                    )
                )
                continue

            events.append(
                RawEvent(
                    source=source,
                    timestamp=timestamp,
                    data=data,
                    schema_version="cepea-v1",
                )
            )

        logger.info(
            "cepea.collected",
            commodity=self.config.commodity,
            records=len(events),
            flags=len(flags),
        )
        return events, flags

    async def _collect_conab(self) -> tuple[list[RawEvent], list[QualityFlag]]:
        try:
            from agrobr import conab
        except ImportError as exc:
            raise CollectionError(
                "agrobr not installed. Run: pip install universal-gear[agro]"
            ) from exc

        events: list[RawEvent] = []
        flags: list[QualityFlag] = []

        source = SourceMeta(
            source_id=f"conab-{self.config.commodity}",
            source_type=SourceType.API,
            url_or_path="https://conab.gov.br",
            reliability=SourceReliability.MEDIUM,
        )

        try:
            df = await conab.safras(
                produto=self.config.commodity,
                safra=self.config.safra,
                uf=self.config.uf,
            )
        except Exception as exc:
            logger.error("conab.fetch_failed", error=str(exc))
            flags.append(
                QualityFlag(
                    field_name="conab_fetch",
                    issue="collection_error",
                    severity="critical",
                    details=str(exc),
                )
            )
            return events, flags

        for _, row in df.iterrows():
            data: dict[str, Any] = row.to_dict()
            timestamp = _parse_timestamp(data.get("data_publicacao"))
            if timestamp is None:
                timestamp = datetime.now(UTC)

            events.append(
                RawEvent(
                    source=source,
                    timestamp=timestamp,
                    data=data,
                    schema_version="conab-v1",
                )
            )

        logger.info(
            "conab.collected",
            commodity=self.config.commodity,
            records=len(events),
        )
        return events, flags

    def _validate_cepea_row(self, data: dict[str, Any]) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        valor = data.get("valor")

        if valor is None:
            flags.append(
                QualityFlag(
                    field_name="valor",
                    issue="missing",
                    severity="warning",
                    details="Price value is null",
                )
            )
        elif not isinstance(valor, int | float):
            flags.append(
                QualityFlag(
                    field_name="valor",
                    issue="type_mismatch",
                    severity="error",
                    details=f"Expected numeric, got {type(valor).__name__}",
                )
            )
        return flags

    def _is_valid_event(self, event: RawEvent) -> bool:
        valor = event.data.get("valor")
        return valor is not None and isinstance(valor, int | float)


def _parse_timestamp(value: Any) -> datetime | None:
    """Best-effort timestamp parsing from various agrobr formats."""
    if value is None:
        return None

    dt: datetime | None = None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            try:
                import pandas as pd

                ts = pd.Timestamp(value)
                if ts is not pd.NaT:
                    dt = ts.to_pydatetime()
            except Exception:
                pass

    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
