using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Projects;
using AtlasFlow.Orchestration.Projects;

namespace AtlasFlow.Application.Services;

/// <summary>Opening a project, reading it, and adapting it.</summary>
public sealed class ProjectService(AtlasFlowOptions options) : IProjectService
{
    /// <summary>
    /// Files and directories never worth showing in the explorer.
    /// </summary>
    /// <remarks>
    /// Walking <c>node_modules</c> or <c>.venv</c> is how listing a project
    /// takes ten seconds and returns two hundred thousand entries nobody asked
    /// for. <c>.git</c> is excluded for the same reason and one more: its
    /// contents are not the project, they are the machinery under it.
    /// </remarks>
    private static readonly string[] IgnoredDirectories =
    [
        ".git", "node_modules", ".venv", "venv", "__pycache__", "target",
        "bin", "obj", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ];

    /// <summary>Beyond this, a file viewer is not what the user needs.</summary>
    private const int MaxReadBytes = 512 * 1024;

    private readonly string _root = options.ProjectRoot;

    public Task<ProjectInspection> InspectAsync(string root, CancellationToken cancellationToken = default) =>
        Task.Run(() => ProjectInspector.Inspect(root), cancellationToken);

    public Task<ProjectInspection?> GetCurrentAsync(CancellationToken cancellationToken = default) =>
        Task.Run<ProjectInspection?>(
            () => Directory.Exists(_root) ? ProjectInspector.Inspect(_root) : null,
            cancellationToken);

    public Task<IReadOnlyList<ProjectFile>> ListFilesAsync(CancellationToken cancellationToken = default) =>
        Task.Run<IReadOnlyList<ProjectFile>>(() => Walk(cancellationToken), cancellationToken);

    public Task<ProjectFileContent> ReadFileAsync(
        ProjectPath path,
        CancellationToken cancellationToken = default) =>
        Task.Run(() => Read(path), cancellationToken);

    public Task<AdaptationPreview> PreviewAdaptationAsync(CancellationToken cancellationToken = default) =>
        throw new NotSupportedException(
            "Adaptation is not ported yet. See reference/python-backend/atlas_flow/project/adaptation.py.");

    public Task<AdaptationResult> ApplyAdaptationAsync(
        IReadOnlyList<ProjectPath> paths,
        CancellationToken cancellationToken = default) =>
        throw new NotSupportedException(
            "Adaptation is not ported yet. See reference/python-backend/atlas_flow/project/adaptation.py.");

    private List<ProjectFile> Walk(CancellationToken cancellationToken)
    {
        List<ProjectFile> found = [];
        if (!Directory.Exists(_root))
        {
            return found;
        }

        Queue<string> pending = new();
        pending.Enqueue(_root);

        while (pending.Count > 0)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string directory = pending.Dequeue();

            IEnumerable<string> entries;
            try
            {
                entries = Directory.EnumerateFileSystemEntries(directory);
            }
            catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
            {
                // A directory the user cannot read is not a reason to fail the
                // whole listing. It is simply not in it.
                continue;
            }

            foreach (string entry in entries)
            {
                string name = Path.GetFileName(entry);

                if (Directory.Exists(entry))
                {
                    if (IgnoredDirectories.Contains(name, StringComparer.Ordinal))
                    {
                        continue;
                    }

                    pending.Enqueue(entry);
                    found.Add(new ProjectFile
                    {
                        Path = ProjectPaths.Relative(_root, entry),
                        Kind = ProjectFileKind.Directory,
                        SizeInBytes = 0,
                    });
                    continue;
                }

                long size;
                try
                {
                    size = new FileInfo(entry).Length;
                }
                catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
                {
                    continue;
                }

                found.Add(new ProjectFile
                {
                    Path = ProjectPaths.Relative(_root, entry),
                    Kind = Classify(name),
                    SizeInBytes = size,
                });
            }
        }

        return [.. found.OrderBy(file => file.Path.Value, StringComparer.Ordinal)];
    }

    private ProjectFileContent Read(ProjectPath path)
    {
        string absolute;
        try
        {
            absolute = ProjectPaths.Resolve(_root, path);
        }
        catch (ProjectPathEscapeException exc)
        {
            throw new ProjectPathException(exc.Message, exc);
        }

        if (!File.Exists(absolute))
        {
            throw new ProjectPathException($"'{path.Value}' is not a file in the open project");
        }

        using FileStream stream = File.OpenRead(absolute);
        bool isTruncated = stream.Length > MaxReadBytes;

        byte[] buffer = new byte[isTruncated ? MaxReadBytes : (int)stream.Length];
        stream.ReadExactly(buffer);

        return new ProjectFileContent
        {
            Path = path,
            Content = System.Text.Encoding.UTF8.GetString(buffer),
            IsTruncated = isTruncated,
        };
    }

    private static ProjectFileKind Classify(string name) => Path.GetExtension(name) switch
    {
        ".md" or ".txt" or ".rst" or ".adoc" => ProjectFileKind.Document,
        ".cs" or ".py" or ".ts" or ".tsx" or ".js" or ".rs" or ".go" or ".java" => ProjectFileKind.Source,
        ".yaml" or ".yml" or ".json" or ".toml" => ProjectFileKind.Manifest,
        _ => ProjectFileKind.Other,
    };
}
