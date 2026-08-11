using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json.Nodes;

namespace AtlasFlow.Protocols.Acp;

/// <summary>Handles one inbound request from the agent.</summary>
public delegate Task<JsonNode?> AcpRequestHandler(JsonObject parameters, CancellationToken cancellationToken);

/// <summary>Handles one inbound notification from the agent.</summary>
public delegate Task AcpNotificationHandler(string method, JsonObject parameters, CancellationToken cancellationToken);

/// <summary>
/// JSON-RPC 2.0 over newline-delimited stdio — the ACP wire format.
/// </summary>
/// <remarks>
/// <para>
/// The connection is bidirectional: Atlas Flow calls the agent, and the agent
/// calls back for things only the client can decide, such as permission to run
/// a tool. Both directions are multiplexed over the same pair of pipes, so the
/// reader loop routes by message shape rather than assuming request/response
/// alternation.
/// </para>
/// <para>
/// Concurrency differs from the Python implementation this was ported from,
/// and the difference is not cosmetic. There, a single-threaded event loop
/// serialized every touch of the pending-request table for free. Here the read
/// loop runs on the thread pool while callers await from wherever they happen
/// to be, so the table is a <see cref="ConcurrentDictionary{TKey,TValue}"/>,
/// request ids come from <see cref="Interlocked"/>, and writes to the agent's
/// stdin are serialized by a semaphore. Two concurrent writes would otherwise
/// interleave halfway through a JSON line and desynchronize the stream.
/// </para>
/// </remarks>
public sealed class AcpConnection : IAsyncDisposable
{
    private readonly ConcurrentDictionary<long, PendingCall> _pending = new();
    private readonly SemaphoreSlim _writeLock = new(1, 1);
    private readonly CancellationTokenSource _shutdown = new();

    private Process? _process;
    private Task? _readLoop;
    private long _nextId;
    private bool _closed;

    /// <summary>Methods this client answers when the agent calls back.</summary>
    public Dictionary<string, AcpRequestHandler> RequestHandlers { get; } = [];

    /// <summary>Invoked for every inbound notification.</summary>
    public AcpNotificationHandler? OnNotification { get; set; }

    /// <summary>Whether the agent process exists and has not exited.</summary>
    public bool Running => _process is { HasExited: false };

    /// <summary>Everything the agent wrote to stderr, for diagnosis after a failure.</summary>
    public string StandardError => _stderr.ToString();

    private readonly StringBuilder _stderr = new();

    /// <summary>Spawns the agent and begins reading its stdout.</summary>
    public Task StartAsync(IReadOnlyList<string> command, string? workingDirectory = null)
    {
        ArgumentNullException.ThrowIfNull(command);
        if (command.Count == 0)
        {
            throw new AcpException("ACP agent command is empty");
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = command[0],
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        for (var i = 1; i < command.Count; i++)
        {
            // ArgumentList quotes each entry itself. Building a command string
            // by hand is how an argument containing a space becomes two.
            startInfo.ArgumentList.Add(command[i]);
        }

        if (!string.IsNullOrEmpty(workingDirectory))
        {
            startInfo.WorkingDirectory = workingDirectory;
        }

        var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        process.ErrorDataReceived += (_, args) =>
        {
            if (args.Data is not null)
            {
                lock (_stderr)
                {
                    _stderr.AppendLine(args.Data);
                }
            }
        };

        try
        {
            process.Start();
        }
        catch (Exception exc) when (exc is System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            process.Dispose();
            throw new AcpException($"ACP agent not found: {command[0]}", exc);
        }

        _process = process;
        process.BeginErrorReadLine();
        _readLoop = Task.Run(() => ReadLoopAsync(process), CancellationToken.None);
        return Task.CompletedTask;
    }

    /// <summary>Sends a request and waits for its response.</summary>
    public async Task<JsonNode?> CallAsync(
        string method,
        JsonObject parameters,
        TimeSpan? timeout = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(method);
        ArgumentNullException.ThrowIfNull(parameters);

        if (!Running)
        {
            throw new AcpException($"Cannot call {method}: agent is not running");
        }

        var effectiveTimeout = timeout ?? TimeSpan.FromSeconds(60);
        var id = Interlocked.Increment(ref _nextId);
        var pending = new PendingCall(method);
        _pending[id] = pending;

        try
        {
            await WriteAsync(new JsonObject
            {
                ["jsonrpc"] = "2.0",
                ["id"] = id,
                ["method"] = method,
                ["params"] = parameters.DeepClone(),
            }, cancellationToken).ConfigureAwait(false);

            using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeoutSource.CancelAfter(effectiveTimeout);

            await using var registration = timeoutSource.Token.Register(
                static state => ((PendingCall)state!).TrySetCanceled(), pending).ConfigureAwait(false);

            return await pending.Task.ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new AcpException(
                string.Create(
                    CultureInfo.InvariantCulture,
                    $"ACP call '{method}' timed out after {effectiveTimeout.TotalSeconds}s"));
        }
        finally
        {
            _pending.TryRemove(id, out _);
        }
    }

    /// <summary>Sends a notification. There is no reply to wait for.</summary>
    public Task NotifyAsync(string method, JsonObject parameters, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(method);
        ArgumentNullException.ThrowIfNull(parameters);

        return WriteAsync(new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["method"] = method,
            ["params"] = parameters.DeepClone(),
        }, cancellationToken);
    }

    private async Task WriteAsync(JsonObject message, CancellationToken cancellationToken)
    {
        var process = _process;
        if (process is null || process.HasExited)
        {
            throw new AcpException("ACP connection is not open");
        }

        await _writeLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await process.StandardInput.WriteAsync(message.ToJsonString().AsMemory(), cancellationToken)
                .ConfigureAwait(false);
            await process.StandardInput.WriteAsync("\n".AsMemory(), cancellationToken).ConfigureAwait(false);
            await process.StandardInput.FlushAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (IOException exc)
        {
            throw new AcpException("ACP agent closed its input stream", exc);
        }
        finally
        {
            _writeLock.Release();
        }
    }

    private async Task ReadLoopAsync(Process process)
    {
        try
        {
            while (!_shutdown.IsCancellationRequested)
            {
                var line = await process.StandardOutput.ReadLineAsync(_shutdown.Token).ConfigureAwait(false);
                if (line is null)
                {
                    break;
                }

                JsonNode? message;
                try
                {
                    message = JsonNode.Parse(line);
                }
                catch (System.Text.Json.JsonException)
                {
                    // Agents sometimes write diagnostics to stdout. Skipping a
                    // non-JSON line is better than tearing down a live session.
                    continue;
                }

                if (message is JsonObject envelope)
                {
                    await DispatchAsync(envelope).ConfigureAwait(false);
                }
            }
        }
        catch (OperationCanceledException)
        {
            // Shutdown requested; the loop has no more work to do.
        }
        catch (IOException)
        {
            // The pipe died. FailPending below is the report.
        }
        finally
        {
            FailPending(new AcpException("ACP agent closed the connection"));
        }
    }

    private async Task DispatchAsync(JsonObject message)
    {
        var hasMethod = message.TryGetPropertyValue("method", out var methodNode);
        var hasId = message.TryGetPropertyValue("id", out var idNode);

        if (hasMethod && hasId)
        {
            await HandleRequestAsync(message, methodNode, idNode).ConfigureAwait(false);
        }
        else if (hasMethod)
        {
            var handler = OnNotification;
            if (handler is not null)
            {
                var method = methodNode?.GetValue<string>() ?? string.Empty;
                await handler(method, ParamsOf(message), _shutdown.Token).ConfigureAwait(false);
            }
        }
        else if (hasId)
        {
            HandleResponse(message, idNode);
        }
    }

    private async Task HandleRequestAsync(JsonObject message, JsonNode? methodNode, JsonNode? idNode)
    {
        var method = methodNode?.GetValue<string>() ?? string.Empty;
        var id = idNode?.DeepClone();

        if (!RequestHandlers.TryGetValue(method, out var handler))
        {
            await WriteErrorAsync(id, -32601, $"Method not found: {method}").ConfigureAwait(false);
            return;
        }

        JsonNode? result;
        try
        {
            result = await handler(ParamsOf(message), _shutdown.Token).ConfigureAwait(false);
        }
#pragma warning disable CA1031 // A handler fault is reported to the agent as a
        // JSON-RPC error rather than killing the read loop. Letting one bad
        // handler tear down a live session is the worse failure.
        catch (Exception exc)
#pragma warning restore CA1031
        {
            await WriteErrorAsync(id, -32603, exc.Message).ConfigureAwait(false);
            return;
        }

        await WriteAsync(new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id,
            ["result"] = result,
        }, _shutdown.Token).ConfigureAwait(false);
    }

    private Task WriteErrorAsync(JsonNode? id, int code, string message) =>
        WriteAsync(new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id,
            ["error"] = new JsonObject { ["code"] = code, ["message"] = message },
        }, _shutdown.Token);

    private void HandleResponse(JsonObject message, JsonNode? idNode)
    {
        if (idNode is null || !TryReadId(idNode, out var id))
        {
            return;
        }

        if (!_pending.TryRemove(id, out var pending))
        {
            return;
        }

        if (message.TryGetPropertyValue("error", out var errorNode) && errorNode is JsonObject error)
        {
            var code = error.TryGetPropertyValue("code", out var c) && c is not null
                ? c.GetValue<int>()
                : -1;
            var text = error.TryGetPropertyValue("message", out var m) && m is not null
                ? m.GetValue<string>()
                : string.Empty;
            var data = error.TryGetPropertyValue("data", out var d) ? d?.ToJsonString() : null;
            pending.TrySetException(new AcpRemoteException(code, text, data));
            return;
        }

        message.TryGetPropertyValue("result", out var resultNode);
        pending.TrySetResult(resultNode?.DeepClone());
    }

    private static bool TryReadId(JsonNode node, out long id)
    {
        try
        {
            id = node.GetValue<long>();
            return true;
        }
        catch (Exception exc) when (exc is FormatException or InvalidOperationException)
        {
            id = 0;
            return false;
        }
    }

    private static JsonObject ParamsOf(JsonObject message) =>
        message.TryGetPropertyValue("params", out var node) && node is JsonObject obj
            ? (JsonObject)obj.DeepClone()
            : [];

    private void FailPending(Exception error)
    {
        foreach (var key in _pending.Keys)
        {
            if (_pending.TryRemove(key, out var pending))
            {
                pending.TrySetException(error);
            }
        }
    }

    /// <summary>
    /// Closes stdin, waits briefly for the agent to exit, then kills it.
    /// </summary>
    /// <remarks>
    /// The kill targets the whole process tree. An agent that spawned a child
    /// and exited leaves that child holding the pipe, and a worktree that never
    /// gets released is the visible symptom much later.
    /// </remarks>
    public async ValueTask DisposeAsync()
    {
        if (_closed)
        {
            return;
        }

        _closed = true;
        await _shutdown.CancelAsync().ConfigureAwait(false);

        var process = _process;
        if (process is not null)
        {
            try
            {
                if (!process.HasExited)
                {
                    process.StandardInput.Close();
                    using var grace = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                    try
                    {
                        await process.WaitForExitAsync(grace.Token).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException)
                    {
                        process.Kill(entireProcessTree: true);
                        await process.WaitForExitAsync(CancellationToken.None).ConfigureAwait(false);
                    }
                }
            }
            catch (InvalidOperationException)
            {
                // The process was already gone. Nothing left to wait for.
            }

            process.Dispose();
        }

        if (_readLoop is not null)
        {
            try
            {
                await _readLoop.ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                // Expected: the read loop is being torn down.
            }
        }

        FailPending(new AcpException("ACP connection closed"));

        _writeLock.Dispose();
        _shutdown.Dispose();
    }

    private sealed class PendingCall(string method)
        : TaskCompletionSource<JsonNode?>(TaskCreationOptions.RunContinuationsAsynchronously)
    {
        public string Method { get; } = method;
    }
}
