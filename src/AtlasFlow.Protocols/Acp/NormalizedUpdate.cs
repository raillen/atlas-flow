using System.Text.Json.Nodes;

namespace AtlasFlow.Protocols.Acp;

/// <summary>The closed set of things an agent update can turn out to be.</summary>
public enum UpdateKind
{
    Message,
    Thought,
    Terminal,
    File,
    Tool,
    Plan,
}

/// <summary>One thing the agent said, ran, or changed.</summary>
public sealed record NormalizedUpdate
{
    public required UpdateKind Kind { get; init; }

    public string Text { get; init; } = string.Empty;

    public IReadOnlyList<string> Paths { get; init; } = [];

    public string Tool { get; init; } = string.Empty;

    public string Status { get; init; } = string.Empty;

    /// <summary>The original payload, kept for diagnosis rather than for dispatch.</summary>
    public JsonObject? Raw { get; init; }

    /// <summary>The AG-UI event name this kind is broadcast under.</summary>
    public string EventName => Kind switch
    {
        UpdateKind.Message => "atlas.agent.message",
        UpdateKind.Thought => "atlas.agent.thought",
        UpdateKind.Terminal => "atlas.terminal.output",
        UpdateKind.File => "atlas.file.changed",
        UpdateKind.Tool => "atlas.tool.call",
        UpdateKind.Plan => "atlas.plan.updated",
        _ => throw new InvalidOperationException($"Unmapped update kind: {Kind}"),
    };

    /// <summary>The wire name of the kind, matching the previous implementation.</summary>
    public string KindName => Kind switch
    {
        UpdateKind.Message => "message",
        UpdateKind.Thought => "thought",
        UpdateKind.Terminal => "terminal",
        UpdateKind.File => "file",
        UpdateKind.Tool => "tool",
        UpdateKind.Plan => "plan",
        _ => throw new InvalidOperationException($"Unmapped update kind: {Kind}"),
    };

    /// <summary>The event payload published to AG-UI consumers.</summary>
    public JsonObject Payload()
    {
        var paths = new JsonArray();
        foreach (var path in Paths)
        {
            paths.Add(path);
        }

        return new JsonObject
        {
            ["kind"] = KindName,
            ["text"] = Text,
            ["paths"] = paths,
            ["tool"] = Tool,
            ["status"] = Status,
        };
    }
}
