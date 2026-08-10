# Event Model

Append-only operational events include ProjectOpened, DecisionProposed/Accepted, FinalizationStarted, GoalLoaded, RunStarted, DagPlanned, TaskReady, RouteSelected, RunnerStarted, PermissionRequested, AttemptCompleted/Failed, FallbackSelected, GatePassed/Failed, ReviewCompleted, EvidenceAttached, GoalCompleted, RunCancelled and RunRecovered.

Every event has id, timestamp, project/run, type, version and redacted payload.
