"""Runtime model discovery through Command Code (P08).

The model policy states it plainly: runtime availability beats static
assumptions. The roster in the policy file says which models Atlas Flow would
*like* to use; only the live registry says which ones it can actually reach, so
routing asks rather than assumes.

Models are reached through the Command Code harness (ADR-012), not through a
provider SDK, which is what keeps the runtime provider-agnostic.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from atlas_flow.routing.router import ModelRouter

DISCOVERY_COMMAND = ("cmd", "--list-models")

# Registry lines look like "  deepseek/deepseek-v4-pro (default)" or
# "* gpt-5.6-luna". Bullets, asterisks, and annotations are stripped so the
# identifier alone is compared against the roster.
_LINE = re.compile(r"^[\s*\-•]*([A-Za-z0-9][\w./:-]*)")


@dataclass
class DiscoveryResult:
    """What the live registry reported, and whether it could be reached."""

    available: list[str] = field(default_factory=list)
    reachable: bool = False
    reason: str = ""
    probed_at: str = ""
    probed: bool = True

    @property
    def degraded(self) -> bool:
        """True when routing has to fall back to the policy's static roster."""
        return self.probed and not self.reachable

    @property
    def state(self) -> str:
        if not self.probed:
            return "pending"
        return "reachable" if self.reachable else "degraded"

    @staticmethod
    def pending() -> DiscoveryResult:
        return DiscoveryResult(
            reachable=False,
            reason="The live registry has not answered yet",
            probed=False,
        )


def parse_model_list(output: str) -> list[str]:
    """Extract model identifiers from `cmd --list-models` output."""
    models: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.endswith(":"):
            continue
        match = _LINE.match(stripped)
        if match is None:
            continue
        identifier = match.group(1)
        # Headings such as "Available models" survive the regex but are not
        # identifiers; a model id always has a separator or a digit.
        if identifier not in models and re.search(r"[./:\d]", identifier):
            models.append(identifier)
    return models


async def discover_models(timeout: float = 15.0) -> DiscoveryResult:
    """Ask Command Code which models are live.

    A missing or failing harness is a degraded state, never a fatal one: Atlas
    Flow still runs with the policy roster, it just cannot confirm that any of
    those models are reachable.
    """
    probed_at = datetime.now(UTC).isoformat()

    try:
        process = await asyncio.create_subprocess_exec(
            *DISCOVERY_COMMAND,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return DiscoveryResult(
            reachable=False,
            reason="Command Code (cmd) is not on PATH",
            probed_at=probed_at,
        )

    try:
        raw_out, raw_err = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return DiscoveryResult(
            reachable=False,
            reason=f"cmd --list-models timed out after {timeout}s",
            probed_at=probed_at,
        )

    if process.returncode != 0:
        detail = raw_err.decode("utf-8", errors="replace").strip()
        return DiscoveryResult(
            reachable=False,
            reason=f"cmd --list-models failed: {detail[:200]}",
            probed_at=probed_at,
        )

    models = parse_model_list(raw_out.decode("utf-8", errors="replace"))
    return DiscoveryResult(
        available=models,
        reachable=True,
        reason=f"{len(models)} model(s) reported by the live registry",
        probed_at=probed_at,
    )


class ModelRegistry:
    """Owns the live model list and keeps the router in step with it.

    Probing costs a subprocess round-trip of several seconds, so it never
    blocks startup: the router begins on the policy's static roster and is
    updated when the registry answers. The result is cached for the life of the
    process, since the set of models a harness exposes does not change under a
    running application.
    """

    _cached: DiscoveryResult | None = None

    def __init__(self, router: ModelRouter) -> None:
        self.router = router
        self.current = ModelRegistry._cached or DiscoveryResult.pending()
        if self.current.reachable:
            self.router.probe_available(self.current.available)

    @property
    def probed(self) -> bool:
        return self.current.probed

    async def refresh(self, timeout: float = 15.0) -> DiscoveryResult:
        """Probe the registry and apply the result to the router."""
        result = await discover_models(timeout=timeout)
        self.current = result
        ModelRegistry._cached = result
        if result.reachable:
            self.router.probe_available(result.available)
        return result

    def start_background_probe(self) -> asyncio.Task[DiscoveryResult] | None:
        """Probe without making callers wait. Returns None if already probed."""
        if self.probed:
            return None
        return asyncio.create_task(self.refresh())

    @classmethod
    def seed(cls, result: DiscoveryResult) -> None:
        """Install a probe result without running one.

        Tests use this so that constructing an application does not shell out
        to `cmd` — the probing itself is covered by the discovery tests.
        """
        cls._cached = result

    @classmethod
    def reset_cache(cls) -> None:
        """Forget the cached probe. For tests and for an explicit re-probe."""
        cls._cached = None
