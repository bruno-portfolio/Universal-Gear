# Universal Gear -- Quickstart

Universal Gear is a Python decision framework that transforms raw observations into actionable decisions through a six-stage pipeline. This guide gets you from zero to a running pipeline in under five minutes.

---

## Requirements

- Python 3.11 or later

---

## Installation

Install from PyPI:

```
pip install universal-gear
```

For local development (editable install):

```
pip install -e .
```

To include test and lint dependencies:

```
pip install -e ".[dev]"
```

To include the agricultural data plugin (requires `agrobr`):

```
pip install -e ".[agro]"
```

---

## Run the Toy Pipeline

The toy pipeline is fully offline and deterministic. It uses synthetic data and requires no external services or API keys.

```
ugear run toy
```

Expected output:

```
┌──────── Universal Gear - toy pipeline ────────┐
│ OK  Observation  90 events │ reliability: 0.93 │
│ OK  Compression  13 states │ weekly            │
│ OK  Hypothesis   1 hypotheses                  │
│ OK  Simulation   baseline + 10 scenarios       │
│ OK  Decision     9 decisions │ alert            │
│ OK  Feedback     9 scorecards │ hit_rate: 1.00  │
└────── SUCCESS - total: 0.0s ──────────────────┘
```

The six stages execute in order:

1. **Observation** -- Collects raw events from data sources.
2. **Compression** -- Normalizes and aggregates events into market states.
3. **Hypothesis** -- Generates testable hypotheses from compressed states.
4. **Simulation** -- Projects multiple scenarios from hypotheses.
5. **Decision** -- Produces actionable recommendations from scenario analysis.
6. **Feedback** -- Evaluates past decisions against reality and feeds learning back into the next cycle.

---

## Run the Agro Pipeline

The agro pipeline uses real Brazilian agricultural data via the `agrobr` library. Make sure the `agro` extra is installed before running it.

```
ugear run agro
```

---

## List Available Plugins

Inspect which plugins are registered in your environment:

```
ugear plugins list
```

---

## Use the Pipeline from Python

```python
from universal_gear import Pipeline

pipeline = Pipeline.from_config({
    "collector": {"plugin": "synthetic"},
    "processor": {"plugin": "aggregator"},
    "analyzer": {"plugin": "seasonal_anomaly"},
    "model": {"plugin": "conditional_scenario"},
    "action": {"plugin": "conditional_alert"},
    "monitor": {"plugin": "backtest"},
})

result = await pipeline.run()
```

Each stage passes its typed output to the next. The pipeline validates contracts between stages at runtime.

---

## Write a Custom Plugin

Every stage has a corresponding base class and registration decorator. To create a custom collector, for example:

```python
from universal_gear.core.interfaces import BaseCollector, CollectionResult
from universal_gear.core.registry import register_collector

@register_collector("my_source")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

The full set of decorators, one per stage:

| Decorator | Stage |
|---|---|
| `@register_collector` | Observation |
| `@register_processor` | Compression |
| `@register_analyzer` | Hypothesis |
| `@register_model` | Simulation |
| `@register_action` | Decision |
| `@register_monitor` | Feedback |

Or use the scaffold to generate a full plugin skeleton:

```
ugear new-plugin weather
ugear check-plugin weather
```

For a complete walkthrough, see [tutorial-first-plugin.md](tutorial-first-plugin.md).

---

## Use Without Code

Generate a guided spreadsheet template:

```
pip install universal-gear[sheets]
ugear template
```

This creates a structured xlsx with seven tabs following the six-stage loop. Fill in the green cells, track your decisions, and export to JSON when ready.

---

## Next Steps

- [architecture.md](architecture.md) -- Architectural decisions, component diagram, and data flow.
- [contracts.md](contracts.md) -- Full schema reference for every stage's input and output types.
- [plugins.md](plugins.md) -- Detailed guide to creating, registering, and distributing plugins.
- [tutorial-first-plugin.md](tutorial-first-plugin.md) -- Step-by-step: your first plugin.
- [cli.md](cli.md) -- Full CLI reference.
