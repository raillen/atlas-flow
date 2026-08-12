# Operational Database Schema

## C# runtime atual

O porte C# usa SQLite operacional versão 5 com as tabelas `projects`, `runs`,
`tasks`, `attempts`, `events`, `evidence`, `plans`, `discussions`,
`discussion_messages` e `decisions`. A tabela `plans` guarda o grafo em JSON e
possui `context TEXT` opcional para o `ContextPlan` persistido. Discuss guarda
a conversa e as decisões como estado operacional reidratável; a fonte
canônica de decisões continua sendo o ledger em Git.
Na inicialização, bancos v3 recebem essa coluna de forma incremental; snapshots
antigos continuam válidos e retornam `Context = null`.

Bancos anteriores à versão 5 recebem as tabelas do Discuss de forma idempotente
na inicialização. Referências de mensagens são armazenadas em JSON para manter
o contrato de caminho relativo, tipo, rótulo e MIME sem transformar anexos em
uploads implícitos.

Project Intelligence não é duplicado no SQLite: seu snapshot canônico fica em
`.atlas/history/project-intelligence.json`; eventos SQLite continuam sendo a
fonte operacional detalhada.

## Direção histórica

Tables: projects, discussions, messages, decision_candidates, runs, tasks, task_dependencies, route_decisions, attempts, runner_sessions, events, evidence, reviews, usage_observations, model_scores, artifacts.

Constraints: transactional state changes, monotonic event sequence per Run, evidence digest where stable, Goal referenced by revision/hash rather than duplicated as authority.

Evaluate SQLite WAL in P03.
