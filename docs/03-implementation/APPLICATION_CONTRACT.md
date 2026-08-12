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
          Contracts/  ← the seam. 8 interfaces, 0 implementations.
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

## The eight services

| Interface | Workspace stage |
| --- | --- |
| `IProjectService` | opening a directory, the explorer, adaptation |
| `IGoalService` | the Goal list, and whether a Goal may close |
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

Written and building: all eight interfaces, the domain types behind them, and
`AtlasFlowServices.AddAtlasFlow`.

**Nothing is registered.** The container is wired but empty, so a host that
resolves a service today throws. That is deliberate — an empty registration
that returned null would fail later and further away.

Ported so far: the ACP client (`AtlasFlow.Protocols`), 29 tests. Everything
else — project inspection, goals, discussions, planning, execution,
persistence, routing, settings, docs — is still Python under `reference/`.

**Next, and it unblocks the UI:** in-memory fakes for the eight services, so
the desktop app runs against plausible data before any of the real
implementations land.
