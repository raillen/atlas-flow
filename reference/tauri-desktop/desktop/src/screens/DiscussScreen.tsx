import {
  Check,
  FileText,
  Image as ImageIcon,
  MessageSquare,
  Paperclip,
  PanelRight,
  PanelRightClose,
  Plus,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import type { FC, RefObject } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgUiClient, type AgUiMessage } from "@atlas-flow/ag-ui-client";
import {
  api,
  resolveBaseUrl,
  type DecisionCandidate,
  type DiscussionSession,
  type MessageReference,
  type ProjectDraft,
  type ProjectFileView,
} from "../api";
import { useAsync } from "../hooks/useAsync";
import { AsyncPanel, StatusBadge } from "../components/Primitives";

/** The socket lives wherever the backend does, which only the shell knows. */
async function socketUrl(): Promise<string> {
  return (await resolveBaseUrl()).replace(/^http/, "ws");
}

/** The nine domains a Project Draft tracks, in the order the Goal system lists them. */
export const DRAFT_DOMAINS: (keyof ProjectDraft)[] = [
  "product",
  "architecture",
  "ux",
  "data",
  "security",
  "quality",
  "operations",
  "aiOrchestration",
  "roadmap",
];

export function describeDraft(draft: ProjectDraft | undefined): string {
  if (draft === undefined) return "No draft yet.";
  const missing = DRAFT_DOMAINS.filter((domain) => draft[domain] !== "sufficient");
  if (missing.length === 0) return "Every domain is sufficient; the draft can be finalized.";
  return `${missing.length} of ${DRAFT_DOMAINS.length} domains still need work: ${missing.join(", ")}`;
}

function isImagePath(path: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg)$/i.test(path);
}

function referenceFromFile(file: ProjectFileView): MessageReference {
  return {
    path: file.path,
    kind: isImagePath(file.path) ? "image" : "file",
    label: file.path.split("/").pop() ?? file.path,
    mimeType: null,
  };
}

export const DiscussScreen: FC = () => {
  const sessions = useAsync(() => api.discussions(), []);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [draftText, setDraftText] = useState("");
  const [references, setReferences] = useState<MessageReference[]>([]);
  const [referencePickerOpen, setReferencePickerOpen] = useState(false);
  const [referenceQuery, setReferenceQuery] = useState("");
  const [contextOpen, setContextOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [live, setLive] = useState<AgUiMessage[]>([]);
  const feedRef = useRef<HTMLDivElement | null>(null);

  const session = useAsync(
    async () => (sessionId ? await api.discussion(sessionId) : null),
    [sessionId, reload],
  );
  const files = useAsync(
    () => (sessionId ? api.projectFiles() : Promise.resolve([] as ProjectFileView[])),
    [sessionId],
  );

  useEffect(() => {
    if (sessionId === null && sessions.data && sessions.data.length > 0) {
      setSessionId(sessions.data[0]);
    }
  }, [sessions.data, sessionId]);

  useEffect(() => {
    if (sessionId === null) return;
    const client = new AgUiClient();
    client.onStatus(setConnected);
    client.onMessage((message) => setLive((current) => [...current, message]));
    let dropped = false;
    void socketUrl().then((url) => {
      if (!dropped) client.connect(sessionId, url);
    });
    return () => {
      dropped = true;
      client.disconnect();
      setConnected(false);
    };
  }, [sessionId]);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [session.data, live]);

  const act = useCallback(async (work: () => Promise<unknown>) => {
    try {
      await work();
      setError(null);
      setReload((value) => value + 1);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  const start = () =>
    void act(async () => {
      const created = await api.createDiscussion();
      setSessionId(created.sessionId);
      setReferences([]);
      sessions.reload();
    });

  const send = () => {
    const content = draftText.trim();
    if (!content || sessionId === null) return;
    const attached = [...references];
    setDraftText("");
    setReferences([]);
    void act(() => api.sendMessage(sessionId, content, attached));
  };

  const propose = () => {
    const content = draftText.trim();
    if (!content || sessionId === null) return;
    setDraftText("");
    setReferences([]);
    void act(() => api.proposeDecision(sessionId, content, content));
  };

  const filteredFiles = useMemo(() => {
    const query = referenceQuery.trim().toLowerCase();
    const availableFiles = Array.isArray(files.data) ? files.data : [];
    return availableFiles
      .filter((file) => file.path.toLowerCase().includes(query))
      .slice(0, 40);
  }, [files.data, referenceQuery]);

  const toggleReference = (file: ProjectFileView) => {
    const reference = referenceFromFile(file);
    setReferences((current) =>
      current.some((item) => item.path === reference.path)
        ? current.filter((item) => item.path !== reference.path)
        : [...current, reference],
    );
  };

  return (
    <div className="chat-shell">
      <header className="chat-header">
        <div className="chat-title">
          <MessageSquare size={15} strokeWidth={1.7} aria-hidden="true" />
          <h2>{session.data?.title || "Project conversation"}</h2>
        </div>
        <div className="chat-header__actions">
          <span className="connection-state" data-state={connected ? "connected" : "offline"}>
            <span aria-hidden="true" /> {connected ? "Live" : "Offline"}
          </span>
          <button
            type="button"
            className="icon-button"
            aria-label={contextOpen ? "Hide discussion context" : "Show discussion context"}
            aria-expanded={contextOpen}
            title={contextOpen ? "Hide discussion context" : "Show discussion context"}
            onClick={() => setContextOpen((value) => !value)}
          >
            {contextOpen ? <PanelRightClose size={16} strokeWidth={1.7} aria-hidden="true" /> : <PanelRight size={16} strokeWidth={1.7} aria-hidden="true" />}
          </button>
          <button type="button" className="button button--secondary button--icon" aria-label="New chat" title="New chat" onClick={start}>
            <Plus size={15} strokeWidth={1.7} aria-hidden="true" />
          </button>
        </div>
      </header>

      <AsyncPanel
        loading={sessions.loading}
        error={sessions.error}
        onRetry={sessions.reload}
        isEmpty={sessionId === null && (sessions.data?.length ?? 0) === 0}
        emptyMessage="Start a conversation to shape the next piece of work."
      >
        {sessionId !== null && (
          <AsyncPanel loading={session.loading && !session.data} error={session.error} onRetry={session.reload}>
            {session.data && (
              <div className={`chat-layout${contextOpen ? " chat-layout--context" : ""}`}>
                <section className="chat-main" aria-label="Conversation">
                  <ConversationFeed session={session.data} feedRef={feedRef} />
                  <ChatComposer
                    value={draftText}
                    references={references}
                    pickerOpen={referencePickerOpen}
                    referenceQuery={referenceQuery}
                    files={filteredFiles}
                    filesLoading={files.loading}
                    onChange={setDraftText}
                    onSend={send}
                    onPropose={propose}
                    onTogglePicker={() => setReferencePickerOpen((value) => !value)}
                    onQueryChange={setReferenceQuery}
                    onToggleReference={toggleReference}
                    onRemoveReference={(path) => setReferences((current) => current.filter((item) => item.path !== path))}
                  />
                </section>
                {contextOpen && (
                  <DiscussionContext
                    session={session.data}
                    onAccept={(decisionId) => void act(() => api.acceptDecision(session.data!.id, decisionId))}
                  />
                )}
              </div>
            )}
          </AsyncPanel>
        )}
      </AsyncPanel>

      {error && <p className="chat-error" role="alert">{error}</p>}
    </div>
  );
};

const ConversationFeed: FC<{
  session: DiscussionSession;
  feedRef: RefObject<HTMLDivElement | null>;
}> = ({ session, feedRef }) => (
  <div ref={feedRef} className="chat-feed" role="log" aria-live="polite" aria-label="Conversation messages">
    {session.messages.length === 0 ? (
      <div className="chat-empty">
        <div className="chat-empty__icon" aria-hidden="true"><Sparkles size={18} strokeWidth={1.6} /></div>
        <h2>Start a conversation</h2>
        <p>Define intent, ask a question, or attach a project reference.</p>
      </div>
    ) : (
      session.messages.map((message) => (
        <article key={message.id} className={`chat-message chat-message--${message.turnType === "message" ? "user" : "system"}`}>
          <div className="chat-message__meta">
            <strong>{message.turnType === "message" ? "You" : "Atlas"}</strong>
            <time dateTime={message.timestamp}>{formatTime(message.timestamp)}</time>
          </div>
          <div className="chat-message__bubble">
            <p>{message.content}</p>
            {message.references?.length > 0 && <ReferenceList references={message.references} />}
          </div>
        </article>
      ))
    )}
  </div>
);

const ChatComposer: FC<{
  value: string;
  references: MessageReference[];
  pickerOpen: boolean;
  referenceQuery: string;
  files: ProjectFileView[];
  filesLoading: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onPropose: () => void;
  onTogglePicker: () => void;
  onQueryChange: (value: string) => void;
  onToggleReference: (file: ProjectFileView) => void;
  onRemoveReference: (path: string) => void;
}> = ({
  value,
  references,
  pickerOpen,
  referenceQuery,
  files,
  filesLoading,
  onChange,
  onSend,
  onPropose,
  onTogglePicker,
  onQueryChange,
  onToggleReference,
  onRemoveReference,
}) => (
  <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); onSend(); }}>
    {references.length > 0 && (
      <div className="reference-strip" aria-label="Attached references">
        {references.map((reference) => (
          <ReferenceChip key={reference.path} reference={reference} onRemove={() => onRemoveReference(reference.path)} />
        ))}
      </div>
    )}

    {pickerOpen && (
      <div className="reference-picker" role="dialog" aria-label="Add project reference">
        <div className="reference-picker__header">
          <strong>Project references</strong>
          <button type="button" className="icon-button" aria-label="Close reference picker" onClick={onTogglePicker}><X size={16} /></button>
        </div>
        <input
          aria-label="Search project files"
          value={referenceQuery}
          placeholder="Search files and images…"
          onChange={(event) => onQueryChange(event.target.value)}
        />
        <div className="reference-picker__list">
          {filesLoading ? <span className="text-muted">Loading project files…</span> : files.map((file) => {
            const selected = references.some((reference) => reference.path === file.path);
            return (
              <button type="button" key={file.path} className="reference-option" data-selected={selected} onClick={() => onToggleReference(file)}>
                {isImagePath(file.path) ? <ImageIcon size={15} aria-hidden="true" /> : <FileText size={15} aria-hidden="true" />}
                <code>{file.path}</code>
                {selected && <Check size={15} aria-label="Selected" />}
              </button>
            );
          })}
          {!filesLoading && files.length === 0 && <span className="text-muted">No matching project files.</span>}
        </div>
      </div>
    )}

    <div className="chat-composer__input-row">
      <button type="button" className="icon-button" aria-label="Add file or image reference" title="Add file or image reference" onClick={onTogglePicker}>
        <Paperclip size={16} strokeWidth={1.7} />
      </button>
      <textarea
        aria-label="Message"
        rows={1}
        value={value}
        placeholder="Ask Atlas anything about this project…"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSend();
          }
        }}
      />
      <button type="submit" className="send-button" disabled={!value.trim()} aria-label="Send message" title="Send message">
        <Send size={15} strokeWidth={1.7} aria-hidden="true" />
      </button>
    </div>
    <div className="chat-composer__footer">
      <span>Shift + Enter for a new line</span>
      <button type="button" className="composer-link" disabled={!value.trim()} onClick={onPropose}>Turn into decision</button>
    </div>
  </form>
);

const DiscussionContext: FC<{
  session: DiscussionSession;
  onAccept: (decisionId: string) => void;
}> = ({ session, onAccept }) => (
  <aside className="chat-context" aria-label="Discussion context">
    <section className="context-card">
      <div className="context-card__title"><span>Draft</span><StatusBadge value={session.draft ? "ACTIVE" : "PENDING"} /></div>
      <strong>{draftProgressLabel(session.draft)}</strong>
      <div className="draft-meter" aria-hidden="true"><span style={{ width: `${draftProgress(session.draft)}%` }} /></div>
    </section>

    <section className="context-card context-card--decisions">
      <div className="context-card__title"><span>Decisions</span><span className="context-count">{session.decisions.length}</span></div>
      {session.decisions.length === 0 ? (
        <p className="text-muted">No decisions yet.</p>
      ) : (
        <ul>
          {session.decisions.map((decision) => <DecisionRow key={decision.id} decision={decision} onAccept={onAccept} />)}
        </ul>
      )}
    </section>
  </aside>
);

const DecisionRow: FC<{ decision: DecisionCandidate; onAccept: (id: string) => void }> = ({ decision, onAccept }) => (
  <li>
    <div className="decision-row__header"><StatusBadge value={decision.status.toUpperCase()} /><strong>{decision.title}</strong></div>
    <p>{decision.statement}</p>
    {isPending(decision) && <button type="button" className="button button--secondary button--small" onClick={() => onAccept(decision.id)}>Accept</button>}
  </li>
);

const ReferenceList: FC<{ references: MessageReference[] }> = ({ references }) => (
  <div className="message-references" aria-label="Message references">
    {references.map((reference) => <ReferenceChip key={reference.path} reference={reference} />)}
  </div>
);

const ReferenceChip: FC<{ reference: MessageReference; onRemove?: () => void }> = ({ reference, onRemove }) => (
  <span className="reference-chip">
    {reference.kind === "image" ? <ImageIcon size={14} aria-hidden="true" /> : <FileText size={14} aria-hidden="true" />}
    <code>{reference.label || reference.path}</code>
    {onRemove && <button type="button" className="reference-chip__remove" aria-label={`Remove ${reference.label || reference.path}`} onClick={onRemove}><X size={13} /></button>}
  </span>
);

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function draftProgress(draft: ProjectDraft): number {
  const complete = DRAFT_DOMAINS.filter((domain) => draft[domain] === "sufficient").length;
  return Math.round((complete / DRAFT_DOMAINS.length) * 100);
}

function draftProgressLabel(draft: ProjectDraft): string {
  const complete = DRAFT_DOMAINS.filter((domain) => draft[domain] === "sufficient").length;
  if (complete === DRAFT_DOMAINS.length) return "Draft ready to finalize.";
  return `${complete}/${DRAFT_DOMAINS.length} areas covered`;
}

/** Only a proposal can be accepted; anything else already has an answer. */
export function isPending(decision: DecisionCandidate): boolean {
  return decision.status.toUpperCase() === "PROPOSED";
}
