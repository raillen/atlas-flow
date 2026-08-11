using System.Text.Json.Nodes;

using AtlasFlow.Domain.Security;

namespace AtlasFlow.Protocols.Acp;

/// <summary>
/// Turns ACP <c>session/update</c> payloads into the runtime's own records.
/// </summary>
/// <remarks>
/// An agent narrates its work through <c>session/update</c> notifications, and
/// every agent shapes them slightly differently. This turns that stream into a
/// small closed set of records the rest of the runtime can act on, so nothing
/// downstream has to know the wire vocabulary of a particular agent.
/// <para>
/// What survives normalization is what an operator needs to answer three
/// questions: what is the agent saying, what did it run, and what did it
/// change. An update that answers none of those is dropped rather than
/// forwarded as an untyped blob.
/// </para>
/// </remarks>
public static class SessionUpdateNormalizer
{
    // Terminal output arrives either as a content block of type "terminal" or,
    // in agents that predate that block, as the output of an "execute" tool call.
    private static readonly HashSet<string> ExecuteKinds =
        new(StringComparer.Ordinal) { "execute", "terminal", "shell" };

    private static readonly HashSet<string> EditKinds =
        new(StringComparer.Ordinal) { "edit", "write", "create", "delete", "move" };

    /// <summary>
    /// Normalizes one update, or returns <c>null</c> if it says nothing.
    /// </summary>
    /// <remarks>
    /// Text is redacted here, at the boundary where agent output enters the
    /// runtime. Doing it later would mean choosing which of the several
    /// consumers to protect; doing it here means none of them ever sees a
    /// secret.
    /// </remarks>
    public static NormalizedUpdate? Normalize(JsonObject update)
    {
        ArgumentNullException.ThrowIfNull(update);

        var classified = Classify(update);
        if (classified is not null && classified.Text.Length > 0)
        {
            classified = classified with { Text = SecretRedactor.Redact(classified.Text) };
        }

        return classified;
    }

    private static NormalizedUpdate? Classify(JsonObject update)
    {
        var sessionUpdate = StringOf(update, "sessionUpdate");

        switch (sessionUpdate)
        {
            case "agent_message_chunk":
            case "user_message_chunk":
            {
                var text = ContentText(update["content"]);
                return text.Length == 0
                    ? null
                    : new NormalizedUpdate { Kind = UpdateKind.Message, Text = text, Raw = update };
            }

            case "agent_thought_chunk":
            {
                var text = ContentText(update["content"]);
                return text.Length == 0
                    ? null
                    : new NormalizedUpdate { Kind = UpdateKind.Thought, Text = text, Raw = update };
            }

            case "plan":
                return new NormalizedUpdate
                {
                    Kind = UpdateKind.Plan,
                    Text = PlanSummary(update["entries"]),
                    Raw = update,
                };

            case "tool_call":
            case "tool_call_update":
                return NormalizeToolCall(update);

            default:
                return null;
        }
    }

    private static NormalizedUpdate? NormalizeToolCall(JsonObject update)
    {
        var kind = StringOf(update, "kind").ToLowerInvariant();
        var title = StringOf(update, "title");
        if (title.Length == 0)
        {
            title = StringOf(update, "toolCallId");
        }

        var status = StringOf(update, "status");
        var blocks = update["content"] as JsonArray ?? [];

        var terminalText = string.Concat(
            blocks.OfType<JsonObject>()
                  .Where(block => StringOf(block, "type") == "terminal")
                  .Select(block => ContentText(block["content"])));

        var diffs = blocks.OfType<JsonObject>()
                          .Where(block => StringOf(block, "type") == "diff")
                          .ToList();

        var paths = Paths(update, diffs);

        if (ExecuteKinds.Contains(kind) || terminalText.Length > 0)
        {
            return new NormalizedUpdate
            {
                Kind = UpdateKind.Terminal,
                Text = terminalText.Length > 0 ? terminalText : ContentText(update["rawOutput"]),
                Tool = title,
                Status = status,
                Raw = update,
            };
        }

        if (EditKinds.Contains(kind) || diffs.Count > 0)
        {
            return new NormalizedUpdate
            {
                Kind = UpdateKind.File,
                Text = diffs.Count == 0 ? string.Empty : $"{diffs.Count} file diff(s)",
                Paths = paths,
                Tool = title,
                Status = status,
                Raw = update,
            };
        }

        return title.Length == 0
            ? null
            : new NormalizedUpdate
            {
                Kind = UpdateKind.Tool,
                Tool = title,
                Status = status,
                Paths = paths,
                Raw = update,
            };
    }

    /// <summary>Every file the call names, from its locations and its diffs.</summary>
    private static List<string> Paths(JsonObject update, IReadOnlyList<JsonObject> diffs)
    {
        // Order matters for readability; duplicates do not.
        var found = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        void Add(string candidate)
        {
            if (candidate.Length > 0 && seen.Add(candidate))
            {
                found.Add(candidate);
            }
        }

        if (update["locations"] is JsonArray locations)
        {
            foreach (var location in locations.OfType<JsonObject>())
            {
                Add(StringOf(location, "path"));
            }
        }

        foreach (var diff in diffs)
        {
            Add(StringOf(diff, "path"));
        }

        return found;
    }

    private static string PlanSummary(JsonNode? entries)
    {
        if (entries is not JsonArray array)
        {
            return string.Empty;
        }

        return string.Join(
            "; ",
            array.OfType<JsonObject>()
                 .Select(entry => StringOf(entry, "content"))
                 .Where(content => content.Length > 0));
    }

    /// <summary>Text out of an ACP content block, a list of them, or a bare string.</summary>
    private static string ContentText(JsonNode? content)
    {
        switch (content)
        {
            case null:
                return string.Empty;

            case JsonArray array:
                return string.Concat(array.Select(ContentText));

            case JsonObject obj:
            {
                var type = StringOf(obj, "type");
                if ((type.Length == 0 || type == "text") && obj.ContainsKey("text"))
                {
                    return StringOf(obj, "text");
                }

                if (obj.ContainsKey("output"))
                {
                    return StringOf(obj, "output");
                }

                return obj.ContainsKey("content") ? ContentText(obj["content"]) : string.Empty;
            }

            case JsonValue value:
                return value.TryGetValue<string>(out var text) ? text : string.Empty;

            default:
                return string.Empty;
        }
    }

    private static string StringOf(JsonObject obj, string key) =>
        obj.TryGetPropertyValue(key, out var node) && node is JsonValue value
        && value.TryGetValue<string>(out var text)
            ? text
            : string.Empty;
}
