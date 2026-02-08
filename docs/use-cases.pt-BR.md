# Casos de Uso -- Para quem é o Universal Gear?

*[Read in English](use-cases.md)*

O Universal Gear é um framework de decisão, não um painel de controle. Ele não apenas mostra dados -- ele diz o que os dados significam, o que pode acontecer em seguida e o que você deveria considerar fazer a respeito. Este guia mostra como diferentes profissionais podem usá-lo hoje, sem escrever uma única linha de código.

---

## 1. O Analista de Commodities

**Cenário**: Você acompanha preços de soja, milho ou café semanalmente e precisa decidir quando comprar, vender ou fazer hedge.

**Sem o Universal Gear**: Você consulta o site da CEPEA, copia os números para o Excel, observa a tendência a olho nu e segue a intuição. Se alguém pergunta por que você tomou aquela decisão, você dá de ombros.

**Com o Universal Gear**:

```bash
ugear run agro
```

A ferramenta busca dados reais de preços da CEPEA, comprime o ruído diário em padrões semanais, detecta tendências, projeta cenários e produz recomendações concretas -- tudo em um único comando. Veja como é a saída:

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

O que cada linha significa:

- **12 eventos coletados com confiabilidade 1.00** -- sua fonte de dados é confiável. O Universal Gear validou cada registro da CEPEA e nenhum estava corrompido ou ausente. Uma pontuação de confiabilidade abaixo de 0.10 interromperia o pipeline inteiramente.
- **3 estados semanais** -- a ferramenta comprimiu o ruído diário de preços em padrões semanais. Em vez de ficar olhando para 12 pontos de dados individuais, você agora tem 3 períodos limpos e comparáveis.
- **1 hipótese** -- o sistema detectou uma tendência de queda nos preços (ou um desvio sazonal, dependendo dos dados). Esta é uma afirmação testável, não um palpite -- ela vem com critérios de validação e de falsificação.
- **28 cenários** -- o sistema projetou o que pode acontecer em seguida, combinando premissas de taxa de câmbio (BRL/USD), estimativas de produtividade da safra e níveis de prêmio de exportação. Cada cenário tem uma probabilidade, um intervalo de confiança e um nível de risco.
- **6 decisões** -- recomendações concretas com níveis de risco. Por exemplo: "Scenario projects price at 142.50 BRL (+8.2% vs baseline). Consider forward selling or price fixation for soja." Cada decisão inclui o custo de estar errado nas duas direções.
- **6 scorecards** -- na última vez, o sistema acertou 100% das vezes. A etapa de feedback avalia decisões passadas em relação aos resultados reais e ajusta as premissas do pipeline para a próxima execução.

**Para o seu painel de BI**: Exporte o resultado completo como JSON estruturado para importar no Excel, Power BI ou qualquer outra ferramenta:

```bash
ugear run agro --output json > agro_decisions.json
```

---

## 2. O Analista Financeiro / Macroeconômico

**Cenário**: Você monitora USD/BRL, SELIC, inflação e ativos ligados a commodities. Você precisa sinalizar riscos para a sua equipe antes da reunião de segunda-feira.

**Sem o Universal Gear**: Você consulta o site do Banco Central, varre o Bloomberg, monta uma apresentação manualmente e torce para não ter perdido um sinal escondido no meio do ruído.

**Com o Universal Gear**:

```bash
ugear run finance
```

O pipeline `finance` aplica a mesma lógica de seis etapas a dados macroeconômicos:

- **Observation** -- Coleta taxas de câmbio, decisões de taxa de juros e índices de inflação de fontes oficiais.
- **Compression** -- Normaliza indicadores heterogêneos em janelas de tempo comparáveis.
- **Hypothesis** -- Detecta anomalias como "USD/BRL se moveu 2.3 desvios padrão acima da média de 30 dias" e as enquadra como afirmações testáveis.
- **Simulation** -- Projeta cenários combinando trajetórias de taxa, premissas de inflação e variáveis de política fiscal. Cada cenário recebe uma probabilidade e um nível de risco.
- **Decision** -- Emite alertas como "Considere fazer hedge da exposição em USD" ou "A trajetória da SELIC sugere risco de duration na carteira de renda fixa", cada um com uma pontuação de confiança e uma estimativa de custo do erro.
- **Feedback** -- Avalia se os alertas da semana passada estavam corretos, atualiza a confiabilidade das fontes e ajusta os pesos dos cenários para o próximo ciclo.

O formato de saída é idêntico ao do pipeline agro. O mesmo painel Rich, as mesmas seis etapas, a mesma exportação em JSON. Se você já sabe ler a saída do agro, sabe ler a saída do finance.

> **Nota**: O pipeline `finance` está totalmente implementado com dados do BCB (Banco Central do Brasil). Execute `ugear run finance` para experimentá-lo.

---

## 3. O Analista de Business Intelligence

**Cenário**: Você constrói painéis no Power BI ou Tableau. Seu chefe pergunta "e o que esses dados significam?" e você percebe que seu painel mostra **o que aconteceu**, mas não **o que fazer a respeito**.

**O problema**: Ferramentas tradicionais de BI são descritivas. Elas visualizam dados históricos. Elas não geram hipóteses, projetam cenários nem recomendam ações. Essa camada de raciocínio geralmente é feita de forma improvisada na cabeça de alguém -- sem documentação e sem possibilidade de reprodução.

**Com o Universal Gear**: O Universal Gear é a camada de raciocínio entre a sua fonte de dados e o seu painel. Ele pega observações brutas, passa por um pipeline analítico estruturado e produz decisões legíveis por máquina que o seu painel pode exibir junto com as métricas brutas.

Veja um fluxo de trabalho na prática:

```bash
# Executa o pipeline e exporta JSON estruturado
ugear run agro --output json > decisions.json

# Importe decisions.json no Power BI como fonte de dados
```

A saída em JSON contém o resultado de cada etapa: eventos brutos, estados comprimidos, hipóteses com pontuações de confiança, cenários simulados com probabilidades e decisões com níveis de risco e estimativas de custo do erro. Seu painel agora pode mostrar:

- Um gráfico de tendência (da etapa de compressão)
- Hipóteses ativas e seus níveis de confiança (da etapa de hipótese)
- Uma tabela comparativa de cenários com probabilidades (da etapa de simulação)
- Ações recomendadas com indicadores de risco (da etapa de decisão)
- Um rastreador de precisão histórica (da etapa de feedback)

**Execução agendada**: Execute o Universal Gear como um cron job ou tarefa agendada. Cada execução produz um arquivo JSON novo. Aponte seu painel para o diretório de saída, e ele se atualiza automaticamente com novas hipóteses e recomendações a cada ciclo.

```bash
# Exemplo: executar toda segunda-feira às 7:00 da manhã
0 7 * * 1  ugear run agro --output json > /data/agro_latest.json
```

O esquema JSON completo de cada etapa está documentado em [contracts.pt-BR.md](contracts.pt-BR.md).

---

## 4. O Desenvolvedor / Engenheiro de Dados

**Cenário**: Você quer construir um pipeline de decisão personalizado para o seu domínio -- logística, precificação de energia, gestão de estoque ou qualquer outra área onde raciocínio estruturado sobre dados ruidosos seria útil.

**O Universal Gear oferece**: Um pipeline tipado, validado e com seis etapas, com contratos entre cada uma delas. Você implementa a lógica do domínio; o framework cuida da orquestração, validação, observabilidade e feedback.

O sistema de plugins segue um padrão simples. Veja um coletor em cinco linhas:

```python
from universal_gear.core.interfaces import BaseCollector, CollectionResult
from universal_gear.core.registry import register_collector

@register_collector("my_domain")
class MyCollector(BaseCollector[MyConfig]):
    async def collect(self) -> CollectionResult:
        ...
```

Cada etapa tem a mesma estrutura: uma classe base, um decorator de registro, uma entrada tipada e uma saída tipada. Os seis decorators são `register_collector`, `register_processor`, `register_analyzer`, `register_model`, `register_action` e `register_monitor`.

Plugins externos podem ser distribuídos como pacotes Python independentes usando entry points padrão -- sem necessidade de alterações no Universal Gear.

Para um passo a passo completo, veja [plugins.pt-BR.md](plugins.pt-BR.md). Para os contratos de dados entre etapas, veja [contracts.pt-BR.md](contracts.pt-BR.md). Para instalação e primeira execução, veja [quickstart.pt-BR.md](quickstart.pt-BR.md).

---

## 5. O Não-Programador

**Cenário**: Você toma decisões recorrentes no trabalho -- comprar suprimentos, definir preços, escolher fornecedores -- mas não escreve código. Você quer uma forma estruturada de pensar sobre decisões em vez de seguir a intuição.

**Com o Universal Gear**: Gere um modelo de planilha e siga as sete abas:

```bash
pip install universal-gear[sheets]
ugear template
```

Isso cria o arquivo `ugear-decisao.xlsx`. Abra-o no Excel ou no Google Sheets. Cada aba é uma etapa do processo de decisão, com instruções no topo e um exemplo preenchido (compra de café para um escritório). Preencha as células verdes com os seus próprios dados.

Quando você completar um ciclo inteiro -- da observação até o feedback -- você terá um registro de decisão documentado e estruturado. Com o tempo, a aba DASHBOARD mostra o seu histórico: quantas decisões você acertou, seu erro médio e o que você aprendeu.

Sem programação, sem APIs, sem terminal. Apenas uma planilha e um método.

---

## 6. Futuro: O Analista de Saúde

**Cenário**: Você trabalha com monitoramento epidemiológico ou planejamento de capacidade hospitalar. Você precisa detectar surtos precocemente, projetar ocupação de leitos e recomendar alocação de recursos -- com base em dados, não em intuição.

**Como funcionaria**: O pipeline do Universal Gear é agnóstico em relação ao domínio. As mesmas seis etapas que analisam preços de soja podem analisar dados epidemiológicos:

- **Observation** -- Um coletor `saude` busca dados de notificação do DATASUS ou de APIs de secretarias estaduais de saúde.
- **Compression** -- Normaliza contagens de casos por semana epidemiológica e região, ajustando para atrasos de notificação.
- **Hypothesis** -- Detecta anomalias: "Notificações de dengue em Minas Gerais estão 2.8 desvios padrão acima da média sazonal de 5 anos."
- **Simulation** -- Projeta cenários: "Se a trajetória atual se mantiver, a capacidade hospitalar em Belo Horizonte atinge 90% em 3 semanas."
- **Decision** -- Emite alertas: "Considere ativar leitos de contingência na região metropolitana. Confiança: 0.74. Nível de risco: alto."
- **Feedback** -- Avalia se os alertas de surto do ciclo anterior se concretizaram, atualiza a linha de base e ajusta os limiares de detecção.

**Este plugin ainda não existe** -- mas a arquitetura está pronta para ele. Os contratos, as comportas de validação e o ciclo de feedback já estão implementados. Um plugin `saude` precisaria implementar seis classes (uma por etapa) seguindo o mesmo padrão do plugin `agro` existente.

Quer construí-lo? Comece por [plugins.pt-BR.md](plugins.pt-BR.md).

---

## Referência Rápida

| Perfil | Comando | O que você obtém |
|---|---|---|
| Analista de Commodities | `ugear run agro` | Hipóteses de tendência de preço, recomendações de venda futura, alertas de risco |
| Analista Financeiro | `ugear run finance` | Cenários de câmbio e trajetória de juros, alertas de hedge |
| Analista de BI | `ugear run agro --output json` | JSON estruturado para integração com painéis |
| Não-Programador | `ugear template` | Planilha guiada para decisões estruturadas sem código |
| Desenvolvedor | `pip install -e ".[dev]"` | SDK completo de plugins, contratos tipados, suíte de testes |
| Analista de Saúde | `ugear run saude` | Detecção de surtos, projeções de capacidade (futuro) |

---

## Próximos Passos

- [quickstart.pt-BR.md](quickstart.pt-BR.md) -- Instale o Universal Gear e execute seu primeiro pipeline em menos de cinco minutos.
- [cli.pt-BR.md](cli.pt-BR.md) -- Referência completa da CLI com todos os comandos e opções.
- [architecture.pt-BR.md](architecture.pt-BR.md) -- Como o pipeline de seis etapas funciona por dentro.
- [contracts.pt-BR.md](contracts.pt-BR.md) -- Referência completa de esquemas para entrada e saída de cada etapa.
- [plugins.pt-BR.md](plugins.pt-BR.md) -- Construa e distribua seu próprio plugin de domínio.
