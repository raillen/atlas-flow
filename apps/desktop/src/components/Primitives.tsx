import type { FC, ReactNode } from "react";

export const screen: React.CSSProperties = {
  padding: "1.5rem 2rem",
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
};

export const card: React.CSSProperties = {
  padding: "0.875rem 1rem",
  border: "1px solid #e2e8f0",
  borderRadius: 8,
  background: "white",
};

export const muted: React.CSSProperties = {
  color: "#64748b",
  fontSize: "0.8rem",
};

const VERDICT_COLORS: Record<string, string> = {
  PASSED: "#059669",
  SUCCEEDED: "#059669",
  COMPLETED: "#059669",
  DONE: "#059669",
  FAILED: "#dc2626",
  BLOCKED: "#dc2626",
  PENDING: "#f59e0b",
  RUNNING: "#2563eb",
  READY: "#f59e0b",
  ACTIVE: "#2563eb",
  PLANNED: "#94a3b8",
};

export const StatusBadge: FC<{ value: string }> = ({ value }) => (
  <span
    style={{
      color: VERDICT_COLORS[value] ?? "#475569",
      background: `${VERDICT_COLORS[value] ?? "#475569"}14`,
      border: `1px solid ${VERDICT_COLORS[value] ?? "#475569"}33`,
      borderRadius: 999,
      padding: "0.1rem 0.5rem",
      fontSize: "0.7rem",
      fontWeight: 600,
      letterSpacing: "0.02em",
    }}
  >
    {value}
  </span>
);

export const SectionHeading: FC<{ children: ReactNode; actions?: ReactNode }> = ({
  children,
  actions,
}) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
    <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>{children}</h2>
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
      <div style={{ ...card, borderColor: "#fecaca", background: "#fef2f2" }} role="alert">
        <strong style={{ color: "#b91c1c" }}>Could not reach the backend</strong>
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
  border: "1px solid #cbd5e1",
  background: "white",
  cursor: "pointer",
  fontSize: "0.8rem",
  fontWeight: 500,
};
