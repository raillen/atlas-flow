using Avalonia.Styling;
using AvaloniaApplication = Avalonia.Application;

namespace AtlasFlow.Desktop.Integration;

public sealed class AvaloniaThemeController : IThemeController
{
    public string CurrentMode => AvaloniaApplication.Current?.ActualThemeVariant == ThemeVariant.Light
        ? "Claro"
        : "Escuro";

    public string Toggle()
    {
        AvaloniaApplication application = AvaloniaApplication.Current
            ?? throw new InvalidOperationException("A aplicação Avalonia ainda não foi inicializada.");

        ThemeVariant nextMode = application.ActualThemeVariant == ThemeVariant.Light
            ? ThemeVariant.Dark
            : ThemeVariant.Light;
        application.RequestedThemeVariant = nextMode;

        return nextMode == ThemeVariant.Light ? "Claro" : "Escuro";
    }
}
