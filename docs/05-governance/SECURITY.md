# Security Governance

Trust boundaries: user/desktop, desktop/backend, backend/runner, runner/provider, agent/MCP, workspace/untrusted repository.

Principles: least privilege, explicit destructive permissions, secrets outside Git, local-first retention, audit important actions, sanitize untrusted output, deterministic mutation-boundary hooks, no automatic remote sharing.

Security boundary changes require ADR + security review.
