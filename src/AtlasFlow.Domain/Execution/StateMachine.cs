namespace AtlasFlow.Domain.Execution;

/// <summary>
/// Which state changes are legal, for runs, tasks and attempts.
/// </summary>
/// <remarks>
/// This is domain law, not storage policy, which is why it lives here rather
/// than beside the SQL that enforces it. A transition that is not listed is
/// refused, and the refusal is an error rather than a silent no-op — a state
/// machine that quietly ignores an illegal move leaves the event log unable to
/// explain the current state, and the event log is what recovery reads back.
/// </remarks>
public static class StateMachine
{
    private static readonly Dictionary<RunState, RunState[]> RunTransitions = new()
    {
        [RunState.Created] = [RunState.Planning, RunState.Cancelled],
        [RunState.Planning] = [RunState.Ready, RunState.Failed, RunState.Cancelled],
        [RunState.Ready] = [RunState.Running, RunState.Cancelled],
        [RunState.Running] = [RunState.Verifying, RunState.Blocked, RunState.Failed, RunState.Cancelled],
        [RunState.Verifying] = [RunState.Reviewing, RunState.Failed],
        [RunState.Reviewing] = [RunState.Completed, RunState.Failed],
    };

    // Cancellation has to reach every state that is not already finished.
    // Planned could not be cancelled and Blocked could not move at all, so a
    // run stopped before its tasks started had to mark them Ready first — a lie
    // the state machine forced — and a task that became unblocked was stuck
    // forever. Both were real defects.
    private static readonly Dictionary<TaskState, TaskState[]> TaskTransitions = new()
    {
        [TaskState.Planned] = [TaskState.Ready, TaskState.Blocked, TaskState.Cancelled],
        [TaskState.Blocked] = [TaskState.Ready, TaskState.Cancelled],
        [TaskState.Ready] = [TaskState.Running, TaskState.Cancelled],
        [TaskState.Running] = [TaskState.Succeeded, TaskState.Failed, TaskState.Cancelled],
        [TaskState.Succeeded] = [TaskState.Superseded],
        [TaskState.Failed] = [TaskState.Ready, TaskState.Cancelled],
    };

    private static readonly Dictionary<AttemptState, AttemptState[]> AttemptTransitions = new()
    {
        [AttemptState.Created] = [AttemptState.Starting, AttemptState.Cancelled],
        [AttemptState.Starting] = [AttemptState.Running, AttemptState.Failed, AttemptState.Cancelled],
        [AttemptState.Running] = [AttemptState.Completed, AttemptState.Failed, AttemptState.Cancelled],
    };

    public static bool CanTransition(RunState from, RunState to) =>
        RunTransitions.TryGetValue(from, out var allowed) && allowed.Contains(to);

    public static bool CanTransition(TaskState from, TaskState to) =>
        TaskTransitions.TryGetValue(from, out var allowed) && allowed.Contains(to);

    public static bool CanTransition(AttemptState from, AttemptState to) =>
        AttemptTransitions.TryGetValue(from, out var allowed) && allowed.Contains(to);

    /// <summary>Whether a run has stopped for good.</summary>
    public static bool IsTerminal(this RunState state) =>
        state is RunState.Completed or RunState.Cancelled or RunState.Failed;

    /// <summary>Whether a task will not move again on its own.</summary>
    public static bool IsTerminal(this TaskState state) =>
        state is TaskState.Succeeded or TaskState.Cancelled or TaskState.Superseded;

    public static bool IsTerminal(this AttemptState state) =>
        state is AttemptState.Completed or AttemptState.Failed or AttemptState.Cancelled;
}

/// <summary>A state change the domain does not permit.</summary>
public sealed class InvalidTransitionException : Exception
{
    public InvalidTransitionException() { }

    public InvalidTransitionException(string message) : base(message) { }

    public InvalidTransitionException(string message, Exception innerException)
        : base(message, innerException) { }

    public static InvalidTransitionException For(string entity, string id, object from, object to) =>
        new($"{entity} {id}: {from} -> {to} is not a valid transition");
}
