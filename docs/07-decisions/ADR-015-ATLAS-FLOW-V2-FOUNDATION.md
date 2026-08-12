---
schema_version: 1
id: ADR-015-ATLAS-FLOW-V2-FOUNDATION
title: Fundação determinística do Atlas Flow v2
status: active
version: 2
audience: [developer, maintainer, agent]
visibility: internal
authority: canonical
source: human
owner: atlas-flow-maintainers
last_reviewed: 2026-08-12
review_interval: 180d
risk: medium
---

# ADR-015 — Fundação determinística do Atlas Flow v2

**Status:** Accepted
**Date:** 2026-08-11

## Contexto

O AF-EVO-001 amplia o Atlas Flow para organizar conhecimento, selecionar
contexto, publicar documentação e registrar inteligência de projeto. O runtime
v1 já possui contratos estáveis para Goals, execução, SQLite operacional e
desktop. A evolução não pode duplicar esses contratos nem depender de serviços
externos para funcionar.

## Decisão

1. A fundação v2 vive em `src/AtlasFlow.Orchestration/Context/` e usa `record`
   types de domínio versionados, sem nomes de providers ou modelos no domínio.
2. `atlas.json` é o manifesto v2. Projetos legados continuam indexáveis com o
   leitor YAML v0.1; a presença de `atlas.json` seleciona v2 e um manifesto v2
   inválido não cai silenciosamente para o YAML.
3. O primeiro contrato implementado é um `ContextPlan` bounded: classifica a
   tarefa, seleciona perfil/estratégia e lê limites de entrada, saída,
   expansão e delegação. Retrieval, índices e publisher permanecem fatias
   independentes.
4. Project Intelligence usa `.atlas/history/project-intelligence.json` como
   snapshot versionado de relatórios compactos. Traces brutos ficam em SQLite;
   valores observados, estimados, alocados e desconhecidos permanecem
   distintos. Escrita é atômica e o resumo é reconstruível.
5. Registry, grafo, CLI v2 e documentação publicada continuam projeções
   posteriores. Eles não são simulados pelo contrato de contexto ou pela UI.
   O Plan snapshot persiste a decisão de contexto e o ciclo Plan/Run atualiza
   um relatório compacto, sem copiar payloads ou traces para o domínio.

## Consequências

### Positivas

- O mesmo fluxo funciona em projetos novos e legados.
- CI e agentes podem consumir JSON sem depender da interface desktop.
- Índices, site e resumo podem ser apagados e regenerados quando os respectivos
  publishers forem implementados.
- A política “observed > estimated > unknown” fica representada no contrato.

### Limitações aceitas

- A seleção inicial usa heurísticas léxicas; retrieval de símbolos, delta
  context e dashboard visual ainda são fases posteriores.
- O relatório atual representa o lifecycle do plano revisado; não há ainda
  um relatório individual por tarefa, runner ou provider.

## Rejeitadas nesta fase

- Embeddings obrigatórios.
- ML para estimar custo.
- Banco de dados externo.
- Reescrita do runtime de Goals para introduzir o lifecycle v2 nesta fatia.
