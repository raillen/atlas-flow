import type { FC } from "react";
import { useEffect, useState } from "react";
import { api, type AdaptationPreview, type ProjectInspection } from "../api";
import { AsyncPanel, buttonStyle, card, muted, StatusBadge } from "../components/Primitives";
import { accent, space, surface, text, tone } from "../theme";
import { useAsync } from "../hooks/useAsync";

export const AdaptationWizard: FC<{
  inspection: ProjectInspection | null;
  autoOpen: boolean;
  onApplied: () => void;
}> = ({ inspection, autoOpen, onApplied }) => {
  const [open, setOpen] = useState(autoOpen);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const preview = useAsync<AdaptationPreview | null>(
    () => (open && inspection?.capabilities.canAdapt ? api.adaptationPreview() : Promise.resolve(null)),
    [open, inspection?.mode],
  );

  useEffect(() => {
    setOpen(autoOpen);
    setConfirmed(false);
    setError(null);
  }, [autoOpen, inspection?.root]);

  if (!open || inspection === null || !inspection.capabilities) return null;

  const apply = async () => {
    if (!preview.data) return;
    setConfirmed(true);
    setError(null);
    try {
      const paths = preview.data.files
        .filter((file) => file.action === "create")
        .map((file) => file.path);
      await api.applyAdaptation(paths);
      setOpen(false);
      onApplied();
    } catch (cause: unknown) {
      setConfirmed(false);
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="adaptation-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "grid",
        placeItems: "center",
        padding: space.wide,
        background: "rgba(15, 23, 42, 0.32)",
      }}
    >
      <section style={{ ...card, width: "min(680px, 100%)", maxHeight: "90dvh", overflowY: "auto", boxShadow: "0 16px 48px rgba(15, 23, 42, 0.2)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: space.base }}>
          <div>
            <p style={{ ...muted, margin: 0 }}>Project onboarding</p>
            <h2 id="adaptation-title" style={{ margin: `${space.tight}px 0 0` }}>
              Adapt {inspection.projectName} to Project Atlas?
            </h2>
          </div>
          <StatusBadge value={inspection.mode} />
        </div>

        <p style={{ ...muted, margin: `${space.loose}px 0` }}>
          I can inspect and discuss this project now. Plan, Run and Review remain locked until you review and authorize the documentation scaffold below.
        </p>

        <AsyncPanel loading={preview.loading} error={preview.error} onRetry={preview.reload}>
          {preview.data && (
            <>
              <div style={{ ...card, background: surface.raised }}>
                <strong>{preview.data.ready ? "Ready to create new files" : "Review conflicts before applying"}</strong>
                <p style={{ ...muted, margin: `${space.tight}px 0 0` }}>
                  Existing files are never overwritten. No Goals are created or marked complete.
                </p>
              </div>

              <ul style={{ listStyle: "none", padding: 0, margin: `${space.loose}px 0`, display: "grid", gap: space.tight }}>
                {preview.data.files.map((file) => (
                  <li key={file.path} style={{ display: "flex", gap: space.snug, alignItems: "center" }}>
                    <StatusBadge value={file.action} />
                    <code style={{ flex: 1 }}>{file.path}</code>
                    <span style={muted}>{file.reason}</span>
                  </li>
                ))}
              </ul>

              {preview.data.conflicts.length > 0 && (
                <p style={{ ...muted, color: text.danger }} role="alert">
                  Conflicts: {preview.data.conflicts.join(", ")}. Resolve these files manually before applying.
                </p>
              )}
              <ul style={{ ...muted, margin: 0, paddingLeft: "1.2rem" }}>
                {preview.data.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
              </ul>
            </>
          )}
        </AsyncPanel>

        {error && <p style={{ ...muted, color: text.danger }} role="alert">{error}</p>}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: space.snug, marginTop: space.loose }}>
          <button type="button" style={buttonStyle} disabled={confirmed} onClick={() => setOpen(false)}>
            Do this later
          </button>
          {inspection.capabilities.canAdapt && (
            <button
              type="button"
              style={{ ...buttonStyle, background: accent.base, color: accent.on, borderColor: accent.base }}
              disabled={!preview.data?.ready || confirmed}
              onClick={() => void apply()}
            >
              {confirmed ? "Applying…" : "Create scaffold"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
};

export const adaptationTone = (preview: AdaptationPreview | null) =>
  preview?.ready ? tone.positive : tone.waiting;
