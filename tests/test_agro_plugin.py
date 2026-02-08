"""Unit tests for agro plugin stages: config, analyzer, model, action, monitor."""

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
from universal_gear.plugins.agro.action import (
    MARGIN_ALERT_THRESHOLD_PCT,
    MIN_PROBABILITY,
    AgroActionEmitter,
)
from universal_gear.plugins.agro.analyzer import (
    MIN_STATES_FOR_ANALYSIS,
    AgroAnalyzer,
)
from universal_gear.plugins.agro.config import (
    COMMODITY_CANONICAL_UNIT,
    COMMODITY_UNITS,
    SACA_60KG_TO_TON,
    AgroConfig,
)
from universal_gear.plugins.agro.model import (
    AgroModelConfig,
    AgroScenarioEngine,
)
from universal_gear.plugins.agro.monitor import (
    AgroMonitor,
)

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


def _make_state(
    price: float,
    week_offset: int = 0,
    domain: str = "agro",
) -> MarketState:
    """Build a MarketState with a single price signal."""
    base = NOW
    return MarketState(
        domain=domain,
        period_start=base + timedelta(weeks=week_offset),
        period_end=base + timedelta(weeks=week_offset + 1),
        granularity=Granularity.WEEKLY,
        signals=[SignalValue(name="price", value=price, unit="BRL/sc60kg")],
        lineage=[uuid4()],
        source_reliability=0.9,
    )


def _make_compression(prices: list[float]) -> CompressionResult:
    """Build a CompressionResult from a list of prices."""
    states = [_make_state(p, week_offset=i) for i, p in enumerate(prices)]
    return CompressionResult(
        states=states,
        records_consumed=len(prices) * 7,
        records_produced=len(prices),
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
                metric="price_deviation_std",
                operator="gt",
                threshold=1.5,
                description="Price deviation persists",
            ),
        ],
        falsification_criteria=[
            ValidationCriterion(
                metric="price_deviation_std",
                operator="between",
                threshold=(-1.0, 1.0),
                description="Price returns within 1 std dev",
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


class TestAgroConfig:
    @pytest.mark.offline()
    def test_default_commodity(self):
        cfg = AgroConfig()
        assert cfg.commodity == "soja"

    @pytest.mark.offline()
    def test_default_currency(self):
        cfg = AgroConfig()
        assert cfg.currency == "BRL"

    @pytest.mark.offline()
    def test_default_region_is_none(self):
        cfg = AgroConfig()
        assert cfg.region is None

    @pytest.mark.offline()
    def test_saca_60kg_to_ton_constant(self):
        expected = 1000 / 60
        assert pytest.approx(expected) == SACA_60KG_TO_TON

    @pytest.mark.offline()
    def test_commodity_units_soja(self):
        assert COMMODITY_UNITS["soja"] == "BRL/sc60kg"

    @pytest.mark.offline()
    def test_commodity_canonical_unit_soja(self):
        assert COMMODITY_CANONICAL_UNIT["soja"] == "BRL/ton"

    @pytest.mark.offline()
    def test_commodity_units_all_present(self):
        for key in COMMODITY_CANONICAL_UNIT:
            assert key in COMMODITY_UNITS


class TestAgroAnalyzer:
    def _make_analyzer(self, **kwargs) -> AgroAnalyzer:
        return AgroAnalyzer(config=AgroConfig(**kwargs))

    @pytest.mark.offline()
    async def test_returns_null_hypothesis_when_insufficient_data(self):
        """With fewer than MIN_STATES, analyze returns only a null hypothesis."""
        analyzer = self._make_analyzer()
        compression = _make_compression([100.0, 101.0])
        assert len(compression.states) < MIN_STATES_FOR_ANALYSIS

        result = await analyzer.analyze(compression)
        assert len(result.hypotheses) == 1
        assert "within normal range" in result.hypotheses[0].statement

    @pytest.mark.offline()
    async def test_returns_empty_when_std_zero(self):
        """All identical prices produce std==0, so no seasonal deviation is flagged."""
        analyzer = self._make_analyzer()
        compression = _make_compression([100.0, 100.0, 100.0, 100.0, 100.0])

        result = await analyzer.analyze(compression)
        seasonal = [h for h in result.hypotheses if "std dev" in h.statement.lower()]
        assert seasonal == []

    @pytest.mark.offline()
    async def test_check_seasonal_price_detects_high_deviation(self):
        """A large spike in the last price should exceed SEASONAL_DEVIATION_THRESHOLD."""
        analyzer = self._make_analyzer()
        prices = [100.0, 102.0, 98.0, 101.0, 200.0]
        compression = _make_compression(prices)

        result = await analyzer.analyze(compression)
        seasonal = [h for h in result.hypotheses if "above" in h.statement]
        assert len(seasonal) == 1
        assert "above seasonal mean" in seasonal[0].statement

    @pytest.mark.offline()
    async def test_check_price_trend_rising(self):
        """Consistently rising prices over last 3 periods should be detected."""
        analyzer = self._make_analyzer()
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        compression = _make_compression(prices)

        result = await analyzer.analyze(compression)
        trend = [h for h in result.hypotheses if "rising" in h.statement.lower()]
        assert len(trend) == 1

    @pytest.mark.offline()
    async def test_check_price_trend_falling(self):
        """Consistently falling prices over last 3 periods should be detected."""
        analyzer = self._make_analyzer()
        prices = [100.0, 100.0, 99.0, 98.0, 97.0]
        compression = _make_compression(prices)

        result = await analyzer.analyze(compression)
        trend = [h for h in result.hypotheses if "falling" in h.statement.lower()]
        assert len(trend) == 1


class TestAgroScenarioEngine:
    def _make_engine(self, **kwargs) -> AgroScenarioEngine:
        return AgroScenarioEngine(config=AgroModelConfig(**kwargs))

    @pytest.mark.offline()
    def test_model_config_defaults(self):
        cfg = AgroModelConfig()
        assert cfg.exchange_rates == [5.0, 5.5, 6.0]
        assert cfg.harvest_multipliers == [0.85, 1.0, 1.15]
        assert cfg.export_premium_pct == [0.0, 3.0, 6.0]
        assert cfg.base_price_brl == 130.0

    @pytest.mark.offline()
    async def test_generates_27_scenarios_plus_baseline(self):
        engine = self._make_engine()
        hr = _make_hypothesis_result(1)

        result = await engine.simulate(hr)

        assert len(result.scenarios) == 28
        assert result.baseline is not None
        assert result.baseline.name == "baseline (status quo)"

    @pytest.mark.offline()
    async def test_baseline_uses_median_values(self):
        engine = self._make_engine()
        hr = _make_hypothesis_result(1)

        result = await engine.simulate(hr)
        baseline = result.baseline

        assumptions = {a.variable: a.assumed_value for a in baseline.assumptions}
        assert assumptions["exchange_rate"] == pytest.approx(5.5)
        assert assumptions["harvest_multiplier"] == pytest.approx(1.0)
        assert assumptions["export_premium_pct"] == pytest.approx(3.0)

    @pytest.mark.offline()
    def test_project_price_linear_combination(self):
        engine = self._make_engine(base_price_brl=100.0)
        price_base = engine._project_price(5.5, 1.0, 0.0)
        assert price_base == pytest.approx(100.0)

        price_high_fx = engine._project_price(6.0, 1.0, 0.0)
        expected = 100.0 * (1 + (6.0 - 5.5) / 5.5 * 0.5)
        assert price_high_fx == pytest.approx(expected)

        price_weak_harvest = engine._project_price(5.5, 0.85, 0.0)
        expected_wh = 100.0 * (1 + 0.06)
        assert price_weak_harvest == pytest.approx(expected_wh)

        price_premium = engine._project_price(5.5, 1.0, 6.0)
        expected_prem = 100.0 * (1 + 0.06)
        assert price_premium == pytest.approx(expected_prem)

    @pytest.mark.offline()
    def test_assess_risk_critical(self):
        engine = self._make_engine(base_price_brl=100.0)
        assert engine._assess_risk(151.0) == RiskLevel.CRITICAL
        assert engine._assess_risk(49.0) == RiskLevel.CRITICAL

    @pytest.mark.offline()
    def test_assess_risk_high(self):
        engine = self._make_engine(base_price_brl=100.0)
        assert engine._assess_risk(135.0) == RiskLevel.HIGH
        assert engine._assess_risk(65.0) == RiskLevel.HIGH

    @pytest.mark.offline()
    def test_assess_risk_medium(self):
        engine = self._make_engine(base_price_brl=100.0)
        assert engine._assess_risk(120.0) == RiskLevel.MEDIUM
        assert engine._assess_risk(80.0) == RiskLevel.MEDIUM

    @pytest.mark.offline()
    def test_assess_risk_low(self):
        engine = self._make_engine(base_price_brl=100.0)
        assert engine._assess_risk(110.0) == RiskLevel.LOW
        assert engine._assess_risk(90.0) == RiskLevel.LOW

    @pytest.mark.offline()
    def test_accepts_agro_config_as_fallback(self):
        """When constructed with AgroConfig, engine internally uses AgroModelConfig defaults."""
        engine = AgroScenarioEngine(config=AgroConfig())
        assert engine.config.base_price_brl == 130.0


class TestAgroActionEmitter:
    def _make_emitter(self, **kwargs) -> AgroActionEmitter:
        return AgroActionEmitter(config=AgroConfig(**kwargs))

    def _make_simulation(
        self,
        baseline_price: float,
        scenario_prices: list[tuple[str, float, float, RiskLevel]],
    ) -> SimulationResult:
        """Build a SimulationResult with a baseline and extra scenarios.

        scenario_prices: list of (name, price, probability, risk_level).
        """
        source_ids = [uuid4()]
        baseline = Scenario(
            name="baseline (status quo)",
            description="Baseline",
            assumptions=[
                Assumption(variable="exchange_rate", assumed_value=5.5, justification="Mid"),
            ],
            projected_outcome={"price_brl": baseline_price},
            confidence_interval=(baseline_price * 0.88, baseline_price * 1.12),
            probability=0.5,
            risk_level=RiskLevel.MEDIUM,
            sensitivity={"exchange_rate": 0.5},
            source_hypotheses=source_ids,
        )

        scenarios = [baseline]
        for name, price, prob, risk in scenario_prices:
            scenarios.append(
                Scenario(
                    name=name,
                    description=f"Scenario {name}",
                    assumptions=[
                        Assumption(
                            variable="exchange_rate",
                            assumed_value=5.5,
                            justification="Test",
                        ),
                    ],
                    projected_outcome={"price_brl": price},
                    confidence_interval=(price * 0.88, price * 1.12),
                    probability=prob,
                    risk_level=risk,
                    sensitivity={"exchange_rate": 0.5},
                    source_hypotheses=source_ids,
                )
            )

        return SimulationResult(scenarios=scenarios, baseline=baseline)

    @pytest.mark.offline()
    async def test_filter_upside_selects_above_threshold(self):
        emitter = self._make_emitter()
        sim = self._make_simulation(
            baseline_price=100.0,
            scenario_prices=[
                ("big-up", 110.0, 0.4, RiskLevel.LOW),
                ("small-up", 103.0, 0.4, RiskLevel.LOW),
            ],
        )

        upside = emitter._filter_upside(sim)
        assert len(upside) == 1
        assert upside[0].name == "big-up"

    @pytest.mark.offline()
    async def test_filter_downside_selects_below_threshold_with_risk(self):
        emitter = self._make_emitter()
        sim = self._make_simulation(
            baseline_price=100.0,
            scenario_prices=[
                ("big-down", 88.0, 0.4, RiskLevel.HIGH),
                ("small-down", 97.0, 0.4, RiskLevel.HIGH),
                ("low-risk-down", 88.0, 0.4, RiskLevel.LOW),
            ],
        )

        downside = emitter._filter_downside(sim)
        assert len(downside) == 1
        assert downside[0].name == "big-down"

    @pytest.mark.offline()
    async def test_build_hold_recommendation_when_no_signals(self):
        emitter = self._make_emitter()
        sim = self._make_simulation(
            baseline_price=100.0,
            scenario_prices=[
                ("flat-a", 101.0, 0.4, RiskLevel.LOW),
                ("flat-b", 99.0, 0.4, RiskLevel.LOW),
            ],
        )

        result = await emitter.decide(sim)
        assert len(result.decisions) == 1
        dec = result.decisions[0]
        assert dec.decision_type == DecisionType.REPORT
        assert "No actionable signal" in dec.title

    @pytest.mark.offline()
    def test_margin_alert_threshold_constant(self):
        assert MARGIN_ALERT_THRESHOLD_PCT == 5.0

    @pytest.mark.offline()
    def test_min_probability_constant(self):
        assert MIN_PROBABILITY == 0.3


class TestAgroMonitor:
    def _make_monitor(self, **kwargs) -> AgroMonitor:
        return AgroMonitor(config=AgroConfig(**kwargs))

    def _make_decision_object(
        self,
        *,
        conditions: list[Condition] | None = None,
    ) -> DecisionObject:
        source_id = uuid4()
        return DecisionObject(
            decision_type=DecisionType.ALERT,
            title="Test alert",
            recommendation="Test recommendation",
            conditions=conditions
            if conditions is not None
            else [
                Condition(
                    description="Test condition",
                    metric="spread_pct",
                    operator="lt",
                    threshold=-5.0,
                    window="7 days",
                ),
            ],
            drivers=[
                DecisionDriver(
                    name="exchange_rate",
                    weight=0.5,
                    description="exchange_rate = 5.5",
                ),
            ],
            confidence=0.6,
            risk_level=RiskLevel.HIGH,
            cost_of_error=CostOfError(
                false_positive="Unnecessary hedge",
                false_negative="Unhedged loss",
            ),
            source_scenarios=[source_id],
        )

    @pytest.mark.offline()
    def test_evaluate_decision_produces_scorecard(self):
        monitor = self._make_monitor()
        dec = self._make_decision_object()

        scorecard = monitor._evaluate_decision(dec)

        assert scorecard.decision_id == dec.decision_id
        assert len(scorecard.predictions_vs_reality) > 0
        assert scorecard.predictions_vs_reality[0].metric == "spread_pct"

    @pytest.mark.offline()
    def test_evaluate_decision_without_conditions_uses_confidence(self):
        monitor = self._make_monitor()
        dec = self._make_decision_object(conditions=[])

        scorecard = monitor._evaluate_decision(dec)

        assert scorecard.predictions_vs_reality[0].metric == "confidence"

    @pytest.mark.offline()
    def test_assess_outcome_beneficial(self):
        monitor = self._make_monitor()
        predictions = [
            PredictionVsReality(
                metric="m1",
                predicted=5.0,
                actual=5.1,
                error_pct=2.0,
                within_confidence=True,
            ),
            PredictionVsReality(
                metric="m2",
                predicted=10.0,
                actual=9.8,
                error_pct=2.0,
                within_confidence=True,
            ),
        ]
        assert monitor._assess_outcome(predictions) == "beneficial"

    @pytest.mark.offline()
    def test_assess_outcome_detrimental(self):
        monitor = self._make_monitor()
        predictions = [
            PredictionVsReality(
                metric="m1",
                predicted=5.0,
                actual=8.0,
                error_pct=60.0,
                within_confidence=False,
            ),
            PredictionVsReality(
                metric="m2",
                predicted=10.0,
                actual=3.0,
                error_pct=70.0,
                within_confidence=False,
            ),
        ]
        assert monitor._assess_outcome(predictions) == "detrimental"

    @pytest.mark.offline()
    def test_assess_outcome_neutral(self):
        monitor = self._make_monitor()
        predictions = [
            PredictionVsReality(
                metric="m1",
                predicted=5.0,
                actual=5.1,
                error_pct=2.0,
                within_confidence=True,
            ),
            PredictionVsReality(
                metric="m2",
                predicted=10.0,
                actual=3.0,
                error_pct=70.0,
                within_confidence=False,
            ),
        ]
        assert monitor._assess_outcome(predictions) == "neutral"

    @pytest.mark.offline()
    def test_assess_outcome_empty_predictions(self):
        monitor = self._make_monitor()
        assert monitor._assess_outcome([]) == "neutral"


# ---------------------------------------------------------------------------
# Cross-cutting: 5 coherence improvements
# ---------------------------------------------------------------------------


class TestAgroCoherenceImprovements:
    """Tests for context, probability_method, aggregation_methods, priority, accuracy_trend."""

    @pytest.mark.offline()
    async def test_analyzer_populates_context(self):
        analyzer = AgroAnalyzer(config=AgroConfig())
        compression = _make_compression([100.0, 102.0, 98.0, 101.0, 99.0])
        result = await analyzer.analyze(compression)

        assert "price" in result.context
        assert result.context["price"] == pytest.approx(99.0)

    @pytest.mark.offline()
    async def test_model_anchors_baseline_from_context(self):
        engine = AgroScenarioEngine(config=AgroModelConfig())
        hr = HypothesisResult(
            hypotheses=[_make_hypothesis()],
            states_analyzed=4,
            context={"price": 142.50},
        )

        await engine.simulate(hr)
        assert engine.config.base_price_brl == pytest.approx(142.50)

    @pytest.mark.offline()
    async def test_model_uses_default_baseline_without_context(self):
        engine = AgroScenarioEngine(config=AgroModelConfig())
        hr = _make_hypothesis_result(1)

        await engine.simulate(hr)
        assert engine.config.base_price_brl == pytest.approx(130.0)

    @pytest.mark.offline()
    async def test_scenarios_have_probability_method(self):
        engine = AgroScenarioEngine(config=AgroModelConfig())
        hr = _make_hypothesis_result(1)

        result = await engine.simulate(hr)

        for scenario in result.scenarios:
            assert scenario.probability_method in (
                "inverse_distance_to_baseline",
                "fixed_baseline",
            )
        assert result.baseline.probability_method == "fixed_baseline"

    @pytest.mark.offline()
    async def test_decisions_have_priority_and_sorted(self):
        emitter = AgroActionEmitter(config=AgroConfig())
        source_ids = [uuid4()]
        baseline = Scenario(
            name="baseline (status quo)",
            description="Baseline",
            assumptions=[
                Assumption(
                    variable="exchange_rate",
                    assumed_value=5.5,
                    justification="Mid",
                ),
            ],
            projected_outcome={"price_brl": 130.0},
            confidence_interval=(114.4, 145.6),
            probability=0.5,
            risk_level=RiskLevel.MEDIUM,
            sensitivity={"exchange_rate": 0.5},
            source_hypotheses=source_ids,
        )
        high_risk = Scenario(
            name="big-up",
            description="Big up",
            assumptions=[
                Assumption(
                    variable="exchange_rate",
                    assumed_value=6.0,
                    justification="Test",
                ),
            ],
            projected_outcome={"price_brl": 160.0},
            confidence_interval=(140.8, 179.2),
            probability=0.5,
            risk_level=RiskLevel.HIGH,
            sensitivity={"exchange_rate": 0.5},
            source_hypotheses=source_ids,
        )
        low_risk = Scenario(
            name="small-up",
            description="Small up",
            assumptions=[
                Assumption(
                    variable="exchange_rate",
                    assumed_value=5.8,
                    justification="Test",
                ),
            ],
            projected_outcome={"price_brl": 140.0},
            confidence_interval=(123.2, 156.8),
            probability=0.5,
            risk_level=RiskLevel.MEDIUM,
            sensitivity={"exchange_rate": 0.5},
            source_hypotheses=source_ids,
        )
        sim = SimulationResult(
            scenarios=[baseline, high_risk, low_risk],
            baseline=baseline,
        )

        result = await emitter.decide(sim)
        for dec in result.decisions:
            assert dec.priority >= 0
        priorities = [d.priority for d in result.decisions]
        assert priorities == sorted(priorities, reverse=True)

    @pytest.mark.offline()
    def test_monitor_accuracy_trend(self):
        monitor = AgroMonitor(config=AgroConfig())

        dec = DecisionObject(
            decision_type=DecisionType.ALERT,
            title="Test",
            recommendation="Test",
            conditions=[
                Condition(
                    description="Test",
                    metric="m1",
                    operator="gt",
                    threshold=5.0,
                    window="7 days",
                ),
            ],
            drivers=[
                DecisionDriver(
                    name="x",
                    weight=0.5,
                    description="x",
                ),
            ],
            confidence=0.6,
            risk_level=RiskLevel.HIGH,
            cost_of_error=CostOfError(
                false_positive="fp",
                false_negative="fn",
            ),
            source_scenarios=[uuid4()],
        )

        sc = monitor._evaluate_decision(dec)
        trend = monitor._compute_accuracy_trend([sc])
        assert len(trend) == 1
        assert 0.0 <= trend[0] <= 1.0
