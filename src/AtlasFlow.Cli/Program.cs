using System.CommandLine;

namespace AtlasFlow.Cli;

internal static class Program
{
    public static Task<int> Main(string[] args)
    {
        var root = new RootCommand(
            "Atlas Flow — Goal-first orchestration for the Project Atlas Framework.");

        // Commands are registered here as they are ported. The Python CLI in
        // reference/python-backend/atlas_flow/cli.py is the specification for
        // what this surface must eventually cover.

        return root.Parse(args).InvokeAsync();
    }
}
