"""Runner abstraction and capability negotiation (P04)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class RunnerCapability(StrEnum):
    AGENT_SESSION = "agent_session"
    CANCELLATION = "cancellation"
    PERMISSIONS = "permissions"
    TRANSCRIPT = "transcript"
    FILE_ACCESS = "file_access"
    TOOL_ACCESS = "tool_access"
    STREAMING = "streaming"
    RESULT_CAPTURE = "result_capture"


@dataclass
class RunnerResult:
    task_id: str
    success: bool
    output: str = ""
    error: str = ""
    transcript: str = ""
    evidence: dict[str, str] = field(default_factory=dict)


@dataclass
class RunnerConfig:
    model: str
    max_turns: int = 20
    timeout_seconds: int = 300
    headless: bool = True
    extra_args: list[str] = field(default_factory=list)


class Runner(ABC):
    """Abstract runner that Atlas Harness coordinates."""

    def __init__(self, name: str, capabilities: list[RunnerCapability]) -> None:
        self.name = name
        self.capabilities = set(capabilities)

    def has_capability(self, cap: RunnerCapability) -> bool:
        return cap in self.capabilities

    def negotiate(self, required: list[RunnerCapability]) -> list[RunnerCapability]:
        """Negotiate capabilities; returns intersection of requested and available."""
        return [c for c in required if c in self.capabilities]

    @abstractmethod
    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        ...

    @abstractmethod
    async def cancel(self, task_id: str) -> bool:
        ...


class DummyRunner(Runner):
    """Fixture runner for tests — never touches a real agent."""

    def __init__(self, name: str = "dummy") -> None:
        super().__init__(name, list(RunnerCapability))

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        return RunnerResult(
            task_id=task_id,
            success=True,
            output=f"Dummy executed: {prompt[:80]}",
            transcript="[dummy transcript]",
        )

    async def cancel(self, task_id: str) -> bool:
        return True
