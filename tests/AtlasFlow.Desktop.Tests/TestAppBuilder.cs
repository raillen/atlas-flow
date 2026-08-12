using AtlasFlow.Desktop;
using Avalonia;
using Avalonia.Headless;

[assembly: AvaloniaTestApplication(typeof(AtlasFlow.Desktop.Tests.TestAppBuilder))]

namespace AtlasFlow.Desktop.Tests;

public static class TestAppBuilder
{
    public static AppBuilder BuildAvaloniaApp() => AppBuilder
        .Configure<App>()
        .UseSkia()
        .UseHeadless(new AvaloniaHeadlessPlatformOptions
        {
            UseHeadlessDrawing = false,
        });
}
