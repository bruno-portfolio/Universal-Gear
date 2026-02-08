# Use Cases -- Who is Universal Gear for?

Universal Gear is a decision framework, not a dashboard. It does not just show you data -- it tells you what the data means, what could happen next, and what you should consider doing about it. This guide shows how different professionals can use it today, without writing a single line of code.

---

## 1. The Commodity Analyst

**Scenario**: You track soy, corn, or coffee prices weekly and need to decide when to buy, sell, or hedge.

**Without Universal Gear**: You check the CEPEA website, copy numbers into Excel, eyeball the trend, and go with gut feeling. If someone asks why you made that call, you shrug.

**With Universal Gear**:

```bash
ugear run agro
```

The tool fetches real price data from CEPEA, compresses daily noise into weekly patterns, detects trends, projects scenarios, and produces concrete recommendations -- all in one command. Here is what the output looks like:

```
+-------- Universal Gear - agro pipeline --------+
| OK  Observation   12 events | reliability: 1.00 |
| OK  Compression   3 states | weekly             |
| OK  Hypothesis    1 hypotheses                   |
| OK  Simulation    baseline + 28 scenarios        |
| OK  Decision      6 decisions | alert            |
| OK  Feedback      6 scorecards | hit_rate: 1.00  |
+-------- SUCCESS - total: 2.1s -------------------+
```

What each line means:

- **12 events collected with 1.00 reliability** -- your data source is trustworthy. Universal Gear validated every record from CEPEA and none were corrupt or missing. A reliability score below 0.10 would halt the pipeline entirely.
- **3 weekly states** -- the tool compressed daily price noise into weekly patterns. Instead of staring at 12 individual data points, you now have 3 clean, comparable periods.
- **1 hypothesis** -- the system detected a falling price trend (or a seasonal deviation, depending on the data). This is a testable claim, not a guess -- it comes with validation and falsification criteria.
- **28 scenarios** -- it projected what could happen next by combining exchange rate assumptions (BRL/USD), harvest yield estimates, and export premium levels. Each scenario has a probability, a confidence interval, and a risk level.
- **6 decisions** -- concrete recommendations with risk levels. For example: "Scenario projects price at 142.50 BRL (+8.2% vs baseline). Consider forward selling or price fixation for soja." Each decision includes the cost of being wrong in both directions.
- **6 scorecards** -- last time, the system got it right 100% of the time. The feedback stage evaluates past decisions against actual outcomes and adjusts the pipeline's assumptions for the next run.

**For your BI dashboard**: Export the full result as structured JSON for import into Excel, Power BI, or any other tool:

```bash
ugear run agro --output json > agro_decisions.json
```

---

## 2. The Financial / Macro Analyst

**Scenario**: You monitor USD/BRL, SELIC, inflation, and commodity-linked assets. You need to flag risks to your team before the Monday meeting.

**Without Universal Gear**: You check the Central Bank website, scan Bloomberg, manually build a slide deck, and hope you did not miss a signal buried in the noise.

**With Universal Gear**:

```bash
ugear run finance
```

The `finance` pipeline applies the same six-stage logic to macroeconomic data:

- **Observation** -- Collects exchange rates, interest rate decisions, and inflation indices from official sources.
- **Compression** -- Normalizes heterogeneous indicators into comparable time windows.
- **Hypothesis** -- Detects anomalies such as "USD/BRL moved 2.3 standard deviations above its 30-day mean" and frames them as testable claims.
- **Simulation** -- Projects scenarios by combining rate paths, inflation assumptions, and fiscal policy variables. Each scenario gets a probability and a risk level.
- **Decision** -- Emits alerts like "Consider hedging USD exposure" or "SELIC path suggests duration risk in fixed-income portfolio," each with a confidence score and a cost-of-error estimate.
- **Feedback** -- Evaluates whether last week's alerts were correct, updates source reliability, and tunes scenario weights for the next cycle.

The output format is identical to the agro pipeline. The same Rich panel, the same six stages, the same JSON export. If you already know how to read agro output, you know how to read finance output.

> **Note**: The `finance` pipeline is fully implemented with data from BCB (Brazilian Central Bank). Run `ugear run finance` to try it.

---

## 3. The Business Intelligence Analyst

**Scenario**: You build dashboards in Power BI or Tableau. Your boss asks "so what does this data mean?" and you realize your dashboard shows **what happened** but not **what to do about it**.

**The problem**: Traditional BI tools are descriptive. They visualize historical data. They do not generate hypotheses, project scenarios, or recommend actions. That reasoning layer is usually done ad hoc in someone's head -- undocumented and unreproducible.

**With Universal Gear**: Universal Gear is the reasoning layer between your data source and your dashboard. It takes raw observations, runs them through a structured analytical pipeline, and outputs machine-readable decisions that your dashboard can display alongside the raw metrics.

Here is a practical workflow:

```bash
# Run the pipeline and export structured JSON
ugear run agro --output json > decisions.json

# Import decisions.json into Power BI as a data source
```

The JSON output contains every stage's result: raw events, compressed states, hypotheses with confidence scores, simulated scenarios with probabilities, and decisions with risk levels and cost-of-error estimates. Your dashboard can now show:

- A trend chart (from the compression stage)
- Active hypotheses and their confidence levels (from the hypothesis stage)
- A scenario comparison table with probabilities (from the simulation stage)
- Recommended actions with risk indicators (from the decision stage)
- A historical accuracy tracker (from the feedback stage)

**Scheduled execution**: Run Universal Gear as a cron job or scheduled task. Each run produces a fresh JSON file. Point your dashboard at the output directory, and it refreshes automatically with new hypotheses and recommendations every cycle.

```bash
# Example: run every Monday at 7:00 AM
0 7 * * 1  ugear run agro --output json > /data/agro_latest.json
```

The full JSON schema for every stage is documented in [contracts.md](contracts.md).

---

## 4. The Developer / Data Engineer

**Scenario**: You want to build a custom decision pipeline for your domain -- logistics, energy pricing, inventory management, or anything else where structured reasoning over noisy data would help.

**Universal Gear gives you**: A typed, validated, six-stage pipeline with contracts between every stage. You implement the domain logic; the framework handles orchestration, validation, observability, and feedback.

The plugin system follows a simple pattern. Here is a collector in five lines:

```python
from universal_gear.core.interfaces import BaseCollector, CollectionResult
from universal_gear.core.registry import register_collector

@register_collector("my_domain")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

Every stage has the same structure: a base class, a registration decorator, a typed input, and a typed output. The six decorators are `register_collector`, `register_processor`, `register_analyzer`, `register_model`, `register_action`, and `register_monitor`.

External plugins can be distributed as standalone Python packages using standard entry points -- no changes to Universal Gear required.

For a complete walkthrough, see [plugins.md](plugins.md). For the data contracts between stages, see [contracts.md](contracts.md). For installation and first run, see [quickstart.md](quickstart.md).

---

## 5. The Non-Programmer

**Scenario**: You make recurring decisions at work -- purchasing supplies, setting prices, choosing vendors -- but you don't write code. You want a structured way to think through decisions instead of going with gut feeling.

**With Universal Gear**: Generate a spreadsheet template and follow the seven tabs:

```bash
pip install universal-gear[sheets]
ugear template
```

This creates `ugear-decisao.xlsx`. Open it in Excel or Google Sheets. Each tab is one step of the decision process, with instructions at the top and a pre-filled example (buying coffee for an office). Fill in the green cells with your own data.

When you complete a full cycle -- from observation through feedback -- you have a documented, structured decision record. Over time, the DASHBOARD tab shows your track record: how many decisions you got right, your average error, and what you learned.

No programming, no APIs, no terminal. Just a spreadsheet and a method.

---

## 6. Future: The Healthcare Analyst

**Scenario**: You work in epidemiological monitoring or hospital capacity planning. You need to detect outbreaks early, project bed occupancy, and recommend resource allocation -- based on data, not intuition.

**How it would work**: The Universal Gear pipeline is domain-agnostic. The same six stages that analyze soy prices can analyze epidemiological data:

- **Observation** -- A `saude` collector fetches notification data from DATASUS or state health department APIs.
- **Compression** -- Normalizes case counts by epidemiological week and region, adjusting for reporting delays.
- **Hypothesis** -- Detects anomalies: "Dengue notifications in Minas Gerais are 2.8 standard deviations above the 5-year seasonal mean."
- **Simulation** -- Projects scenarios: "If the current trajectory holds, hospital capacity in Belo Horizonte reaches 90% within 3 weeks."
- **Decision** -- Emits alerts: "Consider activating contingency beds in the metropolitan region. Confidence: 0.74. Risk level: high."
- **Feedback** -- Evaluates whether last cycle's outbreak alerts materialized, updates the baseline, and adjusts detection thresholds.

**This plugin does not exist yet** -- but the architecture is ready for it. The contracts, validation gates, and feedback loop are all in place. A `saude` plugin would need to implement six classes (one per stage) following the same pattern as the existing `agro` plugin.

Want to build it? Start with [plugins.md](plugins.md).

---

## Quick Reference

| Persona | Command | What you get |
|---|---|---|
| Commodity Analyst | `ugear run agro` | Price trend hypotheses, forward-selling recommendations, risk alerts |
| Financial Analyst | `ugear run finance` | Exchange rate and rate-path scenarios, hedging alerts |
| BI Analyst | `ugear run agro --output json` | Structured JSON for dashboard integration |
| Non-Programmer | `ugear template` | Guided spreadsheet for structured decisions without code |
| Developer | `pip install -e ".[dev]"` | Full plugin SDK, typed contracts, test harness |
| Healthcare Analyst | `ugear run saude` | Outbreak detection, capacity projections (future) |

---

## Next Steps

- [quickstart.md](quickstart.md) -- Install Universal Gear and run your first pipeline in under five minutes.
- [cli.md](cli.md) -- Full CLI reference for all commands and options.
- [architecture.md](architecture.md) -- How the six-stage pipeline works under the hood.
- [contracts.md](contracts.md) -- Complete schema reference for every stage's input and output.
- [plugins.md](plugins.md) -- Build and distribute your own domain plugin.
