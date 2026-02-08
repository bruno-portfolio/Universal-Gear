# Universal Gear — Roadmap de Camadas de Acessibilidade
# Cada camada é entregue antes de iniciar a próxima.
# CC = Claude Code. Cada tarefa define o role que o CC deve assumir.

================================================================================
PADRÕES DE QUALIDADE — APLICAM A TODAS AS CAMADAS
================================================================================

# Filosofia
# O MANIFESTO.md é a lei suprema do projeto.
# "Quality code is non-negotiable" — "a senior dev would have nothing to
# point out" é o critério. Não "funciona".
# "Never sell certainty where there is uncertainty" — vale pro código também.
# Se um trecho é incerto, documente. Se um workaround é frágil, marque.

## Estilo e Formatação

- PEP 8 obrigatório, com as seguintes especificidades:
  - Line length: 99 chars (seguir pyproject.toml do projeto)
  - Formatador: ruff format (já configurado no projeto)
  - Linter: ruff check (já configurado no projeto)
  - Executar ruff format + ruff check antes de qualquer commit

## Type Hints (obrigatório em tudo)

- Sintaxe moderna: `X | None` (não `Optional[X]`), `list[str]` (não `List[str]`)
- `from __future__ import annotations` em todo arquivo (já padrão no projeto)
- Retornos explícitos: nunca `-> None` implícito em funções públicas
- Generics tipados: `BaseCollector[MyConfig]`, não `BaseCollector[Any]`
- TypeVar quando necessário, não `Any` como escape

## Imports (ordem obrigatória, 5 níveis)

```python
from __future__ import annotations          # 1. future

from datetime import UTC, datetime          # 2. stdlib
from typing import TYPE_CHECKING
from uuid import UUID

import structlog                            # 3. third-party
from pydantic import BaseModel, Field

from universal_gear.core.contracts import ( # 4. projeto (universal_gear.core)
    CollectionResult,
    DecisionObject,
)
from universal_gear.core.interfaces import BaseCollector

from .config import MyConfig                # 5. local (relative imports no plugin)
```

- TYPE_CHECKING imports: usar `if TYPE_CHECKING:` pra imports que são só pra type hints
  (já é padrão no projeto — ver pipeline.py)
- Sem imports wildcard (`from x import *`) — nunca

## Modelos Pydantic (padrão do projeto)

- `model_config = ConfigDict(frozen=True)` em todo model de dados
  (imutabilidade = previsibilidade)
- Fields com `Field(ge=0.0, le=1.0)` pra bounded values (confidence, reliability)
- Validators: `@field_validator` e `@model_validator` pra invariantes de negócio
- Default factories: `Field(default_factory=list)` não `= []`
- Docstring de 1 linha em todo model

## Async

- Todo stage é async (interface exige)
- Não bloquear event loop: usar `asyncio.to_thread()` pra I/O síncrono
- Sem `asyncio.run()` dentro de stages (só no CLI)

## Funções

- Max 30 linhas por função. Se passar, quebrar.
- 1 função = 1 responsabilidade
- Early return > nested ifs
- Pattern matching (`match/case`) preferido sobre if/elif chains (já padrão no projeto)
- Sem side effects escondidos. Se a função modifica estado, o nome deve indicar.

## Error Handling

- Try/except específico — nunca bare `except:` ou `except Exception:`
- Exceções customizadas do projeto: `PipelineError`, `StageTransitionError`,
  `CollectionError`, `PluginNotFoundError` (ver core/exceptions.py)
- Criar novas exceções em core/exceptions.py quando necessário
- Fail loud: erro silencioso é erro duplo (manifesto)
- Logging do erro ANTES de re-raise: `logger.error("contexto", error=str(exc))`

## Logging

- structlog exclusivamente — nunca `print()`, nunca `logging` stdlib
- `logger = structlog.get_logger()` no topo do módulo
- Eventos descritivos: `logger.info("stage.completed", duration=elapsed)`
- Nunca logar dados sensíveis do usuário (manifesto: zero telemetry)

## Testes

- Framework: pytest (diferente do geemap que usa unittest)
- Nomenclatura: `test_<method>_<state>` (ex: `test_collect_empty_source`)
- 1 teste = 1 comportamento
- Mocks obrigatórios para: APIs externas (CEPEA, CONAB, BCB), filesystem, rede
- Zero chamadas de rede em testes — sempre
- Edge cases obrigatórios: None, lista vazia, inputs inválidos, timeout, API error
- Assertions específicos: `assert result.success is True` não `assert result`
- Fixtures em `tests/fixtures/` pra dados de exemplo
- Conftest.py pra fixtures compartilhadas
- Cobertura: todo código novo deve ter teste correspondente

## Dependências

- Sem dependência nova a menos que absolutamente necessário
- Dependências opcionais via extras: `pip install universal-gear[agro]`
- Imports lazy pra dependências opcionais:
  ```python
  try:
      from agrobr import cepea
  except ImportError as exc:
      raise CollectionError("agrobr not installed. Run: pip install universal-gear[agro]") from exc
  ```
- Nunca importar dependência opcional no topo do módulo

## Documentação

- Docstring de 1 linha em toda classe e função pública
- Sem comentários inline óbvios — código autoexplicativo pela nomenclatura
- Comentários só quando o "porquê" não é óbvio pelo código
- README e docs: sempre bilíngue (EN principal, pt-BR disponível)
- Se algo tem limitação conhecida, documentar (manifesto)

## Git / Commits

- Repositório: https://github.com/bruno-portfolio/Universal-Gear
- REGRA ABSOLUTA: NUNCA executar `git commit`, `git push`, `git tag`,
  ou qualquer operação que modifique o histórico sem pedir autorização
  explícita do usuário ANTES. Sempre mostrar o que será commitado
  (diff resumido ou lista de arquivos) e a mensagem de commit proposta.
  Aguardar confirmação. Sem exceções.
- Commits atômicos: 1 commit = 1 mudança lógica
- Conventional commits: `fix:`, `feat:`, `docs:`, `test:`, `refactor:`
- Nunca commitar código que não passa em ruff + testes
- Nunca commitar features incompletas sem `hidden=True` ou feature flag
- CHANGELOG.md atualizado a cada release
- Antes de push: confirmar branch correta e listar commits que serão enviados

## Checklist pré-commit (CC deve executar mentalmente)

```
[ ] ruff format passou?
[ ] ruff check passou?
[ ] Testes passaram?
[ ] Type hints em toda API pública?
[ ] Nenhuma dependência nova desnecessária?
[ ] Nenhuma chamada de rede em testes?
[ ] Nenhum print() no código?
[ ] Exceções específicas (não bare except)?
[ ] Funções < 30 linhas?
[ ] Imports na ordem correta?
[ ] Frozen models pra dados?
[ ] Edge cases cobertos nos testes?
[ ] Docstring em classes/funções públicas?
[ ] MANIFESTO.md respeitado?
[ ] PEDI AUTORIZAÇÃO pro commit/push? ← OBRIGATÓRIO
```

================================================================================
ROADMAP DE CAMADAS
================================================================================

REGRA #1 DO CC (acima de tudo):
NUNCA executar git commit, git push, git tag, ou qualquer operação
NUNCA commitar .claude ou este roadmap
destrutiva de git sem PEDIR e RECEBER autorização explícita do usuário.
Sempre mostrar: arquivos modificados, diff resumido, mensagem de commit.
Aguardar "ok", "vai", "pode" ou equivalente. Sem exceções. Sem atalhos.

---

## CAMADA 0 — Fixes do release atual [CONCLUIDA]
# Pré-requisito pra tudo. Sem isso não posta.

### 0.1 Finance no PyPI [DONE]
Verificado: match case "finance" já existe em cli/main.py (linhas 295-301).
Nenhuma ação necessária.

### 0.2 Esconder stubs [DONE]
`validate` e `scorecard` → `hidden=True` no typer.

### 0.3 Limpeza [DONE]
- Removido toy_output.txt e artefato nul do root
- README (EN + pt-BR): corrigido `--json` para `--output json`
- README (EN + pt-BR): adicionada seção "Roadmap" com features futuras

### 0.4 agro --sample [DONE]
- Fixture com 90 dias de dados CEPEA realistas (soja, Paranagua)
- Campo `sample: bool` no AgroConfig
- Método `_load_sample()` no AgrobrCollector via importlib.resources
- Flag `--sample` no CLI (`ugear run agro --sample`)
- Fixture incluído no wheel via pyproject.toml artifacts
- 2 testes de integração (collector isolado + pipeline completo)
- 164 testes passando, ruff clean

CC Role: "Senior Python developer doing a pre-release audit.
Fix bugs, remove dead code, hide unfinished features.
Every change must pass existing tests. No new features — only fixes.
Follow all coding standards defined in this document.
Code quality: a reviewer should find nothing to point out."

---

## CAMADA 1 — Output que comunica decisões [CONCLUIDA]
# Transforma o projeto de "framework técnico" em "ferramenta que entrega respostas"

### 1.1 Decision summary panel [DONE]
- Novo módulo cli/panels.py com render_decision_panel()
- Ícone por tipo (! alert, v recommendation, * trigger, # report)
- Title, recommendation, cost_of_error (FP + FN), risk level, confidence
- Ordenado por confidence DESC, max 5, flag --all pra ver todas
- Exibido automaticamente após o painel de stages

### 1.2 Track record panel [DONE]
- render_track_record() em cli/panels.py
- Hit rate (colorido: verde >= 70%, amarelo >= 40%, vermelho < 40%)
- Mean absolute error (colorido por faixa)
- Bias (over/under-predicting)
- Contagem de scorecards, source degradations, accuracy trend

### 1.3 --json que exporta resultado real [DONE]
- JSON já serializa PipelineResult completo via model_dump (decisions + scorecards + metrics)
- Rich panels agora vão pra stderr quando --output json ativo (Console(stderr=True))
- Importável em Power BI / Pandas / jq

### 1.4 --decisions-only flag [DONE]
- `ugear run <pipeline> --decisions-only` mostra só decisions + track record
- Sem stage logs. Pra quem quer resposta rápida.
- `--all` mostra todas as decisions (sem limite de 5)
- 12 testes novos em test_panels.py
- 176 testes passando, ruff clean

### 1.5 Decision output grouping [DONE]
- Decisions with same title prefix + decision_type are grouped visually
- Summary line at top: pct range + actionable count
- Grouped row: scenario count, driver categories, consolidated FP/FN range
- Single decisions render ungrouped (backwards compatible)
- Structured driver parsing with fallback to "e.g." examples
- Confidence and risk shown as ranges (50%-75%, LOW-MEDIUM)
- JSON output unchanged (grouping is presentation-only)
- 31 tests in test_panels.py (12 new for grouping, regression, extraction)
- 223 testes passando, ruff clean

CC Role: "Senior Python developer building CLI user experience.
Use Rich library (already in project). Follow existing code patterns in cli/main.py.
All new output derives from existing Pydantic contracts — no new models needed.
The output must be immediately understandable by a non-technical person.
Follow all coding standards defined in this document.
Test: show the output to someone who doesn't code. If they don't understand
the decision in 5 seconds, redesign it."

---

## CAMADA 2 — Plugin scaffold [CONCLUIDA]
# Transforma de "ferramenta" em "plataforma que outros constroem"

### 2.1 Comando `ugear new-plugin <nome>` [DONE]
- Novo módulo cli/scaffold.py com generate_plugin() e 9 templates
- Gera 9 arquivos: __init__.py + config.py + 6 stages + test_<nome>.py
- Cada arquivo segue padrões: imports 5 níveis, register decorator, async method, docstring
- Validação de nome (snake_case obrigatório)
- Erro claro se diretório já existe

### 2.2 Comando `ugear check-plugin <nome>` [DONE]
- Novo módulo cli/checker.py com check_plugin()
- Verifica existência dos 7 módulos (config + 6 stages)
- Importa cada módulo e verifica herança da ABC correta
- Verifica config exporta BaseModel subclass
- Retorna lista de erros com mensagens claras

### 2.3 Tutorial: docs/tutorial-first-plugin.md [DONE]
- 9 seções práticas: scaffold → config → collector → stages → tests → wire → run
- Exemplo com plugin "weather" usando Open-Meteo API
- Referências cruzadas para architecture.md, contracts.md, plugins.md

### 2.4 Scaffold gera testes [DONE]
- test_<nome>_plugin.py gerado com config test + TODO markers por stage
- Padrão pytest.mark.offline, referência a test_agro_plugin.py como modelo

### Qualidade
- 10 testes novos em test_scaffold.py (estrutura, decorators, base classes, duplicatas, syntax)
- 4 testes em test_checker.py (scaffold válido, missing dir, missing module, plugins existentes)
- 190 testes passando, ruff clean
- Corrigido 192 PT001/PT023 lint issues em todos os test files (parentheses em markers)

CC Role: "Senior developer focused on developer experience (DX).
The scaffold must work out of the box after the user fills the TODOs.
The tutorial must be completable by someone who knows basic Python
but has never seen Pydantic or async/await.
Every generated file must follow the same patterns as the existing
toy and agro plugins — consistency is mandatory.
The scaffold IS the coding standard made tangible — if someone copies
the patterns from the scaffold, they automatically follow the rules.
Follow all coding standards defined in this document.
Do not over-abstract. Do not add frameworks. Keep it simple."

---

## CAMADA 3 — Planilha template [CONCLUIDA]
# Primeira camada que alcança não-programadores

### 3.1 Template com 7 abas [DONE]
- Novo módulo cli/spreadsheet.py com generate_template() via openpyxl
- 7 abas: OBSERVAR, COMPRIMIR, HIPOTESE, SIMULAR, DECIDIR, FEEDBACK, DASHBOARD
- Cada aba com colunas estruturadas mapeando os campos dos contracts do pipeline
- Celulas coloridas: verde (input), laranja (exemplo), azul (calculado), amarelo (instrucao)
- Comando CLI: `ugear template --output arquivo.xlsx --lang pt|en`

### 3.2 Instruções na própria planilha [DONE]
- Bloco de instrução amarelo no topo de cada aba (row 1, merged)
- Linguagem coloquial em pt-BR, sem jargão técnico
- Versão em inglês disponível via --lang en

### 3.3 Exemplos pré-preenchidos [DONE]
- Exemplo completo: compra de café pro escritório (decisão real do dia-a-dia)
- OBSERVAR: 3 observações de preço de fontes diferentes
- COMPRIMIR: resumo com média, variação, tendência
- HIPOTESE: "preço vai subir 10%" com critérios de validação e falsificação
- SIMULAR: 3 cenários (otimista/base/pessimista) com premissas e probabilidades
- DECIDIR: antecipar compra com custo de erro (FP e FN)
- FEEDBACK: resultado real vs previsto, lição aprendida
- DASHBOARD: métricas consolidadas (acertos, erro médio)

### 3.4 Exportar planilha → JSON [DONE]
- read_sheet_as_json() lê xlsx preenchido e retorna dict com 7 seções
- Detecta automaticamente header row (pula instruções)
- Comando CLI: `ugear import-sheet planilha.xlsx` (stdout) ou `--output file.json`
- openpyxl como dependência opcional: `pip install universal-gear[sheets]`

### 3.5 Validação com usuários reais [PENDENTE — processo manual]
Dar a planilha pra 3-5 pessoas não-técnicas, observar uso, coletar feedback.
Só avançar pra Camada 4 quando alguém completar o ciclo sem precisar de ajuda.

### Qualidade
- 14 testes novos em test_spreadsheet.py (geração, 7 abas, exemplos, roundtrip JSON)
- 204 testes passando, ruff clean
- openpyxl adicionado como optional dependency [sheets] no pyproject.toml

CC Role: "Product designer creating a self-service spreadsheet tool.
Generate a Python script that creates the Google Sheets template via
openpyxl (xlsx para download).
The generator script follows all coding standards of this document.
Every cell that the user must fill is highlighted.
Every formula cell is protected and documented.
The language must be Portuguese (BR) with English option.
Test: someone with zero technical knowledge must be able to open,
read the instructions, and complete the first cycle in 20 minutes."

---

## CAMADA 4 — Conteúdo (artigos/posts)
# Explica a metodologia sem exigir nenhuma ferramenta

### 4.1 Post de lançamento (LinkedIn/Medium)
Ângulo: "Toda semana você decide com dados incompletos.
Aqui está um método pra decidir melhor sabendo que pode errar."
- O problema (2 parágrafos)
- Os 6 estágios explicados com exemplo cotidiano
- Link pro GitHub como "pra quem quer automatizar"
- Link pra planilha como "pra quem quer começar agora"

### 4.2 Série "Decisão Estruturada" (6 posts, um por estágio)
Cada post: o estágio, por que importa, exemplo prático, erro comum.
Sem código. Linguagem acessível.

### 4.3 README do repo atualizado
Adicionar seção "Não programa? Comece aqui →" com link pra planilha
e pros artigos. O repo deixa de ser só pra devs.

### 4.4 Vídeo curto (3-5 min)
Screencast com narração mostrando preenchimento da planilha do zero.
Sem produção pesada — tela gravada + voz. Pro público da Camada 3-4,
vídeo vale mais que texto.

CC Role: "Technical writer who translates complex frameworks into
accessible content. Write in Portuguese (BR), direct, no fluff.
Every paragraph must pass the test: 'would my non-technical friend
understand this?' If not, rewrite.
Do not use jargon without explaining it.
Do not assume the reader knows what a pipeline, framework, or API is.
The manifesto is the philosophical guide — the content is the
practical translation for real people."

---

## CAMADA 5 — Webapp (futuro)
# Só inicia depois de validar com feedback real das camadas anteriores

### 5.1 Interface web mínima
Streamlit ou similar. Upload CSV / input manual → roda pipeline → mostra decisions.
Sem login. Sem banco. Sem infra complexa.

### 5.2 Modo guiado
Wizard step-by-step que leva o usuário pelos 6 estágios.
Cada step tem explicação + input. No final: relatório de decisão.

### 5.3 API pública
Endpoint REST que aceita dados e retorna decisions JSON.
Base pra integrações futuras (Power BI, Sheets, bots).

CC Role: "Full-stack developer building a minimal viable product.
Streamlit first — fastest to deploy, easiest to iterate.
No premature optimization. No auth. No database (stateless).
The entire app must be deployable with `streamlit run app.py`.
All Python code follows the coding standards of this document.
Design principle: if a feature doesn't directly help the user
make a better decision, don't build it."

================================================================================
CONTRIBUTING STANDARDS (para CONTRIBUTING.md)
================================================================================

# Quando o projeto receber contribuidores externos, adicionar ao CONTRIBUTING.md:

## Pra todo PR:
1. Leia o MANIFESTO.md antes de começar
2. Execute `ruff format` e `ruff check` — zero warnings
3. Execute `pytest` — zero failures
4. Type hints em toda API pública
5. Testes pra todo código novo
6. 1 PR = 1 feature ou 1 fix. Nunca misture.

## Não será aceito:
- Código sem type hints em APIs públicas
- Testes que fazem chamadas de rede reais
- Bare except ou except Exception
- Funções > 30 linhas sem justificativa
- print() ao invés de structlog
- Dependência nova sem discussão prévia na issue
- Features que contradizem o MANIFESTO.md

## Será muito bem-vindo:
- Novos plugins pra qualquer domínio
- Melhorias no output human-readable
- Traduções da documentação
- Exemplos e tutoriais
- Bug reports com reprodução mínima
