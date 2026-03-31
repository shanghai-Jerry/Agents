"""Sub-agent registry.

Manages declarative sub-agent configurations and provides query interfaces
for the orchestrator and router to discover available sub-agents and their
capabilities. Supports permission-based tool/skill filtering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


@dataclass
class SubAgentConfig:
    """Declarative configuration for a single sub-agent.

    This mirrors the dictionary format accepted by deepagents' `create_deep_agent`
    under the `subagents` parameter.

    Attributes:
        name: Unique identifier for the sub-agent.
        description: Human-readable description of the sub-agent's capabilities.
        system_prompt: System prompt template. May contain format placeholders
            (e.g. ``{date}``) that are filled at registration time.
        tools: List of LangChain tools this sub-agent is allowed to use.
        skills: List of skill file paths this sub-agent is allowed to use.
        max_iterations: Maximum iterations this sub-agent may perform per task.
        enabled: Whether this sub-agent is currently active.
        permissions_path: Path to the ``permissions.yaml`` for this agent.
            If set, tools/skills will be filtered by the permission manager.
    """

    name: str
    description: str
    system_prompt: str
    tools: list[BaseTool | Callable[..., Any] | dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    max_iterations: int = 3
    enabled: bool = True
    model: str | None = None
    """Optional model override for this sub-agent (e.g. ``"claude-sonnet-4-5"`` or ``"openai:gpt-4o"``)."""
    permissions_path: str | Path | None = None
    """Path to the ``permissions.yaml`` for this agent. If set, tools are filtered by the permission manager."""

    # --- Computed properties ---

    @property
    def to_dict(self) -> dict[str, Any]:
        """Convert to the dictionary format expected by ``create_deep_agent``."""
        d: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
        }
        if self.skills:
            d["skills"] = self.skills
        if self.model:
            d["model"] = self.model
        return d

    def format_prompt(self, **kwargs: str) -> SubAgentConfig:
        """Return a copy with the system_prompt formatted using *kwargs*."""
        return SubAgentConfig(
            name=self.name,
            description=self.description,
            system_prompt=self.system_prompt.format(**kwargs),
            tools=self.tools,
            skills=self.skills,
            max_iterations=self.max_iterations,
            enabled=self.enabled,
            model=self.model,
            permissions_path=self.permissions_path,
        )


class AgentRegistry:
    """Registry for managing sub-agent configurations.

    Usage::

        registry = AgentRegistry()
        registry.register(SubAgentConfig(
            name="researcher",
            description="Search the web and synthesize findings",
            system_prompt="You are a research assistant. {date}",
            tools=[tavily_search, think_tool],
        ))
        registry.list_agents()  # -> [{"name": "researcher", ...}]
        registry.get_agent("researcher")  # -> SubAgentConfig
    """

    def __init__(self) -> None:
        self._agents: dict[str, SubAgentConfig] = {}

    def register(self, config: SubAgentConfig) -> None:
        """Register a sub-agent configuration.

        Args:
            config: The sub-agent configuration to register.

        Raises:
            ValueError: If an agent with the same name is already registered.
        """
        if config.name in self._agents:
            raise ValueError(
                f"Sub-agent '{config.name}' is already registered. "
                f"Use unregister() first or choose a different name."
            )
        self._agents[config.name] = config

    def unregister(self, name: str) -> None:
        """Remove a sub-agent from the registry."""
        self._agents.pop(name, None)

    def get_agent(self, name: str) -> SubAgentConfig | None:
        """Look up a sub-agent by name. Returns ``None`` if not found."""
        return self._agents.get(name)

    def list_agents(self) -> list[SubAgentConfig]:
        """Return all registered sub-agent configurations (enabled only)."""
        return [a for a in self._agents.values() if a.enabled]

    def list_all_agents(self) -> list[SubAgentConfig]:
        """Return all registered sub-agent configurations (including disabled)."""
        return list(self._agents.values())

    def agent_names(self) -> list[str]:
        """Return names of all enabled sub-agents."""
        return [a.name for a in self.list_agents()]

    def capabilities_summary(self) -> str:
        """Generate a human-readable summary of all enabled sub-agents.

        This is intended to be injected into the orchestrator's system prompt
        so it knows what sub-agents are available and what they can do.
        """
        lines: list[str] = []
        for agent in self.list_agents():
            tools_desc = ", ".join(
                getattr(t, "name", str(t)) for t in agent.tools
            ) if agent.tools else "default tools only"
            lines.append(
                f"- **{agent.name}**: {agent.description} "
                f"(tools: {tools_desc})"
            )
        if not lines:
            return "No sub-agents are currently registered."
        return "Available sub-agents:\n" + "\n".join(lines)

    def apply_permissions(self, permission_manager: Any) -> None:
        """Apply permission filtering to all registered sub-agents.

        For each registered agent that has a ``permissions_path`` configured,
        loads its ``permissions.yaml`` and filters its ``tools`` list to only
        include authorized tools.

        Agents without a ``permissions_path`` are left unchanged (backward
        compatible with the legacy mode).

        Args:
            permission_manager: A ``PermissionManager`` instance.
        """
        from agents.permissions import PermissionConfig

        for agent in self.list_all_agents():
            if not agent.permissions_path:
                logger.debug(
                    "Agent '%s' has no permissions_path, skipping permission filtering.",
                    agent.name,
                )
                continue

            perm_path = Path(agent.permissions_path)
            if not perm_path.exists():
                logger.warning(
                    "Agent '%s': permissions file not found at '%s'. "
                    "Falling back to unfiltered tools.",
                    agent.name,
                    perm_path,
                )
                continue

            try:
                config = permission_manager.load_from_yaml(
                    agent_name=agent.name,
                    yaml_path=perm_path,
                )

                # Replace tools with only the authorized ones
                allowed_tools = permission_manager.get_allowed_tool_instances(agent.name)
                agent.tools = allowed_tools

                # Replace skills with only the authorized ones
                allowed_skills = permission_manager.get_allowed_skill_paths(agent.name)
                agent.skills = allowed_skills

                logger.info(
                    "Applied permissions for agent '%s': %d tools, %d skills authorized",
                    agent.name,
                    len(allowed_tools),
                    len(allowed_skills),
                )

            except Exception as e:
                logger.error(
                    "Failed to apply permissions for agent '%s': %s. "
                    "Falling back to unfiltered tools.",
                    agent.name,
                    e,
                )
