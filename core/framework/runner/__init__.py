"""Agent Runner - load and run exported agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from framework.runner.mcp_registry import MCPRegistry
from framework.runner.protocol import (
    AgentMessage,
    CapabilityLevel,
    CapabilityResponse,
    MessageType,
    OrchestratorResult,
)
from framework.runner.tool_registry import ToolRegistry, tool

if TYPE_CHECKING:
    from framework.runner.runner import AgentInfo, AgentRunner, ValidationResult

__all__ = [
    # Single agent
    "AgentRunner",
    "AgentInfo",
    "ValidationResult",
    "ToolRegistry",
    "MCPRegistry",
    "tool",
    "AgentMessage",
    "MessageType",
    "CapabilityLevel",
    "CapabilityResponse",
    "OrchestratorResult",
]


def __getattr__(name: str):
    # Avoid importing runner.py during package initialization because graph/event_loop
    # modules depend on framework.runner.* submodules and can form an import cycle.
    if name in {"AgentRunner", "AgentInfo", "ValidationResult"}:
        from framework.runner.runner import AgentInfo, AgentRunner, ValidationResult

        exports = {
            "AgentRunner": AgentRunner,
            "AgentInfo": AgentInfo,
            "ValidationResult": ValidationResult,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
