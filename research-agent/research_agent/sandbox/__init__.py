"""E2B sandbox integration for isolated sub-agent execution."""

from research_agent.sandbox.e2b_manager import E2BSandboxManager, SandboxInfo
from research_agent.sandbox.agent_executor import (
    SandboxedAgentExecutor,
    ParallelAgentExecutor
)

__all__ = [
    "E2BSandboxManager",
    "SandboxInfo",
    "SandboxedAgentExecutor",
    "ParallelAgentExecutor"
]
