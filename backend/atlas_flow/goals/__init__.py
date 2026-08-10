"""Atlas Flow goals subsystem — Project Atlas compatibility layer (P01)."""

from atlas_flow.goals.loader import AtlasLoadError, resolve_project, validate_compatibility
from atlas_flow.goals.models import (
    Goal,
    Phase,
    ProjectAtlasContext,
    ProjectProfile,
)

__all__ = [
    "AtlasLoadError",
    "Goal",
    "Phase",
    "ProjectAtlasContext",
    "ProjectProfile",
    "resolve_project",
    "validate_compatibility",
]
