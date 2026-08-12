# The Application Contract

The seam between the backend and the desktop UI, while the two are written in
parallel. Read this before touching either side.

## The shape

```text
AtlasFlow.Desktop            AtlasFlow.Cli
  Views, ViewModels            commands
        │                          │
        └──────────┬───────────────┘
                   ▼
        AtlasFlow.Application
          Contracts/  ← the seam. 10 interfaces.
          AtlasFlowServices.AddAtlasFlow(projectRoot)
                   │
                   ▼
        Orchestration · Persistence · Protocols · Domain
```

There is no HTTP, no port and no serialization. The UI holds a reference to
`AtlasFlow.Application` and calls it in-process ([ADR-017](../07-decisions/ADR-017-DOTNET-RUNTIME.md)).
The 33 REST routes the Tauri build had existed only to cross a process boundary
that no longer exists.

## Who owns what

| Path | Owner | The other side |
| --- | --- | --- |
| `src/AtlasFlow.Desktop/**` | UI | never edited by the backend |
| `src/AtlasFlow.Domain/**`, `Orchestration`, `Persistence`, `Protocols` | backend | never edited by the UI |
| `src/AtlasFlow.Application/Contracts/**` | **shared** | changes get agreed first |

`Contracts/` is the only directory both sides read. Changing it is a
conversation, not a commit — it is the one place where an edit breaks work
somebody else has in flight.

## The services

| Interface | Workspace stage |
| --- | --- |
| `IProjectService` | opening a directory, the explorer, adaptation |
| `IGoalService` | the Goal list, and whether a Goal may close |
| `IContextService` | bounded LPC/PCA context planning |
| `IProjectIntelligenceService` | compact task reports and project aggregates |
| `IDiscussionService` | Define — conversation and the decision ledger |
| `IPlanService` | Plan — draw a graph, review it, lock it |
| `IRunService` | Run — start, watch, cancel |
| `IRoutingService` | which model each role resolved to |
| `ISettingsService` | the settings drawer |
| `IDocumentationService` | Knowledge |

## Consuming one

```csharp
public sealed partial class GoalListViewModel(IGoalService goals) : ObservableObject
{
    [ObservableProperty]
    private IReadOnlyList<Goal> _goals = [];

    public async Task LoadAsync(CancellationToken cancellationToken)
        => Goals = await goals.ListAsync(cancellationToken);
}
```

Live events are an `IAsyncEnumerable`, not a callback and not a poll:

```csharp
await foreach (DomainEvent e in runs.WatchAsync(runId, cancellationToken))
{
    Events.Add(e);
}
```

`WatchAsync` replays everything already recorded before it yields anything
live, so a view that attaches late still renders a complete history. It
completes on its own when the run reaches a terminal state.

## Rules the contract encodes

**Every method takes a `CancellationToken`.** Stopping a run is a shipped
feature, and `CA2016` is an error in this repository. A token that is accepted
but not honoured is worse than one never offered.

**Identifiers are types, not strings.** `GoalId`, `PlanId`, `RunId`, `TaskId`,
`DiscussionId`, `ProjectPath`. Several methods take two of them; the previous
implementation took `str` for all of them, and `StartRun(goalId, planId)`
compiled equally well with the arguments swapped.

**States are enums, not strings.** `GoalState`, `RunState`, `TaskState`,
`PlanState`, `Verdict`, `ProjectMode`. These were `state: str` with the valid
set written in a trailing comment, and a comment never stopped `"Done"` from
never equalling `"DONE"`.

**Requests with more than three fields are records.** `CreatePlanRequest`,
`StartRunRequest`, `AppendMessageRequest`. Positional parameters of the same
type are how a runner ends up in the branch argument.

**No secret crosses the seam.** `Provider` carries `CredentialRef` and
`IsCredentialConfigured`, never the credential.

**There are no view models in the contract.** The Python build projected the
domain onto `schemas.py` so that renaming a runtime field could not silently
reshape the API. That protection was needed because the boundary was a wire.
Here the boundary is a compiler: rename a field and the UI stops building,
which is the outcome the projection was buying. A separate projection layer
would now be duplicated knowledge, so there is none.

## The one gotcha

Inside `AtlasFlow.Desktop`, the bare name `Application` resolves to the
`AtlasFlow.Application` **namespace** before it reaches Avalonia's type. Any
file touching `Application.Current` or subclassing `Application` needs it
written out:

```csharp
public sealed partial class App : Avalonia.Application
```

## State

Written and building: the contracts, domain types and
`AtlasFlowServices.AddAtlasFlow` wiring. Project inspection, Goals, planning,
the first run slice, bounded context planning, Project Intelligence and Discuss
are registered with real implementations. New plan snapshots persist their
bounded context decision; Plan/Run updates one compact intelligence report
without blocking the operational run when the derived history projection is
unavailable. Routing, settings and documentation remain deliberately
unregistered until their implementations are ported; the host then fails at
the missing capability boundary rather than receiving a plausible stub.

The v0.2 context contract returns a bounded decision, not a copied context
payload. A Plan captures that decision so the desktop can show the reviewed
budget and strategy. `PlanViewModel` consumes that decision and projects it into
the Plan inspector and context rail without exposing retrieval payloads. The
Project Intelligence contract records compact task reports and recomputes
aggregates with explicit measurement provenance; the desktop shows only this
summary and keeps unavailable cost measurements honest. Discuss rehydrates its
thread from SQLite, validates project-relative references at the application
boundary, and writes accepted decisions to the Git ledger during finalization.
These boundaries are ready for the desktop to consume while retrieval and
provider integration continue independently.
