# Operational Database Schema

## C# runtime atual

O porte C# usa SQLite operacional versão 4 com as tabelas `projects`, `runs`,
`tasks`, `attempts`, `events`, `evidence` e `plans`. A tabela `plans` guarda o
grafo em JSON e possui `context TEXT` opcional para o `ContextPlan` persistido.
Na inicialização, bancos v3 recebem essa coluna de forma incremental; snapshots
antigos continuam válidos e retornam `Context = null`.

Project Intelligence não é duplicado no SQLite: seu snapshot canônico fica em
`.atlas/history/project-intelligence.json`; eventos SQLite continuam sendo a
fonte operacional detalhada.

## Direção histórica

Tables: projects, discussions, messages, decision_candidates, runs, tasks, task_dependencies, route_decisions, attempts, runner_sessions, events, evidence, reviews, usage_observations, model_scores, artifacts.

Constraints: transactional state changes, monotonic event sequence per Run, evidence digest where stable, Goal referenced by revision/hash rather than duplicated as authority.

Evaluate SQLite WAL in P03.
