using System.Text.Json.Nodes;

using AtlasFlow.Protocols.Acp;

namespace AtlasFlow.Protocols.Tests;

/// <summary>
/// P04 event normalization: one closed vocabulary out of many agent dialects.
/// </summary>
/// <remarks>
/// Ported from <c>reference/python-tests/unit/test_acp_events.py</c>, case for
/// case. The assertions are deliberately the same ones: a port that quietly
/// tests something easier is how behaviour drifts across a rewrite.
/// </remarks>
public sealed class SessionUpdateNormalizerTests
{
    private static JsonObject ToolCall(params (string Key, JsonNode? Value)[] overrides)
    {
        JsonObject call = new()
        {
            ["sessionUpdate"] = "tool_call",
            ["toolCallId"] = "call-1",
            ["title"] = "do the thing",
            ["status"] = "completed",
        };

        foreach ((string key, JsonNode? value) in overrides)
        {
            call[key] = value;
        }

        return call;
    }

    private static JsonObject TextBlock(string text) =>
        new() { ["type"] = "text", ["text"] = text };

    // --- Messages ---------------------------------------------------------

    [Fact]
    public void AnAgentMessageBecomesAMessageEvent()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(new JsonObject
        {
            ["sessionUpdate"] = "agent_message_chunk",
            ["content"] = TextBlock("working on it"),
        });

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.Message, update.Kind);
        Assert.Equal("working on it", update.Text);
        Assert.Equal("atlas.agent.message", update.EventName);
    }

    [Fact]
    public void ThoughtsAreDistinguishedFromMessages()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(new JsonObject
        {
            ["sessionUpdate"] = "agent_thought_chunk",
            ["content"] = TextBlock("maybe try X"),
        });

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.Thought, update.Kind);
    }

    [Fact]
    public void AnEmptyChunkPublishesNothing() =>
        Assert.Null(SessionUpdateNormalizer.Normalize(
            new JsonObject { ["sessionUpdate"] = "agent_message_chunk" }));

    [Fact]
    public void AnUnknownUpdateIsDroppedRatherThanForwardedUntyped()
    {
        // Forwarding a blob would leak one agent's vocabulary downstream.
        Assert.Null(SessionUpdateNormalizer.Normalize(
            new JsonObject { ["sessionUpdate"] = "vendor_specific_thing" }));
        Assert.Null(SessionUpdateNormalizer.Normalize([]));
    }

    // --- Terminal ---------------------------------------------------------

    [Fact]
    public void AnExecuteCallBecomesTerminalOutput()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("kind", "execute"),
            ("title", "dotnet test"),
            ("content", new JsonArray(new JsonObject
            {
                ["type"] = "terminal",
                ["content"] = TextBlock("2 passed\n"),
            }))));

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.Terminal, update.Kind);
        Assert.Equal("2 passed\n", update.Text);
        Assert.Equal("dotnet test", update.Tool);
        Assert.Equal("completed", update.Status);
        Assert.Equal("atlas.terminal.output", update.EventName);
    }

    [Fact]
    public void TerminalContentIsRecognizedWithoutAnExecuteKind()
    {
        // Agents that do not label the call kind still stream terminal blocks.
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("content", new JsonArray(new JsonObject
            {
                ["type"] = "terminal",
                ["content"] = TextBlock("hello"),
            }))));

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.Terminal, update.Kind);
        Assert.Equal("hello", update.Text);
    }

    [Fact]
    public void AnExecuteCallWithNoOutputYetStillReportsTheCommand()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(
            ToolCall(("kind", "execute"), ("status", "in_progress")));

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.Terminal, update.Kind);
        Assert.Equal(string.Empty, update.Text);
        Assert.Equal("in_progress", update.Status);
    }

    // --- Files ------------------------------------------------------------

    [Fact]
    public void AnEditReportsThePathsItTouched()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("kind", "edit"),
            ("locations", new JsonArray(new JsonObject { ["path"] = "src/Auth.cs" })),
            ("content", new JsonArray(
                new JsonObject { ["type"] = "diff", ["path"] = "src/Auth.cs", ["newText"] = "x" },
                new JsonObject { ["type"] = "diff", ["path"] = "src/Session.cs", ["newText"] = "y" }))));

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.File, update.Kind);
        Assert.Equal(["src/Auth.cs", "src/Session.cs"], update.Paths);
        Assert.Equal("2 file diff(s)", update.Text);
        Assert.Equal("atlas.file.changed", update.EventName);
    }

    [Fact]
    public void ADiffIsRecognizedWithoutAnEditKind()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("content", new JsonArray(
                new JsonObject { ["type"] = "diff", ["path"] = "a.cs", ["newText"] = "x" }))));

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.File, update.Kind);
        Assert.Equal(["a.cs"], update.Paths);
    }

    [Fact]
    public void ADeleteWithNoDiffIsStillAFileChange()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("kind", "delete"),
            ("locations", new JsonArray(new JsonObject { ["path"] = "old.cs" }))));

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.File, update.Kind);
        Assert.Equal(["old.cs"], update.Paths);
    }

    [Fact]
    public void APathNamedTwiceIsReportedOnce()
    {
        // Order matters for readability; duplicates do not.
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("kind", "edit"),
            ("locations", new JsonArray(new JsonObject { ["path"] = "a.cs" })),
            ("content", new JsonArray(
                new JsonObject { ["type"] = "diff", ["path"] = "a.cs", ["newText"] = "x" }))));

        Assert.NotNull(update);
        Assert.Equal(["a.cs"], update.Paths);
    }

    // --- Other ------------------------------------------------------------

    [Fact]
    public void AnUnclassifiedToolCallIsStillReportedAsAToolCall()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(("kind", "think")));

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.Tool, update.Kind);
        Assert.Equal("do the thing", update.Tool);
    }

    [Fact]
    public void ANamelessToolCallPublishesNothing() =>
        Assert.Null(SessionUpdateNormalizer.Normalize(new JsonObject
        {
            ["sessionUpdate"] = "tool_call",
            ["kind"] = "think",
        }));

    [Fact]
    public void APlanUpdateIsSummarized()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(new JsonObject
        {
            ["sessionUpdate"] = "plan",
            ["entries"] = new JsonArray(
                new JsonObject { ["content"] = "read the code", ["status"] = "completed" },
                new JsonObject { ["content"] = "write the fix", ["status"] = "pending" }),
        });

        Assert.NotNull(update);
        Assert.Equal(UpdateKind.Plan, update.Kind);
        Assert.Equal("read the code; write the fix", update.Text);
    }

    [Fact]
    public void ThePayloadCarriesEverythingAClientRenders()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("kind", "edit"),
            ("locations", new JsonArray(new JsonObject { ["path"] = "a.cs" }))));

        Assert.NotNull(update);
        Assert.Equal(
            """{"kind":"file","text":"","paths":["a.cs"],"tool":"do the thing","status":"completed"}""",
            update.Payload().ToJsonString());
    }

    // --- Redaction --------------------------------------------------------

    [Fact]
    public void ATokenInAgentOutputNeverLeavesTheBoundary()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(new JsonObject
        {
            ["sessionUpdate"] = "agent_message_chunk",
            ["content"] = TextBlock("using ghp_0123456789abcdefghij"),
        });

        Assert.NotNull(update);
        Assert.DoesNotContain("ghp_0123456789abcdefghij", update.Text, StringComparison.Ordinal);
        Assert.Contains("REDACTED", update.Text, StringComparison.Ordinal);
    }

    [Fact]
    public void TerminalOutputIsRedactedToo()
    {
        NormalizedUpdate? update = SessionUpdateNormalizer.Normalize(ToolCall(
            ("kind", "execute"),
            ("content", new JsonArray(new JsonObject
            {
                ["type"] = "terminal",
                ["content"] = TextBlock("export TOKEN=sk-abcdefghijklmnop"),
            }))));

        Assert.NotNull(update);
        Assert.DoesNotContain("sk-abcdefghijklmnop", update.Text, StringComparison.Ordinal);
    }
}
