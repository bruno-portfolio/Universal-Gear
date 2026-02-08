# Universal Gear

*[Leia em Portugues](README.pt-BR.md)*

[![CI](https://github.com/bruno-portfolio/Universal-Gear/actions/workflows/ci.yml/badge.svg)](https://github.com/bruno-portfolio/Universal-Gear/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/universal-gear)](https://pypi.org/project/universal-gear/)
[![Python](https://img.shields.io/pypi/pyversions/universal-gear)](https://pypi.org/project/universal-gear/)
[![License](https://img.shields.io/github/license/bruno-portfolio/Universal-Gear)](LICENSE)

Every week you make decisions based on incomplete data.
Universal Gear structures that process -- so you can decide better, explain why, and learn from mistakes.

## What Does It Do?

Universal Gear runs a six-stage decision loop on real market data and returns structured, auditable results.

**Commodity trader** -- "Soy prices dropped three weeks in a row. Is it seasonal or a trend? Should I hedge?"
Run `ugear run agro` against live Brazilian agricultural data. The pipeline detects anomalies, simulates scenarios, and tells you whether the signal is worth acting on.

**Financial analyst** -- "USD/BRL spiked overnight. Noise or regime change?"
Run `ugear run finance` on Central Bank data. Same six stages, different domain -- observation, compression, hypothesis, simulation, decision, feedback.

**Anyone with recurring decisions** -- You do not need to be a trader. Any decision you make repeatedly under uncertainty (procurement, pricing, inventory) fits this loop. The framework forces you to show your work: what you observed, what you assumed, what you decided, and whether it worked.

## The Six Stages

Every pipeline follows the same loop:

```
  Observe --> Compress --> Hypothesize --> Simulate --> Decide --> Feedback
     ^                                                              |
     +--------------------------------------------------------------+
```

| Stage | What it answers |
|-------|-----------------|
| **Observe** | What is happening in the market right now? |
| **Compress** | What is the pattern over the last weeks? |
| **Hypothesize** | Is this normal or something unusual? |
| **Simulate** | If this continues, what could happen? |
| **Decide** | What should I do about it? |
| **Feedback** | Did my last decision work? |

No stage pretends to be perfect. Each one carries its limitations forward so you always know what you are working with.

## Install and Run

```bash
pip install universal-gear
ugear run toy          # try it now -- offline, no setup needed
ugear run agro         # real soy price data from Brazil
ugear run finance      # USD/BRL exchange rates from BCB
```

Output looks like this:

```
┌──────── Universal Gear - agro pipeline ───────┐
│ OK  Observation  90 events │ reliability: 0.93 │
│ OK  Compression  13 states │ weekly            │
│ OK  Hypothesis   1 hypotheses                  │
│ OK  Simulation   baseline + 10 scenarios       │
│ OK  Decision     9 decisions │ alert            │
│ OK  Feedback     9 scorecards │ hit_rate: 1.00  │
└────── SUCCESS - total: 0.0s ──────────────────┘
```

Every stage reports what it did and how long it took. If something fails, it fails loud -- no silent errors.

## Who Is This For

- **Commodity analysts and traders** -- Structured market intelligence for agricultural products, with real data from Brazilian sources.
- **Financial and macro analysts** -- Decision pipelines for exchange rates, interest rates, and macroeconomic indicators.
- **Business intelligence teams** -- Export results as JSON and import into Power BI, Tableau, or any BI tool.
- **Anyone who makes recurring decisions under uncertainty** -- Procurement, pricing, inventory, logistics -- any domain where you decide regularly with imperfect information.
- **Developers building custom decision pipelines** -- Swap any stage, add new data sources, or build an entirely new domain plugin.

## Export for BI Tools

Add `--json` to get structured output you can feed into dashboards and reports:

```bash
ugear run agro --json
```

The output is structured JSON that can be imported directly into Power BI, Tableau, Metabase, or any tool that consumes JSON data.

## Build Your Own Plugin

Universal Gear is domain-agnostic at its core. The `toy` and `agro` pipelines are plugins -- and you can build your own for any domain.

Register a custom collector, processor, analyzer, or any other stage with a single decorator:

```python
from universal_gear.core.registry import register_collector

@register_collector("my_source")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

Full guide: [docs/plugins.md](docs/plugins.md)

## Documentation

- [MANIFESTO.md](MANIFESTO.md) -- Design philosophy: why every stage acknowledges its limits
- [docs/quickstart.md](docs/quickstart.md) -- Getting started in five minutes
- [docs/architecture.md](docs/architecture.md) -- System architecture and contracts
- [docs/plugins.md](docs/plugins.md) -- Building custom plugins
- [docs/cli.md](docs/cli.md) -- Full CLI reference

## License

MIT -- built in Brazil, made for everywhere.
