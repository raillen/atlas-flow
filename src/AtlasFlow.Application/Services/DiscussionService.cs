using System.Text;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Discuss;
using AtlasFlow.Orchestration;
using AtlasFlow.Orchestration.Projects;
using AtlasFlow.Persistence;

namespace AtlasFlow.Application.Services;

/// <summary>Turns a durable discussion into explicit Git-backed decisions.</summary>
/// <remarks>
/// Provider/model work is intentionally outside this service. This boundary
/// owns user-authored turns, decision state transitions, project-relative
/// references and the final write to canonical Project Atlas documentation.
/// </remarks>
public sealed class DiscussionService(
    AtlasFlowOptions options,
    DiscussionRepository discussions) : IDiscussionService
{
    private static readonly HashSet<string> ImageExtensions =
    [
        ".apng", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp",
    ];

    private readonly string _projectRoot = Path.GetFullPath(options.ProjectRoot);
    private readonly DiscussionRepository _discussions = discussions;

    public async Task<IReadOnlyList<DiscussionId>> ListAsync(
        CancellationToken cancellationToken = default) =>
        await _discussions.ListAsync(cancellationToken).ConfigureAwait(false);

    public Task<Discussion?> FindAsync(
        DiscussionId id,
        CancellationToken cancellationToken = default) =>
        _discussions.FindAsync(id, cancellationToken);

    public async Task<Discussion> StartAsync(CancellationToken cancellationToken = default)
    {
        Discussion discussion = new()
        {
            Id = IdFactory.NewDiscussion(),
            Completeness = Completeness.Unknown,
            CreatedAt = DateTimeOffset.UtcNow,
        };

        await _discussions.CreateAsync(discussion, cancellationToken).ConfigureAwait(false);
        return discussion;
    }

    public async Task<DiscussionMessage> AppendMessageAsync(
        AppendMessageRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        Discussion discussion = await RequireAsync(request.DiscussionId, cancellationToken)
            .ConfigureAwait(false);
        EnsureMutable(discussion);

        string content = request.Content.Trim();
        if (content.Length == 0)
        {
            throw new DiscussionStateException("A discussion message cannot be empty");
        }

        IReadOnlyList<MessageReference> references = ValidateReferences(request.References);
        DiscussionMessage message = new()
        {
            Id = IdFactory.NewMessageId(),
            Author = "user",
            TurnType = request.TurnType,
            Content = content,
            CreatedAt = DateTimeOffset.UtcNow,
            References = references,
        };

        await _discussions.AppendMessageAsync(
            discussion.Id,
            message,
            cancellationToken).ConfigureAwait(false);
        return message;
    }

    public async Task<Decision> ProposeDecisionAsync(
        ProposeDecisionRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        Discussion discussion = await RequireAsync(request.DiscussionId, cancellationToken)
            .ConfigureAwait(false);
        EnsureMutable(discussion);

        string title = RequiredText(request.Title, "title");
        string statement = RequiredText(request.Statement, "statement");
        string rationale = RequiredText(request.Rationale, "rationale");
        Decision decision = new()
        {
            Id = IdFactory.NewDecision(),
            Title = title,
            Statement = statement,
            Rationale = rationale,
            State = DecisionState.Proposed,
            AffectedDomains = NormalizeDomains(request.AffectedDomains),
            RequiresAdr = request.RequiresAdr,
            CreatedAt = DateTimeOffset.UtcNow,
        };

        await _discussions.AddDecisionAsync(
            discussion.Id,
            decision,
            cancellationToken).ConfigureAwait(false);
        return decision;
    }

    public async Task<Decision> AcceptDecisionAsync(
        DiscussionId discussionId,
        DecisionId decisionId,
        CancellationToken cancellationToken = default)
    {
        Discussion discussion = await RequireAsync(discussionId, cancellationToken)
            .ConfigureAwait(false);
        EnsureMutable(discussion);

        Decision decision = discussion.Decisions.FirstOrDefault(item => item.Id == decisionId)
            ?? throw new DiscussionStateException($"No decision '{decisionId}' in discussion '{discussionId}'");

        if (decision.State != DecisionState.Proposed)
        {
            throw new DiscussionStateException(
                $"Decision {decisionId} is already {decision.State} and cannot be accepted");
        }

        Decision accepted = decision with { State = DecisionState.Accepted };
        await _discussions.UpdateDecisionAsync(
            discussionId,
            accepted,
            cancellationToken).ConfigureAwait(false);
        return accepted;
    }

    public async Task<DiscussionOutcome> FinalizeAsync(
        DiscussionId id,
        CancellationToken cancellationToken = default)
    {
        Discussion discussion = await RequireAsync(id, cancellationToken).ConfigureAwait(false);
        EnsureMutable(discussion);

        Decision[] accepted = discussion.Decisions
            .Where(decision => decision.State == DecisionState.Accepted)
            .ToArray();
        if (accepted.Length == 0)
        {
            throw new DiscussionStateException(
                "A discussion needs at least one accepted decision before finalization");
        }

        List<ProjectPath> written = [];
        ProjectPath ledger = new("docs/01-architecture/DECISION_LEDGER.md");
        string ledgerPath = ResolveLedgerPath(ledger);
        string existingLedger = File.Exists(ledgerPath)
            ? await File.ReadAllTextAsync(ledgerPath, cancellationToken).ConfigureAwait(false)
            : "# Decision Ledger\n";
        string updatedLedger = AppendLedgerSection(existingLedger, discussion, accepted);
        await WriteAtomicallyAsync(ledgerPath, updatedLedger, cancellationToken).ConfigureAwait(false);
        written.Add(ledger);

        foreach (Decision decision in accepted.Where(item => item.RequiresAdr))
        {
            string slug = Slug(decision.Title);
            ProjectPath adr = new($"docs/07-decisions/ADR-{slug}-{decision.Id.Value}.md");
            string adrPath = ResolveLedgerPath(adr);
            await WriteAtomicallyAsync(
                adrPath,
                RenderAdr(discussion, decision),
                cancellationToken).ConfigureAwait(false);
            written.Add(adr);
        }

        await _discussions.UpdateCompletenessAsync(
            discussion.Id,
            Completeness.Locked,
            cancellationToken).ConfigureAwait(false);

        return new DiscussionOutcome
        {
            DiscussionId = discussion.Id,
            Recorded = accepted.Select(decision => decision.Id).ToArray(),
            Written = written,
        };
    }

    private async Task<Discussion> RequireAsync(
        DiscussionId id,
        CancellationToken cancellationToken)
    {
        return await _discussions.FindAsync(id, cancellationToken).ConfigureAwait(false)
            ?? throw new DiscussionStateException($"No discussion '{id}'");
    }

    private static void EnsureMutable(Discussion discussion)
    {
        if (discussion.Completeness == Completeness.Locked)
        {
            throw new DiscussionStateException($"Discussion {discussion.Id} is finalized");
        }
    }

    private List<MessageReference> ValidateReferences(
        IReadOnlyList<MessageReference> references)
    {
        ArgumentNullException.ThrowIfNull(references);
        List<MessageReference> validated = [];

        foreach (MessageReference reference in references)
        {
            string normalized = NormalizeRelativePath(reference.Path.Value);
            string absolute = ResolveProjectFile(normalized);
            if (!File.Exists(absolute))
            {
                throw new ProjectPathException(
                    $"'{normalized}' is not a file in the open project");
            }

            EnsureNoSymbolicLinks(absolute);

            if (reference.Kind == ReferenceKind.Image
                && !ImageExtensions.Contains(Path.GetExtension(normalized), StringComparer.OrdinalIgnoreCase))
            {
                throw new ProjectPathException(
                    $"'{normalized}' is not a supported image reference");
            }

            validated.Add(reference with
            {
                Path = new ProjectPath(normalized),
                Label = string.IsNullOrWhiteSpace(reference.Label)
                    ? Path.GetFileName(normalized)
                    : reference.Label.Trim(),
            });
        }

        return validated;
    }

    private string ResolveProjectFile(string normalized)
    {
        try
        {
            return ProjectPaths.Resolve(_projectRoot, new ProjectPath(normalized));
        }
        catch (ProjectPathEscapeException exception)
        {
            throw new ProjectPathException(exception.Message, exception);
        }
    }

    private string ResolveLedgerPath(ProjectPath path)
    {
        string absolute = ResolveProjectFile(path.Value);
        string? directory = Path.GetDirectoryName(absolute);
        if (directory is null)
        {
            throw new ProjectPathException($"Could not resolve '{path.Value}'");
        }

        EnsureNoSymbolicLinks(absolute);

        return absolute;
    }

    private void EnsureNoSymbolicLinks(string absolute)
    {
        string root = Path.TrimEndingDirectorySeparator(_projectRoot);
        string? current = Path.GetDirectoryName(absolute);
        while (current is not null
            && !current.Equals(root, StringComparison.Ordinal)
            && current.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal))
        {
            if (Directory.Exists(current)
                && File.GetAttributes(current).HasFlag(FileAttributes.ReparsePoint))
            {
                throw new ProjectPathException(
                    $"'{absolute}' passes through a symbolic link in the open project");
            }

            current = Path.GetDirectoryName(current);
        }

        if (File.Exists(absolute)
            && File.GetAttributes(absolute).HasFlag(FileAttributes.ReparsePoint))
        {
            throw new ProjectPathException(
                $"'{absolute}' is a symbolic link and cannot be referenced or overwritten");
        }
    }

    private static string NormalizeRelativePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ProjectPathException("A project reference needs a relative path");
        }

        string normalized = path.Trim().Replace('\\', '/');
        if (normalized.StartsWith('/')
            || (normalized.Length >= 2 && normalized[1] == ':'))
        {
            throw new ProjectPathException($"'{path}' is not a project-relative path");
        }

        string[] segments = normalized.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (segments.Length == 0 || segments.Any(segment => segment == ".."))
        {
            throw new ProjectPathException($"'{path}' attempts to escape the open project");
        }

        return string.Join('/', segments);
    }

    private static string RequiredText(string value, string field)
    {
        string normalized = value.Trim();
        return normalized.Length > 0
            ? normalized
            : throw new DiscussionStateException($"Decision {field} cannot be empty");
    }

    private static string[] NormalizeDomains(IReadOnlyList<string> domains) =>
        domains
            .Select(domain => domain.Trim())
            .Where(domain => domain.Length > 0)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();

    private static string AppendLedgerSection(
        string existing,
        Discussion discussion,
        IReadOnlyList<Decision> decisions)
    {
        string heading = $"## Discussion `{discussion.Id}`";
        if (existing.Contains(heading, StringComparison.Ordinal))
        {
            return existing;
        }

        StringBuilder builder = new(existing.TrimEnd());
        builder.AppendLine();
        builder.AppendLine();
        builder.AppendLine(heading);
        builder.AppendLine();
        builder.AppendLine($"Recorded on {DateTimeOffset.UtcNow:yyyy-MM-dd}.");
        builder.AppendLine();
        builder.AppendLine("| Decision | Statement | Domains | ADR |");
        builder.AppendLine("| --- | --- | --- | --- |");
        foreach (Decision decision in decisions)
        {
            builder.Append("| ")
                .Append(MarkdownCell(decision.Title)).Append(" | ")
                .Append(MarkdownCell(decision.Statement)).Append(" | ")
                .Append(MarkdownCell(string.Join(", ", decision.AffectedDomains.DefaultIfEmpty("—"))))
                .Append(" | ")
                .Append(decision.RequiresAdr ? "yes" : "no")
                .AppendLine(" |");
        }

        return builder.ToString();
    }

    private static string RenderAdr(Discussion discussion, Decision decision) => $"""
        # {decision.Title}

        **Status:** Accepted
        **Date:** {decision.CreatedAt:yyyy-MM-dd}
        **Source:** discussion `{discussion.Id}`

        ## Decision

        {decision.Statement}

        ## Rationale

        {decision.Rationale}

        ## Affected domains

        {string.Join(", ", decision.AffectedDomains.DefaultIfEmpty("unscoped"))}
        """;

    private static string MarkdownCell(string value) =>
        value.Replace("|", "\\|", StringComparison.Ordinal)
            .Replace('\r', ' ')
            .Replace('\n', ' ');

    private static string Slug(string title)
    {
        StringBuilder builder = new();
        foreach (char character in title)
        {
            builder.Append(char.IsLetterOrDigit(character) || char.IsWhiteSpace(character)
                ? character
                : ' ');
        }

        string slug = string.Join('-', builder.ToString().Split(
            (char[]?)null,
            StringSplitOptions.RemoveEmptyEntries));
        if (slug.Length == 0)
        {
            return "DECISION";
        }

        return slug.Length > 48 ? slug[..48].TrimEnd('-') : slug;
    }

    private static async Task WriteAtomicallyAsync(
        string path,
        string content,
        CancellationToken cancellationToken)
    {
        string? directory = Path.GetDirectoryName(path);
        if (directory is null)
        {
            throw new ProjectPathException($"Could not resolve '{path}'");
        }

        Directory.CreateDirectory(directory);
        string temporary = $"{path}.{Guid.NewGuid():N}.tmp";
        try
        {
            await File.WriteAllTextAsync(temporary, content, Encoding.UTF8, cancellationToken)
                .ConfigureAwait(false);
            File.Move(temporary, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporary))
            {
                File.Delete(temporary);
            }
        }
    }
}
