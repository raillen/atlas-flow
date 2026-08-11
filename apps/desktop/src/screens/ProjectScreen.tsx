import type { FC } from "react";
import { useMemo, useState } from "react";
import { api, type DocEntry } from "../api";
import { useAsync } from "../hooks/useAsync";
import {
  AsyncPanel,
  buttonStyle,
  card,
  muted,
  screen,
  SectionHeading,
} from "../components/Primitives";
import { accent } from "../theme";

function groupBySection(entries: DocEntry[]): [string, DocEntry[]][] {
  const groups = new Map<string, DocEntry[]>();
  entries.forEach((entry) => {
    const bucket = groups.get(entry.section) ?? [];
    bucket.push(entry);
    groups.set(entry.section, bucket);
  });
  return [...groups.entries()];
}

export const ProjectScreen: FC = () => {
  const project = useAsync(() => api.project(), []);
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
