# Creating Custom Plugins for Universal Gear

Universal Gear is built around a modular plugin architecture that makes it straightforward to extend every stage of the pipeline with custom logic. This guide covers how the plugin system works, the base classes you need to implement, and how to register and distribute your plugins.

---

## 1. How the Plugin System Works

Universal Gear uses a **Strategy Pattern + Entry Points** approach:

- Each stage of the pipeline (collector, processor, analyzer, model, action, monitor) is defined by an **abstract base class** that establishes the contract for that stage.
- **Built-in plugins** register themselves via decorators provided by the framework.
- **External plugins** (distributed as separate packages) register via Python **entry points**, allowing Universal Gear to discover them automatically at runtime without any manual wiring.

This design means you can swap, combine, or extend pipeline stages without modifying the core framework.

---

## 2. Base Classes

All base classes live in `universal_gear.core.interfaces`. Each one is generic over a configuration type `ConfigT` (typically a Pydantic model) and defines a single async method that the pipeline calls:

| Base Class | Method Signature |
|---|---|
| `BaseCollector[ConfigT]` | `async def collect(self) -> CollectionResult` |
| `BaseProcessor[ConfigT]` | `async def process(self, collection: CollectionResult) -> CompressionResult` |
| `BaseAnalyzer[ConfigT]` | `async def analyze(self, compression: CompressionResult) -> HypothesisResult` |
| `BaseSimulator[ConfigT]` | `async def simulate(self, hypothesis: HypothesisResult) -> SimulationResult` |
| `BaseDecider[ConfigT]` | `async def decide(self, simulation: SimulationResult) -> DecisionResult` |
| `BaseMonitor[ConfigT]` | `async def evaluate(self, decision: DecisionResult) -> FeedbackResult` |

Every base class inherits from `BaseStage`, which accepts a `config: ConfigT` argument in its `__init__`. This config object is stored as `self.config` and is available throughout the plugin's lifecycle.

```python
from universal_gear.core.interfaces import BaseCollector, CollectionResult

class MyCollector(BaseCollector[MyConfig]):
    # self.config is automatically set by BaseStage.__init__
    async def collect(self) -> CollectionResult:
        ...
```

---

## 3. Registration via Decorator

For plugins that live inside the Universal Gear codebase (or in your application code), the simplest registration method is a decorator. Decorators are available from `universal_gear.core.registry`:

```python
from universal_gear.core.registry import register_collector
from universal_gear.core.interfaces import BaseCollector, CollectionResult

@register_collector("my_source")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

The string argument (`"my_source"`) is the **plugin name** used to reference this implementation in pipeline configurations.

### Available Decorators

| Decorator | Registers a... |
|---|---|
| `register_collector` | Collector plugin |
| `register_processor` | Processor plugin |
| `register_analyzer` | Analyzer plugin |
| `register_model` | Simulator / model plugin |
| `register_action` | Decider / action emitter plugin |
| `register_monitor` | Monitor plugin |

---

## 4. Registration via Entry Points (External Packages)

When you distribute a plugin as a standalone Python package, you register it through **entry points** in your package's `pyproject.toml`. Universal Gear scans specific entry point groups at startup and loads any plugins it finds.

```toml
[project.entry-points."universal_gear.collectors"]
my_source = "my_package.collector:MyCollector"

[project.entry-points."universal_gear.processors"]
my_processor = "my_package.processor:MyProcessor"

[project.entry-points."universal_gear.analyzers"]
my_analyzer = "my_package.analyzer:MyAnalyzer"

[project.entry-points."universal_gear.models"]
my_model = "my_package.model:MySimulator"

[project.entry-points."universal_gear.actions"]
my_action = "my_package.action:MyDecider"

[project.entry-points."universal_gear.monitors"]
my_monitor = "my_package.monitor:MyMonitor"
```

Once the external package is installed in the same environment as Universal Gear, the plugins become available automatically -- no code changes to Universal Gear are needed.

---

## 5. Minimal Plugin Template

Below is a complete, minimal example of a custom collector plugin, from configuration to pipeline usage.

### Define the Configuration

```python
# my_plugin/config.py
from pydantic import BaseModel

class RandomSourceConfig(BaseModel):
    """Configuration for the random data source collector."""
    num_points: int = 100
    seed: int | None = None
```

### Implement the Collector

```python
# my_plugin/collector.py
import random
from datetime import datetime, timezone

from universal_gear.core.interfaces import BaseCollector, CollectionResult
from universal_gear.core.registry import register_collector
from my_plugin.config import RandomSourceConfig


@register_collector("random_source")
class RandomSourceCollector(BaseCollector[RandomSourceConfig]):
    """Collects randomly generated numerical data points."""

    async def collect(self) -> CollectionResult:
        if self.config.seed is not None:
            random.seed(self.config.seed)

        data_points = [random.gauss(0, 1) for _ in range(self.config.num_points)]

        return CollectionResult(
            source="random_source",
            timestamp=datetime.now(timezone.utc),
            data=data_points,
            metadata={"num_points": self.config.num_points, "seed": self.config.seed},
        )
```

### Use in a Pipeline

```python
# main.py
from universal_gear.core.pipeline import Pipeline

pipeline = Pipeline.from_config({
    "collector": {
        "plugin": "random_source",
        "config": {
            "num_points": 500,
            "seed": 42,
        },
    },
    "processor": {"plugin": "aggregator"},
    "analyzer": {"plugin": "seasonal_anomaly"},
    "model": {"plugin": "conditional_scenario"},
    "action": {"plugin": "conditional_alert"},
    "monitor": {"plugin": "backtest"},
})

result = await pipeline.run()
```

---

## 6. Existing Plugins

### Built-in (Toy / Demo)

These plugins ship with Universal Gear and are intended for testing, demos, and as reference implementations:

| Stage | Plugin Name | Class |
|---|---|---|
| Collector | `synthetic` | `SyntheticCollector` |
| Processor | `aggregator` | `AggregatorProcessor` |
| Analyzer | `seasonal_anomaly` | `SeasonalAnomalyDetector` |
| Simulator | `conditional_scenario` | `ConditionalScenarioEngine` |
| Action | `conditional_alert` | `ConditionalAlertEmitter` |
| Monitor | `backtest` | `BacktestMonitor` |

### Agro Plugin

The Agro plugin package provides a complete pipeline tailored for agricultural data analysis:

| Stage | Plugin Name | Class |
|---|---|---|
| Collector | `agrobr` | `AgrobrCollector` |
| Processor | `agro` | `AgroProcessor` |
| Analyzer | `agro` | `AgroAnalyzer` |
| Simulator | `agro_scenario` | `AgroScenarioEngine` |
| Action | `agro_action` | `AgroActionEmitter` |
| Monitor | `agro_monitor` | `AgroMonitor` |

---

## 7. Listing Registered Plugins

Universal Gear provides a CLI command to inspect which plugins are currently registered and available in your environment.

List all registered plugins across every stage:

```
ugear plugins
```

List registered plugins for a specific stage:

```
ugear plugins collector
ugear plugins processor
ugear plugins analyzer
ugear plugins model
ugear plugins action
ugear plugins monitor
```

This is useful for verifying that an external plugin package was installed correctly and that Universal Gear can discover it.
