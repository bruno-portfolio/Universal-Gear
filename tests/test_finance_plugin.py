"""Unit tests for finance plugin stages: config, analyzer, model, action, monitor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from universal_gear.core.contracts import (
    Assumption,
    CompressionResult,
    Condition,
    CostOfError,
    DecisionDriver,
    DecisionObject,
    DecisionType,
    Granularity,
    Hypothesis,
    HypothesisResult,
    HypothesisStatus,
    MarketState,
    PredictionVsReality,
    RiskLevel,
    Scenario,
    SignalValue,
    SimulationResult,
    ValidationCriterion,
)
from universal_gear.plugins.finance.action import (
    EXCHANGE_ALERT_THRESHOLD_PCT,
    MIN_PROBABILITY,
    FinanceActionEmitter,
)
from universal_gear.plugins.finance.analyzer import (
    MIN_STATES_FOR_ANALYSIS,
    FinanceAnalyzer,
)
from universal_gear.plugins.finance.config import (
    INDICATOR_UNITS,
    SGS_SERIES,
    FinanceConfig,
)
from universal_gear.plugins.finance.model import (
    FinanceModelConfig,
    FinanceScenarioEngine,
)
from universal_gear.plugins.finance.monitor import FinanceMonitor

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_state(
    value: float,
    signal_name: str = "exchange_rate",
    week_offset: int = 0,
    unit: str = "BRL/USD",
) -> MarketState:
    """Build a MarketState with a single signal."""
    base = NOW
    return MarketState(
        domain="finance",
        period_start=base + timedelta(weeks=week_offset),
        period_end=base + timedelta(weeks=week_offset + 1),
        granularity=Granularity.WEEKLY,
        signals=[SignalValue(name=signal_name, value=value, unit=unit)],
        lineage=[uuid4()],
        source_reliability=0.95,
    )


def _make_compression(
    values: list[float],
    signal_name: str = "exchange_rate",
) -> CompressionResult:
    """Build a CompressionResult from a list of values."""
    states = [
        _make_state(v, signal_name=signal_name, week_offset=i)
        for i, v in enumerate(values)
    ]
    return CompressionResult(
        states=states,
        records_consumed=len(values) * 7,
        records_produced=len(values),
    )


def _make_hypothesis() -> Hypothesis:
    """Build a minimal valid Hypothesis."""
    return Hypothesis(
        statement="Test hypothesis",
        rationale="For testing",
        status=HypothesisStatus.PENDING,
        confidence=0.7,
        valid_until=NOW + timedelta(days=30),
        validation_criteria=[
            ValidationCriterion(
                metric="exchange_rate_zscore",
                operator="gt",
                threshold=2.0,
                description="Exchange rate deviation persists",
            ),
        ],
        falsification_criteria=[
            ValidationCriterion(
                metric="exchange_rate_zscore",
                operator="between",
                threshold=(-1.0, 1.0),
                description="Rate returns within 1 std dev",
            ),
        ],
        source_states=[uuid4()],
    )


def _make_hypothesis_result(n: int = 1) -> HypothesisResult:
    """Build a HypothesisResult with n hypotheses."""
    return HypothesisResult(
        hypotheses=[_make_hypothesis() for _ in range(n)],
        states_analyzed=4,
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestFinanceConfig:
    @pytest.mark.offline
    def test_default_indicators(self):
        cfg = FinanceConfig()
        assert cfg.indicators == ["usd_brl"]

    @pytest.mark.offline
    def test_default_currency(self):
        cfg = FinanceConfig()
        assert cfg.base_currency == "BRL"

    @pytest.mark.offline
    def test_default_granularity(self):
        cfg = FinanceConfig()
        assert cfg.granularity == "weekly"

    @pytest.mark.offline
    def test_sgs_series_known(self):
        assert "selic" in SGS_SERIES
        assert "ipca" in SGS_SERIES

    @pytest.mark.offline
    def test_indicator_units_known(self):
        assert INDICATOR_UNITS["usd_brl"] == "BRL/USD"
        assert INDICATOR_UNITS["selic"] == "% p.a."
        assert INDICATOR_UNITS["ipca"] == "% m/m"


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class TestFinanceAnalyzer:
    def _make_analyzer(self, **kwargs) -> FinanceAnalyzer:
        return FinanceAnalyzer(config=FinanceConfig(**kwargs))

    @pytest.mark.offline
    async def test_returns_empty_when_insufficient_data(self):
        analyzer = self._make_analyzer()
        compression = _make_compression([5.5, 5.6])
        assert len(compression.states) < MIN_STATES_FOR_ANALYSIS

        result = await analyzer.analyze(compression)
        assert result.hypotheses == []

    @pytest.mark.offline
    async def test_returns_empty_when_std_zero(self):
        analyzer = self._make_analyzer()
        compression = _make_compression([5.5, 5.5, 5.5, 5.5, 5.5])

        result = await analyzer.analyze(compression)
        anomaly = [h for h in result.hypotheses if "std dev" in h.statement.lower()]
        assert anomaly == []

    @pytest.mark.offline
    async def test_detects_exchange_anomaly_above(self):
        analyzer = self._make_analyzer()
        # Small variance in history, then a big spike
        values = [5.50, 5.52, 5.48, 5.51, 7.0]
        compression = _make_compression(values)

        result = await analyzer.analyze(compression)
        anomalies = [h for h in result.hypotheses if "above" in h.statement]
        assert len(anomalies) == 1
        assert "USD/BRL" in anomalies[0].statement

    @pytest.mark.offline
    async def test_detects_rising_trend(self):
        analyzer = self._make_analyzer()
        values = [5.0, 5.1, 5.2, 5.3, 5.4]
        compression = _make_compression(values)

        result = await analyzer.analyze(compression)
        trend = [h for h in result.hypotheses if "rising" in h.statement.lower()]
        assert len(trend) >= 1

    @pytest.mark.offline
    async def test_detects_falling_trend(self):
        analyzer = self._make_analyzer()
        values = [5.5, 5.5, 5.4, 5.3, 5.2]
        compression = _make_compression(values)

        result = await analyzer.analyze(compression)
        trend = [h for h in result.hypotheses if "falling" in h.statement.lower()]
        assert len(trend) >= 1

    @pytest.mark.offline
    async def test_detects_volatility_spike(self):
        analyzer = self._make_analyzer()
        # Stable then a sudden big jump
        values = [5.50, 5.51, 5.50, 5.52, 5.51, 6.20]
        compression = _make_compression(values)

        result = await analyzer.analyze(compression)
        vol = [h for h in result.hypotheses if "volatility" in h.statement.lower()]
        assert len(vol) == 1


# ---------------------------------------------------------------------------
# Model (Scenario Engine)
# ---------------------------------------------------------------------------


class TestFinanceScenarioEngine:
    def _make_engine(self, **kwargs) -> FinanceScenarioEngine:
        return FinanceScenarioEngine(config=FinanceModelConfig(**kwargs))

    @pytest.mark.offline
    def test_model_config_defaults(self):
        cfg = FinanceModelConfig()
        assert cfg.exchange_scenarios == [5.0, 5.5, 6.0, 6.5]
        assert cfg.selic_scenarios == [12.25, 13.25, 14.25]
        assert cfg.baseline_exchange == 5.75
        assert cfg.baseline_selic == 13.25

    @pytest.mark.offline
    async def test_generates_12_scenarios_plus_baseline(self):
        engine = self._make_engine()
        hr = _make_hypothesis_result(1)

        result = await engine.simulate(hr)

        # 4 exchange x 3 selic = 12 + 1 baseline = 13
        assert len(result.scenarios) == 13
        assert result.baseline is not None
        assert result.baseline.name == "baseline (status quo)"

    @pytest.mark.offline
    async def test_baseline_uses_configured_values(self):
        engine = self._make_engine()
        hr = _make_hypothesis_result(1)

        result = await engine.simulate(hr)
        baseline = result.baseline

        assumptions = {a.variable: a.assumed_value for a in baseline.assumptions}
        assert assumptions["exchange_rate"] == pytest.approx(5.75)
        assert assumptions["selic_rate"] == pytest.approx(13.25)

    @pytest.mark.offline
    def test_cost_index_at_baseline(self):
        engine = self._make_engine()
        idx = engine._cost_index(5.75, 13.25)
        assert idx == pytest.approx(1.0)

    @pytest.mark.offline
    def test_cost_index_fx_impact(self):
        engine = self._make_engine(baseline_exchange=5.0)
        # 10% fx increase => cost_index = 1 + 0.1*0.6 = 1.06
        idx = engine._cost_index(5.5, engine.config.baseline_selic)
        assert idx == pytest.approx(1.06)

    @pytest.mark.offline
    def test_assess_risk_critical(self):
        engine = self._make_engine(baseline_exchange=5.0)
        # 20% deviation
        assert engine._assess_risk(6.0) == RiskLevel.CRITICAL

    @pytest.mark.offline
    def test_assess_risk_high(self):
        engine = self._make_engine(baseline_exchange=5.0)
        # ~12% deviation
        assert engine._assess_risk(5.6) == RiskLevel.HIGH

    @pytest.mark.offline
    def test_assess_risk_medium(self):
        engine = self._make_engine(baseline_exchange=5.0)
        # ~8% deviation
        assert engine._assess_risk(5.4) == RiskLevel.MEDIUM

    @pytest.mark.offline
    def test_assess_risk_low(self):
        engine = self._make_engine(baseline_exchange=5.0)
        # ~2% deviation
        assert engine._assess_risk(5.1) == RiskLevel.LOW

    @pytest.mark.offline
    def test_accepts_finance_config_as_fallback(self):
        engine = FinanceScenarioEngine(config=FinanceConfig())
        assert engine.config.baseline_exchange == 5.75


# ---------------------------------------------------------------------------
# Action (Decision Emitter)
# ---------------------------------------------------------------------------


class TestFinanceActionEmitter:
    def _make_emitter(self, **kwargs) -> FinanceActionEmitter:
        return FinanceActionEmitter(config=FinanceConfig(**kwargs))

    def _make_simulation(
        self,
        baseline_rate: float,
        scenario_rates: list[tuple[str, float, float, RiskLevel]],
    ) -> SimulationResult:
        """Build a SimulationResult with a baseline and extra scenarios.

        scenario_rates: list of (name, exchange_rate, probability, risk_level).
        """
        source_ids = [uuid4()]
        baseline = Scenario(
            name="baseline (status quo)",
            description="Baseline",
            assumptions=[
                Assumption(
                    variable="exchange_rate",
                    assumed_value=baseline_rate,
                    justification="Current",
                ),
            ],
            projected_outcome={
                "exchange_rate": baseline_rate,
                "selic_rate": 13.25,
                "cost_index": 1.0,
            },
            confidence_interval=(baseline_rate * 0.92, baseline_rate * 1.08),
            probability=0.5,
            risk_level=RiskLevel.MEDIUM,
            sensitivity={"exchange_rate": 0.6, "selic_rate": 0.4},
            source_hypotheses=source_ids,
        )

        scenarios = [baseline]
        for name, rate, prob, risk in scenario_rates:
            cost_index = 1.0 + (rate - baseline_rate) / baseline_rate * 0.6
            scenarios.append(
                Scenario(
                    name=name,
                    description=f"Scenario {name}",
                    assumptions=[
                        Assumption(
                            variable="exchange_rate",
                            assumed_value=rate,
                            justification="Test",
                        ),
                    ],
                    projected_outcome={
                        "exchange_rate": rate,
                        "selic_rate": 13.25,
                        "cost_index": round(cost_index, 4),
                    },
                    confidence_interval=(rate * 0.92, rate * 1.08),
                    probability=prob,
                    risk_level=risk,
                    sensitivity={"exchange_rate": 0.6},
                    source_hypotheses=source_ids,
                )
            )

        return SimulationResult(scenarios=scenarios, baseline=baseline)

    @pytest.mark.offline
    async def test_filter_usd_strengthens(self):
        emitter = self._make_emitter()
        sim = self._make_simulation(
            baseline_rate=5.75,
            scenario_rates=[
                ("big-up", 6.5, 0.4, RiskLevel.HIGH),
                ("small-up", 5.85, 0.4, RiskLevel.LOW),
            ],
        )

        upside = emitter._filter_usd_strengthens(sim)
        assert len(upside) == 1
        assert upside[0].name == "big-up"

    @pytest.mark.offline
    async def test_filter_usd_weakens(self):
        emitter = self._make_emitter()
        sim = self._make_simulation(
            baseline_rate=5.75,
            scenario_rates=[
                ("big-down", 5.0, 0.4, RiskLevel.HIGH),
                ("small-down", 5.6, 0.4, RiskLevel.MEDIUM),
                ("low-risk-down", 5.0, 0.4, RiskLevel.LOW),
            ],
        )

        downside = emitter._filter_usd_weakens(sim)
        assert len(downside) == 1
        assert downside[0].name == "big-down"

    @pytest.mark.offline
    async def test_build_hold_when_no_signals(self):
        emitter = self._make_emitter()
        sim = self._make_simulation(
            baseline_rate=5.75,
            scenario_rates=[
                ("flat-a", 5.80, 0.4, RiskLevel.LOW),
                ("flat-b", 5.70, 0.4, RiskLevel.LOW),
            ],
        )

        result = await emitter.decide(sim)
        assert len(result.decisions) == 1
        dec = result.decisions[0]
        assert dec.decision_type == DecisionType.REPORT
        assert "No actionable" in dec.title

    @pytest.mark.offline
    def test_exchange_alert_threshold_constant(self):
        assert EXCHANGE_ALERT_THRESHOLD_PCT == 5.0

    @pytest.mark.offline
    def test_min_probability_constant(self):
        assert MIN_PROBABILITY == 0.3


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class TestFinanceMonitor:
    def _make_monitor(self, **kwargs) -> FinanceMonitor:
        return FinanceMonitor(config=FinanceConfig(**kwargs))

    def _make_decision_object(
        self, *, conditions: list[Condition] | None = None,
    ) -> DecisionObject:
        source_id = uuid4()
        return DecisionObject(
            decision_type=DecisionType.ALERT,
            title="Test alert",
            recommendation="Test recommendation",
            conditions=conditions if conditions is not None else [
                Condition(
                    description="Exchange rate deviation",
                    metric="exchange_rate_deviation_pct",
                    operator="gt",
                    threshold=5.0,
                    window="14 days",
                ),
            ],
            drivers=[
                DecisionDriver(
                    name="exchange_rate",
                    weight=0.6,
                    description="exchange_rate = 5.75",
                ),
            ],
            confidence=0.6,
            risk_level=RiskLevel.HIGH,
            cost_of_error=CostOfError(
                false_positive="Unnecessary hedge",
                false_negative="Unhedged FX loss",
            ),
            source_scenarios=[source_id],
        )

    @pytest.mark.offline
    def test_evaluate_decision_produces_scorecard(self):
        monitor = self._make_monitor()
        dec = self._make_decision_object()

        scorecard = monitor._evaluate_decision(dec)

        assert scorecard.decision_id == dec.decision_id
        assert len(scorecard.predictions_vs_reality) > 0
        assert scorecard.predictions_vs_reality[0].metric == "exchange_rate_deviation_pct"

    @pytest.mark.offline
    def test_evaluate_decision_without_conditions_uses_confidence(self):
        monitor = self._make_monitor()
        dec = self._make_decision_object(conditions=[])

        scorecard = monitor._evaluate_decision(dec)

        assert scorecard.predictions_vs_reality[0].metric == "confidence"

    @pytest.mark.offline
    def test_assess_outcome_beneficial(self):
        monitor = self._make_monitor()
        predictions = [
            PredictionVsReality(
                metric="m1", predicted=5.0, actual=5.1, error_pct=2.0,
                within_confidence=True,
            ),
            PredictionVsReality(
                metric="m2", predicted=10.0, actual=9.8, error_pct=2.0,
                within_confidence=True,
            ),
        ]
        assert monitor._assess_outcome(predictions) == "beneficial"

    @pytest.mark.offline
    def test_assess_outcome_detrimental(self):
        monitor = self._make_monitor()
        predictions = [
            PredictionVsReality(
                metric="m1", predicted=5.0, actual=8.0, error_pct=60.0,
                within_confidence=False,
            ),
            PredictionVsReality(
                metric="m2", predicted=10.0, actual=3.0, error_pct=70.0,
                within_confidence=False,
            ),
        ]
        assert monitor._assess_outcome(predictions) == "detrimental"

    @pytest.mark.offline
    def test_assess_outcome_neutral(self):
        monitor = self._make_monitor()
        predictions = [
            PredictionVsReality(
                metric="m1", predicted=5.0, actual=5.1, error_pct=2.0,
                within_confidence=True,
            ),
            PredictionVsReality(
                metric="m2", predicted=10.0, actual=3.0, error_pct=70.0,
                within_confidence=False,
            ),
        ]
        assert monitor._assess_outcome(predictions) == "neutral"

    @pytest.mark.offline
    def test_assess_outcome_empty_predictions(self):
        monitor = self._make_monitor()
        assert monitor._assess_outcome([]) == "neutral"
