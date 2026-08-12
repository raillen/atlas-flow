using System.Text.Json.Nodes;

namespace AtlasFlow.Application.Contracts;

/// <summary>Reading, validating and writing configuration.</summary>
/// <remarks>
/// Validation is a separate call from saving on purpose. The settings drawer
/// shows what a change would do before it does it, and a save that silently
/// repaired an invalid value would be a save the user did not authorize.
/// </remarks>
public interface ISettingsService
{
    Task<SettingsDocument> GetAsync(CancellationToken cancellationToken = default);

    /// <summary>Checks a change without writing it.</summary>
    Task<SettingsDocument> ValidateAsync(SettingsPatch patch, CancellationToken cancellationToken = default);

    Task<SettingsSaveResult> SaveAsync(SettingsPatch patch, CancellationToken cancellationToken = default);

    /// <summary>Returns the named keys in a scope to their defaults.</summary>
    Task<SettingsDocument> ResetAsync(
        SettingsScope scope,
        IReadOnlyList<string> keys,
        CancellationToken cancellationToken = default);

    /// <summary>Checks an MCP server definition without registering it.</summary>
    Task<McpValidation> ValidateMcpAsync(JsonObject definition, CancellationToken cancellationToken = default);
}

/// <summary>Which layer of configuration a value belongs to.</summary>
public enum SettingsScope
{
    /// <summary>Built in. Never written.</summary>
    Default,

    /// <summary>This installation, this user.</summary>
    User,

    /// <summary>Committed with the project, so it applies to everyone on it.</summary>
    Project,

    /// <summary>An environment variable. Read only, and it wins.</summary>
    Environment,
}

/// <summary>Where a value came from.</summary>
public sealed record ConfigSource
{
    public required string Value { get; init; }

    public required SettingsScope Scope { get; init; }

    /// <summary>Set when <see cref="Scope"/> is <see cref="SettingsScope.Environment"/>.</summary>
    public string? EnvironmentVariable { get; init; }
}

/// <summary>One setting, its value, and where that value came from.</summary>
public sealed record Setting
{
    public required string Key { get; init; }

    public required JsonNode? Value { get; init; }

    public required JsonNode? Default { get; init; }

    public required ConfigSource Source { get; init; }

    public required string Kind { get; init; }

    /// <summary>What the setting affects, for grouping in the drawer.</summary>
    public required string AppliesTo { get; init; }

    public required string Description { get; init; }

    /// <summary>Whether changing this takes effect only after a restart.</summary>
    public bool RequiresRestart { get; init; }
}

/// <summary>One configured model provider.</summary>
public sealed record Provider
{
    public required string Key { get; init; }

    public required string Name { get; init; }

    public required string CommandCodeId { get; init; }

    public required string Priority { get; init; }

    public required string Availability { get; init; }

    /// <summary>
    /// The name of the credential, never the credential.
    /// </summary>
    /// <remarks>
    /// A secret does not cross this boundary. The UI renders whether one is
    /// configured, which is all it needs to render.
    /// </remarks>
    public string? CredentialRef { get; init; }

    public bool IsCredentialConfigured { get; init; }
}

/// <summary>Everything the settings drawer renders.</summary>
public sealed record SettingsDocument
{
    public IReadOnlyList<Setting> Settings { get; init; } = [];

    public IReadOnlyList<Provider> Providers { get; init; } = [];

    public JsonObject Mcp { get; init; } = [];

    public JsonObject Diagnostics { get; init; } = [];

    public bool RequiresRestart { get; init; }

    public string? RestartReason { get; init; }
}

/// <summary>A change to apply to one scope.</summary>
public sealed record SettingsPatch
{
    public required SettingsScope Scope { get; init; }

    public required JsonObject Values { get; init; }
}

/// <summary>What a save actually changed.</summary>
public sealed record SettingsSaveResult
{
    public required SettingsDocument Document { get; init; }

    public IReadOnlyList<string> Changed { get; init; } = [];

    /// <summary>The files written, so the user can see what moved.</summary>
    public IReadOnlyList<string> WrittenPaths { get; init; } = [];
}

/// <summary>Whether an MCP server definition is usable.</summary>
public sealed record McpValidation
{
    public required bool IsValid { get; init; }

    public IReadOnlyList<string> Errors { get; init; } = [];

    public IReadOnlyList<string> Warnings { get; init; } = [];
}
