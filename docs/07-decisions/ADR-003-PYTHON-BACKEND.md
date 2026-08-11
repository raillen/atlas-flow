# ADR-003 — Python orchestration backend

**Status:** Superseded by [ADR-017](ADR-017-DOTNET-RUNTIME.md) · 2026-08-11

Use Python to reuse Project Atlas implementation and ACP Python ecosystem. Frontend remains TypeScript/React.

---

## Why this record is not edited

The decision above is left exactly as it was written. An ADR is a record of what
was decided and why, at a time, with the information available then — editing
the body to match a later decision destroys the only thing the document is for.

What is worth adding is why the stated reason did not hold. The decision rested
on reusing "the ACP Python ecosystem". By 2026-08-11 the backend's entire
third-party surface was four packages — `fastapi`, `pydantic`, `aiosqlite`,
`pyyaml` — and the ACP client was 196 lines of hand-written JSON-RPC over child
stdio. No Python-specific ecosystem was ever depended on, which is what made
[ADR-017](ADR-017-DOTNET-RUNTIME.md) cheap enough to consider.
