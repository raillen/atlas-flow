using AtlasFlow.Domain.Execution;

namespace AtlasFlow.Orchestration.Execution;

/// <summary>What a runner did with one task.</summary>
public sealed record TaskOutcome
{
    public required bool IsSuccess { get; init; }

    /// <summary>What the runner produced, or why it failed. Shown to a person.</summary>
    public string Detail { get; init; } = string.Empty;

    public static TaskOutcome Success(string detail = "") =>
        new() { IsSuccess = true, Detail = detail };

    public static TaskOutcome Failure(string detail) =>
        new() { IsSuccess = false, Detail = detail };
}

/// <summary>Performs the work one task describes.</summary>
/// <remarks>
/// The seam between the orchestrator and whatever actually does the work — a
/// shell command, an ACP agent, or nothing at all. Everything above this
/// interface is scheduling; everything below it is the work.
/// </remarks>
public interface ITaskRunner
{
    /// <summary>The name a plan uses to ask for this runner.</summary>
    string Name { get; }

    Task<TaskOutcome> RunAsync(RunTask task, CancellationToken cancellationToken);
}

/// <summary>A runner that succeeds without doing anything.</summary>
/// <remarks>
/// Not a placeholder for a missing implementation — a real and useful one. It
/// is how the scheduler, the state machine and the event stream are exercised
/// end to end without an agent, a model or a worktree in the way. When a task
/// fails under this runner, the defect is in the orchestrator.
/// </remarks>
public sealed class NoOpTaskRunner : ITaskRunner
{
    public string Name => "dummy";

    public Task<TaskOutcome> RunAsync(RunTask task, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(task);
        cancellationToken.ThrowIfCancellationRequested();

        return Task.FromResult(TaskOutcome.Success($"no-op runner accepted '{task.Objective}'"));
    }
}
