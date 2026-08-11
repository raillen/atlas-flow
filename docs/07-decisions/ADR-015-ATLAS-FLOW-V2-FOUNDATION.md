---
schema_version: 1
id: ADR-015-ATLAS-FLOW-V2-FOUNDATION
title: Fundação determinística do Atlas Flow v2
status: active
version: 1
audience: [developer, maintainer, agent]
visibility: internal
authority: canonical
source: human
owner: atlas-flow-maintainers
last_reviewed: 2026-08-11
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

1. A fundação v2 vive em `backend/atlas_flow/evolution/` e usa modelos Pydantic
   versionados, sem nomes de providers ou modelos no domínio.
2. `atlas.config.yaml` é o manifesto v2 opcional na migração; projetos legados
   continuam indexáveis com metadata derivada e recebem um warning explícito.
3. O registry e o grafo são projeções determinísticas. `atlas validate --write`
   e `atlas graph --write` os escrevem atomicamente em `.atlas/index/`.
4. Contexto é selecionado primeiro por `task maps`/`context packs`, depois por
   busca lexical transparente, com budget e exclusões explicáveis. Embeddings e
   banco externo não são requisitos.
5. Custos são append-only em `.atlas/intelligence/ledger.jsonl`; valores
   observados, estimados e desconhecidos permanecem distintos. O resumo é
   derivado e pode ser reconstruído.
6. O primeiro publisher é um builder estático mínimo, com índice de busca local
   e filtragem de visibilidade. Um gerador externo poderá ser adicionado por
   adapter sem mudar os contratos canônicos.

## Consequências

### Positivas

- O mesmo fluxo funciona em projetos novos e legados.
- CI e agentes podem consumir JSON sem depender da interface desktop.
- Índices, site e resumo podem ser apagados e regenerados.
- A política “observed > estimated > unknown” fica representada no contrato.

### Limitações aceitas

- A estimativa de tokens é heurística (`len(text) / 4`) até um tokenizer ser
  configurado.
- Retrieval de símbolos, delta context e dashboard visual ainda são fases
  posteriores do RFC.
- O builder inicial preserva Markdown em HTML escapado; ele é uma base segura,
  não um site de produção completo.

## Rejeitadas nesta fase

- Embeddings obrigatórios.
- ML para estimar custo.
- Banco de dados externo.
- Reescrita do runtime de Goals para introduzir o lifecycle v2.
