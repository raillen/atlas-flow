# Dependency Policy

Atlas Flow follows Project Atlas ADR-001: the framework and runtime are separate
products. This dependency policy keeps both separable.

## Principles

- **Lockfiles tracked in Git.** `pnpm-lock.yaml` and `backend/uv.lock` are
  canonical. Cargo.lock for Tauri is tracked.
- **Pinned ranges.** Semver major ranges in manifests (`>=X,<Y` for pip;
  `catalog:` for pnpm; `{ version = "X" }` with minor range for Cargo).
- **Renovate/dependabot keeps things current.** Weekly grouped updates. Automerge
  only allowed for dev-dependency patch bumps when CI is green.
- **Framework vs runtime separation.** Project Atlas Framework packages are
  consumed as protocol dependencies, never vendored. Atlas Flow owns its own
  implementation and dependencies.
- **Provider independence.** No LLM provider SDKs in core packages. Model routing
  is runtime-discovered via Command Code / ACP.
- **MCP only where required.** MCP client/server deps are added by protocol
  engineering Goals, not the foundation.
- **Security audits.** Lockfile changes trigger SBOM diff and license check in CI.

## Adding a dependency

1. Justify in the Goal/ADR that introduces it.
2. Prefer well-maintained packages with compatible licenses (MIT, Apache 2.0).
3. Pin the major version range.
4. Run lock and verify CI passes before merging.
