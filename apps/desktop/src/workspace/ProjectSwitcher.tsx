import type { FC } from "react";
import { useEffect, useRef, useState } from "react";
import { desktop, isDesktop, projectName } from "../desktop";
import { accent, size, space, surface, text, tone, type } from "../theme";

/**
 * Which project this window is on, and how to change it.
 *
 * A desktop tool that can only be pointed at a project by an environment
 * variable is not openable. This is the way in, and it is the first thing in
 * the window because it is the thing everything else is relative to.
 */
export const ProjectSwitcher: FC<{
  root: string | null;
  onOpened: () => void;
}> = ({ root, onOpened }) => {
  const [open, setOpen] = useState(false);
  const [recents, setRecents] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const container = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    void desktop.recentProjects().then(setRecents);

    const dismiss = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const openPath = async (path: string) => {
    setBusy(true);
    setError(null);
    try {
      // Opening restarts the backend against the new root (ADR-013), so this
      // is deliberately not instant and deliberately not silent.
      await desktop.openProject(path);
      setOpen(false);
      onOpened();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const browse = async () => {
    const chosen = await desktop.pickFolder();
    if (chosen !== null) await openPath(chosen);
  };

  const label = root ? projectName(root) : "No project open";

  return (
    <div ref={container} style={{ position: "relative" }}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={busy}
        onClick={() => setOpen((value) => !value)}
        title={root ?? "No project open"}
        style={{
          display: "flex",
          alignItems: "center",
          gap: space.snug,
          padding: `${space.tight}px ${space.snug}px`,
          border: `1px solid ${surface.border}`,
          borderRadius: 6,
          background: surface.card,
          color: text.primary,
          font: "inherit",
          fontSize: type.ui,
          fontWeight: 600,
          cursor: busy ? "wait" : "pointer",
        }}
      >
        <span aria-hidden="true">▣</span>
        {busy ? "Opening…" : label}
        <span aria-hidden="true" style={{ color: text.faint }}>
          ▾
        </span>
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Projects"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            minWidth: size.sidebar,
            zIndex: 20,
            background: surface.card,
            border: `1px solid ${surface.border}`,
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(15, 23, 42, 0.12)",
            padding: space.tight,
          }}
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => void browse()}
            style={menuItem(true)}
          >
            Open project…
          </button>

          {recents.length > 0 && (
            <>
              <p
                style={{
                  ...menuLabel,
                  margin: `${space.snug}px ${space.snug}px ${space.tight}px`,
                }}
              >
                Recent
              </p>
              {recents.map((path) => (
                <button
                  key={path}
                  type="button"
                  role="menuitem"
                  onClick={() => void openPath(path)}
                  title={path}
                  style={menuItem(path === root)}
                >
                  <span style={{ fontWeight: 600 }}>{projectName(path)}</span>
                  <span style={{ ...menuLabel, marginLeft: space.snug }}>{path}</span>
                </button>
              ))}
            </>
          )}

          {!isDesktop() && (
            <p style={{ ...menuLabel, padding: space.snug, margin: 0 }}>
              Running in a browser — opening a folder needs the desktop app.
            </p>
          )}
        </div>
      )}

      {error && (
        <p
          role="alert"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            zIndex: 21,
            margin: 0,
            padding: space.snug,
            maxWidth: 420,
            background: tone.negative.bg,
            border: `1px solid ${tone.negative.border}`,
            borderRadius: 6,
            color: text.danger,
            fontSize: type.small,
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
};

const menuLabel: React.CSSProperties = {
  color: text.faint,
  fontSize: type.tiny,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

function menuItem(highlighted: boolean): React.CSSProperties {
  return {
    display: "block",
    width: "100%",
    textAlign: "left",
    padding: `${space.snug}px ${space.snug}px`,
    border: "none",
    borderRadius: 6,
    background: highlighted ? accent.soft : "transparent",
    color: text.primary,
    font: "inherit",
    fontSize: type.ui,
    cursor: "pointer",
  };
}
