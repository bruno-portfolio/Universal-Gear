"""Abstract base classes for all six pipeline stages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from universal_gear.core.contracts import (
        CollectionResult,
        CompressionResult,
        DecisionResult,
        FeedbackResult,
        HypothesisResult,
        SimulationResult,
    )

ConfigT = TypeVar("ConfigT")


class BaseStage(ABC, Generic[ConfigT]):
    """Common base for every pipeline stage."""

    def __init__(self, config: ConfigT) -> None:
        self.config = config

    @property
    @abstractmethod
    def stage_name(self) -> str: ...


class BaseCollector(BaseStage[ConfigT]):
    """Observation stage — collects raw events from external sources."""

    @property
    def stage_name(self) -> str:
        return "observation"

    @abstractmethod
    async def collect(self) -> CollectionResult: ...


class BaseProcessor(BaseStage[ConfigT]):
    """Compression stage — normalises and aggregates raw events."""

    @property
    def stage_name(self) -> str:
        return "compression"

    @abstractmethod
    async def process(self, collection: CollectionResult) -> CompressionResult: ...


class BaseAnalyzer(BaseStage[ConfigT]):
    """Hypothesis stage — generates testable hypotheses from market states."""

    @property
    def stage_name(self) -> str:
        return "hypothesis"

    @abstractmethod
    async def analyze(self, compression: CompressionResult) -> HypothesisResult: ...


class BaseSimulator(BaseStage[ConfigT]):
    """Simulation stage — projects conditional scenarios."""

    @property
    def stage_name(self) -> str:
        return "simulation"

    @abstractmethod
    async def simulate(self, hypotheses: HypothesisResult) -> SimulationResult: ...


class BaseDecider(BaseStage[ConfigT]):
    """Decision stage — produces structured decision objects."""

    @property
    def stage_name(self) -> str:
        return "decision"

    @abstractmethod
    async def decide(self, simulation: SimulationResult) -> DecisionResult: ...


class BaseMonitor(BaseStage[ConfigT]):
    """Feedback stage — evaluates past decisions and tracks drift."""

    @property
    def stage_name(self) -> str:
        return "feedback"

    @abstractmethod
    async def evaluate(self, decision: DecisionResult) -> FeedbackResult: ...
