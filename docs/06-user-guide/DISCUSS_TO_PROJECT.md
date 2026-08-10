# From Discussion to Project

## The Discuss Mode

Discuss is a structured project-definition environment, not a generic chat.
Each turn can produce:
- **Messages** — conversation turns
- **Decision candidates** — PROPOSED decisions with rationale and domain impacts
- **Open questions** — unresolved items for the user
- **Constraints** — hard boundaries
- **Project Draft** — 9-domain completeness tracker

## Decision Ledger

Decisions follow a lifecycle:
```
PROPOSED → ACCEPTED / REJECTED
ACCEPTED → SUPERSEDED (by newer decision)
```

Accepted decisions with `requires_adr: true` generate ADR stubs on finalization.
Rejected decisions are kept for searchability but have no authority.
Later choices supersede — they do not silently overwrite.

## Finalization Pipeline

1. **Gap analysis** — which domains are incomplete?
2. **Resolution** — user accepts assumptions or fills gaps
3. **Generation** — ADR stubs and canonical artifact stubs
4. **Validation** — Project Atlas conformance check
5. **Commit** — write canonical artifacts to Git

Never implement finalization as a single "summarize chat" call.
