using System.Globalization;
using System.Text;
using System.Text.Json.Nodes;

namespace AtlasFlow.Protocols.Acp;

/// <summary>Decides whether an agent may do what it is asking to do.</summary>
public delegate Task<bool> PermissionPolicy(PermissionRequest request, CancellationToken cancellationToken);

/// <summary>Receives every raw <c>session/update</c>, recognized or not.</summary>
public delegate Task UpdateListener(string sessionUpdate, JsonObject update, CancellationToken cancellationToken);

/// <summary>Receives every update that normalized into a known kind.</summary>
public delegate Task EventListener(NormalizedUpdate update, CancellationToken cancellationToken);

/// <summary>An agent asking to do something the client must authorize.</summary>
public sealed record PermissionRequest
{
    public required string SessionId { get; init; }

    public required string ToolName { get; init; }

    public IReadOnlyList<JsonObject> Options { get; init; } = [];

    public JsonObject? Raw { get; init; }

    /// <summary>First option matching a kind such as <c>allow_once</c> or <c>reject_once</c>.</summary>
    public string? OptionId(string kind)
    {
        foreach (JsonObject option in Options)
        {
            if (option.TryGetPropertyValue("kind", out JsonNode? k)
                && k?.GetValue<string>() == kind
                && option.TryGetPropertyValue("optionId", out JsonNode? id)
                && id is not null)
            {
                return id.ToString();
            }
        }

        return null;
    }
}

/// <summary>What the agent said it can do, as returned from initialize.</summary>
public sealed record AgentCapabilities
{
    public int ProtocolVersion { get; init; } = AcpClient.ProtocolVersion;

    public JsonObject Raw { get; init; } = [];

    public bool Supports(string name)
    {
        if (!Raw.TryGetPropertyValue(name, out JsonNode? value) || value is null)
        {
            return false;
        }

        return value is JsonValue v && v.TryGetValue<bool>(out bool flag)
            ? flag
            : value is not JsonValue || value.ToJsonString() != "null";
    }

    public JsonObject PromptCapabilities =>
        Raw.TryGetPropertyValue("promptCapabilities", out JsonNode? value) && value is JsonObject obj
            ? obj
            : [];
}

/// <summary>Everything one <c>session/prompt</c> turn produced.</summary>
public sealed record PromptResult
{
    public string StopReason { get; init; } = string.Empty;

    public string Text { get; init; } = string.Empty;

    public IReadOnlyList<JsonObject> Updates { get; init; } = [];

    public IReadOnlyList<NormalizedUpdate> Events { get; init; } = [];

    public IReadOnlyList<PermissionRequest> PermissionsRequested { get; init; } = [];

    public IReadOnlyList<string> PermissionsDenied { get; init; } = [];

    public bool Completed =>
        StopReason is "end_turn" or "completed";

    public string TerminalOutput =>
        string.Concat(Events.Where(e => e.Kind == UpdateKind.Terminal).Select(e => e.Text));

    /// <summary>Every path the agent reported touching, in the order it touched them.</summary>
    public IReadOnlyList<string> FilesChanged
    {
        get
        {
            List<string> paths = [];
            HashSet<string> seen = new(StringComparer.Ordinal);
            foreach (NormalizedUpdate e in Events.Where(e => e.Kind == UpdateKind.File))
            {
                foreach (string path in e.Paths)
                {
                    if (seen.Add(path))
                    {
                        paths.Add(path);
                    }
                }
            }

            return paths;
        }
    }
}

/// <summary>
/// Drives one ACP agent process: session lifecycle, capability negotiation,
/// permissions.
/// </summary>
/// <remarks>
/// <para>
/// Atlas Flow is the client. It negotiates capabilities on initialize and then
/// only uses what the agent actually advertised — an agent that does not
/// support a feature degrades to doing without it, never to a crash.
/// </para>
/// <para>
/// The accumulators below are guarded by a lock. In the Python original a
/// single-threaded event loop made that unnecessary; here the notification
/// handler runs on the connection's read loop while the caller awaits
/// <see cref="PromptAsync"/> on another thread, so unsynchronized
/// <c>List.Add</c> would be a genuine race rather than a theoretical one.
/// </para>
/// </remarks>
public sealed class AcpClient : IAsyncDisposable
{
    public const int ProtocolVersion = 1;

    private readonly Lock _gate = new();
    private readonly List<JsonObject> _updates = [];
    private readonly List<NormalizedUpdate> _events = [];
    private readonly List<PermissionRequest> _permissions = [];
    private readonly List<string> _denied = [];

    public AcpClient(
        PermissionPolicy? permissionPolicy = null,
        UpdateListener? onUpdate = null,
        EventListener? onEvent = null)
    {
        Connection = new AcpConnection();
        Connection.RequestHandlers["session/request_permission"] = OnPermissionRequestAsync;
        Connection.OnNotification = OnNotificationAsync;

        PermissionPolicy = permissionPolicy ?? DenyAllAsync;
        OnUpdate = onUpdate;
        OnEvent = onEvent;
    }

    public AcpConnection Connection { get; }

    public PermissionPolicy PermissionPolicy { get; set; }

    public UpdateListener? OnUpdate { get; set; }

    public EventListener? OnEvent { get; set; }

    public AgentCapabilities Capabilities { get; private set; } = new();

    public string? SessionId { get; private set; }

    /// <summary>
    /// Default policy: refuse anything nobody explicitly allowed.
    /// </summary>
    /// <remarks>
    /// Silently granting an agent whatever it asks for would make the
    /// permission round-trip decorative. Callers opt into a looser policy
    /// deliberately.
    /// </remarks>
    public static Task<bool> DenyAllAsync(PermissionRequest request, CancellationToken cancellationToken) =>
        Task.FromResult(false);

    public Task StartAsync(IReadOnlyList<string> command, string? workingDirectory = null) =>
        Connection.StartAsync(command, workingDirectory);

    public async Task<AgentCapabilities> InitializeAsync(
        JsonObject? clientCapabilities = null,
        CancellationToken cancellationToken = default)
    {
        clientCapabilities ??= new JsonObject
        {
            ["fs"] = new JsonObject { ["readTextFile"] = true, ["writeTextFile"] = true },
        };

        JsonNode? result = await Connection.CallAsync(
            "initialize",
            new JsonObject
            {
                ["protocolVersion"] = ProtocolVersion,
                ["clientCapabilities"] = clientCapabilities,
            },
            cancellationToken: cancellationToken).ConfigureAwait(false);

        if (result is not JsonObject payload)
        {
            throw new AcpException("initialize returned no capabilities");
        }

        int negotiated = payload.TryGetPropertyValue("protocolVersion", out JsonNode? version) && version is not null
            ? version.GetValue<int>()
            : ProtocolVersion;

        if (negotiated > ProtocolVersion)
        {
            throw new AcpException(string.Create(
                CultureInfo.InvariantCulture,
                $"Agent speaks ACP v{negotiated}; this client supports v{ProtocolVersion}"));
        }

        Capabilities = new AgentCapabilities
        {
            ProtocolVersion = negotiated,
            Raw = payload.TryGetPropertyValue("agentCapabilities", out JsonNode? caps) && caps is JsonObject obj
                ? (JsonObject)obj.DeepClone()
                : [],
        };

        return Capabilities;
    }

    public async Task<string> NewSessionAsync(
        string workingDirectory,
        IReadOnlyList<JsonObject>? mcpServers = null,
        CancellationToken cancellationToken = default)
    {
        JsonArray servers = [];
        foreach (JsonObject server in mcpServers ?? [])
        {
            servers.Add(server.DeepClone());
        }

        JsonNode? result = await Connection.CallAsync(
            "session/new",
            new JsonObject { ["cwd"] = workingDirectory, ["mcpServers"] = servers },
            cancellationToken: cancellationToken).ConfigureAwait(false);

        if (result is not JsonObject payload
            || !payload.TryGetPropertyValue("sessionId", out JsonNode? id)
            || id is null)
        {
            throw new AcpException("session/new did not return a sessionId");
        }

        SessionId = id.ToString();
        return SessionId;
    }

    /// <summary>Resumes a previous session when the agent supports it.</summary>
    public async Task<bool> LoadSessionAsync(
        string sessionId,
        string workingDirectory,
        CancellationToken cancellationToken = default)
    {
        if (!Capabilities.Supports("loadSession"))
        {
            return false;
        }

        await Connection.CallAsync(
            "session/load",
            new JsonObject { ["sessionId"] = sessionId, ["cwd"] = workingDirectory },
            cancellationToken: cancellationToken).ConfigureAwait(false);

        SessionId = sessionId;
        return true;
    }

    public async Task<PromptResult> PromptAsync(
        string text,
        TimeSpan? timeout = null,
        CancellationToken cancellationToken = default)
    {
        if (SessionId is null)
        {
            throw new AcpException("prompt called before a session was created");
        }

        lock (_gate)
        {
            _updates.Clear();
            _events.Clear();
            _permissions.Clear();
            _denied.Clear();
        }

        JsonNode? result = await Connection.CallAsync(
            "session/prompt",
            new JsonObject
            {
                ["sessionId"] = SessionId,
                ["prompt"] = new JsonArray(new JsonObject { ["type"] = "text", ["text"] = text }),
            },
            timeout ?? TimeSpan.FromSeconds(300),
            cancellationToken).ConfigureAwait(false);

        string stopReason = result is JsonObject payload
            && payload.TryGetPropertyValue("stopReason", out JsonNode? reason)
            && reason is not null
                ? reason.ToString()
                : string.Empty;

        lock (_gate)
        {
            return new PromptResult
            {
                StopReason = stopReason,
                Text = CollectedText(),
                Updates = [.. _updates],
                Events = [.. _events],
                PermissionsRequested = [.. _permissions],
                PermissionsDenied = [.. _denied],
            };
        }
    }

    public Task CancelAsync(CancellationToken cancellationToken = default) =>
        SessionId is null
            ? Task.CompletedTask
            : Connection.NotifyAsync(
                "session/cancel",
                new JsonObject { ["sessionId"] = SessionId },
                cancellationToken);

    public ValueTask DisposeAsync() => Connection.DisposeAsync();

    /// <remarks>Callers hold <see cref="_gate"/>.</remarks>
    private string CollectedText()
    {
        StringBuilder chunks = new();
        foreach (JsonObject update in _updates)
        {
            if (update.TryGetPropertyValue("content", out JsonNode? content)
                && content is JsonObject block
                && block.TryGetPropertyValue("type", out JsonNode? type)
                && type?.ToString() == "text"
                && block.TryGetPropertyValue("text", out JsonNode? value))
            {
                chunks.Append(value?.ToString() ?? string.Empty);
            }
        }

        return chunks.ToString();
    }

    private async Task OnNotificationAsync(string method, JsonObject parameters, CancellationToken cancellationToken)
    {
        if (method != "session/update")
        {
            return;
        }

        if (!parameters.TryGetPropertyValue("update", out JsonNode? node) || node is not JsonObject update)
        {
            return;
        }

        JsonObject snapshot = (JsonObject)update.DeepClone();

        lock (_gate)
        {
            _updates.Add(snapshot);
        }

        if (OnUpdate is not null)
        {
            string sessionUpdate = snapshot.TryGetPropertyValue("sessionUpdate", out JsonNode? kind)
                ? kind?.ToString() ?? string.Empty
                : string.Empty;
            await OnUpdate(sessionUpdate, snapshot, cancellationToken).ConfigureAwait(false);
        }

        // An update the normalizer does not recognize is kept in Updates but
        // not published: forwarding an untyped blob would put the wire
        // vocabulary of one agent into every consumer downstream.
        NormalizedUpdate? normalized = SessionUpdateNormalizer.Normalize(snapshot);
        if (normalized is null)
        {
            return;
        }

        lock (_gate)
        {
            _events.Add(normalized);
        }

        if (OnEvent is not null)
        {
            await OnEvent(normalized, cancellationToken).ConfigureAwait(false);
        }
    }

    private async Task<JsonNode?> OnPermissionRequestAsync(JsonObject parameters, CancellationToken cancellationToken)
    {
        JsonObject? toolCall = parameters["toolCall"] as JsonObject;
        string toolName = Text(toolCall, "title");
        if (toolName.Length == 0)
        {
            toolName = Text(toolCall, "kind");
        }

        if (toolName.Length == 0)
        {
            toolName = "unknown";
        }

        List<JsonObject> options = [];
        if (parameters["options"] is JsonArray array)
        {
            options.AddRange(array.OfType<JsonObject>().Select(o => (JsonObject)o.DeepClone()));
        }

        PermissionRequest request = new()
        {
            SessionId = Text(parameters, "sessionId"),
            ToolName = toolName,
            Options = options,
            Raw = (JsonObject)parameters.DeepClone(),
        };

        lock (_gate)
        {
            _permissions.Add(request);
        }

        bool allowed = await PermissionPolicy(request, cancellationToken).ConfigureAwait(false);
        if (allowed)
        {
            string? granted = request.OptionId("allow_once") ?? request.OptionId("allow_always");
            if (granted is not null)
            {
                return Outcome("selected", granted);
            }
        }

        lock (_gate)
        {
            _denied.Add(request.ToolName);
        }

        string? rejected = request.OptionId("reject_once");
        return rejected is not null ? Outcome("selected", rejected) : Outcome("cancelled", null);
    }

    private static JsonObject Outcome(string outcome, string? optionId)
    {
        JsonObject inner = new() { ["outcome"] = outcome };
        if (optionId is not null)
        {
            inner["optionId"] = optionId;
        }

        return new JsonObject { ["outcome"] = inner };
    }

    private static string Text(JsonObject? obj, string key) =>
        obj is not null && obj.TryGetPropertyValue(key, out JsonNode? node) && node is not null
            ? node.ToString()
            : string.Empty;
}
