"""Pydantic v2 contracts for every pipeline stage."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SourceType(StrEnum):
    API = "api"
    FILE = "file"
    SCRAPER = "scraper"
    MANUAL = "manual"
    SYNTHETIC = "synthetic"


class Granularity(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class SourceReliability(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEGRADED = "degraded"


class HypothesisStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionType(StrEnum):
    ALERT = "alert"
    RECOMMENDATION = "recommendation"
    TRIGGER = "trigger"
    REPORT = "report"


class SourceMeta(BaseModel):
    """Source metadata attached to every raw event."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_type: SourceType
    url_or_path: str | None = None
    expected_schema_version: str | None = None
    reliability: SourceReliability = SourceReliability.HIGH


class QualityFlag(BaseModel):
    """Individual data-quality flag."""

    model_config = ConfigDict(frozen=True)

    field_name: str
    issue: str
    severity: str
    details: str | None = None


class RawEvent(BaseModel):
    """Single raw event collected from a source."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    source: SourceMeta
    timestamp: datetime
    collected_at: datetime = Field(default_factory=_utcnow)
    data: dict[str, Any]
    schema_version: str | None = None


class DataQualityReport(BaseModel):
    """Quality report produced by the observation stage."""

    model_config = ConfigDict(frozen=True)

    source: SourceMeta
    collected_at: datetime = Field(default_factory=_utcnow)
    total_records: int
    valid_records: int
    flags: list[QualityFlag] = Field(default_factory=list)
    schema_match: bool = True
    reliability_score: float = Field(ge=0.0, le=1.0, default=1.0)
    notes: str | None = None

    @property
    def valid_ratio(self) -> float:
        if self.total_records == 0:
            return 0.0
        return self.valid_records / self.total_records


class CollectionResult(BaseModel):
    """Full output of the Observation stage."""

    events: list[RawEvent]
    quality_report: DataQualityReport
    stage: str = "observation"


class SignalValue(BaseModel):
    """Single normalised signal."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: float
    unit: str
    original_unit: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class MarketState(BaseModel):
    """Compressed, normalised market state for a time window."""

    model_config = ConfigDict(frozen=True)

    state_id: UUID = Field(default_factory=uuid4)
    domain: str
    period_start: datetime
    period_end: datetime
    granularity: Granularity
    signals: list[SignalValue]
    lineage: list[UUID]
    source_reliability: float = Field(ge=0.0, le=1.0)

    @field_validator("signals")
    @classmethod
    def at_least_one_signal(cls, v: list[SignalValue]) -> list[SignalValue]:
        if not v:
            raise ValueError("MarketState requires at least 1 signal")
        return v


class CompressionResult(BaseModel):
    """Full output of the Compression stage."""

    states: list[MarketState]
    records_consumed: int
    records_produced: int
    normalization_log: list[str] = Field(default_factory=list)
    stage: str = "compression"


class ValidationCriterion(BaseModel):
    """Criterion used to validate or falsify a hypothesis."""

    model_config = ConfigDict(frozen=True)

    metric: str
    operator: str
    threshold: float | tuple[float, float]
    description: str


class Hypothesis(BaseModel):
    """Testable hypothesis derived from market states."""

    model_config = ConfigDict(frozen=True)

    hypothesis_id: UUID = Field(default_factory=uuid4)
    statement: str
    rationale: str
    status: HypothesisStatus = HypothesisStatus.PENDING
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utcnow)
    valid_until: datetime
    validation_criteria: list[ValidationCriterion]
    falsification_criteria: list[ValidationCriterion]
    competing_hypotheses: list[str] = Field(default_factory=list)
    source_states: list[UUID]

    @field_validator("validation_criteria")
    @classmethod
    def needs_validation(cls, v: list[ValidationCriterion]) -> list[ValidationCriterion]:
        if not v:
            raise ValueError("Hypothesis requires at least 1 validation criterion")
        return v

    @field_validator("falsification_criteria")
    @classmethod
    def needs_falsification(cls, v: list[ValidationCriterion]) -> list[ValidationCriterion]:
        if not v:
            raise ValueError("Hypothesis requires at least 1 falsification criterion")
        return v


class HypothesisResult(BaseModel):
    """Full output of the Hypothesis stage."""

    hypotheses: list[Hypothesis]
    states_analyzed: int
    stage: str = "hypothesis"


class Assumption(BaseModel):
    """Explicit assumption underpinning a scenario."""

    model_config = ConfigDict(frozen=True)

    variable: str
    assumed_value: float | str
    justification: str


class Scenario(BaseModel):
    """Conditional scenario produced by simulation."""

    model_config = ConfigDict(frozen=True)

    scenario_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    assumptions: list[Assumption]
    projected_outcome: dict[str, float]
    confidence_interval: tuple[float, float]
    probability: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    sensitivity: dict[str, float] = Field(default_factory=dict)
    source_hypotheses: list[UUID]


MIN_SCENARIOS = 2


class SimulationResult(BaseModel):
    """Full output of the Simulation stage."""

    scenarios: list[Scenario]
    baseline: Scenario | None = None
    stage: str = "simulation"

    @model_validator(mode="after")
    def at_least_two_scenarios(self) -> SimulationResult:
        if len(self.scenarios) < MIN_SCENARIOS:
            raise ValueError("Simulation requires at least 2 scenarios")
        return self


class DecisionDriver(BaseModel):
    """Factor influencing the decision."""

    model_config = ConfigDict(frozen=True)

    name: str
    weight: float = Field(ge=0.0, le=1.0)
    description: str


class CostOfError(BaseModel):
    """Estimated cost of being wrong."""

    model_config = ConfigDict(frozen=True)

    false_positive: str
    false_negative: str
    estimated_magnitude: str | None = None


class Condition(BaseModel):
    """Activation condition for a decision."""

    model_config = ConfigDict(frozen=True)

    description: str
    metric: str
    operator: str
    threshold: float
    window: str


class DecisionObject(BaseModel):
    """Structured decision object."""

    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    decision_type: DecisionType
    title: str
    recommendation: str
    conditions: list[Condition] = Field(default_factory=list)
    drivers: list[DecisionDriver]
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    cost_of_error: CostOfError
    expires_at: datetime | None = None
    source_scenarios: list[UUID]
    created_at: datetime = Field(default_factory=_utcnow)


class DecisionResult(BaseModel):
    """Full output of the Decision stage."""

    decisions: list[DecisionObject]
    stage: str = "decision"


class PredictionVsReality(BaseModel):
    """Comparison between projection and observed reality."""

    model_config = ConfigDict(frozen=True)

    metric: str
    predicted: float
    actual: float
    error_pct: float
    within_confidence: bool


class SourceDegradation(BaseModel):
    """Record of source reliability degradation."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    previous_reliability: float
    current_reliability: float
    reason: str


class Scorecard(BaseModel):
    """Feedback scorecard evaluating a past decision."""

    model_config = ConfigDict(frozen=True)

    scorecard_id: UUID = Field(default_factory=uuid4)
    decision_id: UUID
    evaluated_at: datetime = Field(default_factory=_utcnow)
    predictions_vs_reality: list[PredictionVsReality]
    decision_outcome: str
    source_degradations: list[SourceDegradation] = Field(default_factory=list)
    model_adjustments: list[str] = Field(default_factory=list)
    threshold_updates: dict[str, float] = Field(default_factory=dict)
    lessons_learned: str | None = None


class FeedbackResult(BaseModel):
    """Full output of the Feedback stage."""

    scorecards: list[Scorecard]
    sources_updated: int
    thresholds_adjusted: int
    stage: str = "feedback"
