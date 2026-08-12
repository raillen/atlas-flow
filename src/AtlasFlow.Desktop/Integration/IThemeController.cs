namespace AtlasFlow.Desktop.Integration;

public interface IThemeController
{
    string CurrentMode { get; }

    string Toggle();
}
