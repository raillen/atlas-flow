# Atlas-Flow — Plano de Implementação da Evolução do Framework

**Documento:** AF-EVO-001  
**Status:** Proposed / Implementation Guide  
**Versão:** 1.0  
**Data:** 2026-08-11  
**Objetivo:** orientar a evolução do Atlas-Flow de um framework de documentação orientado a humanos/LLMs para uma plataforma de **Knowledge, Context, Documentation Publishing, Token Economy e Project Intelligence** reutilizável entre projetos.

> **Implementation status — 2026-08-11:** a primeira fatia vertical está em
> `backend/atlas_flow/evolution/`. Ela cobre a fundação determinística de
> manifesto/metadata, registry, grafo, validação, task maps, context packs,
> impacto, token estimation, ledger de custo e builder estático mínimo. As
> fases posteriores — símbolos, delta context, routing avançado e dashboard
> visual — permanecem planejadas.

---

## 1. Resumo executivo

O Atlas-Flow deve evoluir de um conjunto de convenções documentais para uma **camada de engenharia do projeto** capaz de:

1. organizar documentação para usuários, desenvolvedores, operadores e agentes;
2. manter um grafo de conhecimento entre requisitos, decisões, código, testes, documentação, riscos e ownership;
3. entregar somente o contexto necessário a cada tarefa e agente;
4. reduzir o consumo de tokens e custo de LLMs;
5. registrar o custo aproximado/observado de cada tarefa;
6. manter um ledger cumulativo de custos e esforço do projeto;
7. gerar indicadores de qualidade, documentação, dívida técnica e eficiência de contexto;
8. publicar automaticamente um site de documentação vivo;
9. exibir Project Intelligence em dashboards simples dentro desse site;
10. validar consistência documental e arquitetural em CI;
11. servir como motor central, evitando copiar toda a lógica do framework para cada projeto consumidor.

### Visão resumida

```text
                         PROJECT
                            │
             ┌──────────────┴──────────────┐
             │                             │
            CODE                          DOCS
             │                             │
             └──────────────┬──────────────┘
                            │
                         ATLAS-FLOW
                            │
       ┌────────────────────┼─────────────────────┐
       │                    │                     │
 Knowledge Graph       Context Engine       Intelligence
       │                    │                     │
 Impact Analysis      Token Economy        Cost / Quality
       │                    │                     │
       └────────────────────┼─────────────────────┘
                            │
                       Docs Builder
                            │
                            ▼
                  Documentation Website
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    User Docs          Developer Docs      Dashboards
```

---

# 2. Goals oficiais do Atlas-Flow

O framework deve adotar seis pilares obrigatórios.

## 2.1 Documentation System

Criar e manter documentação orientada a diferentes leitores e intenções:

- usuários finais;
- contribuidores;
- desenvolvedores;
- mantenedores;
- operadores;
- integradores/API consumers;
- agentes/LLMs.

## 2.2 Knowledge Graph

Representar relações entre:

- requisitos;
- features;
- componentes;
- módulos;
- arquivos;
- símbolos;
- APIs;
- contratos;
- ADRs;
- RFCs;
- invariantes;
- riscos;
- testes;
- documentação;
- tarefas;
- releases;
- owners.

## 2.3 Context Engine

Selecionar o **mínimo contexto suficiente** para uma tarefa, por meio de:

- progressive context loading;
- summaries hierárquicos;
- task maps;
- context packs;
- symbol retrieval;
- change impact;
- delta context;
- negative context;
- budgets por tarefa/agente/modelo.

## 2.4 Token Economy

Reduzir custo e desperdício de contexto usando:

- orçamentos de tokens;
- exclusões explícitas;
- cache/delta context;
- resumos curtos;
- recuperação seletiva;
- dados estruturados compactos;
- stop conditions;
- métricas de eficiência.

## 2.5 Project Intelligence

Produzir visão cumulativa do projeto sobre:

- custo LLM;
- custo de CI/build;
- esforço humano-equivalente;
- custo de manutenção;
- dívida técnica;
- qualidade;
- bugs/retrabalho;
- riscos;
- cobertura documental;
- cobertura de testes;
- eficiência de contexto;
- evolução por release/componente/feature/modelo.

## 2.6 Documentation Publishing

Gerar um site documental vivo a partir da mesma fonte canônica utilizada por humanos e agentes, sem duplicação.

---

# 3. Non-goals iniciais

Para evitar overengineering, a primeira implementação **não deve**:

- depender de ML para estimativas de custo;
- exigir embeddings para funcionar;
- exigir banco de dados externo;
- exigir backend para o site documental;
- substituir Git como histórico;
- reproduzir ferramentas completas de observabilidade de produção;
- transformar métricas aproximadas em falsa precisão;
- obrigar todos os projetos a usar a mesma stack de aplicação;
- duplicar documentação pública e interna em árvores independentes.

Embeddings, ML e serviços externos podem ser adicionados posteriormente como plugins opcionais.

---

# 4. Princípios arquiteturais

## 4.1 Single Source of Truth

O conteúdo documental vive no repositório do projeto. O site é uma visão derivada.

## 4.2 Structured First

Quando um dado precisa ser processado, filtrado ou agregado, sua fonte primária deve ser estruturada (YAML/JSON/JSONL), e Markdown deve ser uma apresentação derivada quando necessário.

## 4.3 Minimum Sufficient Context

Nenhum agente deve carregar mais contexto que o necessário para executar a tarefa com segurança.

## 4.4 Progressive Disclosure

Navegação humana e contexto de LLM devem começar em representações compactas e aprofundar somente quando necessário.

## 4.5 Measured > Estimated > Unknown

Para custos e métricas:

1. usar valor observado quando disponível;
2. usar estimativa/faixa quando necessário;
3. marcar claramente como desconhecido quando não houver base suficiente.

## 4.6 No False Precision

Exibir:

```text
Estimated API cost: US$ 1.80–3.10
Confidence: Medium
```

em vez de inventar:

```text
Cost: US$ 2.47
```

## 4.7 Engine Centralizado

Projetos consumidores guardam principalmente:

- configuração;
- documentação;
- manifests;
- dados Atlas;
- caches locais opcionais.

A lógica reutilizável permanece no Atlas-Flow.

## 4.8 Automation Friendly

Todo recurso deve ser utilizável tanto por humanos quanto por agentes através de CLI e formatos estruturados.

## 4.9 Deterministic First

Antes de soluções probabilísticas, preferir:

- schemas;
- metadata;
- índices;
- grafos explícitos;
- busca textual;
- AST;
- heurísticas transparentes;
- estatísticas simples.

---

# 5. Arquitetura alvo do repositório Atlas-Flow

```text
atlas-flow/
├── packages/
│   ├── core/
│   │   ├── registry/
│   │   ├── graph/
│   │   ├── schemas/
│   │   ├── validation/
│   │   └── events/
│   │
│   ├── context/
│   │   ├── planner/
│   │   ├── retrieval/
│   │   ├── summaries/
│   │   ├── packs/
│   │   ├── task-maps/
│   │   ├── impact/
│   │   ├── budget/
│   │   └── delta/
│   │
│   ├── intelligence/
│   │   ├── costs/
│   │   ├── effort/
│   │   ├── quality/
│   │   ├── debt/
│   │   ├── risk/
│   │   ├── coverage/
│   │   └── metrics/
│   │
│   ├── docs/
│   │   ├── builder/
│   │   ├── navigation/
│   │   ├── coverage/
│   │   ├── publishing/
│   │   └── adapters/
│   │
│   ├── agents/
│   │   ├── roles/
│   │   ├── routing/
│   │   ├── workflows/
│   │   └── policies/
│   │
│   └── cli/
│
├── apps/
│   └── docs-site/
│
├── templates/
│   ├── project/
│   ├── docs/
│   ├── agents/
│   └── workflows/
│
├── schemas/
├── examples/
├── tests/
└── docs/
```

> Caso a arquitetura atual do Atlas-Flow seja diferente, esta árvore deve ser adaptada sem exigir uma reescrita desnecessária. Os **limites de domínio** importam mais que os nomes físicos das pastas.

---

# 6. Estrutura canônica esperada nos projetos consumidores

Congelar uma taxonomia estável.

```text
project/
├── AGENTS.md
├── README.md
├── docs/
│   ├── ATLAS.md
│   ├── USER_ATLAS.md
│   ├── DEVELOPER_ATLAS.md
│   ├── ARCHITECTURE_ATLAS.md
│   ├── OPERATIONS_ATLAS.md
│   ├── AGENT_ATLAS.md
│   │
│   ├── 00-product/
│   ├── 01-user/
│   ├── 02-onboarding/
│   ├── 03-architecture/
│   ├── 04-data/
│   ├── 05-api-contracts/
│   ├── 06-ui-ux/
│   ├── 07-developer/
│   ├── 08-implementation/
│   ├── 09-extensions/
│   ├── 10-testing/
│   ├── 11-quality/
│   ├── 12-performance/
│   ├── 13-security/
│   ├── 14-operations/
│   ├── 15-support/
│   ├── 16-release/
│   ├── 17-governance/
│   ├── 18-decisions/
│   ├── 19-research/
│   ├── 20-reference/
│   │
│   ├── adr/
│   ├── rfc/
│   ├── specs/
│   ├── migrations/
│   ├── examples/
│   ├── benchmarks/
│   ├── reports/
│   │
│   └── _meta/
│       ├── project.yaml
│       ├── registry.yaml
│       ├── document-map.yaml
│       ├── knowledge-graph.yaml
│       ├── compact-graph.json
│       ├── change-impact.yaml
│       ├── ownership.yaml
│       ├── query-packs.yaml
│       ├── token-economy.yaml
│       ├── terminology.yaml
│       ├── invariants.yaml
│       ├── context-packs/
│       ├── task-maps/
│       └── schemas/
│
└── .atlas/
    ├── cache/
    ├── index/
    ├── state/
    ├── intelligence/
    │   ├── ledger.jsonl
    │   ├── project-summary.json
    │   ├── baselines.json
    │   ├── estimates.json
    │   └── debt.jsonl
    └── changes/
```

---

# 7. Arquitetura documental por audiência

## 7.1 User Documentation

Adotar quatro tipos de documentação:

```text
01-user/
├── getting-started/
├── tutorials/
├── how-to/
├── reference/
├── concepts/
└── troubleshooting/
```

### Regra

- **Tutorial:** ensina aprendendo/fazendo.
- **How-to:** resolve uma tarefa específica.
- **Reference:** descreve comportamento/opções/contratos.
- **Explanation/Concept:** explica por que e como algo funciona.

Evitar um único `USER_GUIDE.md` monolítico.

## 7.2 Onboarding

```text
02-onboarding/
├── user/
├── contributor/
└── maintainer/
```

Contributor onboarding mínimo:

```text
00-start-here.md
01-development-environment.md
02-build-project.md
03-run-tests.md
04-codebase-tour.md
05-make-first-change.md
06-submit-pr.md
07-common-problems.md
```

## 7.3 Developer Documentation

Cobrir explicitamente:

- setup;
- build;
- debug;
- profiling;
- arquitetura prática;
- codebase tour;
- convenções;
- error handling;
- logging;
- testes;
- tarefas recorrentes;
- extensibilidade.

Criar obrigatoriamente quando aplicável:

```text
07-developer/CODEBASE_TOUR.md
07-developer/DEBUGGING_PLAYBOOK.md
07-developer/tasks/
```

## 7.4 Operations Documentation

Cobrir:

```text
14-operations/
├── deployment/
├── configuration/
├── observability/
├── runbooks/
├── backup/
├── recovery/
├── performance/
├── incidents/
└── maintenance/
```

## 7.5 Support Documentation

```text
15-support/
├── support-policy.md
├── reporting-bugs.md
├── diagnostics.md
├── known-issues.md
├── faq.md
└── collecting-logs.md
```

---

# 8. Document metadata v2

Documentos relevantes devem suportar front matter estruturado.

Exemplo:

```yaml
---
id: DOC-ARCH-014
title: Timeline Architecture
status: active
version: 3
audience:
  - developer
  - maintainer
  - agent
visibility: internal
authority: canonical
source: human
owner: editor-platform
last_reviewed: 2026-08-11
review_interval: 180d
estimated_tokens: 1830
risk: medium
tags:
  - timeline
  - architecture
related:
  - SPEC-TIMELINE-003
  - ADR-021
invariants:
  - INV-014
  - INV-021
---
```

### Campos recomendados

- `id`
- `title`
- `status`
- `version`
- `audience`
- `visibility`
- `authority`
- `source`
- `owner`
- `last_reviewed`
- `review_interval`
- `estimated_tokens`
- `risk`
- `tags`
- `related`
- `invariants`

### Valores importantes

`authority`:

- `canonical`
- `derived`
- `informative`

`source`:

- `human`
- `code`
- `generated`
- `external`

`status`:

- `draft`
- `active`
- `review-needed`
- `deprecated`
- `archived`

---

# 9. Documentation freshness

Implementar verificação de freshness.

Estados derivados:

```text
ACTIVE
NEEDS REVIEW
STALE
```

### Regras iniciais sugeridas

- `ACTIVE`: dentro do intervalo de revisão.
- `NEEDS REVIEW`: intervalo vencido.
- `STALE`: intervalo vencido + mudanças detectadas nos componentes relacionados após a última revisão.

### CLI

```bash
atlas docs freshness
atlas docs freshness --json
```

---

# 10. Invariantes e anti-patterns

## 10.1 Invariants

Criar fonte canônica estruturada:

```yaml
# docs/_meta/invariants.yaml
- id: INV-001
  scope: renderer
  statement: Renderer never mutates project state.
  severity: critical
  related_docs:
    - DOC-ARCH-RENDER-001
```

Além de uma representação humana em:

```text
docs/03-architecture/INVARIANTS.md
```

## 10.2 Anti-patterns

Criar:

```text
docs/03-architecture/ANTI_PATTERNS.md
```

Cada item deve conter:

- anti-pattern;
- motivo;
- alternativa correta;
- componentes afetados;
- severidade.

## 10.3 Rejected approaches

Criar:

```text
docs/18-decisions/REJECTED_APPROACHES.md
```

Evita reabrir decisões já analisadas sem nova evidência.

---

# 11. Task Maps

Task Maps respondem:

> “Quero fazer X. O que preciso entender, alterar e validar?”

Exemplo:

```yaml
id: TASKMAP-add-transition
intent: add-transition
risk: medium

read:
  required:
    - DOC-TIMELINE-SUMMARY
    - SPEC-TRANSITION
  optional:
    - ADR-RENDER-021

touch:
  likely:
    - src/timeline/transitions/**
    - tests/transitions/**

usually_dont_touch:
  - src/auth/**
  - src/updater/**

verify:
  - unit-tests
  - transition-e2e
  - serialization-regression

documentation:
  - user-how-to-transitions
  - developer-task-add-transition
```

### Requisitos

- formato compacto;
- IDs estáveis;
- ligação com risk map;
- ligação com context pack;
- possível geração assistida, mas validação humana/CI.

---

# 12. Context Packs

Context Packs definem contexto recomendado por intenção.

```yaml
id: CONTEXT-add-transition
intent: add-transition

include:
  - DOC-TIMELINE-SUMMARY
  - SPEC-TRANSITION
  - SRC-transition-interface
  - TEST-transition

optional:
  - ADR-render-architecture

exclude:
  - authentication
  - updater
  - telemetry

budget:
  target_tokens: 12000
  max_tokens: 20000
```

### Regras

1. incluir o menor conjunto suficiente;
2. distinguir `required` de `optional`;
3. suportar exclusões;
4. suportar budgets;
5. registrar justificativa para itens caros;
6. permitir overrides por agente/modelo.

---

# 13. Progressive Context Loading

Implementar níveis formais:

## L0 — Router

- `AGENTS.md`
- `ATLAS.md`
- project manifest

## L1 — Summaries

- domain summaries;
- compact graph;
- task map.

## L2 — Working Context

- specs;
- context pack;
- documentação específica.

## L3 — Source Context

- símbolos;
- arquivos relevantes;
- testes relacionados.

## L4 — Deep Reference

- ADRs antigos;
- RFCs extensas;
- pesquisas;
- histórico;
- benchmarks antigos.

### Stop condition

O Context Engine deve parar o retrieval quando:

- todos os requisitos da task map estiverem cobertos;
- riscos necessários estiverem compreendidos;
- interfaces afetadas estiverem localizadas;
- testes relevantes estiverem identificados;
- continuar buscando apresentar baixo ganho marginal.

---

# 14. Summaries hierárquicos

Implementar três níveis de resumo:

```text
Project Summary
    ↓
Domain Summary
    ↓
Document/Module Summary
    ↓
Full source/document
```

### Formato sugerido para Agent Summary

```markdown
## Agent Summary

**Purpose:**

**Read when:**

**Key rules:**

**Do not break:**

**Dependencies:**

**Related tests:**

**Read full document when:**
```

Objetivo inicial: 100–300 tokens por resumo, quando possível.

---

# 15. Symbol Retrieval

O Context Engine deve preferir recuperar símbolos relevantes em vez de arquivos completos.

### Fase inicial

- integração com ferramentas já existentes de linguagem/AST;
- fallback para busca textual;
- armazenamento de symbol → file → tests → docs.

### Exemplo

Consulta:

```text
Timeline.addClip
```

Retornar:

```text
Definition
Relevant imports
Interface
Callers relevantes
Tests relacionados
Docs relacionadas
Invariants relacionados
```

Evitar enviar 2.000 linhas quando 150 resolvem a tarefa.

---

# 16. Negative Context

Permitir declarar áreas normalmente irrelevantes para certas tarefas.

```yaml
intent: timeline-transition
irrelevant:
  - authentication
  - telemetry
  - updater
```

O mecanismo **não é uma proibição absoluta**. Caso análise de impacto descubra dependência real, a exclusão deve ser ignorada e registrada.

---

# 17. Delta Context

Criar identificador/hash de contexto.

```yaml
context_id: CTX-a91f27
base_commit: abc123
created_at: 2026-08-11T17:00:00-03:00
```

Em sessões posteriores, preferir:

```text
base context
+
changes since base
```

em vez de recarregar tudo.

### Arquivos derivados

```text
.atlas/changes/latest.json
.atlas/changes/latest.md
```

---

# 18. Change Impact Index

Implementar relações:

```text
component → files
component → tests
component → docs
component → contracts
component → invariants
component → owners
component → risk
```

Exemplo de resposta:

```text
src/project/schema.ts

Impact: HIGH

Read:
- project-schema.md
- serialization.md
- migration-policy.md

Possible updates:
- migrations/
- compatibility matrix
- API reference
- tests/project-format
```

### CLI

```bash
atlas impact src/project/schema.ts
atlas impact --changed
atlas impact --json
```

---

# 19. Token Economy Policy

Criar:

```text
docs/_meta/TOKEN_ECONOMY.md
```

Regras mínimas:

1. nunca carregar o repositório inteiro por padrão;
2. começar pelo router;
3. preferir summaries a documentos completos;
4. usar task maps/context packs;
5. preferir símbolos a arquivos;
6. carregar somente testes relacionados;
7. consultar ADRs somente quando a decisão for relevante;
8. preferir diff a arquivo completo;
9. excluir build/generated/vendor/cache;
10. evitar documentos deprecated no retrieval normal;
11. usar delta context em tarefas sequenciais;
12. encerrar retrieval quando houver contexto suficiente.

---

# 20. Context Budgets

Perfis iniciais:

```yaml
budgets:
  small:
    target: 8000
    max: 12000

  medium:
    target: 20000
    max: 32000

  large:
    target: 48000
    max: 80000
```

Os valores são defaults configuráveis, não limites universais.

### Seleção automática sugerida

Considerar:

- complexidade;
- risco;
- quantidade de componentes;
- mudança de contrato;
- mudança de persistência;
- necessidade de decisão arquitetural.

---

# 21. Context Profiles por agente

Exemplos:

```yaml
explorer:
  focus:
    - summaries
    - graph
    - search

architect:
  focus:
    - architecture
    - ADRs
    - RFCs
    - invariants
    - risks

implementer:
  focus:
    - specs
    - source
    - interfaces
    - tests

reviewer:
  focus:
    - diff
    - invariants
    - tests
    - affected contracts

security-reviewer:
  focus:
    - threat-model
    - auth
    - permissions
    - sensitive data
    - dependency changes
```

---

# 22. Context Planner CLI

Implementar:

```bash
atlas context "add transition"
atlas context "fix project corruption" --budget 16000
atlas context "schema migration" --profile reviewer
atlas context "shader bug" --json
```

### Saída humana esperada

```text
Intent: add-transition
Risk: MEDIUM
Budget: 12k target / 20k max

Recommended context:
1. AGENTS.md
2. timeline/SUMMARY.md
3. transitions/SPEC.md
4. src/timeline/transitions/*
5. tests/transitions/*

Estimated context: 9.4k tokens
Excluded: auth, updater, telemetry
```

### Saída machine-readable

JSON estável para consumo por agentes/orquestradores.

---

# 23. Project Intelligence — visão geral

Criar um domínio separado responsável por agregar métricas sem contaminar as fontes documentais.

Categorias:

- cost;
- effort;
- context;
- quality;
- documentation;
- testing;
- debt;
- risk;
- release;
- velocity.

---

# 24. Cost Intelligence

## 24.1 Princípio

Toda tarefa concluída deve produzir um registro de custo.

### Fluxo

```text
PLAN
  ↓
ESTIMATE
  ↓
IMPLEMENT
  ↓
TEST / REVIEW
  ↓
MEASURE
  ↓
FINAL COST REPORT
  ↓
UPDATE LEDGER
  ↓
UPDATE PROJECT SUMMARY
```

## 24.2 Dimensões de custo

### Compute Cost

- APIs LLM;
- CI;
- build;
- storage;
- testes externos;
- serviços utilizados.

### Effort Cost

- esforço humano-equivalente;
- iterações;
- complexidade;
- retrabalho.

### Context Cost

- tokens loaded;
- tokens generated;
- cached tokens;
- avoided tokens;
- retrieval overhead.

### Maintenance Cost

Estimativa qualitativa/quantitativa de:

- novas dependências;
- superfície de testes;
- complexidade;
- novos contratos;
- dívida técnica;
- aumento de manutenção futura.

---

# 25. Task Cost Ledger

Fonte primária:

```text
.atlas/intelligence/ledger.jsonl
```

Um registro por linha.

### Schema inicial sugerido

```json
{
  "schema_version": 1,
  "task_id": "TASK-142",
  "title": "Implement nested compositions",
  "type": "feature",
  "component": ["timeline"],
  "release": "0.4.0",
  "date_started": "2026-08-11T14:00:00-03:00",
  "date_finished": "2026-08-11T17:00:00-03:00",
  "complexity": "medium",
  "risk": "medium",
  "estimate": {
    "effort_hours": {"min": 3.0, "max": 4.0},
    "cost_usd": {"min": 1.5, "max": 2.5},
    "confidence": "medium"
  },
  "observed": {
    "tokens": {
      "input": 184230,
      "output": 31210,
      "cached": 96440,
      "avoided_estimate": 120000
    },
    "llm": [
      {
        "provider": "openai",
        "model": "example-model",
        "billing_mode": "api",
        "sessions": 3,
        "cost_usd": 1.83
      }
    ],
    "ci_cost_usd": 0.08,
    "effort_hours_equivalent": {"min": 3.5, "max": 5.0}
  },
  "changes": {
    "files_created": 7,
    "files_modified": 14,
    "files_deleted": 0,
    "tests_added": 16,
    "docs_created": 2,
    "docs_updated": 5
  },
  "result": {
    "tests_passed": 194,
    "tests_failed": 0
  },
  "maintenance_cost_score": 4,
  "confidence": "high"
}
```

---

# 26. Billing modes

Suportar explicitamente:

```text
api
subscription
free
local
unknown
```

### Regra

Para assinaturas:

- `direct_incremental_cost` pode ser zero;
- custo rateado de assinatura deve ser opcional;
- nunca misturar rateio e custo incremental sem rótulo claro.

Exemplo:

```yaml
billing_mode: subscription
direct_incremental_cost_usd: 0
allocated_subscription_cost_usd: 0.42
allocation_method: monthly-active-time
```

---

# 27. Cost Score

Além de valores monetários, permitir scores de 1–10:

```text
Implementation Cost    4/10
Maintenance Cost       7/10
Runtime Cost           2/10
Documentation Cost     3/10
Testing Cost           5/10
Overall Cost Score     4.2/10
```

### Uso

- comparar alternativas de ADR;
- identificar componentes caros;
- priorizar refactors;
- explicar trade-offs.

Scores devem ter regras documentadas e configuráveis.

---

# 28. Estimated vs Observed

Sempre guardar ambos.

```text
Estimated effort: 3–4h
Observed equivalent effort: 4.8h
Variance: +37%
```

Isso permite calibrar estimativas do próprio projeto ao longo do tempo.

### Estatística inicial

Não usar ML.

Começar com:

- mediana;
- percentis;
- faixa interquartil;
- média móvel opcional;
- tipo de tarefa;
- componente;
- risco;
- complexidade;
- histórico semelhante.

---

# 29. Technical Debt Ledger

Criar:

```text
.atlas/intelligence/debt.jsonl
```

Exemplo:

```json
{
  "id": "DEBT-017",
  "introduced_by": "TASK-198",
  "component": "renderer",
  "reason": "Release blocker",
  "severity": "medium",
  "remediation_hours": {"min": 3, "max": 5},
  "status": "open"
}
```

Dashboard:

```text
Technical Debt
17 open items
Estimated remediation: 42–67 engineering hours
```

---

# 30. Cost of Quality / Bug Cost

Permitir ligar defeito e reparo:

```yaml
bug_id: BUG-149
introduced_by: TASK-122
fixed_by: TASK-149
repair_cost_usd: 3.20
repair_effort_hours: 2.4
```

Métricas derivadas:

- repair cost por componente;
- rework ratio;
- bug cost por release;
- defeitos por feature;
- custo de qualidade.

---

# 31. Context Efficiency Metrics

Registrar quando possível:

```text
Potential context
Actual loaded context
Cached context
Avoided context
Output tokens
```

### Métricas

#### Context Reduction

```text
1 - actual_loaded / potential_context
```

#### CER — Context Efficiency Ratio

Versão inicial aproximada:

```text
useful_context / loaded_context
```

`useful_context` pode ser inicialmente inferido de documentos/símbolos efetivamente citados ou tocados pela tarefa. Deve ser marcado como estimativa.

### Dashboard exemplo

```text
Potential context: 41.7M
Actually loaded:   19.3M
Avoided:           22.4M
Reduction:          53.7%
```

---

# 32. Documentation Coverage

Criar mecanismo parecido com coverage de código.

## 32.1 Por domínio

```text
Product          100%
Architecture      94%
User Docs         76%
API               89%
Troubleshooting   61%
Operations        83%
```

## 32.2 Por feature

```text
Feature             Code  Tests  User Docs  Dev Docs
Timeline              ✓     ✓       ✓          ✓
Transitions           ✓     ✓       ✓          ✓
Motion Tracking       ✓     ✓       ✗          ✓
Audio Ducking         ✓     ✗       ✓          ✗
```

### Fonte

Coverage deve ser derivada de:

- registry;
- feature manifest;
- relations;
- task completion metadata.

Não tentar inferir tudo apenas por nome de arquivo.

---

# 33. Definition of Done v2

Uma feature/tarefa deve declarar quais impactos documentais são aplicáveis.

```yaml
documentation_impact:
  user: true
  developer: true
  api: false
  migration: false
  troubleshooting: false
```

Checklist potencial:

```text
implementation          ✓
tests                   ✓
user docs               ✓
developer docs          ✓
API docs                N/A
migration docs          N/A
changelog               ✓
security review         ✓
accessibility review    ✓
Atlas/registry          ✓
cost report             ✓
knowledge graph         ✓
doc site build          ✓
```

### Regra

Itens não aplicáveis devem ser `N/A`, não simplesmente omitidos.

---

# 34. Novo lifecycle obrigatório de tarefa

Fluxo alvo:

```text
PLAN
  ↓
ESTIMATE
  ↓
CLASSIFY RISK / COMPLEXITY
  ↓
SELECT MODEL / AGENT PROFILE
  ↓
SELECT CONTEXT
  ↓
IMPLEMENT
  ↓
TEST
  ↓
REVIEW
  ↓
UPDATE DOCUMENTATION
  ↓
MEASURE
  ↓
UPDATE COST LEDGER
  ↓
UPDATE DEBT / QUALITY IF NEEDED
  ↓
UPDATE KNOWLEDGE GRAPH
  ↓
UPDATE PROJECT INTELLIGENCE
  ↓
VALIDATE DOCUMENTATION SITE
  ↓
COMPLETE
```

---

# 35. Project Summary

Gerar automaticamente:

```text
.atlas/intelligence/project-summary.json
```

Campos agregados:

- tasks completed;
- total/estimated LLM cost;
- total tokens;
- cached tokens;
- avoided tokens;
- CI cost;
- effort equivalent;
- bugs fixed;
- features delivered;
- technical debt;
- documentation coverage;
- test coverage (quando disponível);
- cost by component;
- cost by release;
- cost by model/provider;
- context efficiency;
- estimation variance.

---

# 36. Documentation Website

## 36.1 Regra principal

Não manter duas documentações.

```text
Canonical docs + metadata
            ↓
        Docs Builder
            ↓
      Documentation Site
```

## 36.2 Requisitos do site

- estático por padrão;
- search;
- breadcrumbs;
- versioning opcional;
- generated navigation;
- related docs;
- API reference quando aplicável;
- tutorials/how-to/reference/concepts;
- internal/public visibility;
- documentation freshness;
- badges de status;
- compatibility matrix;
- changelog;
- Project Intelligence;
- dashboard simples.

## 36.3 Tecnologia

A implementação deve abstrair o gerador do site.

Interface conceitual:

```ts
interface DocsSiteAdapter {
  build(input: DocsBuildInput): Promise<DocsBuildResult>
  validate(input: DocsBuildInput): Promise<ValidationResult>
}
```

Assim Atlas-Flow pode suportar futuramente múltiplos targets.

### Primeira implementação

Escolher apenas **um** gerador estático para evitar dispersão. Requisitos:

- Markdown/MDX;
- build rápido;
- boa navegação;
- busca estática/local;
- possibilidade de páginas geradas por JSON;
- deploy simples.

A escolha concreta deve ser registrada em ADR própria.

---

# 37. Documentation Manifest

Criar `docs/_meta/project.yaml` ou `atlas.config.yaml` na raiz.

Exemplo:

```yaml
schema_version: 2

project:
  name: Rakord
  version: 0.4.0

atlas:
  docs_root: docs
  data_root: .atlas

documentation:
  title: Rakord Documentation
  default_visibility: internal

publishing:
  public:
    - 00-product
    - 01-user
    - 05-api-contracts
    - 15-support
    - 20-reference

  internal:
    - 03-architecture
    - 07-developer
    - 08-implementation
    - 13-security
    - 17-governance
    - 18-decisions

intelligence:
  enabled: true
  dashboard: true

context:
  default_budget: medium
```

---

# 38. Navegação gerada por metadata

Não manter menus manualmente quando possível.

```yaml
id: DOC-USER-014
title: Transitions
section: user
category: editing
order: 30
```

Gera:

```text
Editing
├── Timeline
├── Clips
├── Transitions
└── Effects
```

O ATLAS e os sub-Atlases continuam sendo mapas humanos/LLM, mas podem utilizar os mesmos metadados para evitar inconsistência.

---

# 39. ATLAS como intent router

O `ATLAS.md` deve priorizar intenção.

```text
I want to...

USE
→ Install the application
→ Learn the basics
→ Learn a feature
→ Troubleshoot a problem

DEVELOP
→ Set up development
→ Understand the codebase
→ Implement a feature
→ Fix a bug
→ Add a test
→ Create a plugin

OPERATE
→ Deploy
→ Diagnose production
→ Recover data
→ Perform a release

AI / AGENTS
→ Explore the project
→ Plan a change
→ Implement safely
→ Review a change
```

---

# 40. Sub-Atlases

Criar quando o projeto tiver documentação suficiente:

```text
USER_ATLAS.md
DEVELOPER_ATLAS.md
ARCHITECTURE_ATLAS.md
OPERATIONS_ATLAS.md
AGENT_ATLAS.md
```

Não duplicar conteúdo. Eles são mapas/roteadores.

---

# 41. Project Intelligence Dashboard

Adicionar ao site:

```text
Project Intelligence
├── Overview
├── Costs
├── LLM Usage
├── Context Efficiency
├── Documentation Coverage
├── Quality
├── Technical Debt
├── Risk
└── Development History
```

## 41.1 Implementação

Preferir:

```text
JSON estático gerado no build
+
visualizações client-side
```

Sem backend inicialmente.

## 41.2 Filtros

Suportar progressivamente:

- período;
- release;
- milestone;
- component;
- feature;
- task type;
- model;
- provider;
- agent profile;
- complexity;
- risk;
- status.

## 41.3 Visões prioritárias para MVP

1. custo total do projeto;
2. custo por tarefa;
3. custo por componente;
4. custo por release;
5. token usage;
6. context reduction;
7. documentation coverage;
8. technical debt.

---

# 42. Compatibility, Migration e Lifecycle

Criar quando aplicável:

```text
20-reference/COMPATIBILITY_MATRIX.md
migrations/
16-release/DEPRECATION_POLICY.md
16-release/SUPPORT_LIFECYCLE.md
```

Estados de feature/API:

```text
experimental
preview
stable
deprecated
removed
```

Changelog responde **o que mudou**. Migration guide responde **o que o usuário/dev precisa fazer**.

---

# 43. API e extensibilidade

Quando o projeto expuser API/plugins:

```text
05-api-contracts/
├── overview/
├── guides/
├── examples/
└── reference/

09-extensions/
├── overview.md
├── plugin-lifecycle.md
├── permissions.md
├── manifest.md
├── api.md
├── examples/
└── distribution.md
```

Regra:

- API reference preferencialmente derivada do código;
- guides e conceitos escritos manualmente;
- exemplos executáveis/testáveis em CI.

---

# 44. Troubleshooting e Diagnostics

Criar formato padrão de troubleshooting:

```text
Symptom
Possible causes
Diagnosis
Fix
Verification
Relevant logs
Related issues
```

Projetos compatíveis devem considerar CLI:

```bash
app doctor
app diagnose
```

Atlas-Flow deve permitir documentar a saída esperada e ligar diagnóstico a troubleshooting entries.

---

# 45. Testing Documentation

Criar domínio explícito:

```text
10-testing/
├── strategy.md
├── unit.md
├── integration.md
├── e2e.md
├── visual.md
├── performance.md
├── security.md
├── fixtures.md
├── mocking.md
└── writing-tests.md
```

Deve existir uma resposta clara à pergunta:

> “Como escrever um teste correto neste projeto?”

---

# 46. Performance Budgets

Além de benchmarks, suportar orçamento de performance:

```yaml
startup_ms: 2000
idle_ram_mb: 250
interaction_p95_ms: 16
project_save_p95_ms: 500
```

Benchmarks verificam expectativas, não apenas coletam números.

---

# 47. UI/UX, UX Writing e Accessibility

Adicionar quando aplicável:

```text
06-ui-ux/content/UX_COPY_GUIDE.md
06-ui-ux/accessibility/
```

Cobrir:

- terminologia;
- labels;
- erros;
- empty states;
- confirmações;
- destructive actions;
- keyboard navigation;
- screen readers;
- contrast;
- motion;
- accessibility testing.

---

# 48. Security e Privacy Documentation

Quando aplicável:

```text
SECURITY.md
PRIVACY.md
13-security/security-reporting.md
13-security/permissions.md
13-security/data-storage.md
13-security/telemetry.md
13-security/threat-model.md
```

Separar documentação interna de engenharia da documentação pública de segurança/privacidade.

---

# 49. Data Documentation

Quando houver persistência:

```text
04-data/
├── model.md
├── schemas/
├── persistence.md
├── migrations.md
├── retention.md
├── import-export.md
└── backup.md
```

O Change Impact Index deve tratar alterações de schema como risco elevado por padrão.

---

# 50. Release Documentation

```text
16-release/
├── process.md
├── checklist.md
├── versioning.md
├── channels.md
├── signing.md
├── rollback.md
├── deprecation-policy.md
└── support-lifecycle.md
```

CLI futura:

```bash
atlas release check
```

---

# 51. Legal e distribuição

Adicionar somente quando aplicável:

```text
20-reference/legal/
├── licensing.md
├── third-party-licenses.md
├── trademarks.md
└── redistribution.md
```

---

# 52. CLI alvo

## Core

```bash
atlas init
atlas validate
atlas doctor
atlas graph
atlas impact
```

## Documentation

```bash
atlas docs build
atlas docs validate
atlas docs coverage
atlas docs freshness
atlas docs serve
```

## Context

```bash
atlas context "<intent>"
atlas context "<intent>" --budget 16000
atlas context "<intent>" --profile reviewer
atlas context "<intent>" --json
```

## Intelligence

```bash
atlas cost task TASK-142
atlas cost project
atlas cost release v0.4
atlas cost component renderer
atlas cost compare v0.3 v0.4

atlas intelligence summary
atlas intelligence build
atlas intelligence export --json
```

## Debt / Quality

```bash
atlas debt list
atlas debt summary
atlas quality summary
```

---

# 53. CLI output conventions

Toda ação relevante deve suportar:

```text
human-readable
JSON
```

Exemplo:

```bash
atlas impact --json
```

Isso permite integração simples com Codex, Claude Code, Gemini, CI e orquestradores.

### Regras

- exit codes estáveis;
- schemas versionados;
- stdout para dados;
- stderr para diagnostics;
- `--quiet` quando necessário;
- `--json` sem texto decorativo.

---

# 54. Eventos internos do Atlas-Flow

Criar um modelo simples de eventos para desacoplar módulos.

Exemplos:

```text
TaskStarted
TaskEstimated
ContextPlanned
ContextLoaded
TaskCompleted
DocsChanged
CostRecorded
DebtRecorded
GraphUpdated
ReleaseCompleted
```

Inicialmente pode ser apenas um event bus in-process.

Benefícios:

- intelligence escuta `TaskCompleted`;
- docs escuta `DocsChanged`;
- graph escuta mudanças de registry;
- future plugins podem consumir os mesmos eventos.

---

# 55. Schema versioning

Todos os JSON/YAML estruturados devem conter `schema_version`.

Exemplo:

```yaml
schema_version: 1
```

O Atlas-Flow deve:

- validar versão;
- rejeitar incompatibilidades claras;
- oferecer migrations quando possível;
- documentar breaking changes.

---

# 56. Validation Engine

`atlas validate` deve evoluir para validar:

### Structure

- arquivos canônicos;
- IDs únicos;
- metadata válida;
- schemas.

### Links

- links internos;
- references;
- IDs inexistentes;
- orphan docs.

### Graph

- nodes sem alvo;
- relações inválidas;
- ciclos quando proibidos;
- owner ausente em componentes críticos.

### Documentation

- freshness;
- missing required docs;
- coverage;
- visibility inconsistencies.

### Task completion

- DoD;
- cost record;
- docs impact;
- graph update.

### Site

- build;
- broken navigation;
- unavailable assets.

---

# 57. CI integration

Pipeline mínimo:

```text
lint
  ↓
tests
  ↓
atlas validate
  ↓
atlas docs validate
  ↓
atlas docs build
  ↓
atlas intelligence build
```

Em PRs, adicionar opcionalmente:

```text
atlas impact --changed
atlas docs coverage --changed
```

### Regra

Não tornar o CI impossível de usar no início. Checks devem ser introduzidos em modo:

```text
report-only → warning → required
```

---

# 58. Project bootstrap

`atlas init` deve criar:

- estrutura documental mínima;
- manifests;
- schemas;
- AGENTS.md template;
- ATLAS.md;
- user/developer/agent subatlas skeleton;
- intelligence store;
- token economy defaults;
- CI example;
- docs site starter/config.

### Perfis

```bash
atlas init --profile library
atlas init --profile desktop-app
atlas init --profile web-app
atlas init --profile api
atlas init --profile game
atlas init --profile cli
```

Perfis apenas ajustam defaults; não criam frameworks diferentes.

---

# 59. Documentation site visibility

Suportar pelo menos:

```text
public
internal
private
```

Para build público, documentos internos não devem ser copiados para assets ou índices de busca.

Essa regra deve ser testada.

---

# 60. Search strategy

MVP:

1. metadata;
2. exact IDs;
3. full-text lexical search;
4. tags;
5. graph relations.

Posteriormente:

6. BM25 melhorado;
7. embeddings opcionais;
8. hybrid retrieval.

O funcionamento básico nunca deve depender de embeddings.

---

# 61. Caching

Criar `.atlas/cache/` para:

- parsed front matter;
- token estimates;
- graph compilation;
- file hashes;
- summaries derivadas;
- symbol index;
- docs build intermediate metadata.

Cache deve ser regenerável e nunca ser fonte canônica.

---

# 62. Token estimation

Criar interface abstrata:

```ts
interface TokenEstimator {
  estimate(text: string, model?: string): number
}
```

MVP pode usar estimativa aproximada quando tokenizer específico não estiver disponível.

O relatório deve indicar o método:

```yaml
method: exact-tokenizer
```

ou:

```yaml
method: heuristic
confidence: medium
```

---

# 63. Model / Provider Registry

Para cost intelligence:

```yaml
providers:
  openai:
    models: {}
  anthropic:
    models: {}
  google:
    models: {}
```

Não hardcode preços diretamente em lógica de domínio.

Criar tabela/config versionada e atualizável.

Campos:

- provider;
- model;
- effective date;
- input price;
- output price;
- cached input price;
- billing unit;
- source/verification metadata.

Quando preços forem desconhecidos, custo monetário deve ser `unknown`, preservando métricas de tokens.

---

# 64. Cost estimation pipeline

Ordem de confiança:

1. dados de usage/billing retornados pelo provider;
2. tokens observados × price registry;
3. token estimate × price registry;
4. subscription allocation opcional;
5. unknown.

Guardar sempre:

```yaml
cost_source: provider_usage | calculated | estimated | allocated | unknown
confidence: high | medium | low
```

---

# 65. Project baselines

Criar:

```text
.atlas/intelligence/baselines.json
```

Exemplos:

```json
{
  "task_types": {
    "ui-feature": {
      "median_effort_hours": 1.8,
      "sample_size": 14
    },
    "database-migration": {
      "median_effort_hours": 4.7,
      "sample_size": 8
    }
  }
}
```

Atualizar após tarefas concluídas, usando critérios mínimos de amostra.

---

# 66. ADR integration with cost

ADRs podem ganhar seção opcional:

```text
## Cost comparison

| Option | Implementation | Maintenance | Runtime | Risk |
|---|---:|---:|---:|---:|
| A | 9 | 9 | 4 | 8 |
| B | 2 | 3 | 4 | 3 |
```

Após adoção, permitir:

```text
## Observed outcome
```

com custos e manutenção efetivamente observados.

---

# 67. Reports

Gerar relatórios derivados em:

```text
docs/reports/
├── project-intelligence.md
├── costs.md
├── documentation-coverage.md
├── context-efficiency.md
├── technical-debt.md
└── quality.md
```

Estes relatórios são derivados de `.atlas/intelligence/*`.

Não editar manualmente dados agregados nesses arquivos.

---

# 68. Task Completion Report

Ao finalizar uma tarefa, gerar resumo humano/machine-readable.

### Humano

```text
TASK-0142 — Implement nested compositions

Complexity: Medium
Risk: Medium

Estimated effort: 3–4h
Observed equivalent effort: 3.5–5h

LLM usage:
Input: 184k
Output: 31k
Cached: 96k
Avoided estimate: 120k

Observed API cost: US$ 1.83
Estimated CI cost: US$ 0.05–0.08

Files: +7 / ~14 / -0
Tests added: 16
Docs: +2 / ~5

Maintenance cost score: 4/10
Confidence: High
```

### Estruturado

JSON correspondente no ledger.

---

# 69. Commands expected after task completion

Fluxo automatizável conceitual:

```bash
atlas task finalize TASK-142
```

Internamente:

```text
validate task metadata
collect usage
collect changed files
collect tests
collect docs changes
calculate costs
update graph
update ledger
update project summary
update docs reports
validate docs site
```

Esse comando pode ser introduzido em fase posterior.

---

# 70. Security / privacy do ledger

O ledger não deve registrar automaticamente:

- prompts completos;
- segredos;
- API keys;
- conteúdo sensível;
- paths pessoais desnecessários;
- conteúdo privado de usuário.

Preferir:

- contagens;
- IDs;
- hashes;
- nomes de componentes;
- provider/model;
- custos.

Permitir configuração de redaction.

---

# 71. Data retention

Definir política:

- ledger: versionado ou não conforme projeto;
- cache: descartável;
- summaries: reconstruíveis;
- relatórios: derivados;
- raw provider telemetry: opcional e minimizada.

Projetos open source podem versionar ledger agregado e manter usage bruto local.

---

# 72. Performance do Atlas-Flow

Criar budgets próprios para o framework.

Exemplos iniciais a calibrar:

```text
atlas validate          < 5s em projeto médio
atlas impact file       < 1s com índice quente
atlas context intent    < 2s sem LLM externa
incremental docs build  < 5s
```

Não comprometer portabilidade em busca de micro-otimizações precoces.

---

# 73. Extensibility do próprio Atlas-Flow

Projetar adapters/plugins para:

- docs site generators;
- provider usage importers;
- source control;
- CI providers;
- language symbol indexers;
- test frameworks;
- issue trackers;
- LLM providers;
- embedding engines futuros.

Evitar plugin system sofisticado no MVP. Começar com interfaces internas bem definidas.

---

# 74. Implementation roadmap

## Phase 0 — Audit e baseline

### Objetivo

Entender o Atlas-Flow atual sem quebrar contratos existentes.

### Tarefas

- mapear estrutura atual;
- identificar schemas existentes;
- listar CLIs atuais;
- mapear compatibilidade;
- congelar nomenclatura v2;
- criar ADR da evolução;
- criar migration strategy;
- medir baseline de testes/performance.

### Entregáveis

- `ADR-Atlas-Flow-v2.md`;
- compatibility report;
- migration matrix;
- updated roadmap.

### Critério de aceite

Nenhuma implementação v2 começa sem saber quais contratos v1 precisam ser preservados.

---

## Phase 1 — Schemas e Core Registry

### Objetivo

Criar fundação de dados estável.

### Implementar

- project manifest v2;
- document metadata schema;
- registry schema;
- invariant schema;
- task map schema;
- context pack schema;
- cost ledger schema;
- debt schema;
- schema versioning;
- migrations básicas.

### Critério de aceite

`atlas validate` consegue validar um projeto v2 mínimo sem intelligence avançada.

---

## Phase 2 — Documentation Architecture v2

### Objetivo

Expandir framework para user/dev/operations/support docs.

### Implementar

- nova taxonomia;
- sub-Atlases;
- intent router;
- onboarding templates;
- user docs templates;
- developer docs templates;
- operations/support templates;
- freshness metadata;
- documentation coverage v1.

### Critério de aceite

Um projeto novo consegue gerar uma estrutura documental completa sem documentos monolíticos.

---

## Phase 3 — Knowledge Graph v2 + Impact

### Objetivo

Formalizar relações necessárias para retrieval e análise de impacto.

### Implementar

- graph nodes/edges;
- compact graph;
- ownership;
- invariants;
- component mapping;
- impact command;
- changed-files impact;
- orphan detection.

### Critério de aceite

Dado um arquivo alterado, Atlas-Flow encontra docs/tests/contracts/invariants potencialmente afetados.

---

## Phase 4 — Context Engine MVP

### Objetivo

Entregar mínimo contexto suficiente sem embeddings.

### Implementar

- task maps;
- context packs;
- progressive loading;
- token budgets;
- negative context;
- summaries;
- lexical retrieval;
- stop conditions;
- `atlas context`.

### Critério de aceite

Para tarefas conhecidas, `atlas context` retorna contexto relevante, budget e exclusões em JSON e formato humano.

---

## Phase 5 — Symbol Retrieval + Delta Context

### Objetivo

Reduzir ainda mais tokens.

### Implementar

- symbol index adapter;
- symbol → tests/docs mapping;
- file hashes;
- base context IDs;
- changed context;
- latest changes summary;
- context cache.

### Critério de aceite

Tarefas sobre símbolos específicos não exigem carregar arquivo inteiro quando o parser disponível permitir seleção estrutural.

---

## Phase 6 — Cost Intelligence MVP

### Objetivo

Registrar custo estimado e observado por tarefa.

### Implementar

- ledger JSONL;
- billing modes;
- model/provider registry;
- token counters;
- estimated vs observed;
- effort ranges;
- task completion report;
- project summary;
- cost commands.

### Critério de aceite

Toda tarefa finalizada pelo fluxo Atlas pode produzir relatório de custo com confidence e source claramente indicados.

---

## Phase 7 — Project Intelligence

### Objetivo

Agregar métricas cumulativas.

### Implementar

- baselines;
- cost by component;
- cost by release;
- cost by model/provider;
- context efficiency;
- documentation coverage;
- debt ledger;
- bug cost;
- estimation variance;
- reports.

### Critério de aceite

`atlas intelligence summary` produz visão global filtrável do projeto.

---

## Phase 8 — Documentation Site

### Objetivo

Publicar documentação viva e Project Intelligence.

### Implementar

- docs site adapter;
- site escolhido via ADR;
- generated navigation;
- visibility;
- search;
- related docs;
- freshness/status;
- project intelligence pages;
- static dashboard;
- public/internal build modes.

### Critério de aceite

Um projeto consegue construir site estático a partir das fontes canônicas sem duplicar documentação.

---

## Phase 9 — Dashboard Filters

### Objetivo

Transformar intelligence em ferramenta de decisão.

### Implementar

Filtros por:

- period;
- release;
- component;
- task type;
- model;
- provider;
- complexity;
- risk.

### Critério de aceite

Dashboard permite responder custo/eficiência de áreas e releases sem processamento server-side.

---

## Phase 10 — Workflow / CI enforcement

### Objetivo

Tornar o framework parte do ciclo normal de engenharia.

### Implementar

- task finalization workflow;
- docs validation;
- cost report requirement;
- graph update checks;
- site build check;
- report-only → warning → required rollout;
- examples de GitHub Actions/CI genérico.

### Critério de aceite

Projetos podem ativar enforcement progressivamente sem bloquear adoção inicial.

---

## Phase 11 — Multi-LLM Routing Integration

### Objetivo

Usar context/risk/cost para escolher agentes/modelos.

### Implementar

- capability map;
- risk map;
- agent profiles;
- routing hints;
- estimated context cost;
- cost-aware model selection interface.

### Critério de aceite

Atlas-Flow pode produzir uma recomendação estruturada de perfil/modelo sem acoplar-se a um único provider.

---

## Phase 12 — Advanced retrieval opcional

Somente após medir necessidade.

Possíveis recursos:

- BM25 avançado;
- embeddings;
- hybrid retrieval;
- semantic cache;
- automatic context pack suggestions;
- similarity-based cost estimation.

Nunca tornar isso obrigatório para o funcionamento principal.

---

# 75. Prioridade recomendada

## P0 — Fundação obrigatória

- schemas v2;
- registry;
- docs taxonomy v2;
- metadata;
- validation;
- graph/impact;
- context packs/task maps;
- token budget;
- cost ledger;
- project summary.

## P1 — Alto valor

- symbol retrieval;
- delta context;
- docs site;
- intelligence dashboard;
- documentation coverage;
- debt ledger;
- CI integration.

## P2 — Evolução

- cost calibration;
- provider adapters;
- bug/rework analytics;
- routing by risk/cost;
- advanced search.

## P3 — Experimental

- embeddings;
- semantic caching;
- ML estimation;
- autonomous optimization of context packs.

---

# 76. Migration strategy para projetos existentes

## Step 1 — Detect

```bash
atlas migrate inspect
```

Gerar:

- current layout;
- missing canonical docs;
- old IDs;
- incompatible metadata;
- graph gaps;
- suggested mapping.

## Step 2 — Plan

```bash
atlas migrate plan
```

Produzir plano sem alterar arquivos.

## Step 3 — Apply safe transformations

```bash
atlas migrate apply
```

Automatizar somente:

- directory creation;
- metadata upgrades seguras;
- generated manifests;
- moved docs quando mapping for inequívoco.

## Step 4 — Manual/agent review

Itens sem mapping seguro ficam como TODO explícito.

## Step 5 — Validate

```bash
atlas validate
atlas docs validate
```

---

# 77. Backward compatibility

Definir janela de compatibilidade.

Sugestão:

- ler manifest v1 por período de transição;
- emitir warning com migration guide;
- escrever apenas v2 após migração;
- não manter dois modelos internos completos para sempre.

Registrar decisão em ADR.

---

# 78. Testing strategy do Atlas-Flow

## Unit tests

- parsers;
- schemas;
- graph functions;
- cost calculations;
- coverage calculations;
- token budget logic.

## Integration tests

- project init;
- project migration;
- context planning;
- impact analysis;
- cost finalization;
- docs build.

## Golden tests

Úteis para:

- generated manifests;
- CLI JSON;
- markdown reports;
- docs navigation.

## E2E fixtures

Criar projetos exemplo:

```text
examples/fixtures/
├── tiny-library/
├── web-app/
├── desktop-app/
├── api-service/
└── legacy-v1-project/
```

## Regression tests

Especialmente para:

- migrations;
- IDs;
- graph;
- cost aggregation;
- public/private docs separation.

---

# 79. Acceptance tests fundamentais

O Atlas-Flow v2 não deve ser considerado concluído sem passar por cenários reais.

### Scenario A — New project

1. `atlas init`;
2. criar feature;
3. gerar docs;
4. registrar custo;
5. build site;
6. visualizar dashboard.

### Scenario B — Existing project

1. inspect;
2. migrate;
3. validate;
4. preserve IDs relevantes;
5. build site.

### Scenario C — Agent task

1. receber intenção;
2. `atlas context`;
3. implementar;
4. `atlas impact --changed`;
5. finalizar tarefa;
6. atualizar intelligence.

### Scenario D — Public docs

1. build público;
2. garantir ausência de docs internal/private;
3. search não deve indexá-las.

### Scenario E — Cost uncertainty

1. ausência de provider billing;
2. estimar tokens;
3. reportar faixa/confidence;
4. nunca inventar custo exato.

---

# 80. Observability do próprio Atlas-Flow

Logs estruturados opcionais:

```text
validation
retrieval
context selection
cache hits
cost calculation
site build
```

Modo debug:

```bash
ATLAS_LOG=debug atlas context "..."
```

Permitir explicar:

> por que este documento entrou no contexto?

Exemplo:

```bash
atlas context "add transition" --explain
```

Saída:

```text
DOC-TIMELINE-SUMMARY
Reason: required by TASKMAP-add-transition

SPEC-TRANSITION
Reason: direct contract dependency
```

Esse recurso é importante para auditabilidade.

---

# 81. Context quality safeguards

O sistema deve impedir ou alertar sobre:

- documentos deprecated sendo usados como canonical;
- summaries mais novos que source hash incompatível;
- context pack referenciando IDs inexistentes;
- budget impossível de cumprir com required items;
- exclusão conflitante com impact graph;
- high-risk task sem invariants relevantes carregados.

---

# 82. Intelligence quality safeguards

Alertar sobre:

- custos misturando moedas sem conversão explícita;
- estimativa apresentada como observed;
- subscription allocation somada a API cost incorretamente;
- sample size pequeno em baseline;
- technical debt sem owner/componente;
- task sem final cost report;
- cost records duplicados.

---

# 83. Documentation quality safeguards

Alertar sobre:

- páginas órfãs;
- documentação pública sem owner;
- reference sem fonte;
- tutorial sem prerequisitos;
- how-to muito abrangente;
- user docs contendo detalhes internos desnecessários;
- code examples não testados quando marcados como executable;
- stale docs relacionados a código modificado.

---

# 84. Project Intelligence filters — modelo de dados

Toda tarefa deve preferencialmente registrar dimensões úteis para agregação:

```yaml
release:
milestone:
components: []
features: []
type:
complexity:
risk:
models: []
providers: []
agent_profiles: []
```

Isso evita precisar inferir filtros posteriormente.

---

# 85. Dashboard MVP — páginas

## Overview

Cards:

- tasks completed;
- total estimated/observed cost;
- total tokens;
- context reduction;
- docs coverage;
- debt open.

## Costs

- timeline por período;
- por componente;
- por release;
- por task type.

## LLM Usage

- input/output/cached;
- provider/model;
- subscription/API separation.

## Context Efficiency

- potential vs actual;
- avoided tokens;
- savings mechanism.

## Documentation

- coverage por domínio;
- stale docs;
- missing user/dev docs.

## Debt

- open debt;
- remediation hours;
- by component/severity.

---

# 86. Dashboard implementation constraints

- sem backend obrigatório;
- JSON estático;
- progressive enhancement;
- funcionamento sem JavaScript para páginas documentais básicas;
- dashboard pode exigir JS;
- sem dependências de charting gigantes sem necessidade;
- dados brutos exportáveis como JSON/CSV posteriormente;
- respeitar public/internal visibility.

---

# 87. Documentation builder API

Modelo conceitual:

```ts
interface DocumentationBuilder {
  scan(): Promise<DocumentRegistry>
  validate(registry: DocumentRegistry): Promise<ValidationResult>
  buildNavigation(registry: DocumentRegistry): NavigationTree
  buildSearchIndex(registry: DocumentRegistry): SearchIndex
  buildIntelligencePages(data: IntelligenceSummary): GeneratedPage[]
  build(target: DocsSiteAdapter): Promise<BuildResult>
}
```

---

# 88. Intelligence API

Modelo conceitual:

```ts
interface IntelligenceEngine {
  recordTask(record: TaskCostRecord): Promise<void>
  calculateProjectSummary(filters?: IntelligenceFilters): Promise<ProjectSummary>
  calculateBaselines(): Promise<Baselines>
  calculateContextEfficiency(filters?: IntelligenceFilters): Promise<ContextMetrics>
  calculateDocumentationCoverage(): Promise<DocumentationCoverage>
}
```

---

# 89. Context Engine API

Modelo conceitual:

```ts
interface ContextEngine {
  classifyTask(input: TaskInput): Promise<TaskClassification>
  resolveTaskMap(input: TaskInput): Promise<TaskMap | null>
  buildPlan(input: ContextRequest): Promise<ContextPlan>
  explain(plan: ContextPlan): Promise<ContextExplanation>
  materialize(plan: ContextPlan): Promise<ContextBundle>
}
```

---

# 90. Knowledge Graph API

Modelo conceitual:

```ts
interface KnowledgeGraph {
  addNode(node: GraphNode): void
  addEdge(edge: GraphEdge): void
  neighbors(id: string, relation?: string): GraphNode[]
  impact(target: string): ImpactResult
  validate(): ValidationIssue[]
  compact(): CompactGraph
}
```

---

# 91. Agent integration contract

Agents devem receber, idealmente:

```yaml
task:
  id:
  intent:
  risk:
  complexity:

context:
  plan_id:
  budget:
  required:
  optional:
  excluded:
  invariants:

completion:
  required_checks:
  documentation_impact:
  cost_report_required: true
```

Ao finalizar, devolver:

```yaml
changed_files: []
tests_run: []
docs_changed: []
usage:
risks_found: []
debt_introduced: []
```

---

# 92. AGENTS.md v2

Continuar curto — idealmente ~80–150 linhas.

Deve funcionar como roteador, não enciclopédia.

Conteúdo:

- project entrypoint;
- mandatory rules;
- context workflow;
- invariants link;
- validation commands;
- testing commands;
- task finalize requirement;
- ADR/RFC policy;
- security rules;
- docs update rule;
- cost report rule.

---

# 93. Query Packs

Manter e expandir.

Exemplos:

```yaml
architecture:
  queries:
    - architecture overview
    - invariants
    - ADR current

bug-fix:
  queries:
    - symbol definition
    - related tests
    - recent changes
    - known issues
```

Query Pack é estratégia de busca; Context Pack é pacote de contexto resolvido/recomendado.

Não confundir os dois.

---

# 94. Hot vs Cold Context

## Hot

- AGENTS;
- current architecture summaries;
- invariants;
- task maps;
- context packs;
- current specs;
- recent changes.

## Cold

- historical ADRs;
- rejected RFCs;
- old benchmarks;
- research archive;
- deprecated docs.

Retrieval normal favorece Hot Context.

---

# 95. Generated summaries

Summaries automáticas devem conter provenance:

```yaml
source: generated
authority: derived
source_hash: abc123
created_at: ...
```

Nunca promover resumo gerado a canonical sem processo explícito.

---

# 96. Report visibility

Project Intelligence pode ter dados internos que não devem ir ao site público.

Manifest deve permitir:

```yaml
intelligence:
  public_metrics:
    - documentation_coverage
    - release_history
  internal_metrics:
    - costs
    - model_usage
    - technical_debt
```

Default recomendado: intelligence interna, salvo configuração explícita.

---

# 97. Versioned documentation

Suportar posteriormente, sem bloquear MVP:

```text
latest
stable
v1.x
v2.x
```

Evitar duplicar todos os documentos manualmente; integrar com Git tags/releases quando apropriado.

---

# 98. Definition of Ready para implementação desta evolução

Antes de cada epic:

- scope definido;
- interfaces afetadas conhecidas;
- backward compatibility analisada;
- acceptance criteria definidos;
- schemas definidos antes de producers/consumers;
- migration impact registrado;
- testes previstos;
- documentação prevista;
- custo estimado registrado.

---

# 99. Definition of Done para cada epic desta evolução

Um epic só é concluído quando:

- implementação concluída;
- unit/integration tests;
- CLI documentada;
- schemas versionados;
- migration tratada;
- examples adicionados;
- user/dev docs aplicáveis atualizados;
- AGENT docs/context atualizados;
- cost report gerado;
- graph atualizado;
- docs site passa;
- changelog/release notes preparados quando aplicável.

---

# 100. Riscos principais

## R1 — Overengineering

**Mitigação:** implementar em camadas; começar determinístico; evitar ML/embeddings no MVP.

## R2 — Framework mais caro que o benefício

**Mitigação:** medir tempo/token overhead do próprio Atlas-Flow.

## R3 — Métricas pouco confiáveis

**Mitigação:** observed/estimated/unknown + confidence + source.

## R4 — Taxonomia excessivamente rígida

**Mitigação:** categorias canônicas + applicability/N/A + profiles.

## R5 — Site documental acoplado ao framework

**Mitigação:** adapter interface.

## R6 — Knowledge graph manual impossível de manter

**Mitigação:** combinar metadata explícita com geração derivada e validação.

## R7 — Context packs desatualizados

**Mitigação:** relacionar source hashes/registry e alertar sobre stale packs.

## R8 — Dashboard expor informações internas

**Mitigação:** visibility defaults seguros e testes de build público.

## R9 — Ledger virar telemetria invasiva

**Mitigação:** dados mínimos, opt-in para raw telemetry, redaction, sem prompts completos.

## R10 — Backward compatibility consumir todo desenvolvimento

**Mitigação:** janela de migração definida e sunset de v1.

---

# 101. KPIs da própria evolução

Medir se Atlas-Flow v2 funciona.

### Documentation

- % docs com metadata válida;
- % features com user/dev docs;
- stale docs count;
- broken links;
- documentation coverage.

### Context

- average context tokens/task;
- context reduction;
- cache hit rate;
- % tasks usando task maps;
- % tasks usando context packs.

### Cost

- LLM cost/task;
- cost/release;
- estimation variance;
- token cost trend.

### Quality

- rework ratio;
- bug repair cost;
- open technical debt;
- failed task finalization checks.

### Atlas overhead

- validation duration;
- docs build duration;
- context planning duration;
- size of generated indexes.

---

# 102. Critério para considerar Atlas-Flow v2 MVP pronto

O MVP estará pronto quando for possível, em um projeto real:

1. executar `atlas init` ou migrar projeto existente;
2. obter estrutura documental v2;
3. validar metadata/registry/graph;
4. executar análise de impacto;
5. gerar context plan com budget;
6. finalizar tarefa registrando custo;
7. atualizar project intelligence;
8. gerar site documental;
9. visualizar dashboard estático de custos/context/docs;
10. executar tudo em CI;
11. manter funcionamento sem embeddings, banco externo ou backend obrigatório.

---

# 103. Ordem concreta recomendada de implementação

Para programação agêntica solo, executar nesta ordem:

```text
01. Audit current Atlas-Flow
02. Freeze v2 terminology/taxonomy
03. Define schemas
04. Upgrade validation engine
05. Implement registry v2
06. Implement documentation metadata
07. Implement docs taxonomy/templates
08. Implement graph v2
09. Implement impact analysis
10. Implement task maps
11. Implement context packs
12. Implement token estimator/budgets
13. Implement atlas context MVP
14. Implement cost ledger schema
15. Implement task cost reporting
16. Implement project summary aggregation
17. Implement documentation coverage
18. Implement technical debt ledger
19. Implement docs builder abstraction
20. Select docs site through ADR
21. Implement docs site MVP
22. Add intelligence dashboard
23. Add filters
24. Add symbol retrieval
25. Add delta context/cache
26. Add CI enforcement
27. Add multi-LLM routing hints
28. Measure results
29. Optimize context packs
30. Evaluate advanced retrieval only if justified
```

---

# 104. Primeiro pacote de ADRs a criar

Antes/ao iniciar implementação:

```text
ADR-001 — Atlas-Flow v2 architecture
ADR-002 — Canonical documentation taxonomy
ADR-003 — Structured data and provenance policy
ADR-004 — Knowledge graph representation
ADR-005 — Context planning model
ADR-006 — Intelligence ledger storage format
ADR-007 — Cost estimation policy
ADR-008 — Documentation site generator
ADR-009 — Public/internal documentation visibility
ADR-010 — Backward compatibility and migration window
```

---

# 105. Primeiro pacote de schemas

```text
schemas/
├── atlas-project.schema.json
├── document-metadata.schema.json
├── registry.schema.json
├── graph.schema.json
├── invariant.schema.json
├── task-map.schema.json
├── context-pack.schema.json
├── context-plan.schema.json
├── task-cost-record.schema.json
├── debt-record.schema.json
├── project-summary.schema.json
└── intelligence-filters.schema.json
```

---

# 106. Primeiro pacote de commands

Implementação incremental sugerida:

```text
atlas validate
atlas impact
atlas context
atlas docs validate
atlas docs coverage
atlas cost task
atlas cost project
atlas intelligence summary
atlas docs build
```

Depois:

```text
atlas task finalize
atlas migrate inspect
atlas migrate plan
atlas migrate apply
atlas release check
```

---

# 107. Primeiro pacote de templates

```text
templates/
├── AGENTS.md
├── ATLAS.md
├── USER_ATLAS.md
├── DEVELOPER_ATLAS.md
├── AGENT_ATLAS.md
├── CODEBASE_TOUR.md
├── DEBUGGING_PLAYBOOK.md
├── INVARIANTS.md
├── ANTI_PATTERNS.md
├── TOKEN_ECONOMY.md
├── task-map.yaml
├── context-pack.yaml
├── ADR.md
├── RFC.md
├── troubleshooting.md
├── runbook.md
└── task-completion-report.md
```

---

# 108. Exemplo de task manifest

```yaml
schema_version: 1
id: TASK-142
title: Implement nested compositions
type: feature
status: in-progress
components:
  - timeline
  - serialization
features:
  - nested-compositions
risk: medium
complexity: medium
release: 0.4.0

context:
  task_map: TASKMAP-nested-composition
  budget: medium
  profile: implementer

documentation_impact:
  user: true
  developer: true
  api: false
  migration: true

cost:
  estimate_required: true
  final_report_required: true
```

---

# 109. Exemplo de context plan

```yaml
schema_version: 1
id: CTXPLAN-TASK-142-01
intent: implement-nested-composition
risk: medium
budget:
  target_tokens: 20000
  max_tokens: 32000
estimated_tokens: 17240

required:
  - AGENTS.md
  - DOC-TIMELINE-SUMMARY
  - SPEC-COMPOSITION-002
  - INV-021
  - SRC-composition-model
  - TEST-composition-serialization

optional:
  - ADR-RENDER-021

excluded:
  - authentication
  - telemetry

stop_condition:
  - contracts-located
  - invariants-loaded
  - implementation-surface-known
  - tests-known
```

---

# 110. Exemplo de project intelligence summary

```json
{
  "schema_version": 1,
  "project": "Rakord",
  "period": "all-time",
  "tasks_completed": 184,
  "tokens": {
    "input": 18400000,
    "output": 4200000,
    "cached": 9800000,
    "avoided_estimate": 11200000
  },
  "cost": {
    "observed_api_usd": 148.2,
    "estimated_total_usd": {"min": 183, "max": 226}
  },
  "effort_hours_equivalent": {"min": 620, "max": 770},
  "documentation_coverage": 0.84,
  "context_reduction": 0.537,
  "technical_debt": {
    "open_items": 17,
    "remediation_hours": {"min": 42, "max": 67}
  }
}
```

---

# 111. Decisões que devem permanecer configuráveis

Não hardcode no core:

- moeda de apresentação;
- provider/model prices;
- docs site implementation;
- context budgets;
- review intervals;
- performance budgets;
- public/internal sections;
- branch/release conventions;
- task types;
- risk thresholds;
- CI provider.

---

# 112. Decisões que devem ser canônicas

Evitar variação por projeto em:

- significado de `canonical/derived/informative`;
- significado de `observed/estimated/unknown`;
- schema versioning;
- IDs estáveis;
- ledger append-only semantics;
- distinction task map/context pack/query pack;
- no false precision;
- minimum sufficient context;
- generated site is derived;
- cache is not source of truth.

---

# 113. Estratégia de lançamento

## Alpha

Aplicar apenas no próprio Atlas-Flow.

Objetivo: dogfooding.

## Beta

Aplicar em 1–2 projetos reais de perfis diferentes.

Exemplo:

- uma aplicação desktop;
- uma biblioteca/CLI.

## RC

Migrar projeto maior e testar:

- docs site;
- cost ledger;
- context reduction;
- multi-agent workflows.

## Stable

Congelar schemas v2.x e publicar migration guide.

---

# 114. Dogfooding obrigatório

O próprio Atlas-Flow deve usar:

- Atlas docs v2;
- context packs;
- task maps;
- cost reports;
- knowledge graph;
- docs site;
- project intelligence dashboard.

Nenhum recurso deve ser declarado stable antes de ser utilizado pelo próprio Atlas-Flow em desenvolvimento real.

---

# 115. Métrica-chave de sucesso

A principal pergunta após algumas dezenas de tarefas deve ser:

> **O Atlas-Flow está reduzindo contexto/custo e aumentando previsibilidade sem criar mais overhead do que economiza?**

A decisão de manter, simplificar ou ampliar cada mecanismo deve usar essa resposta.

---

# 116. Checklist de implementação final

## Core

- [ ] schemas v2
- [ ] registry v2
- [ ] graph v2
- [ ] validation v2
- [ ] migration support

## Documentation

- [ ] canonical taxonomy
- [ ] user docs templates
- [ ] developer docs templates
- [ ] operations/support templates
- [ ] sub-Atlases
- [ ] freshness
- [ ] coverage
- [ ] site builder

## Context

- [ ] task maps
- [ ] context packs
- [ ] progressive loading
- [ ] budgets
- [ ] negative context
- [ ] summaries
- [ ] lexical retrieval
- [ ] symbol retrieval
- [ ] delta context
- [ ] context explainability

## Token Economy

- [ ] token estimator
- [ ] context metrics
- [ ] exclusion rules
- [ ] cache metrics
- [ ] context reduction report

## Intelligence

- [ ] cost ledger
- [ ] provider/model registry
- [ ] estimated vs observed
- [ ] effort ranges
- [ ] project summary
- [ ] baselines
- [ ] debt ledger
- [ ] bug/rework cost
- [ ] filters

## Site / Dashboard

- [ ] site adapter
- [ ] generated nav
- [ ] visibility
- [ ] search
- [ ] Project Intelligence overview
- [ ] cost dashboard
- [ ] context dashboard
- [ ] docs coverage dashboard
- [ ] debt dashboard

## Workflow

- [ ] task lifecycle v2
- [ ] task finalize
- [ ] Definition of Done v2
- [ ] CI examples
- [ ] gradual enforcement
- [ ] multi-agent profiles

---

# 117. Próxima ação recomendada

A primeira tarefa concreta deve ser **AF-V2-001 — Atlas-Flow Current-State Audit**.

Saída esperada:

1. árvore atual do repositório;
2. packages/modules existentes;
3. CLI existente;
4. schemas existentes;
5. contratos públicos;
6. testes existentes;
7. documentação atual;
8. pontos de compatibilidade v1;
9. gaps contra este plano;
10. proposta de mapping entre arquitetura atual e arquitetura v2.

Somente depois disso criar o primeiro PR estrutural.

---

# 118. Prompt-base para o agente que iniciar a implementação

```text
Você está evoluindo o Atlas-Flow segundo o documento AF-EVO-001.

Antes de alterar código:
1. audite a arquitetura atual do repositório;
2. identifique contratos e compatibilidade existentes;
3. mapeie o estado atual para as fases do plano;
4. não reescreva módulos funcionais sem necessidade;
5. priorize schemas e contratos antes dos produtores/consumidores;
6. implemente em pequenos incrementos testáveis;
7. mantenha backward compatibility conforme a política definida;
8. atualize documentação, knowledge graph e testes no mesmo change set;
9. registre custo estimado antes e relatório de custo após cada tarefa;
10. use Minimum Sufficient Context e registre métricas de contexto quando possível.

Comece por AF-V2-001 — Current-State Audit e produza um relatório de gaps e um plano de migração concreto antes da primeira mudança arquitetural.
```

---

# 119. Conclusão

A evolução proposta transforma o Atlas-Flow em uma infraestrutura composta por cinco capacidades operacionais e uma camada de publicação:

```text
Knowledge
Context
Token Economy
Project Intelligence
Governance
Documentation Publishing
```

O objetivo final não é aumentar a quantidade de documentação, mas **aumentar a qualidade do conhecimento disponível, reduzir o contexto necessário para agir e registrar de forma verificável como o projeto evolui**.

O sucesso do Atlas-Flow v2 será medido não pela quantidade de recursos implementados, e sim pela capacidade de:

- orientar usuários;
- acelerar contribuidores;
- reduzir ambiguidades para agentes;
- economizar tokens;
- reduzir retrabalho;
- tornar custos visíveis;
- manter documentação sincronizada;
- preservar decisões e invariantes;
- facilitar manutenção de longo prazo.

---

**End of AF-EVO-001**
