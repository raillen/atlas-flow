"""Deterministic registry and knowledge graph projections."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from atlas_flow.evolution.documents import (
    ParsedDocument,
    discover_documents,
    load_manifest,
    resolve_project_path,
)
from atlas_flow.evolution.models import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    ProjectManifest,
    RegistryEntry,
)


def build_registry(documents: list[ParsedDocument]) -> list[RegistryEntry]:
    """Build a stable document registry sorted by path."""

    entries: list[RegistryEntry] = []
    for document in documents:
        metadata = document.metadata
        entries.append(
            RegistryEntry(
                id=metadata.id,
                path=document.relative_path,
                title=metadata.title,
                section=metadata.section or "root",
                category=metadata.category,
                visibility=metadata.visibility,
                authority=metadata.authority,
                status=metadata.status,
                estimated_tokens=metadata.estimated_tokens or 0,
                tags=metadata.tags,
            )
        )
    return sorted(entries, key=lambda entry: (entry.path, entry.id))


def build_graph(documents: list[ParsedDocument]) -> KnowledgeGraph:
    """Build document nodes and explicit metadata relationships."""

    nodes = [
        GraphNode(
            id=document.metadata.id,
            type="document",
            path=document.relative_path,
            title=document.metadata.title,
            visibility=document.metadata.visibility,
        )
        for document in documents
    ]
    known_ids = {node.id for node in nodes}
    edges: list[GraphEdge] = []
    for document in documents:
        metadata = document.metadata
        for target in metadata.related:
            edges.append(GraphEdge(source=metadata.id, relation="related_to", target=target))
        for target in metadata.invariants:
            edges.append(GraphEdge(source=metadata.id, relation="governed_by", target=target))
    # Keep the set deterministic and avoid duplicate edges from repeated metadata.
    unique_edges = sorted(
        {edge.model_dump_json(): edge for edge in edges}.values(),
        key=lambda e: (e.source, e.relation, e.target),
    )
    dangling = sorted({edge.target for edge in unique_edges if edge.target not in known_ids})
    nodes.extend(GraphNode(id=target, type="reference") for target in dangling)
    return KnowledgeGraph(
        nodes=sorted(nodes, key=lambda node: node.id),
        edges=unique_edges,
    )


def load_project_index(
    root: Path,
) -> tuple[ProjectManifest, list[ParsedDocument], list[RegistryEntry], KnowledgeGraph]:
    """Load all v2 projections for a project in one deterministic operation."""

    manifest, _ = load_manifest(root)
    documents = discover_documents(root, manifest)
    registry = build_registry(documents)
    graph = build_graph(documents)
    return manifest, documents, registry, graph


def write_project_index(root: Path) -> list[Path]:
    """Write rebuildable registry and graph projections atomically."""

    manifest, _, registry, graph = load_project_index(root)
    output = resolve_project_path(root, manifest.atlas.data_root, "data_root") / "index"
    output.mkdir(parents=True, exist_ok=True)
    projections = {
        output / "registry.json": {
            "schema_version": 1,
            "entries": [entry.model_dump(mode="json") for entry in registry],
        },
        output / "graph.json": graph.model_dump(mode="json"),
    }
    written: list[Path] = []
    for path, payload in projections.items():
        fd, temporary = tempfile.mkstemp(prefix=f"{path.stem}-", suffix=".json", dir=output)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
            Path(temporary).replace(path)
            written.append(path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    return written


def registry_lookup(registry: list[RegistryEntry]) -> dict[str, RegistryEntry]:
    """Index registry entries by both stable ID and relative path."""

    lookup: dict[str, RegistryEntry] = {}
    for entry in registry:
        lookup[entry.id] = entry
        lookup[entry.path] = entry
    return lookup


def graph_neighbors(graph: KnowledgeGraph, node_id: str) -> set[str]:
    """Return direct graph neighbors for impact/context expansion."""

    neighbors: set[str] = set()
    for edge in graph.edges:
        if edge.source == node_id:
            neighbors.add(edge.target)
        elif edge.target == node_id:
            neighbors.add(edge.source)
    return neighbors


def reverse_path_index(registry: list[RegistryEntry]) -> dict[str, str]:
    """Return a normalized path-to-document ID index."""

    return {Path(entry.path).as_posix(): entry.id for entry in registry}
