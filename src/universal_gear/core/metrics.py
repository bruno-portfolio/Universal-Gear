"""Internal metrics for pipeline stage execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StageMetrics:
    """Metrics captured for a single stage execution."""

    stage: str
    duration_seconds: float
    success: bool
    records_in: int = 0
    records_out: int = 0
    error: str | None = None


@dataclass
class PipelineMetrics:
    """Aggregated metrics for a full pipeline run."""

    stages: list[StageMetrics] = field(default_factory=list)

    def add(self, metrics: StageMetrics) -> None:
        self.stages.append(metrics)

    @property
    def total_duration(self) -> float:
        return sum(s.duration_seconds for s in self.stages)

    @property
    def all_success(self) -> bool:
        return all(s.success for s in self.stages)

    def summary(self) -> dict[str, Any]:
        return {
            "total_duration": self.total_duration,
            "all_success": self.all_success,
            "stages": [
                {
                    "stage": s.stage,
                    "duration": s.duration_seconds,
                    "success": s.success,
                    "error": s.error,
                }
                for s in self.stages
            ],
        }
