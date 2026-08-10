# Command Code Development Integration

Command Code is the development harness.

Project surfaces: root `AGENTS.md`, `.commandcode/AGENTS.md`, `.commandcode/agents/`, `.commandcode/skills/`.

Commands:
- interactive: `cmd`
- plan: `cmd --plan`
- headless: `cmd --print "<task>" --max-turns <n> --model <id>`
- discovery: `cmd --list-models`

Custom Agent files do not encode model routing. Project Atlas model policy selects a model; execution uses `--model` or `/model`.

Safety: standard/plan by default; auto-accept only in isolated trusted scope; `--yolo` not default; deterministic hooks for dangerous actions.

Project Skills are Git-tracked. MCP only where required.
