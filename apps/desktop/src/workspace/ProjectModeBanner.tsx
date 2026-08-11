import type { FC } from "react";
import type { ProjectInspection } from "../api";
import { buttonStyle, card, muted, StatusBadge } from "../components/Primitives";
import { accent, space, surface, text, tone } from "../theme";

const MODE_LABELS: Record<ProjectInspection["mode"], string> = {
  "atlas-ready": "Project Atlas ready",
  "atlas-needs-adaptation": "Needs adaptation",
  "atlas-incompatible": "Incompatible framework",
  external: "External project",
};

export const ProjectModeBanner: FC<{
  inspection: ProjectInspection | null;
  onAdapt: () => void;
}> = ({ inspection, onAdapt }) => {
  if (inspection === null || !inspection.capabilities || inspection.mode === "atlas-ready") return null;

  const blocked = !inspection.capabilities.canPlan;
  const colours = inspection.mode === "atlas-incompatible" ? tone.negative : tone.waiting;

  return (
    <section
      role="status"
      style={{
        ...card,
        borderColor: colours.border,
        background: colours.bg,
        display: "flex",
        alignItems: "flex-start",
        gap: space.base,
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: space.snug }}>
          <StatusBadge value={MODE_LABELS[inspection.mode]} />
          <strong>{inspection.projectName}</strong>
        </div>
        <p style={{ ...muted, margin: `${space.snug}px 0 ${space.tight}px` }}>
          {inspection.reason}
        </p>
        <p style={{ ...muted, margin: 0 }}>{inspection.recommendation}</p>
        {blocked && (
          <p style={{ color: text.danger, fontSize: "0.8rem", margin: `${space.snug}px 0 0` }}>
            Plan, Run and Review stay locked until this project is Project Atlas ready.
          </p>
        )}
      </div>
      {inspection.capabilities.canAdapt && (
        <button
          type="button"
          onClick={onAdapt}
          style={{ ...buttonStyle, background: accent.base, color: accent.on, borderColor: accent.base }}
        >
          Review adaptation
        </button>
      )}
    </section>
  );
};

export const projectModeLabel = (inspection: ProjectInspection | null): string =>
  inspection ? MODE_LABELS[inspection.mode] : "Checking project";

export const projectModeSurface = (inspection: ProjectInspection | null): string =>
  inspection?.mode === "atlas-ready" ? surface.card : surface.raised;
