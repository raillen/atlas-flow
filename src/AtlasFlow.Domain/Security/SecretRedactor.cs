using System.Text.RegularExpressions;

namespace AtlasFlow.Domain.Security;

/// <summary>
/// Removes known secret shapes from text before it is logged, stored or shown.
/// </summary>
/// <remarks>
/// Applied to every piece of agent-produced text that leaves a runner, so a
/// token an agent echoed never reaches a log, a transcript or a client.
/// </remarks>
public static partial class SecretRedactor
{
    private const string Replacement = "[REDACTED]";

    [GeneratedRegex(@"(?:sk|api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+",
        RegexOptions.IgnoreCase)]
    private static partial Regex KeyValuePattern { get; }

    [GeneratedRegex(@"Bearer\s+[A-Za-z0-9\-._~+/]+=*", RegexOptions.IgnoreCase)]
    private static partial Regex BearerPattern { get; }

    [GeneratedRegex(@"\bgh[pousr]_[A-Za-z0-9]{16,}", RegexOptions.IgnoreCase)]
    private static partial Regex GitHubTokenPattern { get; }

    [GeneratedRegex(@"\bsk-[A-Za-z0-9]{16,}", RegexOptions.IgnoreCase)]
    private static partial Regex OpenAiKeyPattern { get; }

    [GeneratedRegex(@"-----BEGIN [A-Z ]*PRIVATE KEY-----", RegexOptions.IgnoreCase)]
    private static partial Regex PrivateKeyPattern { get; }

    private static readonly Regex[] Defaults =
    [
        KeyValuePattern,
        BearerPattern,
        GitHubTokenPattern,
        OpenAiKeyPattern,
        PrivateKeyPattern,
    ];

    /// <summary>
    /// Redacts every default pattern, plus any extra ones supplied.
    /// </summary>
    /// <remarks>
    /// Extra patterns are added to the defaults rather than replacing them: a
    /// project that wants to catch one more shape of secret should not have to
    /// restate the ones already covered, and silently losing the defaults is
    /// exactly the mistake that turns a redaction list into a leak.
    /// </remarks>
    public static string Redact(string text, IEnumerable<Regex>? additional = null)
    {
        ArgumentNullException.ThrowIfNull(text);

        foreach (Regex pattern in Defaults)
        {
            text = pattern.Replace(text, Replacement);
        }

        if (additional is not null)
        {
            foreach (Regex pattern in additional)
            {
                text = pattern.Replace(text, Replacement);
            }
        }

        return text;
    }
}
