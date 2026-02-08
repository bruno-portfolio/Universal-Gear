# Criando Plugins Personalizados para o Universal Gear

*[Read in English](plugins.md)*

O Universal Gear é construído em torno de uma arquitetura modular de plugins que torna simples estender cada estágio do pipeline com lógica personalizada. Este guia aborda como o sistema de plugins funciona, as classes base que você precisa implementar e como registrar e distribuir seus plugins.

---

## 1. Como o Sistema de Plugins Funciona

O Universal Gear utiliza uma abordagem de **Strategy Pattern + Entry Points**:

- Cada estágio do pipeline (collector, processor, analyzer, model, action, monitor) é definido por uma **classe base abstrata** que estabelece o contrato para aquele estágio.
- **Plugins integrados** se registram por meio de decorators fornecidos pelo framework.
- **Plugins externos** (distribuídos como pacotes separados) se registram via **entry points** do Python, permitindo que o Universal Gear os descubra automaticamente em tempo de execução sem qualquer configuração manual.

Esse design significa que você pode trocar, combinar ou estender estágios do pipeline sem modificar o núcleo do framework.

---

## 2. Classes Base

Todas as classes base residem em `universal_gear.core.interfaces`. Cada uma é genérica sobre um tipo de configuração `ConfigT` (tipicamente um modelo Pydantic) e define um único método assíncrono que o pipeline invoca:

| Classe Base | Assinatura do Método |
|---|---|
| `BaseCollector[ConfigT]` | `async def collect(self) -> CollectionResult` |
| `BaseProcessor[ConfigT]` | `async def process(self, collection: CollectionResult) -> CompressionResult` |
| `BaseAnalyzer[ConfigT]` | `async def analyze(self, compression: CompressionResult) -> HypothesisResult` |
| `BaseSimulator[ConfigT]` | `async def simulate(self, hypothesis: HypothesisResult) -> SimulationResult` |
| `BaseDecider[ConfigT]` | `async def decide(self, simulation: SimulationResult) -> DecisionResult` |
| `BaseMonitor[ConfigT]` | `async def evaluate(self, decision: DecisionResult) -> FeedbackResult` |

Toda classe base herda de `BaseStage`, que aceita um argumento `config: ConfigT` em seu `__init__`. Esse objeto de configuração é armazenado como `self.config` e fica disponível durante todo o ciclo de vida do plugin.

```python
from universal_gear.core.interfaces import BaseCollector, CollectionResult

class MyCollector(BaseCollector[MyConfig]):
    # self.config is automatically set by BaseStage.__init__
    async def collect(self) -> CollectionResult:
        ...
```

---

## 3. Registro via Decorator

Para plugins que residem dentro do código-fonte do Universal Gear (ou no código da sua aplicação), o método de registro mais simples é um decorator. Os decorators estão disponíveis em `universal_gear.core.registry`:

```python
from universal_gear.core.registry import register_collector
from universal_gear.core.interfaces import BaseCollector, CollectionResult

@register_collector("my_source")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

O argumento de string (`"my_source"`) é o **nome do plugin** usado para referenciar essa implementação nas configurações do pipeline.

### Decorators Disponíveis

| Decorator | Registra um... |
|---|---|
| `register_collector` | Plugin de coleta (Collector) |
| `register_processor` | Plugin de processamento (Processor) |
| `register_analyzer` | Plugin de análise (Analyzer) |
| `register_model` | Plugin de simulação / modelo (Simulator) |
| `register_action` | Plugin de decisão / emissor de ações (Decider) |
| `register_monitor` | Plugin de monitoramento (Monitor) |

---

## 4. Registro via Entry Points (Pacotes Externos)

Quando você distribui um plugin como um pacote Python independente, o registro é feito por meio de **entry points** no `pyproject.toml` do seu pacote. O Universal Gear escaneia grupos de entry points específicos na inicialização e carrega todos os plugins que encontrar.

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

Uma vez que o pacote externo esteja instalado no mesmo ambiente do Universal Gear, os plugins ficam disponíveis automaticamente -- nenhuma alteração de código no Universal Gear é necessária.

---

## 5. Template Mínimo de Plugin

Abaixo está um exemplo completo e mínimo de um plugin de coleta personalizado, desde a configuração até o uso no pipeline.

### Defina a Configuração

```python
# my_plugin/config.py
from pydantic import BaseModel

class RandomSourceConfig(BaseModel):
    """Configuration for the random data source collector."""
    num_points: int = 100
    seed: int | None = None
```

### Implemente o Collector

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

### Use no Pipeline

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

## 6. Plugins Existentes

### Integrados (Demonstração / Teste)

Estes plugins acompanham o Universal Gear e são destinados a testes, demonstrações e como implementações de referência:

| Estágio | Nome do Plugin | Classe |
|---|---|---|
| Collector | `synthetic` | `SyntheticCollector` |
| Processor | `aggregator` | `AggregatorProcessor` |
| Analyzer | `seasonal_anomaly` | `SeasonalAnomalyDetector` |
| Simulator | `conditional_scenario` | `ConditionalScenarioEngine` |
| Action | `conditional_alert` | `ConditionalAlertEmitter` |
| Monitor | `backtest` | `BacktestMonitor` |

### Plugin Agro

O pacote de plugins Agro fornece um pipeline completo voltado para análise de dados agrícolas:

| Estágio | Nome do Plugin | Classe |
|---|---|---|
| Collector | `agrobr` | `AgrobrCollector` |
| Processor | `agro` | `AgroProcessor` |
| Analyzer | `agro` | `AgroAnalyzer` |
| Simulator | `agro_scenario` | `AgroScenarioEngine` |
| Action | `agro_action` | `AgroActionEmitter` |
| Monitor | `agro_monitor` | `AgroMonitor` |

### Plugin Finance

O plugin Finance conecta-se ao Banco Central do Brasil (BCB) para dados macroeconômicos:

| Estágio | Nome do Plugin | Classe |
|---|---|---|
| Collector | `bcb` | `BCBCollector` |
| Processor | `finance` | `FinanceProcessor` |
| Analyzer | `finance` | `FinanceAnalyzer` |
| Simulator | `finance_scenario` | `FinanceScenarioEngine` |
| Action | `finance_action` | `FinanceActionEmitter` |
| Monitor | `finance_monitor` | `FinanceMonitor` |

---

## 7. Gerando a Estrutura de um Novo Plugin

A maneira mais rápida de criar um novo plugin é com o scaffold da CLI:

```
ugear new-plugin energy
```

Isso gera nove arquivos seguindo todas as convenções do projeto: configuração, seis implementações de estágio e um esqueleto de testes. Após preencher os TODOs, valide com:

```
ugear check-plugin energy
```

Para um passo a passo detalhado, consulte [tutorial-first-plugin.md](tutorial-first-plugin.md).

---

## 8. Listando Plugins Registrados

O Universal Gear disponibiliza um comando CLI para inspecionar quais plugins estão registrados e disponíveis no seu ambiente.

Listar todos os plugins registrados em todos os estágios:

```
ugear plugins
```

Listar plugins registrados para um estágio específico:

```
ugear plugins collector
ugear plugins processor
ugear plugins analyzer
ugear plugins model
ugear plugins action
ugear plugins monitor
```

Isso é útil para verificar se um pacote de plugin externo foi instalado corretamente e se o Universal Gear consegue encontrá-lo.
