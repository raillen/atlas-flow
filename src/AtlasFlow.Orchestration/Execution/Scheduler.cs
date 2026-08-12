using System.Text.Json.Nodes;

using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Persistence;

namespace AtlasFlow.Orchestration.Execution;

/// <summary>
/// Moves runs, tasks and attempts, writing the event that explains each move.
/// </summary>
/// <remarks>
/// Every transition goes through <see cref="RunRepository"/>, which writes the
/// row and the event in one transaction. The scheduler's job is to decide
/// which transition happens and what the event says; it never writes state on
/// its own.
/// </remarks>
public sealed class Scheduler(RunRepository runs, string projectId)
{
    private readonly RunRepository _runs = runs;

    /// <summary>
    /// Stamped on every event this scheduler writes.
    /// </summary>
    /// <remarks>
    /// Atlas Flow runs against whatever project it was opened on, so nothing
    /// here may assume one. An event that cannot name its project is
    /// unattributable.
    /// </remarks>
    private readonly string _projectId = projectId;

    // --- runs ---------------------------------------------------------------

    public Task<Run> StartAsync(Run run, CancellationToken cancellationToken = default) =>
        _runs.TransitionAsync(
            run,
            RunState.Planning,
            RunEvent(run, EventType.RunStarted, RunState.Planning),
            cancellationToken);

    public Task<Run> AdvanceAsync(Run run, RunState to, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(run);

        EventType type = to switch
        {
            RunState.Completed => EventType.RunCompleted,
            RunState.Failed => EventType.RunFailed,
            _ => EventType.StateChange,
        };

        return _runs.TransitionAsync(run, to, RunEvent(run, type, to), cancellationToken);
    }

    /// <summary>Persists a planned task set and moves the run to Ready.</summary>
    public async Task<Run> ScheduleAsync(
        Run run,
        IReadOnlyList<RunTask> tasks,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(tasks);

        foreach (RunTask task in tasks)
        {
            await _runs.SaveAsync(task, cancellationToken).ConfigureAwait(false);
        }

        return await _runs.TransitionAsync(
            run,
            RunState.Ready,
            RunEvent(run, EventType.StateChange, RunState.Ready, new JsonObject
            {
                ["task_count"] = tasks.Count,
            }),
            cancellationToken).ConfigureAwait(false);
    }

    // --- tasks ---------------------------------------------------------------

    /// <summary>Tasks whose dependencies have all succeeded.</summary>
    public static IReadOnlyList<RunTask> ReadyTasks(IReadOnlyList<RunTask> tasks)
    {
        ArgumentNullException.ThrowIfNull(tasks);

        Dictionary<TaskId, RunTask> byId = tasks.ToDictionary(task => task.Id);
        return
        [
            .. tasks.Where(task =>
                task.State == TaskState.Planned
                && task.Dependencies.All(id =>
                    byId.TryGetValue(id, out RunTask? dependency)
                    && dependency.State == TaskState.Succeeded)),
        ];
    }

    public Task<RunTask> MarkReadyAsync(RunTask task, CancellationToken cancellationToken = default) =>
        _runs.TransitionAsync(task, TaskState.Ready, TaskEvent(task, EventType.TaskReady), cancellationToken);

    public Task<RunTask> StartTaskAsync(RunTask task, CancellationToken cancellationToken = default) =>
        _runs.TransitionAsync(task, TaskState.Running, TaskEvent(task, EventType.StateChange), cancellationToken);

    public Task<RunTask> CompleteTaskAsync(RunTask task, CancellationToken cancellationToken = default) =>
        _runs.TransitionAsync(
            task, TaskState.Succeeded, TaskEvent(task, EventType.TaskSucceeded), cancellationToken);

    public Task<RunTask> FailTaskAsync(RunTask task, string reason, CancellationToken cancellationToken = default) =>
        _runs.TransitionAsync(
            task,
            TaskState.Failed,
            TaskEvent(task, EventType.TaskFailed, new JsonObject { ["reason"] = reason }),
            cancellationToken);

    /// <summary>Closes a task nobody is going to finish.</summary>
    public Task<RunTask> CancelTaskAsync(RunTask task, string reason, CancellationToken cancellationToken = default) =>
        _runs.TransitionAsync(
            task,
            TaskState.Cancelled,
            TaskEvent(task, EventType.TaskFailed, new JsonObject { ["reason"] = reason }),
            cancellationToken);

    /// <summary>
    /// Closes a run and everything in it that is still open.
    /// </summary>
    /// <remarks>
    /// Tasks that were never started are cancelled rather than failed. A task
    /// nobody ran did not fail, and recording it as a failure makes a run that
    /// was stopped on purpose look like one that went wrong.
    /// </remarks>
    public async Task<Run> CancelRunAsync(Run run, string reason, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(run);

        TaskState[] open = [TaskState.Planned, TaskState.Blocked, TaskState.Ready, TaskState.Running];

        foreach (RunTask task in await _runs.ListTasksAsync(run.Id, cancellationToken).ConfigureAwait(false))
        {
            if (open.Contains(task.State))
            {
                await CancelTaskAsync(task, reason, cancellationToken).ConfigureAwait(false);
            }
        }

        Run current = await _runs.FindAsync(run.Id, cancellationToken).ConfigureAwait(false) ?? run;

        if (current.State is RunState.Planning or RunState.Ready or RunState.Running)
        {
            return await _runs.TransitionAsync(
                current,
                RunState.Cancelled,
                RunEvent(current, EventType.RunFailed, RunState.Cancelled, new JsonObject
                {
                    ["reason"] = reason,
                }),
                cancellationToken).ConfigureAwait(false);
        }

        return current;
    }

    /// <summary>Whether every task is finished, and moves the run accordingly.</summary>
    public async Task<bool> EvaluateCompletionAsync(Run run, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(run);

        List<RunTask> tasks = await _runs.ListTasksAsync(run.Id, cancellationToken).ConfigureAwait(false);
        if (tasks.Count == 0)
        {
            return false;
        }

        if (tasks.Any(task => task.State == TaskState.Failed))
        {
            await AdvanceAsync(run, RunState.Failed, cancellationToken).ConfigureAwait(false);
            return false;
        }

        if (tasks.Any(task => task.State == TaskState.Cancelled))
        {
            // Stopping on purpose is not failing, and a run whose work was
            // cancelled must not be reported as verifiable.
            await AdvanceAsync(run, RunState.Cancelled, cancellationToken).ConfigureAwait(false);
            return false;
        }

        if (tasks.All(task => task.State.IsTerminal()))
        {
            await AdvanceAsync(run, RunState.Verifying, cancellationToken).ConfigureAwait(false);
            return true;
        }

        return false;
    }

    // --- events ---------------------------------------------------------------

    private DomainEvent RunEvent(Run run, EventType type, RunState to, JsonObject? extra = null)
    {
        JsonObject payload = new()
        {
            ["run_id"] = run.Id.Value,
            ["goal_id"] = run.GoalId.Value,
            ["previous"] = run.State.ToString(),
            ["next"] = to.ToString(),
        };

        Merge(payload, extra);

        return new DomainEvent
        {
            Id = IdFactory.NewEventId(),
            Timestamp = DateTimeOffset.UtcNow,
            ProjectId = _projectId,
            RunId = run.Id,
            Type = type,
            Payload = payload,
        };
    }

    private DomainEvent TaskEvent(RunTask task, EventType type, JsonObject? extra = null)
    {
        JsonObject payload = new()
        {
            ["task_id"] = task.Id.Value,
            ["objective"] = task.Objective,
            ["previous"] = task.State.ToString(),
        };

        Merge(payload, extra);

        return new DomainEvent
        {
            Id = IdFactory.NewEventId(),
            Timestamp = DateTimeOffset.UtcNow,
            ProjectId = _projectId,
            RunId = task.RunId,
            Type = type,
            Payload = payload,
        };
    }

    private static void Merge(JsonObject target, JsonObject? extra)
    {
        if (extra is null)
        {
            return;
        }

        foreach ((string key, JsonNode? value) in extra)
        {
            target[key] = value?.DeepClone();
        }
    }
}
