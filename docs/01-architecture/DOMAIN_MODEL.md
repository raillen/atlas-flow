# Domain Model

## Canonical concepts

Project, Decision, Constraint, Goal, GoalAmendment, AgentRole, Skill, Recipe.

## Operational concepts

ProjectInspection, Discussion, ProjectDraft, PlanSnapshot, Run, Task,
ModelRoute, Runner, Attempt, Evidence, Review.

## Canonical vs operational

Git: manifest, docs, accepted decisions/ADRs, Goals and policies.

SQLite/event log: project discussions, plan snapshots, runs, tasks, attempts,
route decisions, usage and artifact pointers.

A `PlanSnapshot` is a reviewable operational contract tied to a Goal revision.
After `LOCKED`, it is immutable; execution consumes it and records the resulting
run/evidence separately.

## v2 project intelligence

AF-EVO-001 acrescenta contratos derivados, sem criar um segundo Goal:
`DocumentMetadata`, `RegistryEntry`, `KnowledgeGraph`, `TaskMap`, `ContextPack`,
`ContextPlan` e `TaskCostRecord`. O conteúdo do projeto continua em Git; os
índices, site e resumo em `.atlas/` são regeneráveis.
