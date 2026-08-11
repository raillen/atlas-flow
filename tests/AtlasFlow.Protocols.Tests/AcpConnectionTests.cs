using System.Runtime.Versioning;
using System.Text.Json.Nodes;

using AtlasFlow.Protocols.Acp;

namespace AtlasFlow.Protocols.Tests;

/// <summary>
/// The wire, exercised against a real child process.
/// </summary>
/// <remarks>
/// These spawn an actual agent rather than a mocked stream. The defects this
/// layer produces — a half-written line, a reply that never comes, a process
/// that dies holding a pending call — do not reproduce against an in-memory
/// fake, which is why the Python suite this is ported from ran a fixture agent
/// as a subprocess too.
/// <para>
/// The fixture is POSIX shell. Linux is the development platform (the owner
/// deferred Windows on 2026-08-11), and a shell script keeps the fixture
/// readable as a protocol transcript. If Windows comes back, this fixture is
/// the first thing that has to be replaced.
/// </para>
/// </remarks>
[SupportedOSPlatform("linux")]
public sealed class AcpConnectionTests : IDisposable
{
    private readonly string _agentPath = Path.Combine(
        Path.GetTempPath(), $"atlas-fake-acp-agent-{Guid.NewGuid():N}.sh");

    public AcpConnectionTests()
    {
        File.WriteAllText(_agentPath, FakeAgentScript);
        File.SetUnixFileMode(
            _agentPath,
            UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
    }

    public void Dispose() => File.Delete(_agentPath);

    private const string FakeAgentScript = """
        #!/bin/sh
        # A diagnostic line on stdout, before any protocol traffic. Real agents
        # do this, and the reader must skip it rather than tear down the session.
        echo "fake agent starting"
        while IFS= read -r line; do
          id=$(printf '%s' "$line" | sed -n 's/.*"id":\([0-9]*\).*/\1/p')
          case "$line" in
            *'"initialize"'*)
              printf '{"jsonrpc":"2.0","id":%s,"result":{"protocolVersion":1,"agentCapabilities":{"loadSession":true}}}\n' "$id"
              ;;
            *'"session/new"'*)
              printf '{"jsonrpc":"2.0","id":%s,"result":{"sessionId":"sess-1"}}\n' "$id"
              ;;
            *'"session/prompt"'*)
              printf '%s\n' '{"jsonrpc":"2.0","id":9001,"method":"session/request_permission","params":{"sessionId":"sess-1","toolCall":{"title":"rm -rf /"},"options":[{"kind":"allow_once","optionId":"yes"},{"kind":"reject_once","optionId":"no"}]}}'
              printf '%s\n' '{"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"done"}}}}'
              printf '{"jsonrpc":"2.0","id":%s,"result":{"stopReason":"end_turn"}}\n' "$id"
              ;;
            *'"boom"'*)
              printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32000,"message":"exploded"}}\n' "$id"
              ;;
            *'"silent"'*)
              : # deliberately no reply, to exercise the timeout
              ;;
          esac
        done
        """;

    private AcpClient StartedClient(PermissionPolicy? policy = null)
    {
        AcpClient client = new(policy);
        client.StartAsync(["/bin/sh", _agentPath]).GetAwaiter().GetResult();
        return client;
    }

    [Fact]
    public async Task AMissingAgentIsReportedAsAnAcpFailure()
    {
        await using AcpConnection connection = new();

        AcpException error = await Assert.ThrowsAsync<AcpException>(
            () => connection.StartAsync(["/nonexistent/atlas-no-such-agent"]));

        Assert.Contains("not found", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task AnEmptyCommandIsRefusedBeforeSpawning()
    {
        await using AcpConnection connection = new();
        await Assert.ThrowsAsync<AcpException>(() => connection.StartAsync([]));
    }

    [Fact]
    public async Task InitializeNegotiatesAndReportsCapabilities()
    {
        await using AcpClient client = StartedClient();

        AgentCapabilities capabilities = await client.InitializeAsync();

        Assert.Equal(1, capabilities.ProtocolVersion);
        Assert.True(capabilities.Supports("loadSession"));
        Assert.False(capabilities.Supports("somethingElse"));
    }

    [Fact]
    public async Task ANonJsonLineOnStdoutIsSkippedRatherThanFatal()
    {
        // The fixture prints "fake agent starting" before any protocol traffic.
        // Reaching a session at all proves the reader stepped over it.
        await using AcpClient client = StartedClient();
        await client.InitializeAsync();

        string sessionId = await client.NewSessionAsync("/tmp");

        Assert.Equal("sess-1", sessionId);
    }

    [Fact]
    public async Task AJsonRpcErrorBecomesARemoteException()
    {
        await using AcpClient client = StartedClient();

        AcpRemoteException error = await Assert.ThrowsAsync<AcpRemoteException>(
            () => client.Connection.CallAsync("boom", []));

        Assert.Equal(-32000, error.Code);
        Assert.Contains("exploded", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ACallThatIsNeverAnsweredTimesOutRatherThanHanging()
    {
        await using AcpClient client = StartedClient();

        AcpException error = await Assert.ThrowsAsync<AcpException>(
            () => client.Connection.CallAsync("silent", [], TimeSpan.FromMilliseconds(300)));

        Assert.Contains("timed out", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task PromptingBeforeASessionExistsIsRefused()
    {
        await using AcpClient client = StartedClient();
        await client.InitializeAsync();

        await Assert.ThrowsAsync<AcpException>(() => client.PromptAsync("hello"));
    }

    [Fact]
    public async Task APromptCollectsNormalizedEvents()
    {
        await using AcpClient client = StartedClient();
        await client.InitializeAsync();
        await client.NewSessionAsync("/tmp");

        PromptResult result = await client.PromptAsync("do the thing", TimeSpan.FromSeconds(10));

        Assert.True(result.Completed);
        Assert.Equal("end_turn", result.StopReason);
        Assert.Contains(result.Events, e => e.Kind == UpdateKind.Message && e.Text == "done");
    }

    [Fact]
    public async Task ThePermissionRoundTripDeniesByDefault()
    {
        await using AcpClient client = StartedClient();
        await client.InitializeAsync();
        await client.NewSessionAsync("/tmp");

        PromptResult result = await client.PromptAsync("do the thing", TimeSpan.FromSeconds(10));

        // Silently granting whatever an agent asks for would make the
        // round-trip decorative, so the default policy refuses.
        Assert.Contains(result.PermissionsRequested, r => r.ToolName == "rm -rf /");
        Assert.Contains("rm -rf /", result.PermissionsDenied);
    }

    [Fact]
    public async Task AnExplicitPolicyCanAllow()
    {
        await using AcpClient client = StartedClient((_, _) => Task.FromResult(true));
        await client.InitializeAsync();
        await client.NewSessionAsync("/tmp");

        PromptResult result = await client.PromptAsync("do the thing", TimeSpan.FromSeconds(10));

        Assert.Contains(result.PermissionsRequested, r => r.ToolName == "rm -rf /");
        Assert.Empty(result.PermissionsDenied);
    }

    [Fact]
    public async Task LoadSessionIsSkippedWhenTheAgentDidNotAdvertiseIt()
    {
        await using AcpClient client = StartedClient();

        // Capabilities are empty until initialize negotiates them, so an
        // unsupported feature degrades to false rather than to a call.
        Assert.False(await client.LoadSessionAsync("sess-1", "/tmp"));
    }

    [Fact]
    public async Task AnAgentThatExitsFailsItsPendingCall()
    {
        await using AcpConnection connection = new();
        await connection.StartAsync(["/bin/sh", "-c", "exit 0"]);

        await Assert.ThrowsAnyAsync<AcpException>(
            () => connection.CallAsync("initialize", [], TimeSpan.FromSeconds(5)));
    }
}
