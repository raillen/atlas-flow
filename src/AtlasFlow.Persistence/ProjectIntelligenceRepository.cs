using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Intelligence;

namespace AtlasFlow.Persistence;

/// <summary>A Project Intelligence file is invalid or unsafe to use.</summary>
public sealed class IntelligenceFormatException : Exception
{
    public IntelligenceFormatException(string message) : base(message) { }

    public IntelligenceFormatException(string message, Exception innerException)
        : base(message, innerException) { }
}

/// <summary>
/// Reads and atomically updates the v0.2 Project Intelligence JSON document.
/// </summary>
/// <remarks>
/// The file is canonical project history, while raw execution traces remain in
/// SQLite. A per-process gate serializes read-modify-write operations, and the
/// final replacement happens only after the temporary file is fully written.
/// Unknown root and task fields are preserved when an existing report is
/// updated, which lets a newer framework write fields this runtime does not
/// yet render.
/// </remarks>
public sealed class ProjectIntelligenceRepository : IDisposable
{
    private const int CurrentVersion = 1;
    private const int MaximumFileBytes = 16 * 1024 * 1024;
    private const int MaximumTaskReports = 10_000;
    private const string DefaultRelativePath = ".atlas/history/project-intelligence.json";

    private static readonly JsonSerializerOptions _jsonOptions = new()
    {
        WriteIndented = true,
    };

    private readonly string _projectRoot;
    private readonly SemaphoreSlim _writeGate = new(1, 1);

    public ProjectIntelligenceRepository(string projectRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);
        _projectRoot = Path.GetFullPath(projectRoot);
    }

    /// <summary>Loads the current snapshot without creating a file.</summary>
    public async Task<ProjectIntelligenceSnapshot> LoadAsync(
        CancellationToken cancellationToken = default)
    {
        await _writeGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            (_, JsonObject document, ProjectIntelligenceSnapshot snapshot) =
                await ReadDocumentAsync(cancellationToken).ConfigureAwait(false);
            _ = document;
            return snapshot;
        }
        finally
        {
            _writeGate.Release();
        }
    }

    /// <summary>Upserts one report and recomputes project-level aggregates.</summary>
    public async Task<ProjectIntelligenceSnapshot> RecordAsync(
        TaskReport report,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(report);
        ValidateReport(report);

        await _writeGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            (string path, JsonObject document, ProjectIntelligenceSnapshot existing) =
                await ReadDocumentAsync(cancellationToken).ConfigureAwait(false);

            JsonArray tasks = document["tasks"] as JsonArray ?? [];
            JsonObject? previousTask = null;
            for (int index = tasks.Count - 1; index >= 0; index--)
            {
                if (tasks[index] is JsonObject task
                    && string.Equals(ReadOptionalString(task, "id"), report.Id, StringComparison.Ordinal))
                {
                    previousTask = task;
                    tasks.RemoveAt(index);
                }
            }

            if (tasks.Count >= MaximumTaskReports)
            {
                throw new IntelligenceFormatException(
                    $"Project Intelligence cannot contain more than {MaximumTaskReports} task reports.");
            }

            JsonObject serializedReport = ToJson(report);
            if (previousTask is not null)
            {
                foreach ((string key, JsonNode? value) in previousTask)
                {
                    if (!serializedReport.ContainsKey(key))
                    {
                        serializedReport[key] = value?.DeepClone();
                    }
                }
            }

            tasks.Add(serializedReport);
            document["version"] = existing.Version;
            document["tasks"] = tasks;

            IReadOnlyList<TaskReport> reports = [.. tasks.Select(node => node is JsonObject task
                ? ReadTaskReport(task)
                : throw new IntelligenceFormatException("Project Intelligence contains a non-object task report."))];
            ProjectIntelligenceSummary summary = Summarize(reports);
            DateTimeOffset updatedAt = DateTimeOffset.UtcNow;
            document["updated_at"] = FormatMoment(updatedAt);
            document["summary"] = ToJson(summary);

            await WriteAtomicallyAsync(path, document.ToJsonString(_jsonOptions), cancellationToken)
                .ConfigureAwait(false);

            return new ProjectIntelligenceSnapshot
            {
                Version = existing.Version,
                UpdatedAt = updatedAt,
                Summary = summary,
                Tasks = reports,
                Debt = ReadDebt(document),
            };
        }
        finally
        {
            _writeGate.Release();
        }
    }

    private async Task<(string Path, JsonObject Document, ProjectIntelligenceSnapshot Snapshot)> ReadDocumentAsync(
        CancellationToken cancellationToken)
    {
        string path = ResolveStorePath();
        if (!File.Exists(path))
        {
            return (path, NewDocument(), EmptySnapshot());
        }

        string text = await ReadBoundedTextAsync(path, cancellationToken).ConfigureAwait(false);
        JsonObject document = ParseDocument(text, path);
        ProjectIntelligenceSnapshot snapshot = ReadSnapshot(document, path);
        return (path, document, snapshot);
    }

    private string ResolveStorePath()
    {
        string configured = DefaultRelativePath;
        string atlasPath = Path.Combine(_projectRoot, "atlas.json");
        if (File.Exists(atlasPath))
        {
            string text;
            try
            {
                FileInfo info = new(atlasPath);
                if (info.Length > MaximumFileBytes)
                {
                    throw new IntelligenceFormatException($"{atlasPath} exceeds the manifest size limit.");
                }

                text = File.ReadAllText(atlasPath);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                throw new IntelligenceFormatException($"Could not read {atlasPath}: {exception.Message}", exception);
            }

            JsonObject atlas = ParseDocument(text, atlasPath);
            if (atlas["intelligence"] is JsonObject intelligence
                && intelligence["path"] is JsonValue value
                && value.TryGetValue<string>(out string? path)
                && !string.IsNullOrWhiteSpace(path))
            {
                configured = path.Trim();
            }
        }

        string fullPath = Path.GetFullPath(Path.Combine(_projectRoot, configured));
        if (!IsInsideProject(fullPath))
        {
            throw new IntelligenceFormatException(
                $"Project Intelligence path '{configured}' escapes the open project.");
        }

        return fullPath;
    }

    private bool IsInsideProject(string path)
    {
        string root = Path.TrimEndingDirectorySeparator(_projectRoot);
        StringComparison comparison = OperatingSystem.IsWindows()
            ? StringComparison.OrdinalIgnoreCase
            : StringComparison.Ordinal;

        return path.Equals(root, comparison)
            || path.StartsWith(root + Path.DirectorySeparatorChar, comparison);
    }

    private static async Task<string> ReadBoundedTextAsync(
        string path,
        CancellationToken cancellationToken)
    {
        try
        {
            FileInfo info = new(path);
            if (info.Length > MaximumFileBytes)
            {
                throw new IntelligenceFormatException($"{path} exceeds the intelligence size limit.");
            }

            return await File.ReadAllTextAsync(path, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            throw new IntelligenceFormatException($"Could not read {path}: {exception.Message}", exception);
        }
    }

    private static JsonObject ParseDocument(string text, string path)
    {
        try
        {
            JsonNode? node = JsonNode.Parse(
                text,
                documentOptions: new JsonDocumentOptions { MaxDepth = 64 });
            return node as JsonObject
                ?? throw new IntelligenceFormatException($"{path} must contain a mapping.");
        }
        catch (JsonException exception)
        {
            throw new IntelligenceFormatException($"Could not parse {path}: {exception.Message}", exception);
        }
    }

    private static ProjectIntelligenceSnapshot ReadSnapshot(JsonObject document, string path)
    {
        int version = ReadRequiredInt(document, "version", path);
        if (version != CurrentVersion)
        {
            throw new IntelligenceFormatException(
                $"{path} has unsupported Project Intelligence version {version}.");
        }

        DateTimeOffset updatedAt = ReadRequiredMoment(document, "updated_at", path);
        JsonArray tasks = document["tasks"] as JsonArray
            ?? throw new IntelligenceFormatException($"{path} must contain a tasks array.");

        if (tasks.Count > MaximumTaskReports)
        {
            throw new IntelligenceFormatException(
                $"{path} contains more than {MaximumTaskReports} task reports.");
        }

        List<TaskReport> reports = [.. tasks.Select(node =>
            node is JsonObject task
                ? ReadTaskReport(task)
                : throw new IntelligenceFormatException($"{path} contains a non-object task report."))];

        return new ProjectIntelligenceSnapshot
        {
            Version = version,
            UpdatedAt = updatedAt,
            Summary = Summarize(reports),
            Tasks = reports,
            Debt = ReadDebt(document),
        };
    }

    private static TaskReport ReadTaskReport(JsonObject node)
    {
        string id = ReadRequiredString(node, "id", "task report");
        TaskReportStatus status = ParseStatus(ReadRequiredString(node, "status", id));
        JsonObject tokens = node["tokens"] as JsonObject ?? [];
        JsonObject? cost = (node["cost"] as JsonObject)?["direct"] as JsonObject;

        return new TaskReport
        {
            Id = id,
            Status = status,
            Type = ReadOptionalString(node, "type") ?? string.Empty,
            Components = ReadStrings(node, "component"),
            Risk = ParseRisk(ReadOptionalString(node, "risk")),
            Complexity = ReadOptionalString(node, "complexity") ?? string.Empty,
            Strategy = ReadOptionalString(node, "strategy") ?? string.Empty,
            Tokens = new TokenUsage
            {
                Input = ReadOptionalNonNegativeInt(tokens, "input", id),
                Output = ReadOptionalNonNegativeInt(tokens, "output", id),
                Cached = ReadOptionalNonNegativeInt(tokens, "cached", id),
                IntermediateOutput = ReadOptionalNonNegativeInt(tokens, "intermediate_output", id),
                Retrieved = ReadOptionalNonNegativeInt(tokens, "retrieved", id),
                Injected = ReadOptionalNonNegativeInt(tokens, "injected", id),
            },
            DirectCost = cost is null ? null : ReadCost(cost, id),
            ChangedFiles = ReadStrings(node, "files_changed"),
            Tests = ReadStrings(node, "tests"),
            Documentation = ReadStrings(node, "documentation"),
            Debt = ReadStrings(node, "debt"),
            Evidence = ReadStrings(node, "evidence"),
            Models = ReadStrings(node, "models"),
            StartedAt = ReadOptionalMoment(node, "started_at", id),
            FinishedAt = ReadOptionalMoment(node, "finished_at", id),
        };
    }

    private static CostMeasurement ReadCost(JsonObject node, string reportId)
    {
        decimal amount = ReadOptionalDecimal(node, "amount", reportId);
        string currency = ReadRequiredString(node, "currency", reportId);
        MeasurementProvenance provenance = ParseProvenance(ReadRequiredString(node, "provenance", reportId));
        MeasurementConfidence confidence = ParseConfidence(ReadRequiredString(node, "confidence", reportId));
        return new CostMeasurement
        {
            Amount = amount,
            Currency = currency,
            Provenance = provenance,
            Confidence = confidence,
        };
    }

    private static ProjectIntelligenceSummary Summarize(IReadOnlyList<TaskReport> reports)
    {
        string[] currencies = reports
            .Where(report => report.DirectCost is not null)
            .Select(report => report.DirectCost!.Currency)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();

        if (currencies.Length > 1)
        {
            throw new IntelligenceFormatException(
                "Project Intelligence cannot aggregate direct costs with different currencies.");
        }

        return new ProjectIntelligenceSummary
        {
            Tasks = reports.Count,
            InputTokens = reports.Sum(report => (long)report.Tokens.Input),
            OutputTokens = reports.Sum(report => (long)report.Tokens.Output),
            CachedTokens = reports.Sum(report => (long)report.Tokens.Cached),
            IntermediateOutputTokens = reports.Sum(report => (long)report.Tokens.IntermediateOutput),
            DirectCost = reports
                .Where(report => report.DirectCost is not null)
                .Sum(report => report.DirectCost!.Amount),
        };
    }

    private static void ValidateReport(TaskReport report)
    {
        if (string.IsNullOrWhiteSpace(report.Id) || report.Id.Length > 256)
        {
            throw new IntelligenceFormatException("Task report id must contain between 1 and 256 characters.");
        }

        TokenUsage tokens = report.Tokens;
        int[] tokenCounts = [
            tokens.Input,
            tokens.Output,
            tokens.Cached,
            tokens.IntermediateOutput,
            tokens.Retrieved,
            tokens.Injected,
        ];
        if (tokenCounts
            .Any(value => value < 0))
        {
            throw new IntelligenceFormatException($"Task report '{report.Id}' contains a negative token count.");
        }

        if (report.DirectCost is { } cost
            && (cost.Amount < 0 || string.IsNullOrWhiteSpace(cost.Currency)))
        {
            throw new IntelligenceFormatException($"Task report '{report.Id}' contains an invalid direct cost.");
        }
    }

    private static JsonObject NewDocument() => new()
    {
        ["version"] = CurrentVersion,
        ["updated_at"] = FormatMoment(DateTimeOffset.UtcNow),
        ["summary"] = ToJson(new ProjectIntelligenceSummary
        {
            Tasks = 0,
            InputTokens = 0,
            OutputTokens = 0,
            CachedTokens = 0,
            IntermediateOutputTokens = 0,
            DirectCost = 0,
        }),
        ["tasks"] = new JsonArray(),
        ["debt"] = new JsonArray(),
    };

    private static ProjectIntelligenceSnapshot EmptySnapshot() => new()
    {
        Version = CurrentVersion,
        UpdatedAt = DateTimeOffset.UtcNow,
        Summary = new ProjectIntelligenceSummary
        {
            Tasks = 0,
            InputTokens = 0,
            OutputTokens = 0,
            CachedTokens = 0,
            IntermediateOutputTokens = 0,
            DirectCost = 0,
        },
    };

    private static JsonObject ToJson(TaskReport report)
    {
        JsonObject node = new()
        {
            ["id"] = report.Id,
            ["status"] = StatusText(report.Status),
            ["type"] = report.Type,
            ["component"] = Strings(report.Components),
            ["complexity"] = report.Complexity,
            ["strategy"] = report.Strategy,
            ["tokens"] = ToJson(report.Tokens),
            ["files_changed"] = Strings(report.ChangedFiles),
            ["tests"] = Strings(report.Tests),
            ["documentation"] = Strings(report.Documentation),
            ["debt"] = Strings(report.Debt),
            ["evidence"] = Strings(report.Evidence),
            ["models"] = Strings(report.Models),
        };

        if (report.Risk is { } risk)
        {
            node["risk"] = RiskText(risk);
        }

        if (report.DirectCost is { } cost)
        {
            node["cost"] = new JsonObject { ["direct"] = ToJson(cost) };
        }

        if (report.StartedAt is { } startedAt)
        {
            node["started_at"] = FormatMoment(startedAt);
        }

        if (report.FinishedAt is { } finishedAt)
        {
            node["finished_at"] = FormatMoment(finishedAt);
        }

        return node;
    }

    private static JsonObject ToJson(TokenUsage tokens) => new()
    {
        ["input"] = tokens.Input,
        ["output"] = tokens.Output,
        ["cached"] = tokens.Cached,
        ["intermediate_output"] = tokens.IntermediateOutput,
        ["retrieved"] = tokens.Retrieved,
        ["injected"] = tokens.Injected,
    };

    private static JsonObject ToJson(CostMeasurement cost) => new()
    {
        ["amount"] = cost.Amount,
        ["currency"] = cost.Currency,
        ["provenance"] = ProvenanceText(cost.Provenance),
        ["confidence"] = ConfidenceText(cost.Confidence),
    };

    private static JsonObject ToJson(ProjectIntelligenceSummary summary) => new()
    {
        ["tasks"] = summary.Tasks,
        ["input_tokens"] = summary.InputTokens,
        ["output_tokens"] = summary.OutputTokens,
        ["cached_tokens"] = summary.CachedTokens,
        ["intermediate_output_tokens"] = summary.IntermediateOutputTokens,
        ["direct_cost"] = summary.DirectCost,
    };

    private static JsonArray Strings(IEnumerable<string> values)
    {
        JsonArray array = [];
        foreach (string value in values)
        {
            array.Add(value);
        }

        return array;
    }

    private static async Task WriteAtomicallyAsync(
        string path,
        string content,
        CancellationToken cancellationToken)
    {
        string? directory = Path.GetDirectoryName(path);
        if (string.IsNullOrWhiteSpace(directory))
        {
            throw new IntelligenceFormatException($"Project Intelligence path '{path}' has no directory.");
        }

        Directory.CreateDirectory(directory);
        string temporary = Path.Combine(
            directory,
            $".{Path.GetFileName(path)}.{Guid.NewGuid():N}.tmp");

        try
        {
            FileStream stream = new(
                temporary,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.None,
                bufferSize: 4096,
                useAsync: true);
            await using (stream.ConfigureAwait(false))
            {
                byte[] bytes = Encoding.UTF8.GetBytes(content);
                await stream.WriteAsync(bytes, cancellationToken).ConfigureAwait(false);
                await stream.FlushAsync(cancellationToken).ConfigureAwait(false);
#pragma warning disable CA1849 // FileStream has no asynchronous flush-to-disk API; durability is required before replacement.
                stream.Flush(flushToDisk: true);
#pragma warning restore CA1849
            }

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

    public void Dispose() => _writeGate.Dispose();

    private static List<string> ReadDebt(JsonObject document) =>
        document["debt"] is JsonArray debt
            ? [.. debt.Select(node => node switch
            {
                JsonValue value when value.TryGetValue<string>(out string? text) => text,
                JsonObject item when item["id"] is JsonValue id && id.TryGetValue<string>(out string? value)
                    => value,
                _ => null,
            }).Where(value => !string.IsNullOrWhiteSpace(value)).Select(value => value!)]
            : [];

    private static List<string> ReadStrings(JsonObject node, string key)
    {
        JsonNode? value = node[key];
        if (value is JsonValue scalar && scalar.TryGetValue<string>(out string? text))
        {
            return string.IsNullOrWhiteSpace(text) ? [] : [text.Trim()];
        }

        if (value is JsonArray array)
        {
            return [.. array.OfType<JsonValue>()
                .Select(item => item.TryGetValue<string>(out string? itemText) ? itemText?.Trim() : null)
                .Where(itemText => !string.IsNullOrEmpty(itemText))
                .Select(itemText => itemText!)];
        }

        if (value is JsonObject objectValue
            && objectValue["summary"] is JsonValue summary
            && summary.TryGetValue<string>(out string? summaryText)
            && !string.IsNullOrWhiteSpace(summaryText))
        {
            return [summaryText.Trim()];
        }

        return [];
    }

    private static string? ReadOptionalString(JsonObject node, string key) =>
        node[key] is JsonValue value
        && value.TryGetValue<string>(out string? text)
        && !string.IsNullOrWhiteSpace(text)
            ? text.Trim()
            : null;

    private static string ReadRequiredString(JsonObject node, string key, string source) =>
        ReadOptionalString(node, key)
        ?? throw new IntelligenceFormatException($"{source} must contain non-empty string '{key}'.");

    private static int ReadRequiredInt(JsonObject node, string key, string source) =>
        node[key] is JsonValue value
        && value.TryGetValue<int>(out int number)
        && number >= 0
            ? number
            : throw new IntelligenceFormatException($"{source} must contain non-negative integer '{key}'.");

    private static int ReadOptionalNonNegativeInt(JsonObject node, string key, string source) =>
        node[key] is null
            ? 0
            : node[key] is JsonValue value
              && value.TryGetValue<int>(out int number)
              && number >= 0
                ? number
                : throw new IntelligenceFormatException($"{source} contains invalid integer '{key}'.");

    private static decimal ReadOptionalDecimal(JsonObject node, string key, string source) =>
        node[key] is JsonValue value
        && value.TryGetValue<decimal>(out decimal number)
        && number >= 0
            ? number
            : throw new IntelligenceFormatException($"{source} contains invalid decimal '{key}'.");

    private static DateTimeOffset ReadRequiredMoment(JsonObject node, string key, string source) =>
        ParseMoment(ReadRequiredString(node, key, source), source);

    private static DateTimeOffset? ReadOptionalMoment(JsonObject node, string key, string source) =>
        ReadOptionalString(node, key) is { } text ? ParseMoment(text, source) : null;

    private static DateTimeOffset ParseMoment(string text, string source) =>
        DateTimeOffset.TryParse(
            text,
            CultureInfo.InvariantCulture,
            DateTimeStyles.RoundtripKind,
            out DateTimeOffset moment)
                ? moment
                : throw new IntelligenceFormatException($"{source} contains invalid timestamp '{text}'.");

    private static TaskReportStatus ParseStatus(string value) => value switch
    {
        "planned" => TaskReportStatus.Planned,
        "running" => TaskReportStatus.Running,
        "success" => TaskReportStatus.Success,
        "failed" => TaskReportStatus.Failed,
        "blocked" => TaskReportStatus.Blocked,
        "cancelled" => TaskReportStatus.Cancelled,
        _ => throw new IntelligenceFormatException($"Task report status '{value}' is not supported."),
    };

    private static RiskLevel? ParseRisk(string? value) => value switch
    {
        null => null,
        "low" => RiskLevel.Low,
        "medium" => RiskLevel.Medium,
        "high" => RiskLevel.High,
        _ => throw new IntelligenceFormatException($"Risk '{value}' is not supported."),
    };

    private static MeasurementProvenance ParseProvenance(string value) => value switch
    {
        "observed" => MeasurementProvenance.Observed,
        "estimated" => MeasurementProvenance.Estimated,
        "allocated" => MeasurementProvenance.Allocated,
        "unknown" => MeasurementProvenance.Unknown,
        _ => throw new IntelligenceFormatException($"Cost provenance '{value}' is not supported."),
    };

    private static MeasurementConfidence ParseConfidence(string value) => value switch
    {
        "low" => MeasurementConfidence.Low,
        "medium" => MeasurementConfidence.Medium,
        "high" => MeasurementConfidence.High,
        "unknown" => MeasurementConfidence.Unknown,
        _ => throw new IntelligenceFormatException($"Cost confidence '{value}' is not supported."),
    };

    private static string StatusText(TaskReportStatus status) => status switch
    {
        TaskReportStatus.Planned => "planned",
        TaskReportStatus.Running => "running",
        TaskReportStatus.Success => "success",
        TaskReportStatus.Failed => "failed",
        TaskReportStatus.Blocked => "blocked",
        TaskReportStatus.Cancelled => "cancelled",
        _ => throw new ArgumentOutOfRangeException(nameof(status)),
    };

    private static string RiskText(RiskLevel risk) => risk switch
    {
        RiskLevel.Low => "low",
        RiskLevel.Medium => "medium",
        RiskLevel.High => "high",
        _ => throw new ArgumentOutOfRangeException(nameof(risk)),
    };

    private static string ProvenanceText(MeasurementProvenance provenance) => provenance switch
    {
        MeasurementProvenance.Observed => "observed",
        MeasurementProvenance.Estimated => "estimated",
        MeasurementProvenance.Allocated => "allocated",
        MeasurementProvenance.Unknown => "unknown",
        _ => throw new ArgumentOutOfRangeException(nameof(provenance)),
    };

    private static string ConfidenceText(MeasurementConfidence confidence) => confidence switch
    {
        MeasurementConfidence.Low => "low",
        MeasurementConfidence.Medium => "medium",
        MeasurementConfidence.High => "high",
        MeasurementConfidence.Unknown => "unknown",
        _ => throw new ArgumentOutOfRangeException(nameof(confidence)),
    };

    private static string FormatMoment(DateTimeOffset value) =>
        value.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);
}
