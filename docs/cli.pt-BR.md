# Refer\u00eancia da CLI

*[Read in English](cli.md)*

O Universal Gear disponibiliza o comando `ugear`, uma CLI baseada em Typer para
executar pipelines de intelig\u00eancia de mercado, inspecionar plugins e gerenciar
configura\u00e7\u00f5es.

```
ugear [COMMAND] [OPTIONS]
```

---

## Comandos

### `ugear run`

Executa um pipeline de ponta a ponta.

```
ugear run <PIPELINE> [OPTIONS]
```

**Argumentos**

| Argumento  | Obrigat\u00f3rio | Descri\u00e7\u00e3o                                              |
|------------|-------------|--------------------------------------------------------|
| `PIPELINE` | Sim         | Nome do pipeline: `toy`, `agro`, ou caminho para arquivo YAML. |

**Op\u00e7\u00f5es**

| Op\u00e7\u00e3o                        | Curto | Padr\u00e3o     | Descri\u00e7\u00e3o                                                                          |
|------------------------------|-------|------------|-------------------------------------------------------------------------------------|
| `--verbose`                  | `-v`  | `false`    | Habilita logging no n\u00edvel DEBUG (o padr\u00e3o \u00e9 INFO).                                  |
| `--json`                     |       | `false`    | Emite sa\u00edda de log estruturada em JSON em vez de texto leg\u00edvel.                     |
| `--fail-fast / --no-fail-fast` |     | `true`     | Aborta o pipeline na primeira falha de est\u00e1gio (`--no-fail-fast` para continuar).   |
| `--output`                   | `-o`  | `terminal` | Formato de sa\u00edda: `terminal`, `json` ou `csv`.                                     |
| `--sample`                   |       | `false`    | Usa dados de amostra inclusos em vez de APIs ao vivo (modo offline).                |
| `--decisions-only`           |       | `false`    | Mostra apenas decis\u00f5es e hist\u00f3rico de acertos, pula logs de est\u00e1gios.               |
| `--all`                      |       | `false`    | Mostra todas as decis\u00f5es (padr\u00e3o: top 5 por confian\u00e7a).                             |

**Pipelines dispon\u00edveis**

| Nome   | Descri\u00e7\u00e3o                                                                   |
|--------|-----------------------------------------------------------------------------|
| `toy`     | Pipeline de dados sint\u00e9ticos. Usa um coletor sint\u00e9tico, processador agregador, detector de anomalias sazonais, motor de cen\u00e1rios condicional, emissor de alertas e monitor de backtest. \u00datil para desenvolvimento e demonstra\u00e7\u00e3o. |
| `agro`    | Pipeline de agroneg\u00f3cio. Coleta dados reais via coletor agrobr e executa est\u00e1gios espec\u00edficos de agro: processador, analisador, motor de cen\u00e1rios, emissor de a\u00e7\u00f5es e monitor. |
| `finance` | Pipeline financeiro. Coleta dados macroecon\u00f4micos do BCB (Banco Central do Brasil) e executa est\u00e1gios espec\u00edficos de finan\u00e7as. |

Qualquer outro valor para `PIPELINE` imprime um erro e encerra com c\u00f3digo 1.

**Exemplos**

```bash
# Executar o pipeline toy com configura\u00e7\u00f5es padr\u00e3o
ugear run toy

# Executar o pipeline agro com logging detalhado
ugear run agro --verbose

# Executar com sa\u00edda de log em JSON e sem fail-fast
ugear run toy --json --no-fail-fast

# Combinar flags curtas e longas
ugear run agro -v --json --fail-fast
```

Ap\u00f3s a execu\u00e7\u00e3o, um painel formatado com Rich \u00e9 exibido no terminal mostrando
o status de cada est\u00e1gio (OK / FAIL), um resumo em uma linha, a dura\u00e7\u00e3o do
est\u00e1gio e o resultado geral do pipeline.

---

### `ugear plugins`

Lista os plugins registrados.

```
ugear plugins [STAGE]
```

**Argumentos**

| Argumento | Obrigat\u00f3rio | Descri\u00e7\u00e3o                                                            |
|-----------|-------------|----------------------------------------------------------------------|
| `STAGE`   | N\u00e3o         | Filtra os resultados para um \u00fanico est\u00e1gio. Omita para listar todos. |

Nomes de est\u00e1gio v\u00e1lidos: `collector`, `processor`, `analyzer`, `model`, `action`, `monitor`.

**Exemplos**

```bash
# Listar todos os plugins registrados em todos os est\u00e1gios
ugear plugins

# Listar apenas plugins do tipo collector
ugear plugins collector
```

A sa\u00edda \u00e9 uma tabela Rich com duas colunas: **Stage** e **Plugins**.

---

### `ugear new-plugin`

Cria a estrutura de um novo plugin de dom\u00ednio com todos os seis est\u00e1gios do pipeline.

```
ugear new-plugin <NAME>
```

**Argumentos**

| Argumento | Obrigat\u00f3rio | Descri\u00e7\u00e3o                                              |
|-----------|-------------|--------------------------------------------------------|
| `NAME`    | Sim         | Nome do plugin em snake_case (ex.: `energy`, `weather`). |

Cria nove arquivos:

- `src/universal_gear/plugins/<name>/` \u2014 `__init__.py`, `config.py`, `collector.py`, `processor.py`, `analyzer.py`, `model.py`, `action.py`, `monitor.py`
- `tests/test_<name>_plugin.py` \u2014 esqueleto de testes com teste de configura\u00e7\u00e3o e marcadores TODO

Cada arquivo gerado segue as conven\u00e7\u00f5es do projeto: classe base correta, decorador de registro, assinatura de m\u00e9todo ass\u00edncrono e ordem de importa\u00e7\u00e3o.

**Exemplos**

```bash
ugear new-plugin weather
ugear new-plugin supply_chain
```

---

### `ugear check-plugin`

Valida se um plugin implementa todas as interfaces exigidas.

```
ugear check-plugin <NAME>
```

**Argumentos**

| Argumento | Obrigat\u00f3rio | Descri\u00e7\u00e3o                    |
|-----------|-------------|------------------------------|
| `NAME`    | Sim         | Nome do plugin a ser validado. |

Verifica\u00e7\u00f5es:

- Todos os sete m\u00f3dulos existem (config + seis est\u00e1gios)
- Cada m\u00f3dulo de est\u00e1gio cont\u00e9m uma classe que herda da ABC correta
- O m\u00f3dulo de config exporta uma subclasse de `BaseModel` do Pydantic

Encerra com c\u00f3digo 0 se todas as verifica\u00e7\u00f5es passarem, c\u00f3digo 1 se problemas forem encontrados.

**Exemplos**

```bash
ugear check-plugin weather
ugear check-plugin agro
```

---

### `ugear template`

Gera um modelo de planilha (xlsx) para framework de decis\u00e3o.

```
ugear template [OPTIONS]
```

**Op\u00e7\u00f5es**

| Op\u00e7\u00e3o      | Curto | Padr\u00e3o               | Descri\u00e7\u00e3o                                            |
|------------|-------|----------------------|------------------------------------------------------|
| `--output` | `-o`  | `ugear-decisao.xlsx` | Caminho do arquivo de sa\u00edda para o modelo xlsx.      |
| `--lang`   |       | `pt`                 | Idioma: `pt` (Portugu\u00eas) ou `en` (Ingl\u00eas).           |

Requer `openpyxl`. Instale com `pip install universal-gear[sheets]`.

**Exemplos**

```bash
ugear template
ugear template --output my-decisions.xlsx --lang en
```

---

### `ugear import-sheet`

Converte um modelo de planilha preenchido para JSON.

```
ugear import-sheet <XLSX_PATH> [OPTIONS]
```

**Argumentos**

| Argumento   | Obrigat\u00f3rio | Descri\u00e7\u00e3o                                |
|-------------|-------------|------------------------------------------|
| `XLSX_PATH` | Sim         | Caminho para o modelo xlsx preenchido.   |

**Op\u00e7\u00f5es**

| Op\u00e7\u00e3o      | Curto | Padr\u00e3o  | Descri\u00e7\u00e3o                                            |
|------------|-------|---------|------------------------------------------------------|
| `--output` | `-o`  | `-`     | Caminho do arquivo de sa\u00edda (padr\u00e3o: stdout).        |

Requer `openpyxl`. Instale com `pip install universal-gear[sheets]`.

**Exemplos**

```bash
ugear import-sheet planilha.xlsx
ugear import-sheet planilha.xlsx --output result.json
ugear import-sheet planilha.xlsx | jq '.decisions'
```

---

### `ugear validate`

Valida um arquivo de configura\u00e7\u00e3o de pipeline sem execut\u00e1-lo.

> **Nota:** Este comando \u00e9 um stub. A l\u00f3gica de valida\u00e7\u00e3o ainda n\u00e3o foi implementada.

```
ugear validate <CONFIG>
```

**Argumentos**

| Argumento | Obrigat\u00f3rio | Descri\u00e7\u00e3o                                        |
|-----------|-------------|--------------------------------------------------|
| `CONFIG`  | Sim         | Caminho para um arquivo YAML de configura\u00e7\u00e3o de pipeline. |

**Exemplos**

```bash
ugear validate pipelines/my-pipeline.yaml
```

---

### `ugear scorecard`

Exibe scorecards de execu\u00e7\u00f5es anteriores de pipelines.

> **Nota:** Este comando \u00e9 um stub. Ele requer uma camada de persist\u00eancia que ainda n\u00e3o est\u00e1 dispon\u00edvel.

```
ugear scorecard <PIPELINE> [OPTIONS]
```

**Argumentos**

| Argumento  | Obrigat\u00f3rio | Descri\u00e7\u00e3o                                              |
|------------|-------------|--------------------------------------------------------|
| `PIPELINE` | Sim         | Pipeline cujo hist\u00f3rico de scorecard ser\u00e1 exibido.      |

**Op\u00e7\u00f5es**

| Op\u00e7\u00e3o    | Curto | Padr\u00e3o  | Descri\u00e7\u00e3o                                      |
|----------|-------|---------|-------------------------------------------------|
| `--last` | `-n`  | `5`     | N\u00famero de execu\u00e7\u00f5es recentes a exibir.          |

**Exemplos**

```bash
# Mostrar as \u00faltimas 5 execu\u00e7\u00f5es do pipeline agro
ugear scorecard agro

# Mostrar as \u00faltimas 10 execu\u00e7\u00f5es
ugear scorecard agro --last 10
ugear scorecard agro -n 10
```

---

## Comportamento global

- **Logging** \u00e9 configurado por execu\u00e7\u00e3o atrav\u00e9s das flags `--verbose` e `--json`
  no `ugear run`. O modo verbose define o n\u00edvel como DEBUG; caso contr\u00e1rio,
  INFO \u00e9 utilizado.
- **C\u00f3digos de sa\u00edda**: comandos encerram com `0` em caso de sucesso. `ugear run`
  encerra com `1` quando um nome de pipeline desconhecido \u00e9 fornecido.
- **Sa\u00edda Rich**: toda a sa\u00edda no terminal (tabelas, pain\u00e9is, indicadores de status)
  \u00e9 renderizada atrav\u00e9s do Rich com modo de terminal for\u00e7ado.

---

## Ponto de entrada

A CLI \u00e9 registrada como um console script no `pyproject.toml`:

```toml
[project.scripts]
ugear = "universal_gear.cli.main:app"
```

Ap\u00f3s instalar o pacote (`pip install -e .`), o comando `ugear` fica dispon\u00edvel
no ambiente ativo.
