import type { FC } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  type SettingsDocument,
  type SettingsSaveResult,
  type SettingView,
} from "../api";
import { AsyncPanel, buttonStyle, card, muted, StatusBadge } from "../components/Primitives";
import { space, surface, text, tone } from "../theme";

/** The drawer reads the document once and keeps a local draft until Save. */
export const SettingsDrawer: FC<{
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}> = ({ open, onClose, onChanged }) => {
  const [document, setDocument] = useState<SettingsDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveResult, setSaveResult] = useState<SettingsSaveResult | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!open) return;
    let current = true;
    setLoading(true);
    setError(null);
    api
      .settings()
      .then((doc) => {
        if (!current) return;
        setDocument(doc);
        setDraft(Object.fromEntries(doc.settings.map((s) => [s.key, s.value])));
        setSaveResult(null);
      })
      .catch((cause: unknown) => {
        if (!current) return;
        setError(cause instanceof Error ? cause.message : String(cause));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [open, nonce]);

  const scopes = useMemo(() => {
    if (!document) return [];
    const order = ["project", "user"] as const;
    return order.map((scope) => ({
      scope,
      settings: document.settings.filter((s) => s.source.scope === scope),
    }));
  }, [document]);

  if (!open) return null;

  const setValue = (key: string, value: unknown) =>
    setDraft((previous) => ({ ...previous, [key]: value }));

  const save = async (scope: string) => {
    const values: Record<string, unknown> = {};
    for (const group of scopes) {
      if (group.scope !== scope) continue;
      for (const setting of group.settings) values[setting.key] = draft[setting.key];
    }
    setSaving(true);
    setSaveError(null);
    try {
      const result = await api.saveSettings(scope, values);
      setSaveResult(result);
      setDocument(result);
      onChanged();
    } catch (cause: unknown) {
      setSaveError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSaving(false);
    }
  };

  const reset = async (scope: string, keys: string[]) => {
    setSaving(true);
    setSaveError(null);
    try {
      const result = await api.resetSettings(scope, keys);
      setDocument(result);
      setDraft((previous) => {
        const next = { ...previous };
        for (const key of keys) next[key] = result.settings.find((s) => s.key === key)?.value;
        return next;
      });
      setSaveResult(null);
      onChanged();
    } catch (cause: unknown) {
      setSaveError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSaving(false);
    }
  };

  const providers = document?.providers ?? [];
  const diagnostics = document?.diagnostics ?? {};

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        justifyContent: "flex-end",
        background: "rgba(15, 23, 42, 0.32)",
      }}
    >
      <section
        style={{
          width: "min(680px, 100%)",
          height: "100dvh",
          overflowY: "auto",
          background: surface.page,
          borderLeft: `1px solid ${surface.border}`,
          boxShadow: "-16px 0 48px rgba(15, 23, 42, 0.18)",
          padding: `${space.loose}px ${space.wide}px`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: space.base }}>
          <div>
            <p style={{ ...muted, margin: 0 }}>Workspace</p>
            <h2 id="settings-title" style={{ margin: `${space.tight}px 0 0` }}>
              Settings
            </h2>
          </div>
          <button type="button" style={buttonStyle} onClick={onClose}>
            Close
          </button>
        </div>

        <p style={{ ...muted, margin: `${space.loose}px 0` }}>
          Values are read from the closest source that defines them: default → project
          → user → environment. Edits are written back to the source owning each scope.
        </p>

        <AsyncPanel loading={loading} error={error} onRetry={() => setNonce((n) => n + 1)}>
          {document && (
            <>
              {document.restartRequired && (
                <p
                  style={{
                    ...muted,
                    color: text.danger,
                    padding: space.snug,
                    border: `1px solid ${tone.negative.border}`,
                    borderRadius: 6,
                    background: tone.negative.bg,
                  }}
                  role="alert"
                >
                  {document.restartReason ?? "Restart the engine to apply recent changes."}
                </p>
              )}

              {saveError && (
                <p style={{ ...muted, color: text.danger }} role="alert">
                  {saveError}
                </p>
              )}

              {scopes.map(({ scope, settings: scopeSettings }) => (
                <section key={scope} style={{ marginTop: space.wide }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: space.base }}>
                    <h3 style={{ margin: 0, textTransform: "capitalize" }}>{scope} settings</h3>
                    <div style={{ display: "flex", gap: space.snug }}>
                      <button
                        type="button"
                        style={buttonStyle}
                        disabled={saving}
                        onClick={() => void reset(scope, scopeSettings.map((s) => s.key))}
                      >
                        Reset all
                      </button>
                      <button
                        type="button"
                        style={{ ...buttonStyle, background: surface.selected, fontWeight: 600 }}
                        disabled={saving}
                        onClick={() => void save(scope)}
                      >
                        {saving ? "Saving…" : "Save"}
                      </button>
                    </div>
                  </div>

                  <ul style={{ listStyle: "none", padding: 0, margin: `${space.snug}px 0`, display: "grid", gap: space.snug }}>
                    {scopeSettings.map((setting) => (
                      <SettingRow
                        key={setting.key}
                        setting={setting}
                        value={draft[setting.key]}
                        onValue={setValue}
                      />
                    ))}
                  </ul>
                </section>
              ))}

              {saveResult && saveResult.changed.length > 0 && (
                <p style={{ ...muted }} role="status">
                  Saved {saveResult.changed.length} setting{saveResult.changed.length === 1 ? "" : "s"}.
                </p>
              )}

              <section style={{ marginTop: space.wide }}>
                <h3 style={{ margin: 0 }}>Model providers</h3>
                <ul style={{ listStyle: "none", padding: 0, margin: `${space.snug}px 0`, display: "grid", gap: space.snug }}>
                  {providers.map((provider) => (
                    <li key={provider.key} style={{ ...card, display: "flex", alignItems: "center", gap: space.base, background: surface.raised }}>
                      <code style={{ flex: 1 }}>{provider.commandCodeId}</code>
                      <StatusBadge value={provider.priority} />
                      <StatusBadge value={provider.availability} />
                      <span style={{ ...muted, color: provider.credentialConfigured ? undefined : text.danger }}>
                        {provider.credentialConfigured
                          ? "credential set"
                          : provider.credentialRef
                            ? `${provider.credentialRef} missing`
                            : "no credential needed"}
                      </span>
                    </li>
                  ))}
                </ul>
                {providers.length === 0 && <p style={muted}>No providers configured.</p>}
              </section>

              <section style={{ marginTop: space.wide }}>
                <h3 style={{ margin: 0 }}>Diagnostics</h3>
                <dl style={{ margin: `${space.snug}px 0 0`, display: "grid", gridTemplateColumns: "auto 1fr", gap: `${space.tight}px ${space.base}px` }}>
                  {Object.entries(diagnostics).map(([key, value]) => (
                    <div key={key} style={{ display: "contents" }}>
                      <dt style={{ ...muted, margin: 0 }}>{key}</dt>
                      <dd style={{ margin: 0, fontFamily: "monospace", fontSize: "0.75rem", wordBreak: "break-all" }}>
                        {typeof value === "object" ? JSON.stringify(value) : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            </>
          )}
        </AsyncPanel>
      </section>
    </div>
  );
};

const SELECT_OPTIONS: Record<string, string[]> = {
  autonomy_mode: ["agentic", "supervised", "human"],
  worktree_strategy: ["per-task", "single", "none"],
  log_level: ["DEBUG", "INFO", "WARNING", "ERROR"],
};

function humanize(key: string): string {
  return key.replace(/_/g, " ");
}

const SettingRow: FC<{
  setting: SettingView;
  value: unknown;
  onValue: (key: string, value: unknown) => void;
}> = ({ setting, value, onValue }) => {
  const environmentControlled = setting.source.value === "environment";
  const inputId = `setting-${setting.key}`;
  const input = (() => {
    if (environmentControlled) {
      return (
        <code style={{ fontSize: "0.75rem", color: text.muted }}>
          {setting.source.environmentVariable}
        </code>
      );
    }
    if (setting.kind === "boolean") {
      return (
        <input
          id={inputId}
          type="checkbox"
          checked={Boolean(value)}
          disabled={environmentControlled}
          onChange={(event) => onValue(setting.key, event.target.checked)}
        />
      );
    }
    if (setting.kind === "select") {
      const options = SELECT_OPTIONS[setting.key] ?? [];
      return (
        <select
          id={inputId}
          value={String(value)}
          disabled={environmentControlled}
          onChange={(event) => onValue(setting.key, event.target.value)}
          style={{ font: "inherit", padding: `${space.tight}px ${space.snug}px` }}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      );
    }
    if (setting.kind === "list") {
      return (
        <input
          id={inputId}
          type="text"
          value={Array.isArray(value) ? value.join(", ") : String(value ?? "")}
          disabled={environmentControlled}
          onChange={(event) =>
            onValue(
              setting.key,
              event.target.value
                .split(",")
                .map((part) => part.trim())
                .filter(Boolean),
            )
          }
          style={{ font: "inherit", padding: `${space.tight}px ${space.snug}px`, width: "100%" }}
        />
      );
    }
    return (
      <input
        id={inputId}
        type={setting.kind === "integer" || setting.kind === "number" ? "number" : "text"}
        value={String(value ?? "")}
        disabled={environmentControlled}
        onChange={(event) => {
          const raw = event.target.value;
          if (setting.kind === "integer") onValue(setting.key, raw === "" ? "" : Number.parseInt(raw, 10));
          else if (setting.kind === "number") onValue(setting.key, raw === "" ? "" : Number.parseFloat(raw));
          else onValue(setting.key, raw);
        }}
        style={{ font: "inherit", padding: `${space.tight}px ${space.snug}px`, width: "100%" }}
      />
    );
  })();

  return (
    <li style={{ ...card, display: "grid", gap: space.tight, background: surface.raised }}>
      <div style={{ display: "flex", alignItems: "center", gap: space.snug }}>
        <code style={{ fontWeight: 600 }}>{humanize(setting.key)}</code>
        <StatusBadge value={setting.source.value} />
        {setting.restartRequired && <StatusBadge value="restart" />}
      </div>
      <p style={{ ...muted, margin: 0 }}>{setting.description}</p>
      <label htmlFor={inputId} style={{ ...muted, display: "grid", gap: space.tight }}>
        <span>{humanize(setting.key)}</span>
        {input}
      </label>
    </li>
  );
};
