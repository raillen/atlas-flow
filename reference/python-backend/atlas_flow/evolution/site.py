"""Small static documentation builder with visibility-safe search."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas_flow.evolution.documents import (
    discover_documents,
    freshness_of,
    load_manifest,
    resolve_project_path,
)

_VISIBILITY_RANK = {"public": 0, "internal": 1, "private": 2}
_MARKER = ".atlas-flow-site.json"


@dataclass(frozen=True)
class SiteBuildResult:
    output: Path
    visibility: str
    pages: list[str]
    search_index: str


def _visible(document_visibility: str, requested_visibility: str) -> bool:
    return _VISIBILITY_RANK[document_visibility] <= _VISIBILITY_RANK[requested_visibility]


def _page_html(title: str, body: str, navigation: list[tuple[str, str]]) -> str:
    links = "\n".join(
        f'<li><a href="{html.escape(path)}">{html.escape(label)}</a></li>'
        for path, label in navigation
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title></head>
<body><nav><ul>{links}</ul></nav><main><h1>{html.escape(title)}</h1>
<pre>{html.escape(body)}</pre></main></body></html>
"""


def _prepare_output(output: Path) -> None:
    if not output.exists():
        output.mkdir(parents=True)
        return
    marker_path = output / _MARKER
    if not marker_path.is_file():
        if any(output.iterdir()):
            raise ValueError(
                f"refusing to write documentation site into non-generated directory: {output}"
            )
        return
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    for relative in marker.get("files", []):
        target = output / str(relative)
        if target.is_file() or target.is_symlink():
            target.unlink()
    marker_path.unlink(missing_ok=True)


def build_site(
    root: Path, output: Path | None = None, visibility: str = "internal"
) -> SiteBuildResult:
    """Build only documents permitted by the requested visibility."""

    if visibility not in _VISIBILITY_RANK:
        raise ValueError(f"unknown documentation visibility '{visibility}'")
    manifest, _ = load_manifest(root)
    documents = [
        document
        for document in discover_documents(root, manifest)
        if _visible(document.metadata.visibility, visibility)
    ]
    target = output or resolve_project_path(root, manifest.atlas.data_root, "data_root") / "site"
    _prepare_output(target)
    page_specs = [
        (document, f"{document.relative_path.removesuffix('.md')}.html") for document in documents
    ]
    navigation = [(path, document.metadata.title) for document, path in page_specs]
    files: list[str] = []
    for document, page_path in page_specs:
        target_path = target / page_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            _page_html(document.metadata.title, document.body, navigation), encoding="utf-8"
        )
        files.append(page_path)
    search = [
        {
            "id": document.metadata.id,
            "title": document.metadata.title,
            "path": page_path,
            "section": document.metadata.section,
            "tags": document.metadata.tags,
        }
        for document, page_path in page_specs
    ]
    (target / "search.json").write_text(
        json.dumps(search, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files.append("search.json")
    index = _page_html(
        f"{manifest.documentation.title} — Documentation",
        "Generated documentation index",
        navigation,
    )
    (target / "index.html").write_text(index, encoding="utf-8")
    files.append("index.html")
    marker = {"files": sorted(files), "visibility": visibility, "schema_version": 1}
    (target / _MARKER).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return SiteBuildResult(target, visibility, sorted(files), "search.json")


def freshness_report(root: Path) -> list[dict[str, str]]:
    manifest, _ = load_manifest(root)
    return [
        {
            "id": document.metadata.id,
            "path": document.relative_path,
            "status": freshness_of(document.metadata),
        }
        for document in discover_documents(root, manifest)
    ]


def documentation_coverage(root: Path) -> dict[str, Any]:
    manifest, _ = load_manifest(root)
    documents = discover_documents(root, manifest)
    by_section: dict[str, dict[str, int]] = {}
    for document in documents:
        section = document.metadata.section or "root"
        bucket = by_section.setdefault(section, {"total": 0, "versioned": 0})
        bucket["total"] += 1
        bucket["versioned"] += int(document.has_front_matter)
    total = len(documents)
    versioned = sum(int(document.has_front_matter) for document in documents)
    return {
        "documents": total,
        "versioned": versioned,
        "coverage": versioned / total if total else None,
        "by_section": by_section,
    }
