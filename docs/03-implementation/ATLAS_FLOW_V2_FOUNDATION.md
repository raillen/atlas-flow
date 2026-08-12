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
last_reviewed: 2026-08-12
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

Esta é a segunda fatia de compatibilidade implementada do
[AF-EVO-001](../08-rfcs/AF-EVO-001-ATLAS-FLOW-EVOLUTION.md). Ela adiciona
contratos bounded de contexto e Project Intelligence integrados ao snapshot de
Plan e ao ciclo operacional de Run, sem alterar os contratos existentes de
Goals ou desktop.

## O que existe

- `src/AtlasFlow.Orchestration/Context/ContextPlanner.cs`: classificação
  bounded, perfil, estratégia e limites LPC/PCA;
- `src/AtlasFlow.Domain/Context/ContextPlan.cs`: contrato de decisão sem
  payload de contexto;
- `src/AtlasFlow.Domain/Planning/Plan.cs` e
  `src/AtlasFlow.Persistence/PlanRepository.cs`: persistência compatível do
  `ContextPlan` no snapshot do plano;
- `src/AtlasFlow.Domain/Intelligence/TaskReport.cs`: relatório compacto,
  token usage e provenance de custo;
- `src/AtlasFlow.Application/Services/ProjectIntelligenceReportFactory.cs`:
  emissão do lifecycle `planned → running → success|failed|cancelled`;
- `src/AtlasFlow.Persistence/ProjectIntelligenceRepository.cs`: leitura,
  agregação, preservação de campos desconhecidos e escrita atômica;
- `src/AtlasFlow.Application/Contracts/`: seam consumível pelo desktop para
  planejar contexto e ler/registrar inteligência.

## Como usar

A validação desta fatia é feita pelo runtime .NET:

```sh
dotnet build AtlasFlow.slnx --no-restore
dotnet test AtlasFlow.slnx --no-restore
```

O CLI C# ainda é uma superfície em porting; os comandos de validação,
publisher e inteligência descritos no guia de CLI são alvo futuro e não devem
ser tratados como disponíveis neste estado.

## Fonte canônica e projeções

O conteúdo Markdown, metadata, manifests, task maps e context packs são fonte
do projeto. O registry, o grafo, o site e `project-summary.json` são derivados.
`atlas.json` e Goals são canônicos no formato v2. O snapshot de inteligência é
uma projeção durable versionada; SQLite continua operacional e não substitui
decisões, Goals ou documentação canônica. A coluna `plans.context` usa uma
migração incremental de schema (v3 → v4) e continua opcional para snapshots
antigos; o schema v5 adiciona as tabelas operacionais de Discuss sem substituir
a autoridade do ledger em Git.

## Compatibilidade

Um projeto sem manifesto v2 continua sendo lido: documentos Markdown recebem um
ID e uma estimativa de tokens derivados do caminho e do texto. O comando informa
`legacy-project` para tornar a migração visível. Nenhum arquivo legado é
reescrito automaticamente.

## Limitações da primeira fatia

Ainda não há indexação AST de símbolos, retrieval progressivo, embeddings,
preços de providers, relatórios por tarefa/runner, CLI v2 ou dashboard visual.
Quando não existe usage observado, o snapshot preserva provenance não observada
e não inventa custo direto.
