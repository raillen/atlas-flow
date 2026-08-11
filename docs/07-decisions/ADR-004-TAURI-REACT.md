# ADR-004 — Tauri 2 + React desktop

**Status:** Superseded by [ADR-018](ADR-018-AVALONIA-DESKTOP.md) · 2026-08-11

Use Tauri 2 for cross-platform desktop shell and React/TypeScript for UI.

---

## Why this record is not edited

The decision above is left exactly as it was written, for the reason given in
[ADR-003](ADR-003-PYTHON-BACKEND.md).

Worth recording alongside it: this decision was not wrong on its own terms. The
webview is what let the project reach WCAG 2.2 AA with `axe-core` running over
real DOM, and [ADR-018](ADR-018-AVALONIA-DESKTOP.md) gives that up knowingly.
What made the arrangement untenable was the pairing with ADR-003 — the shell
had to spawn a Python process it could not bundle, so the packaged application
required an interpreter to be present on the user's machine.
