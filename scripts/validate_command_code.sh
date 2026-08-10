#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

# Verify command code is available
if ! command -v cmd >/dev/null 2>&1; then
  echo "FAIL: Command Code (cmd) not found in PATH." >&2
  exit 1
fi

echo "=== Command Code model discovery ==="
MODELS="$(cmd --list-models)" || { echo "FAIL: cmd --list-models failed" >&2; exit 1; }

# Check that required roster is discoverable (model-policy.yaml)
check_model() {
  model_pattern="$1"
  if printf '%s\n' "$MODELS" | grep -qi "$model_pattern"; then
    echo "  ✓ $model_pattern"
  else
    echo "  ✗ $model_pattern not exposed by current registry" >&2
    FAILED=1
  fi
}

check_model 'deepseek-v4-pro'
check_model 'mimo-v2.5-pro'

echo "=== Custom agents ==="
agent_dir="$ROOT/.commandcode/agents"
for agent in "$agent_dir"/*.md; do
  [ -f "$agent" ] || continue
  agent_name="$(basename "$agent" .md)"
  echo "  ✓ $agent_name"
done
AGENT_COUNT="$(find "$agent_dir" -maxdepth 1 -name '*.md' | wc -l)"
echo "  Total custom agents: $AGENT_COUNT"

echo "=== Project skills ==="
skill_dir="$ROOT/.commandcode/skills"
for skill in "$skill_dir"/*/SKILL.md; do
  [ -f "$skill" ] || continue
  skill_name="$(basename "$(dirname "$skill")")"
  echo "  ✓ $skill_name"
done
SKILL_COUNT="$(find "$skill_dir" -maxdepth 2 -name 'SKILL.md' | wc -l)"
echo "  Total project skills: $SKILL_COUNT"

echo "=== Project Atlas validation ==="
python3 "$ROOT/scripts/validate_docs.py" || { echo "FAIL: docs validation" >&2; FAILED=1; }
python3 "$ROOT/scripts/validate_goals.py" || { echo "FAIL: goals validation" >&2; FAILED=1; }

if [ "$FAILED" -eq 0 ]; then
  echo "Command Code discoverability: PASS"
  echo "  agents=$AGENT_COUNT skills=$SKILL_COUNT"
  echo "Project Atlas validation: PASS"
else
  echo "Validation FAILED" >&2
  exit 1
fi
