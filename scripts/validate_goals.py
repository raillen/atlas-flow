import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
errors = []
ids = set()

required = {
    "id", "phase", "title", "state", "objective",
    "constraints", "acceptance", "gates", "dependencies", "evidence",
}
for path in root.glob(".ai/goals/*/*.yaml"):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = required - set(data or {})
    if missing:
        errors.append(f"{path}: missing {sorted(missing)}")
        continue
    if data["id"] in ids:
        errors.append(f"duplicate Goal id: {data['id']}")
    ids.add(data["id"])
    if not data["acceptance"]:
        errors.append(f"{data['id']}: acceptance must not be empty")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"Goal validation: PASS ({len(ids)} goals)")
