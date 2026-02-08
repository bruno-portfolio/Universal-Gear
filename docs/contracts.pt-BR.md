# Contratos do Pipeline Universal Gear

*[Read in English](contracts.md)*

Fonte de verdade: `src/universal_gear/core/contracts.py`

Todos os modelos utilizam Pydantic v2 com `ConfigDict(frozen=True)` (imutáveis após a construção).
Campos com `Field(default_factory=uuid4)` ou `Field(default_factory=_utcnow)` são gerados automaticamente no momento da criação.

---

## Enums

| Enum | Valores |
|------|---------|
| `SourceType` | `api`, `file`, `scraper`, `manual`, `synthetic` |
| `Granularity` | `daily`, `weekly`, `monthly`, `quarterly` |
| `SourceReliability` | `high`, `medium`, `low`, `degraded` |
| `HypothesisStatus` | `pending`, `confirmed`, `rejected`, `expired` |
| `RiskLevel` | `low`, `medium`, `high`, `critical` |
| `DecisionType` | `alert`, `recommendation`, `trigger`, `report` |

Todos os enums são `StrEnum`, portanto são serializados como seu valor em string minúscula.

---

## Estágio 1: Observação

Coleta eventos brutos de fontes externas e produz um relatório de qualidade.

### Modelos

**SourceMeta** -- Metadados da fonte anexados a cada evento bruto.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `source_id` | `str` | obrigatório |
| `source_type` | `SourceType` | obrigatório |
| `url_or_path` | `str \| None` | `None` |
| `expected_schema_version` | `str \| None` | `None` |
| `reliability` | `SourceReliability` | `high` |

**QualityFlag** -- Flag individual de qualidade de dados.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `field_name` | `str` | obrigatório |
| `issue` | `str` | obrigatório |
| `severity` | `str` | obrigatório |
| `details` | `str \| None` | `None` |

**RawEvent** -- Evento bruto único coletado de uma fonte.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `event_id` | `UUID` | auto `uuid4` |
| `source` | `SourceMeta` | obrigatório |
| `timestamp` | `datetime` | obrigatório |
| `collected_at` | `datetime` | auto `utcnow` |
| `data` | `dict[str, Any]` | obrigatório |
| `schema_version` | `str \| None` | `None` |

**DataQualityReport** -- Relatório de qualidade produzido pelo estágio de observação.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `source` | `SourceMeta` | obrigatório |
| `collected_at` | `datetime` | auto `utcnow` |
| `total_records` | `int` | obrigatório |
| `valid_records` | `int` | obrigatório |
| `flags` | `list[QualityFlag]` | `[]` |
| `schema_match` | `bool` | `True` |
| `reliability_score` | `float` (0--1) | `1.0` |
| `notes` | `str \| None` | `None` |

A propriedade `valid_ratio` retorna `valid_records / total_records` (0.0 quando `total_records` é 0).

**CollectionResult** -- Saída completa do estágio de Observação.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `events` | `list[RawEvent]` | obrigatório |
| `quality_report` | `DataQualityReport` | obrigatório |
| `stage` | `str` | `"observation"` |

### Exemplo JSON

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

### Transição para Compressão

```
quality_report.reliability_score >= 0.1   (MIN_RELIABILITY_SCORE)
```

Levanta `StageTransitionError("Reliability score too low to proceed")` em caso de falha.

---

## Estágio 2: Compressão

Normaliza e agrega eventos brutos em snapshots de `MarketState`.

### Modelos

**SignalValue** -- Sinal normalizado único.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `name` | `str` | obrigatório |
| `value` | `float` | obrigatório |
| `unit` | `str` | obrigatório |
| `original_unit` | `str \| None` | `None` |
| `confidence` | `float` (0--1) | `1.0` |

**MarketState** -- Estado de mercado comprimido e normalizado para uma janela de tempo.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `state_id` | `UUID` | auto `uuid4` |
| `domain` | `str` | obrigatório |
| `period_start` | `datetime` | obrigatório |
| `period_end` | `datetime` | obrigatório |
| `granularity` | `Granularity` | obrigatório |
| `signals` | `list[SignalValue]` | obrigatório (mín. 1) |
| `lineage` | `list[UUID]` | obrigatório |
| `source_reliability` | `float` (0--1) | obrigatório |

Validador `at_least_one_signal` -- `signals` deve conter pelo menos uma entrada.

**CompressionResult** -- Saída completa do estágio de Compressão.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `states` | `list[MarketState]` | obrigatório |
| `records_consumed` | `int` | obrigatório |
| `records_produced` | `int` | obrigatório |
| `normalization_log` | `list[str]` | `[]` |
| `stage` | `str` | `"compression"` |

### Exemplo JSON

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

### Transição para Hipótese

```
len(states) > 0
```

Levanta `StageTransitionError("No MarketState produced")` em caso de falha.

---

## Estágio 3: Hipótese

Gera hipóteses testáveis a partir de estados de mercado comprimidos.

### Modelos

**ValidationCriterion** -- Critério utilizado para validar ou falsificar uma hipótese.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `metric` | `str` | obrigatório |
| `operator` | `str` | obrigatório |
| `threshold` | `float \| tuple[float, float]` | obrigatório |
| `description` | `str` | obrigatório |

**Hypothesis** -- Hipótese testável derivada de estados de mercado.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `hypothesis_id` | `UUID` | auto `uuid4` |
| `statement` | `str` | obrigatório |
| `rationale` | `str` | obrigatório |
| `status` | `HypothesisStatus` | `pending` |
| `confidence` | `float` (0--1) | obrigatório |
| `created_at` | `datetime` | auto `utcnow` |
| `valid_until` | `datetime` | obrigatório |
| `validation_criteria` | `list[ValidationCriterion]` | obrigatório (mín. 1) |
| `falsification_criteria` | `list[ValidationCriterion]` | obrigatório (mín. 1) |
| `competing_hypotheses` | `list[str]` | `[]` |
| `source_states` | `list[UUID]` | obrigatório |

Validadores:
- `needs_validation` -- `validation_criteria` deve conter pelo menos uma entrada.
- `needs_falsification` -- `falsification_criteria` deve conter pelo menos uma entrada.

**HypothesisResult** -- Saída completa do estágio de Hipótese.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `hypotheses` | `list[Hypothesis]` | obrigatório |
| `states_analyzed` | `int` | obrigatório |
| `stage` | `str` | `"hypothesis"` |

### Exemplo JSON

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

### Transição para Simulação

```
len(hypotheses) > 0
```

Levanta `StageTransitionError("No hypotheses generated")` em caso de falha.

---

## Estágio 4: Simulação

Projeta múltiplos cenários a partir de hipóteses, cada um com premissas e níveis de risco.

### Modelos

**Assumption** -- Premissa explícita que sustenta um cenário.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `variable` | `str` | obrigatório |
| `assumed_value` | `float \| str` | obrigatório |
| `justification` | `str` | obrigatório |

**Scenario** -- Cenário condicional produzido pela simulação.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `scenario_id` | `UUID` | auto `uuid4` |
| `name` | `str` | obrigatório |
| `description` | `str` | obrigatório |
| `assumptions` | `list[Assumption]` | obrigatório |
| `projected_outcome` | `dict[str, float]` | obrigatório |
| `confidence_interval` | `tuple[float, float]` | obrigatório |
| `probability` | `float` (0--1) | obrigatório |
| `risk_level` | `RiskLevel` | obrigatório |
| `sensitivity` | `dict[str, float]` | `{}` |
| `source_hypotheses` | `list[UUID]` | obrigatório |

**SimulationResult** -- Saída completa do estágio de Simulação.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `scenarios` | `list[Scenario]` | obrigatório (mín. 2) |
| `baseline` | `Scenario \| None` | `None` |
| `stage` | `str` | `"simulation"` |

Validador de modelo `at_least_two_scenarios` -- `scenarios` deve conter pelo menos 2 entradas (`MIN_SCENARIOS = 2`).

### Exemplo JSON

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

### Transição para Decisão

```
len(scenarios) >= 2   (enforced by model_validator at construction time)
```

O pipeline não adiciona uma verificação extra aqui; o validador de modelo em `SimulationResult` já garante a invariante.

---

## Estágio 5: Decisão

Produz objetos de decisão acionáveis a partir da análise de cenários.

### Modelos

**DecisionDriver** -- Fator que influencia a decisão.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `name` | `str` | obrigatório |
| `weight` | `float` (0--1) | obrigatório |
| `description` | `str` | obrigatório |

**CostOfError** -- Custo estimado de estar errado.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `false_positive` | `str` | obrigatório |
| `false_negative` | `str` | obrigatório |
| `estimated_magnitude` | `str \| None` | `None` |

**Condition** -- Condição de ativação para uma decisão.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `description` | `str` | obrigatório |
| `metric` | `str` | obrigatório |
| `operator` | `str` | obrigatório |
| `threshold` | `float` | obrigatório |
| `window` | `str` | obrigatório |

**DecisionObject** -- Objeto de decisão estruturado.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `decision_id` | `UUID` | auto `uuid4` |
| `decision_type` | `DecisionType` | obrigatório |
| `title` | `str` | obrigatório |
| `recommendation` | `str` | obrigatório |
| `conditions` | `list[Condition]` | `[]` |
| `drivers` | `list[DecisionDriver]` | obrigatório |
| `confidence` | `float` (0--1) | obrigatório |
| `risk_level` | `RiskLevel` | obrigatório |
| `cost_of_error` | `CostOfError` | obrigatório |
| `expires_at` | `datetime \| None` | `None` |
| `source_scenarios` | `list[UUID]` | obrigatório |
| `created_at` | `datetime` | auto `utcnow` |

**DecisionResult** -- Saída completa do estágio de Decisão.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `decisions` | `list[DecisionObject]` | obrigatório |
| `stage` | `str` | `"decision"` |

### Exemplo JSON

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

### Transição para Feedback

```
len(decisions) > 0
```

Levanta `StageTransitionError("No decisions generated")` em caso de falha.

---

## Estágio 6: Feedback

Avalia decisões passadas em relação à realidade observada e atualiza a confiabilidade das fontes.

### Modelos

**PredictionVsReality** -- Comparação entre projeção e realidade observada.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `metric` | `str` | obrigatório |
| `predicted` | `float` | obrigatório |
| `actual` | `float` | obrigatório |
| `error_pct` | `float` | obrigatório |
| `within_confidence` | `bool` | obrigatório |

**SourceDegradation** -- Registro de degradação da confiabilidade de uma fonte.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `source_id` | `str` | obrigatório |
| `previous_reliability` | `float` | obrigatório |
| `current_reliability` | `float` | obrigatório |
| `reason` | `str` | obrigatório |

**Scorecard** -- Scorecard de feedback avaliando uma decisão passada.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `scorecard_id` | `UUID` | auto `uuid4` |
| `decision_id` | `UUID` | obrigatório |
| `evaluated_at` | `datetime` | auto `utcnow` |
| `predictions_vs_reality` | `list[PredictionVsReality]` | obrigatório |
| `decision_outcome` | `str` | obrigatório |
| `source_degradations` | `list[SourceDegradation]` | `[]` |
| `model_adjustments` | `list[str]` | `[]` |
| `threshold_updates` | `dict[str, float]` | `{}` |
| `lessons_learned` | `str \| None` | `None` |

**FeedbackResult** -- Saída completa do estágio de Feedback.

| Campo | Tipo | Padrão |
|-------|------|--------|
| `scorecards` | `list[Scorecard]` | obrigatório |
| `sources_updated` | `int` | obrigatório |
| `thresholds_adjusted` | `int` | obrigatório |
| `stage` | `str` | `"feedback"` |

### Exemplo JSON

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

### Transição

Feedback é o estágio terminal. Não há verificação de transição de saída. Suas saídas retroalimentam o Estágio 1 (Observação) atualizando os scores de confiabilidade das fontes e os limiares do pipeline para a próxima execução.

---

## Resumo das Transições

| De | Para | Verificação | Constante |
|----|------|-------------|-----------|
| Observação | Compressão | `quality_report.reliability_score >= 0.1` | `MIN_RELIABILITY_SCORE` |
| Compressão | Hipótese | `len(states) > 0` | -- |
| Hipótese | Simulação | `len(hypotheses) > 0` | -- |
| Simulação | Decisão | `len(scenarios) >= 2` | `MIN_SCENARIOS` (validador de modelo) |
| Decisão | Feedback | `len(decisions) > 0` | -- |
| Feedback | (ciclo) | -- | -- |

Todas as verificações de transição podem ser desativadas configurando `validate_transitions=False` no pipeline.
Falhas levantam `StageTransitionError` (definido em `src/universal_gear/core/exceptions.py`).
