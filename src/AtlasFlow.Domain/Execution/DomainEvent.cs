using System.Text.Json.Nodes;

namespace AtlasFlow.Domain.Execution;

/// <summary>Everything the runtime announces while a run is in flight.</summary>
public enum EventType
{
    RunStarted,
    RunCompleted,
    RunFailed,
    TaskReady,
    TaskSucceeded,
    TaskFailed,
    AttemptStarted,
    AttemptCompleted,
    AttemptFailed,
    GatePassed,
    GateFailed,
    StateChange,
}

/// <summary>
/// One thing that happened, durably recorded.
/// </summary>
/// <remarks>
/// These are the AG-UI stream. They were served over server-sent events to
/// reach a webview; the desktop app consumes them in-process as an
/// <see cref="IAsyncEnumerable{T}"/>. The event model is unchanged — only the
/// transport went away, and the transport existed to cross a process boundary
/// that no longer exists.
/// </remarks>
public sealed record DomainEvent
{
    public required string Id { get; init; }

    public required DateTimeOffset Timestamp { get; init; }

    public required EventType Type { get; init; }

    /// <summary>
    /// Which project produced this.
    /// </summary>
    /// <remarks>
    /// Atlas Flow runs against whatever project it was opened on, so an event
    /// that cannot name its project is unattributable.
    /// </remarks>
    public required string ProjectId { get; init; }

    public RunId? RunId { get; init; }

    /// <summary>
    /// Event-specific detail.
    /// </summary>
    /// <remarks>
    /// Untyped on purpose: the payload shape differs per event type and is
    /// rendered, not dispatched on. Anything the runtime branches on belongs in
    /// a property of its own rather than in here.
    /// </remarks>
    public JsonObject Payload { get; init; } = [];

    /// <summary>The AG-UI name this event is published under.</summary>
    public string Name => Type switch
    {
        EventType.RunStarted => "atlas.run.started",
        EventType.RunCompleted => "atlas.run.completed",
        EventType.RunFailed => "atlas.run.failed",
        EventType.TaskReady => "atlas.task.ready",
        EventType.TaskSucceeded => "atlas.task.succeeded",
        EventType.TaskFailed => "atlas.task.failed",
        EventType.AttemptStarted => "atlas.attempt.started",
        EventType.AttemptCompleted => "atlas.attempt.completed",
        EventType.AttemptFailed => "atlas.attempt.failed",
        EventType.GatePassed => "atlas.gate.passed",
        EventType.GateFailed => "atlas.gate.failed",
        EventType.StateChange => "atlas.state.change",
        _ => throw new InvalidOperationException($"Unmapped event type: {Type}"),
    };
}
