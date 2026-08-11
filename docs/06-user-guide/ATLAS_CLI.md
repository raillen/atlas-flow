---
schema_version: 1
id: DOC-USER-ATLAS-CLI
title: Atlas CLI
status: active
version: 1
audience:
  - developer
  - agent
visibility: internal
authority: canonical
source: human
owner: atlas-flow-maintainers
last_reviewed: 2026-08-11
review_interval: 180d
risk: low
tags:
  - cli
  - atlas-flow-v2
---

# Atlas CLI

O CLI v2 oferece a mesma superfície para pessoas, agentes e CI. Dados para
automação devem usar `--json`; diagnósticos continuam no stderr quando a ação
falha.

## Inicializar um projeto

```sh
atlas --root /caminho/projeto init
atlas --root /caminho/projeto init --name "Meu Projeto"
```

`init` não sobrescreve arquivos existentes. Cria o manifesto, diretórios de
metadata e mapas iniciais somente quando ausentes.

## Validar e indexar

```sh
atlas --root . validate
atlas --root . validate --json
atlas --root . validate --write
atlas --root . graph --write --json
```

`validate` aceita Markdown legado, mas valida estritamente os documentos com
front matter e os YAML v2. `--write` gera `registry.json` e `graph.json` em
`.atlas/index/`.

## Contexto e impacto

```sh
atlas --root . context "schema migration" --budget medium --profile reviewer
atlas --root . context "schema migration" --budget 16000 --json
atlas --root . impact src/module.py --json
atlas --root . impact --changed --json
```

O planejador começa por `AGENTS.md` e `docs/ATLAS.md`, usa o `task map` e o
`context pack` correspondente quando existem e completa com busca lexical. O
resultado mostra o motivo de cada item, o budget, as exclusões e a condição de
parada.

## Documentação

```sh
atlas --root . docs validate --json
atlas --root . docs freshness
atlas --root . docs coverage --json
atlas --root . docs build --visibility public --output ./site
```

Um build público inclui somente páginas `public`. Builds `internal` incluem
`public` e `internal`; `private` inclui todas. O índice `search.json` segue a
mesma filtragem.

## Inteligência e custos

```sh
atlas --root . cost task TASK-142 --title "Implementar contexto" \
  --component context --estimate-min 1.0 --estimate-max 2.0 \
  --input-tokens 1200 --output-tokens 300 --confidence medium --json
atlas --root . cost project --write --json
atlas --root . intelligence summary
```

O ledger é `.atlas/intelligence/ledger.jsonl`. Se o provider não fornecer custo
observado, o resumo mostra `null`/`unknown`; o CLI não transforma estimativa em
precisão falsa.
