import type { FC } from "react";
import { useMemo, useState } from "react";
import { api, type DocEntry } from "../api";
import { desktop, isDesktop, type BackendStatus } from "../desktop";
import { useAsync } from "../hooks/useAsync";
import {
  AsyncPanel,
  buttonStyle,
  card,
  muted,
  screen,
  SectionHeading,
  StatusBadge,
} from "../components/Primitives";
import { accent, text } from "../theme";

function groupBySection(entries: DocEntry[]): [string, DocEntry[]][] {
  const groups = new Map<string, DocEntry[]>();
  entries.forEach((entry) => {
    const bucket = groups.get(entry.section) ?? [];
    bucket.push(entry);
    groups.set(entry.section, bucket);
  });
  return [...groups.entries()];
}

/** What the shell panel says about a backend it may or may not have started. */
export function describeBackend(status: BackendStatus | null): string {
  if (status === null) return "Running in a browser — the shell manages nothing here.";
  if (status.running) return `Backend running at ${status.url}`;
  return `No backend started by this window. It would run: ${status.command.join(" ")}`;
}

const BackendPanel: FC = () => {
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const state = useAsync(async () => await desktop.backendStatus(), []);

  const current = status ?? state.data;

  const act = async (action: () => Promise<BackendStatus | null>) => {
    try {
      setStatus(await action());
      setError(null);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  return (
    <section>
      <SectionHeading>Backend</SectionHeading>
      <div style={card}>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <StatusBadge value={current?.running ? "RUNNING" : "STOPPED"} />
          <span style={muted}>{describeBackend(current)}</span>
        </div>
        {current && (
          <p style={{ ...muted, margin: "0.25rem 0 0" }}>
            Project root: {current.projectRoot}
            {current.logPath && ` · log: ${current.logPath}`}
          </p>
        )}
        {error && (
          <p style={{ ...muted, color: text.danger, margin: "0.25rem 0 0" }} role="alert">
            {error}
          </p>
        )}
        <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.5rem" }}>
          <button
            type="button"
            style={buttonStyle}
            disabled={current?.running === true}
            onClick={() => void act(desktop.startBackend)}
          >
            Start
          </button>
          <button
            type="button"
            style={buttonStyle}
            disabled={current?.running !== true}
            onClick={() => void act(desktop.stopBackend)}
          >
            Stop
          </button>
        </div>
      </div>
    </section>
  );
};

export const ProjectScreen: FC = () => {
  const project = useAsync(() => api.project(), []);
  const goals = useAsync(() => api.goals(), []);
  const docs = useAsync(() => api.docs(), []);
  const [openDoc, setOpenDoc] = useState<string | null>(null);
  const content = useAsync(
    async () => (openDoc ? (await api.doc(openDoc)).content : null),
    [openDoc],
  );

  const sections = useMemo(() => groupBySection(docs.data ?? []), [docs.data]);

  return (
    <div style={screen}>
      <SectionHeading>Project</SectionHeading>

      <AsyncPanel loading={project.loading} error={project.error} onRetry={project.reload}>
        {project.data && (
          <div style={card}>
            <strong>{project.data.id}</strong>
            <p style={{ ...muted, margin: "0.25rem 0 0" }}>
              {project.data.phases} phases · {project.data.agents.length} agents ·{" "}
              {project.data.skills.length} skills · runners:{" "}
              {project.data.runners.join(", ")}
            </p>
          </div>
        )}
      </AsyncPanel>

      {isDesktop() && <BackendPanel />}

      <section>
        <SectionHeading>Goals</SectionHeading>
        <AsyncPanel loading={goals.loading} error={goals.error} onRetry={goals.reload}>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.3rem" }}>
            {goals.data?.map((goal) => (
              <li key={goal.id} style={{ ...card, display: "flex", gap: "0.5rem" }}>
                <StatusBadge value={goal.state} />
                <strong style={{ minWidth: 80 }}>{goal.id}</strong>
                <span>{goal.title}</span>
              </li>
            ))}
          </ul>
        </AsyncPanel>
      </section>

      <section>
        <SectionHeading>Canonical documentation</SectionHeading>
        <AsyncPanel loading={docs.loading} error={docs.error} onRetry={docs.reload}>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) 2fr", gap: "1rem" }}>
            <nav aria-label="Documentation" style={{ maxHeight: 420, overflowY: "auto" }}>
              {sections.map(([section, entries]) => (
                <div key={section} style={{ marginBottom: "0.75rem" }}>
                  <p style={{ ...muted, fontWeight: 600, margin: "0 0 0.25rem" }}>{section}</p>
                  <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                    {entries.map((entry) => (
                      <li key={entry.path}>
                        <button
                          type="button"
                          aria-pressed={openDoc === entry.path}
                          onClick={() => setOpenDoc(entry.path)}
                          style={{
                            ...buttonStyle,
                            width: "100%",
                            textAlign: "left",
                            border: "none",
                            background: openDoc === entry.path ? accent.soft : "transparent",
                            fontWeight: openDoc === entry.path ? 600 : 400,
                          }}
                        >
                          {entry.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </nav>

            <article style={{ ...card, maxHeight: 420, overflowY: "auto" }}>
              {openDoc ? (
                <AsyncPanel
                  loading={content.loading}
                  error={content.error}
                  onRetry={content.reload}
                >
                  <pre
                    style={{
                      whiteSpace: "pre-wrap",
                      fontFamily: "ui-monospace, monospace",
                      fontSize: "0.78rem",
                      margin: 0,
                    }}
                  >
                    {content.data}
                  </pre>
                </AsyncPanel>
              ) : (
                <p style={muted}>Select a document to read it.</p>
              )}
            </article>
          </div>
        </AsyncPanel>
      </section>
    </div>
  );
};
