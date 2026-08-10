"""Project Atlas bootstrap smoke tests against the real repository manifest."""

from pathlib import Path

from atlas_flow.bootstrap import detect_framework, load_project_manifest

ROOT = Path(__file__).resolve().parents[2]


def test_manifest_contains_project_identity() -> None:
    manifest = load_project_manifest(ROOT)
    project = manifest["project"]
    assert isinstance(project, dict)
    assert project["id"] == "atlas-flow"


def test_detect_framework_matches_project_atlas() -> None:
    info = detect_framework(ROOT)
    assert info.name == "project-atlas-framework"
    assert info.version == "0.1.0"
    assert info.entrypoint == "ENTRYPOINT.md"
