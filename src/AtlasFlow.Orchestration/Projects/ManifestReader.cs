using YamlDotNet.RepresentationModel;

namespace AtlasFlow.Orchestration.Projects;

/// <summary>One YAML manifest, read defensively.</summary>
/// <remarks>
/// Inspection runs against an arbitrary directory the user pointed at, so
/// every read here assumes the file may be absent, unreadable, malformed, or
/// valid YAML that is not a mapping. A failure is a value to report, not an
/// exception to propagate: telling the user which manifest is broken and why
/// is the entire product of inspection.
/// </remarks>
internal sealed record Manifest
{
    private readonly YamlMappingNode? _root;

    private Manifest(YamlMappingNode? root, string? error)
    {
        _root = root;
        Error = error;
    }

    /// <summary>Why the file could not be read, or <c>null</c> if it could.</summary>
    internal string? Error { get; }

    internal bool IsValid => Error is null;

    internal static Manifest Read(string path)
    {
        string name = Path.GetFileName(path);

        string text;
        try
        {
            text = File.ReadAllText(path);
        }
        catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
        {
            return new Manifest(null, $"Could not read {name}: {exc.Message}");
        }

        YamlStream stream = new();
        try
        {
            stream.Load(new StringReader(text));
        }
        catch (YamlDotNet.Core.YamlException exc)
        {
            return new Manifest(null, $"Could not read {name}: {exc.Message}");
        }

        if (stream.Documents.Count == 0 || stream.Documents[0].RootNode is not YamlMappingNode mapping)
        {
            return new Manifest(null, $"{name} must contain a mapping.");
        }

        return new Manifest(mapping, null);
    }

    /// <summary>A nested mapping, or <c>null</c> if the key is absent or not one.</summary>
    internal Manifest? Section(string key) =>
        _root is not null && _root.Children.TryGetValue(new YamlScalarNode(key), out YamlNode? node)
        && node is YamlMappingNode mapping
            ? new Manifest(mapping, null)
            : null;

    /// <summary>A scalar, trimmed, or <c>null</c> when absent or empty.</summary>
    internal string? Text(string key)
    {
        if (_root is null
            || !_root.Children.TryGetValue(new YamlScalarNode(key), out YamlNode? node)
            || node is not YamlScalarNode scalar
            || string.IsNullOrWhiteSpace(scalar.Value))
        {
            return null;
        }

        return scalar.Value.Trim();
    }

    /// <summary>A scalar or a sequence of them, as a list. Never null.</summary>
    internal IReadOnlyList<string> Strings(string key)
    {
        if (_root is null || !_root.Children.TryGetValue(new YamlScalarNode(key), out YamlNode? node))
        {
            return [];
        }

        return node switch
        {
            YamlScalarNode scalar when !string.IsNullOrWhiteSpace(scalar.Value) => [scalar.Value.Trim()],
            YamlSequenceNode sequence =>
            [
                .. sequence.Children
                    .OfType<YamlScalarNode>()
                    .Select(item => item.Value?.Trim())
                    .Where(value => !string.IsNullOrEmpty(value))
                    .Select(value => value!),
            ],
            _ => [],
        };
    }
}
