import type { FC } from "react";
import { useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks/useAsync";
import { AsyncPanel, buttonStyle, card, muted, SectionHeading } from "../components/Primitives";
import { accent, space } from "../theme";

export const ProjectExplorer: FC = () => {
  const files = useAsync(() => api.projectFiles(), []);
  const [selected, setSelected] = useState<string | null>(null);
  const content = useAsync(() => selected ? api.projectFile(selected) : Promise.resolve(null), [selected]);

  return (
    <section>
      <SectionHeading>Project files</SectionHeading>
      <AsyncPanel loading={files.loading} error={files.error} onRetry={files.reload} isEmpty={files.data?.length === 0} emptyMessage="No readable project files found.">
        <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) 2fr", gap: space.base, marginTop: space.snug }}>
          <nav aria-label="Project files" style={{ ...card, maxHeight: 420, overflowY: "auto" }}>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: space.tight }}>
              {files.data?.map((file) => (
                <li key={file.path}>
                  <button type="button" disabled={file.kind === "binary"} aria-pressed={selected === file.path} onClick={() => setSelected(file.path)} style={{ ...buttonStyle, width: "100%", textAlign: "left", background: selected === file.path ? accent.soft : "transparent" }}>
                    <code>{file.path}</code><span style={muted}> · {file.kind}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
          <article style={{ ...card, maxHeight: 420, overflowY: "auto" }}>
            {selected ? (
              <AsyncPanel loading={content.loading} error={content.error} onRetry={content.reload}>
                {content.data && <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "ui-monospace, monospace", fontSize: "0.78rem" }}>{content.data.content}{content.data.truncated ? "\n\n[truncated]" : ""}</pre>}
              </AsyncPanel>
            ) : <p style={muted}>Select a text file to inspect it.</p>}
          </article>
        </div>
      </AsyncPanel>
    </section>
  );
};
