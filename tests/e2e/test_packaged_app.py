"""Drive the packaged application the way a person does.

Every other gate inspects an artefact: the bundle contains the right files, the
crate compiles, the endpoints answer. Three defects shipped anyway, and all
three were found by launching the AppImage and pressing a button.

Those three are now covered deterministically by the shell's own unit tests,
which is where the defects were. This file covers what those cannot: that the
pieces are wired together in a real window, on a real display, from a real
bundle.

**This is a smoke test, not a gate.** It drives a webview through synthetic
input, so it is slower and more environment-dependent than anything in the gate
suite, and it is not run by `scripts/run_gates.sh`. Run it deliberately:

    sh scripts/package_smoke.sh && sh scripts/e2e_packaged.sh

The UI is driven by keyboard rather than by clicking coordinates. Coordinates
move when a panel above them changes height — the first version of this test
guessed three heights and still missed — while the tab order is part of the
accessibility contract the app already promises and tests.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from fixtures.atlas_project import CLI_TOOL, write_project  # noqa: E402

PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"
ARTEFACTS = Path(os.environ.get("ATLAS_E2E_ARTEFACTS", "/tmp/atlas-flow-e2e"))
BACKEND_LOG = Path("/tmp/atlas-flow-backend.log")


def _bundle() -> Path | None:
    target = os.environ.get("CARGO_TARGET_DIR") or str(
        ROOT / "apps" / "desktop" / "src-tauri" / "target"
    )
    found = sorted(Path(target).glob("release/bundle/appimage/*.AppImage"))
    return found[0] if found else None


pytestmark = [
    pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="needs an X display"),
    pytest.mark.skipif(shutil.which("xdotool") is None, reason="needs xdotool"),
    pytest.mark.skipif(_bundle() is None, reason="no AppImage built"),
]


def xdo(*args: str) -> str:
    return subprocess.run(
        ["xdotool", *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def open_windows() -> set[str]:
    return set(xdo("search", "--name", "^Atlas Flow$").splitlines())


def window_id(exclude: set[str], timeout: float = 30.0) -> str:
    """Wait for a window this launch created, not one left over from another.

    Taking the first matching window found a stale instance from an earlier
    session, whose environment was different — so the test read someone else's
    configuration off the screen and reported it as the app ignoring its own.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        fresh = open_windows() - exclude
        if fresh:
            return sorted(fresh)[0]
        time.sleep(0.4)
    raise AssertionError("no new application window appeared")


def screenshot(wid: str, name: str) -> str:
    ARTEFACTS.mkdir(parents=True, exist_ok=True)
    target = ARTEFACTS / f"{name}.png"
    subprocess.run(
        ["import", "-window", wid, str(target)], capture_output=True, check=False
    )
    return str(target)


def get(path: str, timeout: float = 2.0) -> dict | list | None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def wait_for_backend(timeout: float) -> dict | list | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        answer = get("/healthz")
        if answer is not None:
            return answer
        time.sleep(0.5)
    return None


def press_start(wid: str) -> bool:
    """Reach the Project tab and activate Start, entirely by keyboard.

    Keys go through XTEST to the focused window rather than `xdotool
    --window`, which sends an XSendEvent that WebKit ignores — the first
    version of this test pressed keys into a void and reported it as a missing
    backend.

    Arrow keys walk the tablist; Tab then enters the panel. How many Tabs land
    on Start depends on whether the panel above it is showing an error, so each
    Tab is followed by Return and the loop stops when the backend answers.
    Activating a Retry button by mistake costs nothing; guessing a fixed count
    and calling a missed press a failing backend costs the truth.
    """
    xdo("windowactivate", "--sync", wid)
    time.sleep(1.0)
    xdo("key", "Tab")
    time.sleep(0.6)
    for _ in range(3):  # plan -> build -> review -> project
        xdo("key", "Right")
        time.sleep(0.9)
    time.sleep(1.5)

    for _ in range(4):
        xdo("key", "Return")
        if wait_for_backend(6) is not None:
            return True
        xdo("key", "Tab")
        time.sleep(0.5)
    return False


@pytest.fixture
def app(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """The packaged application, launched against a throwaway project."""
    bundle = _bundle()
    assert bundle is not None
    project = write_project(tmp_path / "quill", CLI_TOOL)
    BACKEND_LOG.unlink(missing_ok=True)
    existing = open_windows()

    python = os.environ.get("ATLAS_PYTHON", sys.executable)
    process = subprocess.Popen(
        [str(bundle)],
        env={
            **os.environ,
            "ATLAS_FLOW_PROJECT_ROOT": str(project),
            "ATLAS_FLOW_API": BASE_URL,
            "ATLAS_FLOW_BACKEND_CMD": (
                f"{python} -m uvicorn atlas_flow.api.app:create_app "
                f"--factory --port {PORT} --log-level warning"
            ),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield window_id(existing), project
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        subprocess.run(["pkill", "-f", f"port {PORT}"], check=False)
        time.sleep(1)


def test_the_packaged_app_starts_a_backend_and_serves_the_right_project(
    app: tuple[str, Path],
) -> None:
    """One walk through everything the three shipped defects broke."""
    wid, _ = app
    assert get("/healthz") is None, "something was already listening on the port"

    started = press_start(wid)

    # It reported RUNNING with a dead backend, so the backend must answer.
    assert started, f"backend never came up; see {screenshot(wid, 'no-backend')}"
    health = get("/healthz")
    assert health is not None and health["status"] == "ok"

    # It launched the backend inside its own mount, so the project served must
    # be the one the app was pointed at.
    project = get("/api/project")
    assert isinstance(project, dict), screenshot(wid, "no-project")
    assert project["id"] == CLI_TOOL.project_id

    goals = get("/api/goals")
    assert isinstance(goals, list)
    assert {goal["id"] for goal in goals} == {goal.id for goal in CLI_TOOL.goals}

    # It poisoned the child's environment with its own Python paths, so the
    # log must be free of that complaint.
    if BACKEND_LOG.is_file():
        assert "PYTHONHOME" not in BACKEND_LOG.read_text(
            encoding="utf-8", errors="replace"
        )
