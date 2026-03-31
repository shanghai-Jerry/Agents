"""Permission System — Whitelist-based access control for Skills and Tools.

Provides ``PermissionConfig`` for declarative YAML-based permission definitions
and ``PermissionManager`` for runtime access control. Agents operate under a
**whitelist** model: by default, no access is granted; explicit entries in the
agent's ``permissions.yaml`` are required.

Architecture::

    subagents/{agent}/permissions.yaml
        --> PermissionConfig.load_from_yaml()
        --> PermissionConfig.resolve(ResourceRegistry)
        --> PermissionManager.register(agent_name, resolved_config)
        --> PermissionManager.check_tool_access() / get_allowed_tools()

Usage::

    from agents.permissions import PermissionManager, PermissionConfig
    from agents.resources import resource_registry

    manager = PermissionManager(registry=resource_registry)
    config = PermissionConfig.load_from_yaml("subagents/general/permissions.yaml")
    resolved = config.resolve(registry)
    manager.register("general", resolved)

    # Check access
    manager.check_tool_access("general", "think_tool")   # True
    manager.check_tool_access("general", "tavily_search")  # raises UnauthorizedAccessError
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agents.resources import ResourceRegistry, SkillMetadata, ToolMetadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnauthorizedAccessError(Exception):
    """Raised when an agent attempts to use a Tool or Skill it is not authorized for.

    Attributes:
        agent_name: The name of the agent that attempted unauthorized access.
        resource_name: The name of the Tool or Skill being accessed.
        resource_type: Either ``"tool"`` or ``"skill"``.
    """

    def __init__(
        self,
        agent_name: str,
        resource_name: str,
        resource_type: str = "tool",
    ) -> None:
        self.agent_name = agent_name
        self.resource_name = resource_name
        self.resource_type = resource_type
        super().__init__(
            f"Agent '{agent_name}' is not authorized to use {resource_type} "
            f"'{resource_name}'. Check the permissions.yaml for '{agent_name}'."
        )


class PermissionConfigError(Exception):
    """Raised when a permission configuration file is invalid."""


# ---------------------------------------------------------------------------
# PermissionConfig
# ---------------------------------------------------------------------------


@dataclass
class PermissionConfig:
    """Declarative permission configuration for a single agent.

    Represents the parsed content of a ``permissions.yaml`` file. Uses
    **whitelist** semantics: only explicitly listed tools, skills, and groups
    are permitted.

    Attributes:
        tools: Allowed tool names (exact match).
        skills: Allowed skill names (exact match).
        groups: Allowed group names — tools and skills in these groups are
            automatically permitted.
    """

    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)

    # --- Resolved sets (populated by resolve()) ---

    _resolved_tool_names: set[str] = field(default_factory=set, repr=False)
    _resolved_skill_names: set[str] = field(default_factory=set, repr=False)

    @classmethod
    def load_from_yaml(cls, path: str | Path) -> PermissionConfig:
        """Load a permission configuration from a YAML file.

        Expected YAML structure::

            permissions:
              tools:
                - think_tool
                - fetch_webpage_content
              skills:
                - deep_research
              groups:
                - core
                - search

        Args:
            path: Path to the YAML file.

        Returns:
            A ``PermissionConfig`` instance.

        Raises:
            PermissionConfigError: If the file is missing or malformed.
        """
        path = Path(path)
        if not path.exists():
            raise PermissionConfigError(f"Permission file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise PermissionConfigError(f"Invalid YAML in {path}: {e}")

        perm_data = data.get("permissions", data)
        if not isinstance(perm_data, dict):
            raise PermissionConfigError(
                f"Expected 'permissions' dict in {path}, got {type(perm_data).__name__}"
            )

        return cls(
            tools=[str(t) for t in perm_data.get("tools", [])],
            skills=[str(s) for s in perm_data.get("skills", [])],
            groups=[str(g) for g in perm_data.get("groups", [])],
        )

    def resolve(self, registry: ResourceRegistry) -> PermissionConfig:
        """Resolve group references into concrete tool/skill name sets.

        Expands each group name into the actual tools and skills registered
        under that group in the ResourceRegistry, then merges with the
        explicitly listed tool/skill names.

        Args:
            registry: The global resource registry.

        Returns:
            Self, with ``_resolved_tool_names`` and ``_resolved_skill_names``
            populated.
        """
        # Start with explicitly listed names
        resolved_tools = set(self.tools)
        resolved_skills = set(self.skills)

        # Expand groups
        for group in self.groups:
            resolved_tools.update(registry.tool_names_by_group(group))
            resolved_skills.update(registry.skill_names_by_group(group))

        self._resolved_tool_names = resolved_tools
        self._resolved_skill_names = resolved_skills
        return self

    @property
    def allowed_tool_names(self) -> set[str]:
        """Return the resolved set of allowed tool names."""
        return self._resolved_tool_names

    @property
    def allowed_skill_names(self) -> set[str]:
        """Return the resolved set of allowed skill names."""
        return self._resolved_skill_names


# ---------------------------------------------------------------------------
# PermissionManager
# ---------------------------------------------------------------------------


class PermissionManager:
    """Runtime permission manager for multi-agent systems.

    Manages per-agent permission configurations and provides access control
    checks. Operates on a **whitelist** model.

    Usage::

        manager = PermissionManager(registry=resource_registry)
        config = PermissionConfig.load_from_yaml("subagents/general/permissions.yaml")
        config.resolve(registry)
        manager.register("general", config)

        # Runtime checks
        manager.check_tool_access("general", "think_tool")
        allowed = manager.get_allowed_tool_instances("general")
    """

    def __init__(self, registry: ResourceRegistry | None = None) -> None:
        self._configs: dict[str, PermissionConfig] = {}
        self._registry = registry

    @property
    def registry(self) -> ResourceRegistry | None:
        """The resource registry used for group resolution."""
        return self._registry

    @registry.setter
    def registry(self, value: ResourceRegistry) -> None:
        self._registry = value

    # --- Registration ---

    def register(self, agent_name: str, config: PermissionConfig) -> None:
        """Register a permission configuration for an agent.

        Args:
            agent_name: The agent's unique name.
            config: The resolved permission configuration.
        """
        self._configs[agent_name] = config
        logger.debug(
            "Registered permissions for agent '%s': "
            "%d tools, %d skills",
            agent_name,
            len(config.allowed_tool_names),
            len(config.allowed_skill_names),
        )

    def unregister(self, agent_name: str) -> None:
        """Remove a registered agent's permission configuration."""
        self._configs.pop(agent_name, None)

    def load_from_yaml(
        self,
        agent_name: str,
        yaml_path: str | Path,
    ) -> PermissionConfig:
        """Load, resolve, and register permissions from a YAML file.

        Convenience method that combines ``PermissionConfig.load_from_yaml``,
        ``resolve()``, and ``register()`` in one call.

        Args:
            agent_name: The agent's unique name.
            yaml_path: Path to the ``permissions.yaml`` file.

        Returns:
            The resolved ``PermissionConfig`` instance.

        Raises:
            PermissionConfigError: If the YAML file is invalid.
            RuntimeError: If no registry has been set for group resolution.
        """
        if self._registry is None:
            raise RuntimeError(
                "Cannot load permissions: no ResourceRegistry set. "
                "Assign one via PermissionManager(registry=...) or .registry = ..."
            )

        config = PermissionConfig.load_from_yaml(yaml_path)
        config.resolve(self._registry)
        self.register(agent_name, config)
        return config

    # --- Access checks ---

    def check_tool_access(self, agent_name: str, tool_name: str) -> bool:
        """Check whether an agent is authorized to use a specific tool.

        Args:
            agent_name: The agent's unique name.
            tool_name: The tool name to check.

        Returns:
            ``True`` if access is granted.

        Raises:
            UnauthorizedAccessError: If the agent is not authorized.
        """
        config = self._configs.get(agent_name)
        if config is None:
            # Agent has no permissions configured — deny by default
            raise UnauthorizedAccessError(agent_name, tool_name, "tool")

        if tool_name not in config.allowed_tool_names:
            raise UnauthorizedAccessError(agent_name, tool_name, "tool")

        return True

    def check_skill_access(self, agent_name: str, skill_name: str) -> bool:
        """Check whether an agent is authorized to use a specific skill.

        Args:
            agent_name: The agent's unique name.
            skill_name: The skill name to check.

        Returns:
            ``True`` if access is granted.

        Raises:
            UnauthorizedAccessError: If the agent is not authorized.
        """
        config = self._configs.get(agent_name)
        if config is None:
            raise UnauthorizedAccessError(agent_name, skill_name, "skill")

        if skill_name not in config.allowed_skill_names:
            raise UnauthorizedAccessError(agent_name, skill_name, "skill")

        return True

    # --- Resource retrieval (filtered by permissions) ---

    def get_allowed_tool_instances(
        self, agent_name: str
    ) -> list[Any]:
        """Get all tool instances that an agent is authorized to use.

        Args:
            agent_name: The agent's unique name.

        Returns:
            A list of LangChain ``BaseTool`` instances that the agent
            is authorized to use. Tools without an ``instance`` reference
            are skipped.
        """
        config = self._configs.get(agent_name)
        if config is None or self._registry is None:
            return []

        instances: list[Any] = []
        for tool_name in config.allowed_tool_names:
            meta = self._registry.get_tool(tool_name)
            if meta and meta.instance is not None:
                instances.append(meta.instance)
            else:
                logger.warning(
                    "Tool '%s' is authorized for agent '%s' but has no "
                    "registered instance in ResourceRegistry. Skipping.",
                    tool_name,
                    agent_name,
                )

        return instances

    def get_allowed_skill_paths(self, agent_name: str) -> list[str]:
        """Get file paths of all skills that an agent is authorized to use.

        Args:
            agent_name: The agent's unique name.

        Returns:
            A list of file paths (as strings) for authorized skills.
            Skills without a ``file_path`` are skipped.
        """
        config = self._configs.get(agent_name)
        if config is None or self._registry is None:
            return []

        paths: list[str] = []
        for skill_name in config.allowed_skill_names:
            meta = self._registry.get_skill(skill_name)
            if meta and meta.file_path:
                paths.append(str(meta.file_path))

        return paths

    # --- Query ---

    def get_config(self, agent_name: str) -> PermissionConfig | None:
        """Get the permission configuration for a specific agent."""
        return self._configs.get(agent_name)

    def list_agents(self) -> list[str]:
        """Return names of all agents with registered permissions."""
        return list(self._configs.keys())

    def summary(self) -> str:
        """Generate a human-readable summary of all permission configurations."""
        lines: list[str] = ["## Permission Summary"]

        if not self._configs:
            lines.append("  No agents have permission configurations.")
            return "\n".join(lines)

        for agent_name in sorted(self._configs.keys()):
            config = self._configs[agent_name]
            lines.append(f"\n### Agent: {agent_name}")
            lines.append(
                f"  Tools ({len(config.allowed_tool_names)}): "
                f"{', '.join(sorted(config.allowed_tool_names)) or '(none)'}"
            )
            lines.append(
                f"  Skills ({len(config.allowed_skill_names)}): "
                f"{', '.join(sorted(config.allowed_skill_names)) or '(none)'}"
            )

        return "\n".join(lines)
