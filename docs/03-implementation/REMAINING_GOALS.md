# Remaining Goals — C# port

Status: `Atualizado em 2026-08-12`. Os Goals abaixo são o plano de trabalho
remanescente depois das fatias C# já portadas. `PLANNED` significa que o Goal
está salvo e pode ser executado; P25 é um Goal planejado explicitamente fora do
caminho crítico.

## O que já existe

O porte C# já possui Project inspection, Goal loading, ContextPlan, Project
Intelligence, Plan/Run, persistência SQLite, ACP transport, shell Avalonia e o
fluxo Discuss com Decision Rail e ledger. Essas fatias não são repetidas nos
Goals novos; os Goals P00–P12 continuam registrando a história e a revalidação
dos critérios do porte.

## Caminho crítico

| Goal | Entrega | Depende de |
| --- | --- | --- |
| P13-G01 | baseline de CI, gates, evidência e revisão do porte C# | P11, P12 |
| P14-G01 | schemas v2, registry e knowledge graph determinísticos | P13 |
| P15-G01 | serviço de documentação e Knowledge | P14 |
| P16-G01 | retrieval, context packs e impacto | P14 |
| P17-G01 | adaptação, verificação, evidência e readiness | P13, P14 |
| P18-G01 | runners ACP/CLI e MCP stdio | P17 |
| P19-G01 | routing, settings, budgets e usage intelligence | P18 |
| P20-G01 | AG-UI, eventos ao vivo e Discuss assistido | P17, P19 |
| P21-G01 | superfícies Avalonia restantes | P15, P17, P19, P20 |
| P22-G01 | hardening, recovery, acessibilidade e performance | P21 |
| P23-G01 | CLI C# para pessoas, agentes e CI | P15, P16, P19 |
| P24-G01 | packaging, compatibilidade, dogfooding e 1.0 | P22, P23 |

## Backlog fora do caminho crítico

P25-G01 mantém explícitas as extensões do AF-EVO-001 — AST/symbol retrieval,
delta context avançado, embeddings, dashboard, telemetria ampliada, MCP
HTTP/SSE e routing adaptativo. Ele está em `DRAFT` porque essas possibilidades
precisam de uma decisão de produto, métrica de benefício e orçamento de
complexidade antes de entrarem no caminho crítico.

## Regras de execução

- Cada Goal deve ser entregue como uma fatia vertical revisável, com testes e
  documentação no mesmo commit/PR.
- Não usar evidência histórica do Python/Tauri para fechar gates do C#.
- Não promover P25 enquanto P24 não tiver release e dogfooding reproduzíveis.
- Se um Goal alterar contrato compartilhado, registrar impacto antes de editar
  `src/AtlasFlow.Application/Contracts`.
- O estado `DONE` só pode ser gravado depois de build, testes, revisão e
  documentação verificáveis.

## Arquivos canônicos

- Goals: `.ai/goals/P13` até `.ai/goals/P25`.
- Estado resumido: [`PROJECT_STATE.md`](../../PROJECT_STATE.md).
- Roadmap histórico: [`docs/00-product/ROADMAP.md`](../00-product/ROADMAP.md).
- Gates: [`docs/04-quality/RELEASE_GATES.md`](../04-quality/RELEASE_GATES.md).
- Evolução de framework: [`ATLAS_FLOW_V2_FOUNDATION.md`](ATLAS_FLOW_V2_FOUNDATION.md).
