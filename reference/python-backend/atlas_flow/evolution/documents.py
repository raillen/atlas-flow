"""Document discovery, metadata parsing and freshness calculations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from atlas_flow.evolution.models import DocumentMetadata, ProjectManifest

_FRONT_MATTER = re.compile(r"\A---\s*\n(?P<header>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)
_INTERVAL = re.compile(r"\A(?P<amount>\d+)\s*(?P<unit>[dwm])\Z", re.IGNORECASE)


class DocumentParseError(ValueError):
    """A document contains malformed or invalid front matter."""


@dataclass(frozen=True)
class ParsedDocument:
    path: Path
    relative_path: str
    metadata: DocumentMetadata
    body: str
    has_front_matter: bool


def load_manifest(root: Path) -> tuple[ProjectManifest, Path | None]:
    """Load the v2 manifest without requiring one for legacy projects."""

    candidates = (root / "atlas.config.yaml", root / "docs" / "_meta" / "project.yaml")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                raise DocumentParseError(f"{path}: manifest must be a YAML mapping")
            manifest = ProjectManifest.model_validate(raw)
            _validate_project_relative_path(manifest.atlas.docs_root, "docs_root")
            _validate_project_relative_path(manifest.atlas.data_root, "data_root")
            return manifest, path
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise DocumentParseError(f"{path}: invalid manifest: {exc}") from exc

    return ProjectManifest(project={"name": root.name}), None


def resolve_project_path(root: Path, relative: str, field_name: str) -> Path:
    """Resolve a manifest path without allowing it to escape the project."""

    _validate_project_relative_path(relative, field_name)
    project_root = root.resolve()
    candidate = (project_root / relative).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise DocumentParseError(f"{field_name} must stay inside the project root") from exc
    return candidate


def _validate_project_relative_path(value: str, field_name: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise DocumentParseError(f"{field_name} must be a relative path inside the project")


def split_front_matter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return YAML front matter and markdown body."""

    match = _FRONT_MATTER.match(text)
    if match is None:
        return None, text
    try:
        header = yaml.safe_load(match.group("header")) or {}
    except yaml.YAMLError as exc:
        raise DocumentParseError(f"invalid YAML front matter: {exc}") from exc
    if not isinstance(header, dict):
        raise DocumentParseError("front matter must be a YAML mapping")
    return header, match.group("body")


def _title_from_body(body: str, path: Path) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def _document_id(relative_path: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", relative_path.removesuffix(".md")).strip("-")
    return f"DOC-{slug.upper()}"


def _section(relative_path: str) -> str:
    parts = Path(relative_path).parts
    if not parts:
        return "root"
    return parts[0]


def _legacy_visibility(
    relative_path: str, manifest: ProjectManifest
) -> Literal["public", "internal", "private"]:
    section = _section(relative_path)
    if section in manifest.publishing.public:
        return "public"
    if section in manifest.publishing.private:
        return "private"
    if section in manifest.publishing.internal:
        return "internal"
    return manifest.documentation.default_visibility


def parse_document(root: Path, path: Path, manifest: ProjectManifest) -> ParsedDocument:
    """Parse one markdown document, deriving metadata for legacy files."""

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DocumentParseError(f"{path}: cannot read document: {exc}") from exc

    relative_path = path.relative_to(root).as_posix()
    raw_metadata, body = split_front_matter(text)
    section = _section(relative_path)
    if raw_metadata is None:
        metadata = DocumentMetadata(
            id=_document_id(relative_path),
            title=_title_from_body(body, path),
            visibility=_legacy_visibility(relative_path, manifest),
            section=section,
            estimated_tokens=max(1, (len(body) + 3) // 4),
        )
        return ParsedDocument(path, relative_path, metadata, body, False)

    raw_metadata.setdefault("title", _title_from_body(body, path))
    raw_metadata.setdefault("id", _document_id(relative_path))
    raw_metadata.setdefault("section", section)
    if "estimated_tokens" not in raw_metadata:
        raw_metadata["estimated_tokens"] = max(1, (len(body) + 3) // 4)
    try:
        metadata = DocumentMetadata.model_validate(raw_metadata)
    except ValidationError as exc:
        raise DocumentParseError(f"{path}: invalid document metadata: {exc}") from exc
    return ParsedDocument(path, relative_path, metadata, body, True)


def discover_documents(root: Path, manifest: ProjectManifest) -> list[ParsedDocument]:
    """Discover markdown docs deterministically, excluding generated state."""

    docs_root = resolve_project_path(root, manifest.atlas.docs_root, "docs_root")
    if not docs_root.is_dir():
        return []
    documents: list[ParsedDocument] = []
    for path in sorted(docs_root.rglob("*.md")):
        if path.is_symlink() or any(
            part in {"node_modules", "build", "dist"} for part in path.parts
        ):
            continue
        documents.append(parse_document(root, path, manifest))
    return documents


def parse_review_interval(value: str) -> timedelta:
    match = _INTERVAL.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid review interval '{value}', expected e.g. 180d")
    amount = int(match.group("amount"))
    unit = match.group("unit").lower()
    days = amount if unit == "d" else amount * (7 if unit == "w" else 30)
    return timedelta(days=days)


def freshness_of(metadata: DocumentMetadata, today: date | None = None) -> str:
    """Return ACTIVE, NEEDS REVIEW or STALE from metadata only.

    Change-aware stale detection is performed by the graph/impact layer. A
    document without a review date remains active until a project adopts v2
    metadata, which keeps legacy projects usable during migration.
    """

    if metadata.status in {"deprecated", "archived"}:
        return metadata.status.upper()
    if metadata.last_reviewed is None:
        return "ACTIVE"
    current = today or date.today()
    try:
        due = metadata.last_reviewed + parse_review_interval(metadata.review_interval)
    except ValueError:
        return "NEEDS REVIEW"
    return "NEEDS REVIEW" if current > due else "ACTIVE"
