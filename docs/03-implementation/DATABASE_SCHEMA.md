# Operational Database Schema

Tables: projects, discussions, messages, decision_candidates, runs, tasks, task_dependencies, route_decisions, attempts, runner_sessions, events, evidence, reviews, usage_observations, model_scores, artifacts.

Constraints: transactional state changes, monotonic event sequence per Run, evidence digest where stable, Goal referenced by revision/hash rather than duplicated as authority.

Evaluate SQLite WAL in P03.
