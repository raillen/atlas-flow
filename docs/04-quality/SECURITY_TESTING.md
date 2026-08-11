# Security Testing

Threats: prompt and tool injection, malicious repository content, path
traversal, secret leakage, MCP trust, permission bypass, destructive Git,
supply chain.

## What is enforced, and where

Each control lives at one choke point, so there is one place to get right and
one place to test.

| Control | Choke point | Tests |
| --- | --- | --- |
| Path traversal | `SecurityGuard.validate_path`, used by `GET /api/docs/{path}` | `test_api.py`, `test_faults_security.py` |
| Secret leakage | `SecurityGuard.redact_secrets`, applied to every `RunnerResult` and every normalized ACP update | `test_faults_security.py`, `test_acp_events.py` |
| Destructive Git | `SecurityGuard.validate_git_command`, called by `run_git` — the single entry point for every git call in the runtime | `test_faults_security.py` |
| Permission bypass | ACP `session/request_permission`, denied by default | `test_acp.py` |
| MCP trust | `McpRegistry`: explicit servers, role allowlists, read-only planning roles, refused literal secrets | `test_mcp.py` |
| Malformed protocol payloads | Non-JSON stdout lines skipped; unknown `session/update` kinds dropped | `test_acp.py`, `test_acp_events.py` |
| Fault tolerance | Real runs driven through timeout, process kill, malformed output, disconnect, conflict and interrupted-process recovery | `test_fault_injection.py` |

## Findings closed in this pass

1. **Redaction was never invoked.** `redact_secrets` existed and no caller used
   it, so agent output reached transcripts, attempt errors and the event stream
   unfiltered. Now applied at the runner boundary, with patterns for bare
   credentials that arrive without a `token:` label.
2. **Custom redaction patterns replaced the defaults.** Declaring one project
   pattern silently disabled every built-in one. They are additive now.
3. **The desktop shell had no Content Security Policy** (`csp: null`). It now
   declares `default-src 'self'` with `connect-src` limited to IPC and the
   backend on localhost.
4. **`validate_git_command` forbade `commit` and `merge`** — the two operations
   the runtime exists to perform — and was never wired in, so it protected
   nothing while being wrong. It now refuses publishing, history rewriting and
   discarding uncommitted work, and every git call passes through it.
5. **`sanitize_shell_arg` and `validate_model_output_for_ui` were removed.** The
   CLI runner passes arguments as argv, never through a shell, and React
   escapes its own output; applying either would have corrupted prompts and
   double-escaped transcripts while looking like protection.

## Dependency auditing

`sh scripts/audit_dependencies.sh` checks all three ecosystems against their own
advisory databases — pip-audit, `pnpm audit`, `cargo audit` — and is what CI
runs, so a reviewer can reproduce the result instead of taking CI's word for it.

Being unable to reach a database is reported as a **failure**, not skipped:
"I could not check" and "there is nothing to find" are different answers, and
only one of them is evidence.

Adding it found **PYSEC-2026-1845** in pytest 8.4.2 on the first run; the
project is on pytest 9.x.

Current result: no vulnerabilities in any ecosystem, and **17 unmaintained-crate
warnings** from Rust — the gtk-rs GTK3 bindings that Tauri 2 pulls in
transitively. `cargo audit` exits zero for those, so the script counts and
reports them rather than letting a zero exit code imply there was nothing to
say. Nothing can be done about them from this repository; they move when Tauri
moves.

## Release integrity

`SHA256SUMS` covers the `.deb`, the AppImage and the SBOM, and is signed with a
detached GPG signature by the project key `C4ECF972E0FFC81D`, whose public half
is committed at `docs/09-references/RELEASE_SIGNING_KEY.asc`. The signature is
over the digest list rather than each artefact — that is what a verifier
checks, and it cannot be sidestepped by swapping a file the list already names.
The packaging script verifies its own signature before reporting success, and
prints `unsigned` when no key is configured rather than staying quiet about it.

## Not yet covered

- No fuzzing of the ACP wire format beyond the malformed cases in the fixture
  agent.
- The signing key has no passphrase, so it is usable unattended and anyone who
  can read the maintainer's home directory can sign as the project. A deliberate
  trade, recorded rather than hidden.
- No independent security review, as opposed to the code review.
- The AG-UI WebSocket is unauthenticated. The backend binds localhost, so the
  boundary is the machine: any local process can subscribe to run events.
