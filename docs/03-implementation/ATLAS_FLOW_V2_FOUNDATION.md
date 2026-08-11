---
schema_version: 1
id: DOC-IMPL-V2-FOUNDATION
title: Atlas Flow v2 Foundation
status: active
version: 1
audience:
  - developer
  - maintainer
  - agent
visibility: internal
authority: canonical
source: human
owner: atlas-flow-maintainers
last_reviewed: 2026-08-11
review_interval: 180d
risk: medium
tags:
  - atlas-flow-v2
  - schemas
  - context
related:
  - ADR-015-ATLAS-FLOW-V2-FOUNDATION
---

# Atlas Flow v2 Foundation

Esta é a primeira fatia implementada do [AF-EVO-001](../08-rfcs/AF-EVO-001-ATLAS-FLOW-EVOLUTION.md).
Ela adiciona uma camada determinística de conhecimento e inteligência sem
alterar o runtime existente de Goals, Runs ou desktop.

## O que existe

- `atlas.config.yaml`: manifesto v2 do projeto;
- `schemas/`: contratos JSON versionados para manifesto, metadata, task maps,
  context packs, grafo e custo;
- `backend/atlas_flow/evolution/documents.py`: front matter, discovery e
  freshness;
- `registry.py`: registry e grafo derivados, com escrita atômica em
  `.atlas/index/`;
- `validation.py`: validação de manifesto, documentos, IDs, task maps e packs;
- `context.py`: budgets, contexto obrigatório/opcional/excluído, busca lexical e
  impacto explicável;
- `intelligence.py`: ledger JSONL append-only, dívida e resumo reconstruível;
- `site.py`: publisher estático mínimo com filtragem `public`/`internal`/`private`;
- `cli.py`: superfície `atlas` para humanos e agentes.

## Como usar

Sempre execute a partir da raiz do projeto:

```sh
uv run --project backend --all-groups atlas validate --json
uv run --project backend --all-groups atlas validate --write
uv run --project backend --all-groups atlas impact --changed --json
uv run --project backend --all-groups atlas context "context engine" --budget small --json
uv run --project backend --all-groups atlas docs build --visibility internal
uv run --project backend --all-groups atlas intelligence summary --json
```

O guia completo está em [Atlas CLI](../06-user-guide/ATLAS_CLI.md).

O gate `scripts/validate_all.sh` executa `atlas validate --json` junto com os
validadores existentes. Assim, uma mudança documental que quebre metadata,
IDs, task maps ou context packs falha no mesmo fluxo usado pelo CI.

## Fonte canônica e projeções

O conteúdo Markdown, metadata, manifests, task maps e context packs são fonte
do projeto. O registry, o grafo, o site e `project-summary.json` são derivados.
`.atlas/` é ignorado pelo Git e pode ser recriado; ele não substitui decisões,
Goals ou documentação canônica.

## Compatibilidade

Um projeto sem manifesto v2 continua sendo lido: documentos Markdown recebem um
ID e uma estimativa de tokens derivados do caminho e do texto. O comando informa
`legacy-project` para tornar a migração visível. Nenhum arquivo legado é
reescrito automaticamente.

## Limitações da primeira fatia

Ainda não há indexação AST de símbolos, delta context, embeddings, preços de
providers ou dashboard visual. Quando não existe usage observado, o ledger
preserva custo monetário como `null` e registra somente os tokens fornecidos.
