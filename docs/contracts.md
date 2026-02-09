# Universal Gear Pipeline Contracts

Source of truth: `src/universal_gear/core/contracts.py`

All models use Pydantic v2 with `ConfigDict(frozen=True)` (immutable after construction).
Fields with `Field(default_factory=uuid4)` or `Field(default_factory=_utcnow)` are auto-generated at creation time.

---

## Enums

| Enum | Values |
|------|--------|
| `SourceType` | `api`, `file`, `scraper`, `manual`, `synthetic` |
| `Granularity` | `daily`, `weekly`, `monthly`, `quarterly` |
| `SourceReliability` | `high`, `medium`, `low`, `degraded` |
| `HypothesisStatus` | `pending`, `confirmed`, `rejected`, `expired` |
| `RiskLevel` | `low`, `medium`, `high`, `critical` |
| `DecisionType` | `alert`, `recommendation`, `trigger`, `report` |

All enums are `StrEnum`, so they serialize as their lowercase string value.

---

## Stage 1: Observation

Collects raw events from external sources and produces a quality report.

### Models

**SourceMeta** -- Source metadata attached to every raw event.

| Field | Type | Default |
|-------|------|---------|
| `source_id` | `str` | required |
| `source_type` | `SourceType` | required |
| `url_or_path` | `str \| None` | `None` |
| `expected_schema_version` | `str \| None` | `None` |
| `reliability` | `SourceReliability` | `high` |

**QualityFlag** -- Individual data-quality flag.

| Field | Type | Default |
|-------|------|---------|
| `field_name` | `str` | required |
| `issue` | `str` | required |
| `severity` | `str` | required |
| `details` | `str \| None` | `None` |

**RawEvent** -- Single raw event collected from a source.

| Field | Type | Default |
|-------|------|---------|
| `event_id` | `UUID` | auto `uuid4` |
| `source` | `SourceMeta` | required |
| `timestamp` | `datetime` | required |
| `collected_at` | `datetime` | auto `utcnow` |
| `data` | `dict[str, Any]` | required |
| `schema_version` | `str \| None` | `None` |

**DataQualityReport** -- Quality report produced by the observation stage.

| Field | Type | Default |
|-------|------|---------|
| `source` | `SourceMeta` | required |
| `collected_at` | `datetime` | auto `utcnow` |
| `total_records` | `int` | required |
| `valid_records` | `int` | required |
| `flags` | `list[QualityFlag]` | `[]` |
| `schema_match` | `bool` | `True` |
| `reliability_score` | `float` (0--1) | `1.0` |
| `notes` | `str \| None` | `None` |

Property `valid_ratio` returns `valid_records / total_records` (0.0 when `total_records` is 0).

**CollectionResult** -- Full output of the Observation stage.

| Field | Type | Default |
|-------|------|---------|
| `events` | `list[RawEvent]` | required |
| `quality_report` | `DataQualityReport` | required |
| `stage` | `str` | `"observation"` |

### JSON Example

```json
{
  "events": [
    {
      "event_id": "a1b2c3d4-0000-0000-0000-000000000001",
      "source": {
        "source_id": "cepea-soy",
        "source_type": "api",
        "url_or_path": "https://api.cepea.example/soy",
        "expected_schema_version": "1.0",
        "reliability": "high"
      },
      "timestamp": "2025-06-01T12:00:00Z",
      "collected_at": "2025-06-01T12:05:00Z",
      "data": {
        "price_brl": 145.30,
        "volume_tons": 2500
      },
      "schema_version": "1.0"
    }
  ],
  "quality_report": {
    "source": {
      "source_id": "cepea-soy",
      "source_type": "api",
      "reliability": "high"
    },
    "collected_at": "2025-06-01T12:05:00Z",
    "total_records": 50,
    "valid_records": 48,
    "flags": [
      {
        "field_name": "volume_tons",
        "issue": "negative_value",
        "severity": "warning",
        "details": "2 records had negative volumes"
      }
    ],
    "schema_match": true,
    "reliability_score": 0.96,
    "notes": null
  },
  "stage": "observation"
}
```

### Transition to Compression

```
quality_report.reliability_score >= 0.1   (MIN_RELIABILITY_SCORE)
```

Raises `StageTransitionError("Reliability score too low to proceed")` on failure.

---

## Stage 2: Compression

Normalizes and aggregates raw events into `MarketState` snapshots.

### Models

**SignalValue** -- Single normalized signal.

| Field | Type | Default |
|-------|------|---------|
| `name` | `str` | required |
| `value` | `float` | required |
| `unit` | `str` | required |
| `original_unit` | `str \| None` | `None` |
| `confidence` | `float` (0--1) | `1.0` |

**MarketState** -- Compressed, normalized market state for a time window.

| Field | Type | Default |
|-------|------|---------|
| `state_id` | `UUID` | auto `uuid4` |
| `domain` | `str` | required |
| `period_start` | `datetime` | required |
| `period_end` | `datetime` | required |
| `granularity` | `Granularity` | required |
| `signals` | `list[SignalValue]` | required (min 1) |
| `lineage` | `list[UUID]` | required |
| `source_reliability` | `float` (0--1) | required |

Validator `at_least_one_signal` -- `signals` must contain at least one entry.

**CompressionResult** -- Full output of the Compression stage.

| Field | Type | Default |
|-------|------|---------|
| `states` | `list[MarketState]` | required |
| `records_consumed` | `int` | required |
| `records_produced` | `int` | required |
| `normalization_log` | `list[str]` | `[]` |
| `stage` | `str` | `"compression"` |

### JSON Example

```json
{
  "states": [
    {
      "state_id": "b2c3d4e5-0000-0000-0000-000000000002",
      "domain": "soy-br",
      "period_start": "2025-05-26T00:00:00Z",
      "period_end": "2025-06-01T23:59:59Z",
      "granularity": "weekly",
      "signals": [
        {
          "name": "price_usd_per_ton",
          "value": 420.50,
          "unit": "USD/ton",
          "original_unit": "BRL/sack_60kg",
          "confidence": 0.95
        },
        {
          "name": "volume_tons",
          "value": 12000.0,
          "unit": "metric_ton",
          "original_unit": "metric_ton",
          "confidence": 1.0
        }
      ],
      "lineage": [
        "a1b2c3d4-0000-0000-0000-000000000001"
      ],
      "source_reliability": 0.96
    }
  ],
  "records_consumed": 50,
  "records_produced": 1,
  "normalization_log": [
    "Converted BRL/sack_60kg -> USD/ton using rate 5.20"
  ],
  "stage": "compression"
}
```

### Transition to Hypothesis

```
len(states) > 0
```

Raises `StageTransitionError("No MarketState produced")` on failure.

---

## Stage 3: Hypothesis

Generates testable hypotheses from compressed market states.

### Models

**ValidationCriterion** -- Criterion used to validate or falsify a hypothesis.

| Field | Type | Default |
|-------|------|---------|
| `metric` | `str` | required |
| `operator` | `str` | required |
| `threshold` | `float \| tuple[float, float]` | required |
| `description` | `str` | required |

**Hypothesis** -- Testable hypothesis derived from market states.

| Field | Type | Default |
|-------|------|---------|
| `hypothesis_id` | `UUID` | auto `uuid4` |
| `statement` | `str` | required |
| `rationale` | `str` | required |
| `status` | `HypothesisStatus` | `pending` |
| `confidence` | `float` (0--1) | required |
| `created_at` | `datetime` | auto `utcnow` |
| `valid_until` | `datetime` | required |
| `validation_criteria` | `list[ValidationCriterion]` | required (min 1) |
| `falsification_criteria` | `list[ValidationCriterion]` | required (min 1) |
| `competing_hypotheses` | `list[str]` | `[]` |
| `source_states` | `list[UUID]` | required |

Validators:
- `needs_validation` -- `validation_criteria` must contain at least one entry.
- `needs_falsification` -- `falsification_criteria` must contain at least one entry.

**HypothesisResult** -- Full output of the Hypothesis stage.

| Field | Type | Default |
|-------|------|---------|
| `hypotheses` | `list[Hypothesis]` | required |
| `states_analyzed` | `int` | required |
| `stage` | `str` | `"hypothesis"` |

### JSON Example

```json
{
  "hypotheses": [
    {
      "hypothesis_id": "c3d4e5f6-0000-0000-0000-000000000003",
      "statement": "Soy price will rise above 450 USD/ton within 30 days",
      "rationale": "Weekly price trend shows 3.2% growth with tightening supply",
      "status": "pending",
      "confidence": 0.72,
      "created_at": "2025-06-02T10:00:00Z",
      "valid_until": "2025-07-02T10:00:00Z",
      "validation_criteria": [
        {
          "metric": "price_usd_per_ton",
          "operator": ">=",
          "threshold": 450.0,
          "description": "Price reaches 450 USD/ton"
        }
      ],
      "falsification_criteria": [
        {
          "metric": "price_usd_per_ton",
          "operator": "<",
          "threshold": 400.0,
          "description": "Price drops below 400 USD/ton"
        }
      ],
      "competing_hypotheses": [
        "Price stagnates due to increased Argentine supply"
      ],
      "source_states": [
        "b2c3d4e5-0000-0000-0000-000000000002"
      ]
    }
  ],
  "states_analyzed": 1,
  "stage": "hypothesis"
}
```

### Transition to Simulation

```
len(hypotheses) > 0
```

Raises `StageTransitionError("No hypotheses generated")` on failure.

---

## Stage 4: Simulation

Projects multiple scenarios from hypotheses, each with assumptions and risk levels.

### Models

**Assumption** -- Explicit assumption underpinning a scenario.

| Field | Type | Default |
|-------|------|---------|
| `variable` | `str` | required |
| `assumed_value` | `float \| str` | required |
| `justification` | `str` | required |

**Scenario** -- Conditional scenario produced by simulation.

| Field | Type | Default |
|-------|------|---------|
| `scenario_id` | `UUID` | auto `uuid4` |
| `name` | `str` | required |
| `description` | `str` | required |
| `assumptions` | `list[Assumption]` | required |
| `projected_outcome` | `dict[str, float]` | required |
| `confidence_interval` | `tuple[float, float]` | required |
| `probability` | `float` (0--1) | required |
| `risk_level` | `RiskLevel` | required |
| `sensitivity` | `dict[str, float]` | `{}` |
| `source_hypotheses` | `list[UUID]` | required |

**SimulationResult** -- Full output of the Simulation stage.

| Field | Type | Default |
|-------|------|---------|
| `scenarios` | `list[Scenario]` | required (min 2) |
| `baseline` | `Scenario \| None` | `None` |
| `stage` | `str` | `"simulation"` |

Model validator `at_least_two_scenarios` -- `scenarios` must contain at least 2 entries (`MIN_SCENARIOS = 2`).

### JSON Example

```json
{
  "scenarios": [
    {
      "scenario_id": "d4e5f6a7-0000-0000-0000-000000000004",
      "name": "Bull case",
      "description": "Continued supply tightening pushes prices up",
      "assumptions": [
        {
          "variable": "supply_growth_pct",
          "assumed_value": -2.5,
          "justification": "Drought forecast in Mato Grosso"
        }
      ],
      "projected_outcome": {
        "price_usd_per_ton": 470.0,
        "volume_change_pct": -5.0
      },
      "confidence_interval": [440.0, 500.0],
      "probability": 0.55,
      "risk_level": "medium",
      "sensitivity": {
        "supply_growth_pct": 0.82
      },
      "source_hypotheses": [
        "c3d4e5f6-0000-0000-0000-000000000003"
      ]
    },
    {
      "scenario_id": "d4e5f6a7-0000-0000-0000-000000000005",
      "name": "Bear case",
      "description": "Argentine harvest recovery increases global supply",
      "assumptions": [
        {
          "variable": "supply_growth_pct",
          "assumed_value": 4.0,
          "justification": "Normal rainfall expected in Pampas"
        }
      ],
      "projected_outcome": {
        "price_usd_per_ton": 390.0,
        "volume_change_pct": 8.0
      },
      "confidence_interval": [370.0, 410.0],
      "probability": 0.35,
      "risk_level": "low",
      "sensitivity": {
        "supply_growth_pct": 0.78
      },
      "source_hypotheses": [
        "c3d4e5f6-0000-0000-0000-000000000003"
      ]
    }
  ],
  "baseline": null,
  "stage": "simulation"
}
```

### Transition to Decision

```
len(scenarios) >= 2   (enforced by model_validator at construction time)
```

The pipeline does not add an extra gate here; the model validator on `SimulationResult` already guarantees the invariant.

---

## Stage 5: Decision

Produces actionable decision objects from scenario analysis.

### Models

**DecisionDriver** -- Factor influencing the decision.

| Field | Type | Default |
|-------|------|---------|
| `name` | `str` | required |
| `weight` | `float` (0--1) | required |
| `description` | `str` | required |

**CostOfError** -- Estimated cost of being wrong.

| Field | Type | Default |
|-------|------|---------|
| `false_positive` | `str` | required |
| `false_negative` | `str` | required |
| `estimated_magnitude` | `str \| None` | `None` |

**Condition** -- Activation condition for a decision.

| Field | Type | Default |
|-------|------|---------|
| `description` | `str` | required |
| `metric` | `str` | required |
| `operator` | `str` | required |
| `threshold` | `float` | required |
| `window` | `str` | required |

**DecisionObject** -- Structured decision object.

| Field | Type | Default |
|-------|------|---------|
| `decision_id` | `UUID` | auto `uuid4` |
| `decision_type` | `DecisionType` | required |
| `title` | `str` | required |
| `recommendation` | `str` | required |
| `conditions` | `list[Condition]` | `[]` |
| `drivers` | `list[DecisionDriver]` | required |
| `confidence` | `float` (0--1) | required |
| `risk_level` | `RiskLevel` | required |
| `cost_of_error` | `CostOfError` | required |
| `expires_at` | `datetime \| None` | `None` |
| `source_scenarios` | `list[UUID]` | required |
| `created_at` | `datetime` | auto `utcnow` |

**DecisionResult** -- Full output of the Decision stage.

| Field | Type | Default |
|-------|------|---------|
| `decisions` | `list[DecisionObject]` | required |
| `stage` | `str` | `"decision"` |

### JSON Example

```json
{
  "decisions": [
    {
      "decision_id": "e5f6a7b8-0000-0000-0000-000000000006",
      "decision_type": "recommendation",
      "title": "Consider forward-buying soy at current price",
      "recommendation": "Lock in 60% of Q3 volume at current spot price given bull-case probability of 55%",
      "conditions": [
        {
          "description": "Price stays below 440 USD/ton",
          "metric": "price_usd_per_ton",
          "operator": "<",
          "threshold": 440.0,
          "window": "7d"
        }
      ],
      "drivers": [
        {
          "name": "supply_tightening",
          "weight": 0.65,
          "description": "Drought forecast reducing Mato Grosso output"
        },
        {
          "name": "demand_stability",
          "weight": 0.35,
          "description": "Chinese import volumes remain steady"
        }
      ],
      "confidence": 0.68,
      "risk_level": "medium",
      "cost_of_error": {
        "false_positive": "Overpay by 5-8% if bear case materializes",
        "false_negative": "Miss 12% price increase window",
        "estimated_magnitude": "USD 120k on projected volume"
      },
      "expires_at": "2025-06-15T00:00:00Z",
      "source_scenarios": [
        "d4e5f6a7-0000-0000-0000-000000000004",
        "d4e5f6a7-0000-0000-0000-000000000005"
      ],
      "created_at": "2025-06-02T11:00:00Z"
    }
  ],
  "stage": "decision"
}
```

### Transition to Feedback

```
len(decisions) > 0
```

Raises `StageTransitionError("No decisions generated")` on failure.

---

## Stage 6: Feedback

Evaluates past decisions against observed reality and updates source reliability.

### Models

**PredictionVsReality** -- Comparison between projection and observed reality.

| Field | Type | Default |
|-------|------|---------|
| `metric` | `str` | required |
| `predicted` | `float` | required |
| `actual` | `float` | required |
| `error_pct` | `float` | required |
| `within_confidence` | `bool` | required |

**SourceDegradation** -- Record of source reliability degradation.

| Field | Type | Default |
|-------|------|---------|
| `source_id` | `str` | required |
| `previous_reliability` | `float` | required |
| `current_reliability` | `float` | required |
| `reason` | `str` | required |

**Scorecard** -- Feedback scorecard evaluating a past decision.

| Field | Type | Default |
|-------|------|---------|
| `scorecard_id` | `UUID` | auto `uuid4` |
| `decision_id` | `UUID` | required |
| `evaluated_at` | `datetime` | auto `utcnow` |
| `predictions_vs_reality` | `list[PredictionVsReality]` | required |
| `decision_outcome` | `str` | required |
| `source_degradations` | `list[SourceDegradation]` | `[]` |
| `model_adjustments` | `list[str]` | `[]` |
| `threshold_updates` | `dict[str, float]` | `{}` |
| `lessons_learned` | `str \| None` | `None` |

**FeedbackResult** -- Full output of the Feedback stage.

| Field | Type | Default |
|-------|------|---------|
| `scorecards` | `list[Scorecard]` | required |
| `sources_updated` | `int` | required |
| `thresholds_adjusted` | `int` | required |
| `accuracy_trend` | `list[float]` | `[]` |
| `stage` | `str` | `"feedback"` |

### JSON Example

```json
{
  "scorecards": [
    {
      "scorecard_id": "f6a7b8c9-0000-0000-0000-000000000007",
      "decision_id": "e5f6a7b8-0000-0000-0000-000000000006",
      "evaluated_at": "2025-07-01T10:00:00Z",
      "predictions_vs_reality": [
        {
          "metric": "price_usd_per_ton",
          "predicted": 470.0,
          "actual": 455.0,
          "error_pct": 3.19,
          "within_confidence": true
        }
      ],
      "decision_outcome": "Profitable. Forward purchase saved approx 8% vs spot at delivery.",
      "source_degradations": [
        {
          "source_id": "cepea-soy",
          "previous_reliability": 0.96,
          "current_reliability": 0.91,
          "reason": "Schema changed without version bump on 2025-06-15"
        }
      ],
      "model_adjustments": [
        "Increased weight of Argentine supply signal from 0.3 to 0.45"
      ],
      "threshold_updates": {
        "supply_growth_pct_sensitivity": 0.85
      },
      "lessons_learned": "Argentine harvest recovery was faster than assumed; incorporate satellite data earlier."
    }
  ],
  "sources_updated": 1,
  "thresholds_adjusted": 1,
  "stage": "feedback"
}
```

### Transition

Feedback is the terminal stage. No outbound transition gate. Its outputs feed back into Stage 1 (Observation) by updating source reliability scores and pipeline thresholds for the next run.

---

## Transition Summary

| From | To | Gate | Constant |
|------|----|------|----------|
| Observation | Compression | `quality_report.reliability_score >= 0.1` | `MIN_RELIABILITY_SCORE` |
| Compression | Hypothesis | `len(states) > 0` | -- |
| Hypothesis | Simulation | `len(hypotheses) > 0` | -- |
| Simulation | Decision | `len(scenarios) >= 2` | `MIN_SCENARIOS` (model validator) |
| Decision | Feedback | `len(decisions) > 0` | -- |
| Feedback | (loop) | -- | -- |

All transition checks can be disabled by setting `validate_transitions=False` on the pipeline.
Failures raise `StageTransitionError` (defined in `src/universal_gear/core/exceptions.py`).
