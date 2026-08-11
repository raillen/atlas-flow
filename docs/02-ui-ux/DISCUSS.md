# Discuss UX

Default: `Project Topics | Conversation | Project Draft`.

Conversation streams chat and explicit decision proposals.
Topics show completeness/open questions.
Draft is structured preview, not raw Markdown.

Decision actions: Accept, Edit, Reject, Defer.

Finalize shows readiness, blocking missing decisions and assumptions; user resolves or explicitly finalizes with documented assumptions.

## What the screen actually does

Until 2026-08-11 it did not talk to the backend at all. It opened a WebSocket,
echoed what you typed back at you, and lost it: the Decision Ledger existed and
was tested, and the screen in front of it wrote to nothing.

It now uses the discussion API. A session is created or resumed through
`/api/discussions`, messages are posted and come back stored, decisions are
proposed and accepted against the real ledger, and the socket is kept for what
it is good at — live updates from elsewhere — rather than as the only channel.

The Project Draft is summarised as a sentence naming the domains still short of
`sufficient`. Finalization writes ADRs into `docs/` and the backend refuses
while any domain is incomplete; a button that fails without saying which domain
looks broken.
