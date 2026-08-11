using Avalonia;

namespace AtlasFlow.Desktop;

internal static class Program
{
    /// <summary>
    /// Entry point. Kept free of application logic so that
    /// <see cref="BuildAvaloniaApp"/> can be reused verbatim by the headless
    /// test host — a UI test that configures the app differently from the way
    /// it ships is testing something nobody runs.
    /// </summary>
    [STAThread]
    public static int Main(string[] args) =>
        BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);

    public static AppBuilder BuildAvaloniaApp() =>
        AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .WithInterFont()
            .LogToTrace();
}
