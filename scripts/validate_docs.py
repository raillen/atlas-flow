import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors = []

IGNORE_DIRS = {
    ".git", ".venv", ".mise", ".pyenv", "node_modules",
    "dist", "target", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "coverage",
}

required = [
    "ENTRYPOINT.md", "PROJECT_MANIFEST.yaml", "PROJECT_STATE.md", "docs/ATLAS.md",
    ".ai/orchestration/model-policy.yaml", ".ai/orchestration/role-routing.yaml"
]
for rel in required:
    if not (root / rel).exists():
        errors.append(f"missing required file: {rel}")

link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
for md in root.rglob("*.md"):
    if any(part in IGNORE_DIRS for part in md.parts):
        continue
    text = md.read_text(encoding="utf-8")
    for target in link_re.findall(text):
        if "://" in target or target.startswith("#") or target.startswith("mailto:"):
            continue
        clean = target.split("#",1)[0]
        if not clean:
            continue
        p = (md.parent / clean).resolve()
        if not p.exists():
            errors.append(f"broken link: {md.relative_to(root)} -> {target}")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print("Documentation validation: PASS")
