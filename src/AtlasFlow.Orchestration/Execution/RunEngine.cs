using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Planning;
using AtlasFlow.Persistence;

namespace AtlasFlow.Orchestration.Execution;

/// <summary>Drives one run from a locked plan to a terminal state.</summary>
/// <remarks>
/// <para>
/// The loop is deliberately simple: find the tasks whose dependencies have
/// succeeded, run them, repeat. Concurrency, budgets, retries, worktrees and
/// real runners are not here yet — this exists to make the state machine and
/// the event stream real, and adding the rest on top of something proven is
/// cheaper than debugging all of it at once.
/// </para>
/// <para>
/// Cancellation is honoured between tasks rather than inside one. A task the
/// runner has started is allowed to finish or fail on its own; killing it
/// mid-write is how a worktree is left in a state nobody can explain.
/// </para>
/// </remarks>
public sealed class RunEngine(RunRepository runs, Scheduler scheduler, ITaskRunner runner)
{
    private readonly RunRepository _runs = runs;
    private readonly Scheduler _scheduler = scheduler;
    private readonly ITaskRunner _runner = runner;

    /// <summary>Plans, schedules and executes, returning the run's final state.</summary>
    public async Task<Run> ExecuteAsync(Run created, Plan plan, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(created);
        ArgumentNullException.ThrowIfNull(plan);

        Run run = await _scheduler.StartAsync(created, cancellationToken).ConfigureAwait(false);

        IReadOnlyList<RunTask> tasks = Materialize(plan, run.Id);
        run = await _scheduler.ScheduleAsync(run, tasks, cancellationToken).ConfigureAwait(false);
        run = await _scheduler.AdvanceAsync(run, RunState.Running, cancellationToken).ConfigureAwait(false);

        while (true)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                return await _scheduler
                    .CancelRunAsync(run, "cancelled by request", CancellationToken.None)
                    .ConfigureAwait(false);
            }

            List<RunTask> current = await _runs.ListTasksAsync(run.Id, cancellationToken).ConfigureAwait(false);
            IReadOnlyList<RunTask> ready = Scheduler.ReadyTasks(current);

            if (ready.Count == 0)
            {
                break;
            }

            foreach (RunTask planned in ready)
            {
                await RunOneAsync(planned, cancellationToken).ConfigureAwait(false);
            }
        }

        await _scheduler.EvaluateCompletionAsync(run, cancellationToken).ConfigureAwait(false);
        return await _runs.FindAsync(run.Id, cancellationToken).ConfigureAwait(false) ?? run;
    }

    private async Task RunOneAsync(RunTask planned, CancellationToken cancellationToken)
    {
        RunTask task = await _scheduler.MarkReadyAsync(planned, cancellationToken).ConfigureAwait(false);
        task = await _scheduler.StartTaskAsync(task, cancellationToken).ConfigureAwait(false);

        TaskOutcome outcome;
        try
        {
            outcome = await _runner.RunAsync(task, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            await _scheduler.CancelTaskAsync(task, "cancelled by request", CancellationToken.None)
                .ConfigureAwait(false);
            return;
        }
#pragma warning disable CA1031 // A runner is arbitrary code. Its failure is a
        // failed task, which is a state the run knows how to be in, not an
        // exception that tears down the engine and leaves the run RUNNING
        // forever with nothing behind it.
        catch (Exception exc)
#pragma warning restore CA1031
        {
            await _scheduler.FailTaskAsync(task, exc.Message, cancellationToken).ConfigureAwait(false);
            return;
        }

        if (outcome.IsSuccess)
        {
            await _scheduler.CompleteTaskAsync(task, cancellationToken).ConfigureAwait(false);
        }
        else
        {
            await _scheduler.FailTaskAsync(task, outcome.Detail, cancellationToken).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// Turns plan nodes into persisted tasks, rewriting their dependency ids.
    /// </summary>
    /// <remarks>
    /// Plan nodes carry planner-local ids; tasks get generated ones. The
    /// dependency lists have to be translated with them. Skipping that
    /// translation was a real defect: the scheduler saw dependencies matching
    /// no task, treated every task as immediately ready, and ran the whole DAG
    /// at once — which looks like success until two tasks write the same file.
    /// </remarks>
    internal static IReadOnlyList<RunTask> Materialize(Plan plan, RunId runId)
    {
        DateTimeOffset now = DateTimeOffset.UtcNow;

        Dictionary<TaskId, TaskId> rewritten =
            plan.Tasks.ToDictionary(node => node.Id, _ => IdFactory.NewTask());

        return
        [
            .. plan.Tasks.Select(node => new RunTask
            {
                Id = rewritten[node.Id],
                RunId = runId,
                Objective = node.Objective,
                State = TaskState.Planned,
                Risk = node.Risk,
                CreatedAt = now,
                Role = node.Capabilities.Count > 0 ? node.Capabilities[0] : "core-implementer",
                WriteScope = node.WriteScope,
                Dependencies = [.. node.Dependencies.Select(id => rewritten[id])],
            }),
        ];
    }
}
