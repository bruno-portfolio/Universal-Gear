"""Export helpers for pipeline results (JSON / CSV)."""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from universal_gear.core.pipeline import PipelineResult


def _serialize_stage(obj: object | None) -> dict[str, Any] | None:
    """Serialize a Pydantic contract object to a JSON-safe dict."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")  # type: ignore[union-attr]
    return None


def _build_payload(result: PipelineResult) -> dict[str, Any]:
    """Build the full JSON payload from a PipelineResult."""
    stages_data: dict[str, Any] = {
        "observation": _serialize_stage(result.collection),
        "compression": _serialize_stage(result.compression),
        "hypothesis": _serialize_stage(result.hypothesis),
        "simulation": _serialize_stage(result.simulation),
        "decision": _serialize_stage(result.decision),
        "feedback": _serialize_stage(result.feedback),
    }

    metrics_data: dict[str, Any] = {
        "total_duration": result.metrics.total_duration,
        "all_success": result.metrics.all_success,
        "stages": [
            {
                "stage": s.stage,
                "duration_seconds": s.duration_seconds,
                "success": s.success,
                "error": s.error,
            }
            for s in result.metrics.stages
        ],
    }

    return {
        "success": result.success,
        "error": result.error,
        "stages": stages_data,
        "metrics": metrics_data,
    }


def export_json(result: PipelineResult) -> str:
    """Serialize the full PipelineResult to a JSON string."""
    payload = _build_payload(result)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def export_csv(result: PipelineResult) -> str:
    """Serialize the PipelineResult as a CSV summary table."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["stage", "status", "detail", "duration_seconds"])

    for stage_metric in result.metrics.stages:
        status = "OK" if stage_metric.success else "FAIL"
        detail = _stage_detail_plain(result, stage_metric.stage)
        writer.writerow([
            stage_metric.stage,
            status,
            detail,
            f"{stage_metric.duration_seconds:.3f}",
        ])

    writer.writerow([
        "TOTAL",
        "SUCCESS" if result.success else "FAILED",
        result.error or "",
        f"{result.metrics.total_duration:.3f}",
    ])

    return buf.getvalue()


def _stage_detail_plain(  # noqa: PLR0911
    result: PipelineResult,
    stage: str,
) -> str:
    """Plain-text stage detail (no Rich markup)."""
    match stage:
        case "observation":
            if result.collection:
                n = len(result.collection.events)
                rel = result.collection.quality_report.reliability_score
                return f"{n} events | reliability: {rel:.2f}"
        case "compression":
            if result.compression:
                n = len(result.compression.states)
                gran = (
                    result.compression.states[0].granularity.value
                    if result.compression.states
                    else "?"
                )
                return f"{n} states | {gran}"
        case "hypothesis":
            if result.hypothesis:
                n = len(result.hypothesis.hypotheses)
                return f"{n} hypotheses"
        case "simulation":
            if result.simulation:
                n = len(result.simulation.scenarios)
                has_bl = (
                    "baseline + " if result.simulation.baseline else ""
                )
                return f"{has_bl}{n} scenarios"
        case "decision":
            if result.decision:
                n = len(result.decision.decisions)
                types = {
                    d.decision_type.value
                    for d in result.decision.decisions
                }
                return f"{n} decisions | {', '.join(types)}"
        case "feedback":
            if result.feedback:
                n = len(result.feedback.scorecards)
                return f"{n} scorecards"
    return ""
