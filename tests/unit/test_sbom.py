"""P10 release artefacts: the SBOM describes the release, not the machine."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "generate_sbom", ROOT / "scripts" / "generate_sbom.py"
)
assert _spec is not None and _spec.loader is not None
sbom_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sbom_module)


class TestLockfileReading:
    def test_python_packages_come_from_the_lockfile(self, tmp_path: Path) -> None:
        lock = tmp_path / "uv.lock"
        lock.write_text(
            '[[package]]\nname = "aiosqlite"\nversion = "0.21.0"\n',
            encoding="utf-8",
        )

        components = sbom_module.python_components(lock)

        assert components == [
            {
                "type": "library",
                "name": "aiosqlite",
                "version": "0.21.0",
                "purl": "pkg:pypi/aiosqlite@0.21.0",
            }
        ]

    def test_rust_packages_carry_their_registry_checksum(self, tmp_path: Path) -> None:
        lock = tmp_path / "Cargo.lock"
        lock.write_text(
            '[[package]]\nname = "serde"\nversion = "1.0.229"\nchecksum = "abc123"\n',
            encoding="utf-8",
        )

        component = sbom_module.rust_components(lock)[0]

        assert component["purl"] == "pkg:cargo/serde@1.0.229"
        assert component["hashes"] == [{"alg": "SHA-256", "content": "abc123"}]

    def test_node_packages_survive_the_blank_lines_between_them(
        self, tmp_path: Path
    ) -> None:
        """pnpm separates entries with blank lines; they do not end the section."""
        lock = tmp_path / "pnpm-lock.yaml"
        lock.write_text(
            "lockfileVersion: '9.0'\n\n"
            "importers:\n"
            "  .:\n"
            "    devDependencies: {}\n\n"
            "packages:\n\n"
            "  '@babel/core@7.29.7':\n"
            "    resolution: {integrity: sha512-x}\n\n"
            "  vite@7.3.6:\n"
            "    resolution: {integrity: sha512-y}\n\n"
            "snapshots:\n\n"
            "  '@babel/core@7.29.7': {}\n",
            encoding="utf-8",
        )

        components = sbom_module.node_components(lock)

        assert [c["purl"] for c in components] == [
            "pkg:npm/@babel/core@7.29.7",
            "pkg:npm/vite@7.3.6",
        ]

    def test_the_snapshots_section_is_not_mistaken_for_packages(
        self, tmp_path: Path
    ) -> None:
        lock = tmp_path / "pnpm-lock.yaml"
        lock.write_text("snapshots:\n\n  ghost@1.0.0: {}\n", encoding="utf-8")

        assert sbom_module.node_components(lock) == []

    def test_a_missing_lockfile_contributes_nothing_rather_than_failing(
        self, tmp_path: Path
    ) -> None:
        absent = tmp_path / "nothing.lock"

        assert sbom_module.python_components(absent) == []
        assert sbom_module.rust_components(absent) == []
        assert sbom_module.node_components(absent) == []


class TestDocument:
    def test_the_real_lockfiles_produce_a_document_covering_all_three_ecosystems(
        self,
    ) -> None:
        document = sbom_module.build_sbom()

        assert document["bomFormat"] == "CycloneDX"
        assert document["specVersion"] == "1.5"
        assert document["metadata"]["component"]["name"] == "atlas-flow"

        ecosystems = {c["purl"].split("/")[0] for c in document["components"]}
        assert ecosystems == {"pkg:pypi", "pkg:npm", "pkg:cargo"}

    def test_components_are_ordered_so_two_runs_are_comparable(self) -> None:
        """A diffable SBOM is what makes a dependency change visible."""
        purls = [c["purl"] for c in sbom_module.build_sbom()["components"]]

        assert purls == sorted(purls)

    def test_every_component_is_serializable_and_identified(self) -> None:
        document = sbom_module.build_sbom()
        json.dumps(document)

        for component in document["components"]:
            assert component["name"]
            assert component["version"], component["name"]
            assert component["purl"].startswith("pkg:")


def test_writing_the_sbom_reports_what_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "nested" / "sbom.json"
    monkeypatch.setattr("sys.argv", ["generate_sbom.py", str(target)])

    assert sbom_module.main() == 0

    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["components"]
    output = capsys.readouterr().out
    assert "sha256:" in output
    assert f"components: {len(written['components'])}" in output
