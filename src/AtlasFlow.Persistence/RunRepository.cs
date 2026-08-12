using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;

using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence;

/// <summary>Runs, their tasks, and the attempts at those tasks.</summary>
/// <remarks>
/// The three live together because they change together: a state transition
/// writes a row and the event that explains it in one transaction, and
/// splitting them across repositories would put that transaction across a
/// boundary where somebody would eventually break it.
/// </remarks>
public sealed class RunRepository(AtlasFlowDatabase database, EventStore events)
{
    private const string UpsertRun = """
        INSERT OR REPLACE INTO runs
            (id, project_id, goal_id, goal_revision, state, autonomy, created_at, started_at, completed_at)
        VALUES ($id, $projectId, $goalId, $goalRevision, $state, $autonomy, $createdAt, $startedAt, $completedAt)
        """;

    private const string UpsertTask = """
        INSERT OR REPLACE INTO tasks
            (id, run_id, objective, role, risk, scope, state, dependencies, created_at)
        VALUES ($id, $runId, $objective, $role, $risk, $scope, $state, $dependencies, $createdAt)
        """;

    private const string UpsertAttempt = """
        INSERT OR REPLACE INTO attempts
            (id, task_id, run_id, runner, model_provider, model_id, state,
             created_at, started_at, completed_at, error_msg)
        VALUES ($id, $taskId, $runId, $runner, $modelProvider, $modelId, $state,
                $createdAt, $startedAt, $completedAt, $error)
        """;

    private readonly AtlasFlowDatabase _database = database;
    private readonly EventStore _events = events;

    // --- runs -------------------------------------------------------------

    public Task SaveAsync(Run run, CancellationToken cancellationToken = default) =>
        _database.ExecuteAsync(UpsertRun, ParametersFor(run), cancellationToken);

    public Task<Run?> FindAsync(RunId id, CancellationToken cancellationToken = default) =>
        _database.QuerySingleAsync(
            "SELECT * FROM runs WHERE id = $id",
            ReadRun,
            new Dictionary<string, object?> { ["$id"] = id.Value },
            cancellationToken);

    public Task<List<Run>> ListAsync(string? projectId = null, CancellationToken cancellationToken = default) =>
        projectId is null
            ? _database.QueryAsync("SELECT * FROM runs ORDER BY created_at DESC", ReadRun, null, cancellationToken)
            : _database.QueryAsync(
                "SELECT * FROM runs WHERE project_id = $projectId ORDER BY created_at DESC",
                ReadRun,
                new Dictionary<string, object?> { ["$projectId"] = projectId },
                cancellationToken);

    /// <summary>Moves a run and appends the event that explains it, atomically.</summary>
    /// <exception cref="InvalidTransitionException">The move is not legal.</exception>
    public async Task<Run> TransitionAsync(
        Run run,
        RunState to,
        DomainEvent domainEvent,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(run);

        if (!StateMachine.CanTransition(run.State, to))
        {
            throw InvalidTransitionException.For("run", run.Id.Value, run.State, to);
        }

        Run updated = run with { State = to };
        await CommitAsync((UpsertRun, ParametersFor(updated)), domainEvent, cancellationToken).ConfigureAwait(false);
        return updated;
    }

    // --- tasks ------------------------------------------------------------

    public Task SaveAsync(RunTask task, CancellationToken cancellationToken = default) =>
        _database.ExecuteAsync(UpsertTask, ParametersFor(task), cancellationToken);

    public Task<List<RunTask>> ListTasksAsync(RunId runId, CancellationToken cancellationToken = default) =>
        _database.QueryAsync(
            "SELECT * FROM tasks WHERE run_id = $runId ORDER BY created_at",
            ReadTask,
            new Dictionary<string, object?> { ["$runId"] = runId.Value },
            cancellationToken);

    /// <inheritdoc cref="TransitionAsync(Run, RunState, DomainEvent, CancellationToken)"/>
    public async Task<RunTask> TransitionAsync(
        RunTask task,
        TaskState to,
        DomainEvent domainEvent,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(task);

        if (!StateMachine.CanTransition(task.State, to))
        {
            throw InvalidTransitionException.For("task", task.Id.Value, task.State, to);
        }

        RunTask updated = task with { State = to };
        await CommitAsync((UpsertTask, ParametersFor(updated)), domainEvent, cancellationToken).ConfigureAwait(false);
        return updated;
    }

    // --- attempts ---------------------------------------------------------

    public Task SaveAsync(Attempt attempt, CancellationToken cancellationToken = default) =>
        _database.ExecuteAsync(UpsertAttempt, ParametersFor(attempt), cancellationToken);

    public Task<List<Attempt>> ListAttemptsAsync(RunId runId, CancellationToken cancellationToken = default) =>
        _database.QueryAsync(
            "SELECT * FROM attempts WHERE run_id = $runId ORDER BY created_at",
            ReadAttempt,
            new Dictionary<string, object?> { ["$runId"] = runId.Value },
            cancellationToken);

    public Task<List<Attempt>> ListAttemptsForTaskAsync(TaskId taskId, CancellationToken cancellationToken = default) =>
        _database.QueryAsync(
            "SELECT * FROM attempts WHERE task_id = $taskId ORDER BY created_at",
            ReadAttempt,
            new Dictionary<string, object?> { ["$taskId"] = taskId.Value },
            cancellationToken);

    /// <inheritdoc cref="TransitionAsync(Run, RunState, DomainEvent, CancellationToken)"/>
    public async Task<Attempt> TransitionAsync(
        Attempt attempt,
        AttemptState to,
        DomainEvent domainEvent,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(attempt);

        if (!StateMachine.CanTransition(attempt.State, to))
        {
            throw InvalidTransitionException.For("attempt", attempt.Id.Value, attempt.State, to);
        }

        Attempt updated = attempt with { State = to };
        await CommitAsync((UpsertAttempt, ParametersFor(updated)), domainEvent, cancellationToken)
            .ConfigureAwait(false);
        return updated;
    }

    // --- shared -----------------------------------------------------------

    private async Task CommitAsync(
        (string Sql, IReadOnlyDictionary<string, object?> Parameters) write,
        DomainEvent domainEvent,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(domainEvent);

        await _database.ExecuteInTransactionAsync(
            [
                (write.Sql, write.Parameters),
                EventStore.InsertStatement(domainEvent),
            ],
            cancellationToken).ConfigureAwait(false);

        await _events.PublishAsync(domainEvent, cancellationToken).ConfigureAwait(false);
    }

    private static Dictionary<string, object?> ParametersFor(Run run) => new()
    {
        ["$id"] = run.Id.Value,
        ["$projectId"] = run.ProjectId,
        ["$goalId"] = run.GoalId.Value,
        ["$goalRevision"] = run.GoalRevision,
        ["$state"] = SqlValues.Text(run.State),
        ["$autonomy"] = SqlValues.Text(run.Autonomy),
        ["$createdAt"] = SqlValues.Text(run.CreatedAt),
        ["$startedAt"] = SqlValues.Text(run.StartedAt),
        ["$completedAt"] = SqlValues.Text(run.CompletedAt),
    };

    private static Dictionary<string, object?> ParametersFor(RunTask task) => new()
    {
        ["$id"] = task.Id.Value,
        ["$runId"] = task.RunId.Value,
        ["$objective"] = task.Objective,
        ["$role"] = task.Role,
        ["$risk"] = SqlValues.Text(task.Risk),
        ["$scope"] = SqlValues.Json(task.WriteScope.Select(path => path.Value)),
        ["$state"] = SqlValues.Text(task.State),
        ["$dependencies"] = SqlValues.Json(task.Dependencies.Select(id => id.Value)),
        ["$createdAt"] = SqlValues.Text(task.CreatedAt),
    };

    private static Dictionary<string, object?> ParametersFor(Attempt attempt) => new()
    {
        ["$id"] = attempt.Id.Value,
        ["$taskId"] = attempt.TaskId.Value,
        ["$runId"] = attempt.RunId.Value,
        ["$runner"] = attempt.Runner,
        ["$modelProvider"] = attempt.ModelProvider,
        ["$modelId"] = attempt.ModelId,
        ["$state"] = SqlValues.Text(attempt.State),
        ["$createdAt"] = SqlValues.Text(attempt.CreatedAt),
        ["$startedAt"] = SqlValues.Text(attempt.StartedAt),
        ["$completedAt"] = SqlValues.Text(attempt.CompletedAt),
        ["$error"] = attempt.Error,
    };

    private static Run ReadRun(SqliteDataReader reader) => new()
    {
        Id = new RunId(reader.String("id")),
        ProjectId = reader.String("project_id"),
        GoalId = new GoalId(reader.String("goal_id")),
        GoalRevision = reader.String("goal_revision"),
        State = SqlValues.RunStateOf(reader.String("state")),
        Autonomy = SqlValues.AutonomyOf(reader.String("autonomy")),
        CreatedAt = reader.Moment("created_at"),
        StartedAt = reader.NullableMoment("started_at"),
        CompletedAt = reader.NullableMoment("completed_at"),
    };

    private static RunTask ReadTask(SqliteDataReader reader) => new()
    {
        Id = new TaskId(reader.String("id")),
        RunId = new RunId(reader.String("run_id")),
        Objective = reader.String("objective"),
        Role = reader.NullableString("role"),
        Risk = SqlValues.RiskOf(reader.String("risk")),
        WriteScope = [.. SqlValues.StringsOf(reader.String("scope")).Select(p => new ProjectPath(p))],
        State = SqlValues.TaskStateOf(reader.String("state")),
        Dependencies = [.. SqlValues.StringsOf(reader.String("dependencies")).Select(d => new TaskId(d))],
        CreatedAt = reader.Moment("created_at"),
    };

    private static Attempt ReadAttempt(SqliteDataReader reader) => new()
    {
        Id = new AttemptId(reader.String("id")),
        TaskId = new TaskId(reader.String("task_id")),
        RunId = new RunId(reader.String("run_id")),
        Runner = reader.NullableString("runner"),
        ModelProvider = reader.NullableString("model_provider"),
        ModelId = reader.NullableString("model_id"),
        State = SqlValues.AttemptStateOf(reader.String("state")),
        CreatedAt = reader.Moment("created_at"),
        StartedAt = reader.NullableMoment("started_at"),
        CompletedAt = reader.NullableMoment("completed_at"),
        Error = reader.NullableString("error_msg"),
    };
}
