import type { FC, ReactNode } from "react";
import { surface, text, tone, toneFor } from "../theme";

export const screen: React.CSSProperties = {
  padding: "1.5rem 2rem",
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
};

export const card: React.CSSProperties = {
  padding: "0.875rem 1rem",
  border: `1px solid ${surface.border}`,
  borderRadius: 8,
  background: surface.card,
};

export const muted: React.CSSProperties = {
  color: text.muted,
  fontSize: "0.8rem",
};

/**
 * Colour is never the only cue: the badge always renders its label, so a
 * grayscale screenshot or a colour-blind reading loses nothing.
 */
export const StatusBadge: FC<{ value: string }> = ({ value }) => {
  const colours = tone[toneFor(value)];
  return (
    <span
      className="status-badge"
      style={{
        color: colours.fg,
        fontSize: "0.64rem",
        fontWeight: 500,
        letterSpacing: "0.01em",
        lineHeight: 1.2,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 5,
          height: 5,
          flex: "0 0 auto",
          borderRadius: "50%",
          background: colours.fg,
        }}
      />
      <span>{value}</span>
    </span>
  );
};

export const SectionHeading: FC<{ children: ReactNode; actions?: ReactNode }> = ({
  children,
  actions,
}) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
    <h2 style={{ fontSize: "1rem", fontWeight: 500, margin: 0 }}>{children}</h2>
    {actions}
  </div>
);

/**
 * Renders loading, error and empty states so a screen never silently shows
 * nothing — an empty panel and a failed request must not look identical.
 */
export const AsyncPanel: FC<{
  loading: boolean;
  error: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  children: ReactNode;
}> = ({ loading, error, isEmpty, emptyMessage, onRetry, children }) => {
  if (error) {
    return (
      <div
        style={{ ...card, borderColor: tone.negative.border, background: tone.negative.bg }}
        role="alert"
      >
        <strong style={{ color: text.danger }}>Could not reach the backend</strong>
        <p style={muted}>{error}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} style={buttonStyle}>
            Retry
          </button>
        )}
      </div>
    );
  }
  if (loading) {
    return (
      <p style={muted} aria-live="polite">
        Loading…
      </p>
    );
  }
  if (isEmpty) {
    return <p style={muted}>{emptyMessage ?? "Nothing here yet."}</p>;
  }
  return <>{children}</>;
};

export const buttonStyle: React.CSSProperties = {
  padding: "0.4rem 0.8rem",
  borderRadius: 6,
  border: `1px solid ${tone.neutral.border}`,
  background: surface.card,
  color: text.primary,
  cursor: "pointer",
  fontSize: "0.8rem",
  fontWeight: 400,
};
