"""Resource Registry — Global registry for Tools and Skills.

Provides a centralized registry for managing metadata of all Tools and Skills
in the system, including name, description, group, and instance references.

Tools are registered via the ``@register_tool`` decorator (a wrapper around
LangChain's ``@tool``). Skills are registered via the ``register_skill()``
function.

Usage::

    from agents.resources import resource_registry, register_tool

    @register_tool(group="search", name="my_search", description="Search stuff")
    def my_search_tool(query: str) -> str:
        return f"Results for: {query}"

    # Query the registry
    resource_registry.get_tool("my_search")
    resource_registry.list_by_group("search")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ToolMetadata:
    """Metadata for a registered Tool.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description.
        group: Functional group this tool belongs to (e.g. ``"search"``, ``"code"``).
        instance: The actual LangChain ``BaseTool`` instance.
    """

    name: str
    description: str
    group: str = "default"
    instance: BaseTool | None = None


@dataclass
class SkillMetadata:
    """Metadata for a registered Skill.

    Attributes:
        name: Unique identifier for the skill.
        description: Human-readable description.
        group: Functional group this skill belongs to.
        file_path: Path to the Markdown definition file.
    """

    name: str
    description: str
    group: str = "default"
    file_path: Path | str | None = None


class ResourceRegistry:
    """Global registry for all Tools and Skills.

    Manages metadata for all registered resources and provides query interfaces
    for permission checking and resource discovery.

    Usage::

        registry = ResourceRegistry()
        registry.register_tool(meta)
        registry.list_by_group("search")
        registry.get_tool("think_tool")
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}
        self._skills: dict[str, SkillMetadata] = {}
        self._tool_groups: dict[str, set[str]] = {}  # group -> set of tool names
        self._skill_groups: dict[str, set[str]] = {}  # group -> set of skill names

    # --- Tool operations ---

    def register_tool(self, meta: ToolMetadata) -> None:
        """Register a tool with its metadata.

        Args:
            meta: The tool metadata to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if meta.name in self._tools:
            raise ValueError(
                f"Tool '{meta.name}' is already registered. "
                f"Use unregister_tool() first or choose a different name."
            )
        self._tools[meta.name] = meta
        # Update group index
        self._tool_groups.setdefault(meta.group, set()).add(meta.name)
        logger.debug("Registered tool '%s' in group '%s'", meta.name, meta.group)

    def unregister_tool(self, name: str) -> None:
        """Remove a tool from the registry."""
        meta = self._tools.pop(name, None)
        if meta:
            group = self._tool_groups.get(meta.group)
            if group:
                group.discard(name)
                if not group:
                    del self._tool_groups[meta.group]

    def get_tool(self, name: str) -> ToolMetadata | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_tool_instance(self, name: str) -> BaseTool | None:
        """Get the actual BaseTool instance for a registered tool."""
        meta = self._tools.get(name)
        if meta and meta.instance:
            return meta.instance
        return None

    def list_tools(self) -> list[ToolMetadata]:
        """Return all registered tool metadata."""
        return list(self._tools.values())

    def list_tools_by_group(self, group: str) -> list[ToolMetadata]:
        """Return all tools belonging to a specific group."""
        names = self._tool_groups.get(group, set())
        return [self._tools[n] for n in names if n in self._tools]

    def tool_names(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def tool_names_by_group(self, group: str) -> list[str]:
        """Return tool names belonging to a specific group."""
        return list(self._tool_groups.get(group, set()))

    # --- Skill operations ---

    def register_skill(self, meta: SkillMetadata) -> None:
        """Register a skill with its metadata.

        Args:
            meta: The skill metadata to register.

        Raises:
            ValueError: If a skill with the same name is already registered.
        """
        if meta.name in self._skills:
            raise ValueError(
                f"Skill '{meta.name}' is already registered. "
                f"Use unregister_skill() first or choose a different name."
            )
        self._skills[meta.name] = meta
        # Update group index
        self._skill_groups.setdefault(meta.group, set()).add(meta.name)
        logger.debug("Registered skill '%s' in group '%s'", meta.name, meta.group)

    def unregister_skill(self, name: str) -> None:
        """Remove a skill from the registry."""
        meta = self._skills.pop(name, None)
        if meta:
            group = self._skill_groups.get(meta.group)
            if group:
                group.discard(name)
                if not group:
                    del self._skill_groups[meta.group]

    def get_skill(self, name: str) -> SkillMetadata | None:
        """Look up a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[SkillMetadata]:
        """Return all registered skill metadata."""
        return list(self._skills.values())

    def list_skills_by_group(self, group: str) -> list[SkillMetadata]:
        """Return all skills belonging to a specific group."""
        names = self._skill_groups.get(group, set())
        return [self._skills[n] for n in names if n in self._skills]

    def skill_names(self) -> list[str]:
        """Return names of all registered skills."""
        return list(self._skills.keys())

    def skill_names_by_group(self, group: str) -> list[str]:
        """Return skill names belonging to a specific group."""
        return list(self._skill_groups.get(group, set()))

    # --- Group operations ---

    def list_tool_groups(self) -> list[str]:
        """Return all registered tool group names."""
        return list(self._tool_groups.keys())

    def list_skill_groups(self) -> list[str]:
        """Return all registered skill group names."""
        return list(self._skill_groups.keys())

    # --- Summary ---

    def summary(self) -> str:
        """Generate a human-readable summary of all registered resources."""
        lines: list[str] = []

        # Tools by group
        lines.append("## Registered Tools")
        if not self._tools:
            lines.append("  (none)")
        else:
            for group_name in sorted(self._tool_groups.keys()):
                names = sorted(self._tool_groups[group_name])
                lines.append(f"  [{group_name}]")
                for n in names:
                    meta = self._tools[n]
                    lines.append(f"    - {n}: {meta.description}")
        lines.append("")

        # Skills by group
        lines.append("## Registered Skills")
        if not self._skills:
            lines.append("  (none)")
        else:
            for group_name in sorted(self._skill_groups.keys()):
                names = sorted(self._skill_groups[group_name])
                lines.append(f"  [{group_name}]")
                for n in names:
                    meta = self._skills[n]
                    lines.append(f"    - {n}: {meta.description}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Global singleton instance
# ---------------------------------------------------------------------------

resource_registry = ResourceRegistry()


# ---------------------------------------------------------------------------
# Decorators & helpers
# ---------------------------------------------------------------------------


def register_tool(
    group: str = "default",
    name: str | None = None,
    description: str | None = None,
) -> Callable[[F], F]:
    """Decorator to register a LangChain tool with metadata in the ResourceRegistry.

    This wraps LangChain's ``@tool`` decorator and additionally registers the
    tool's metadata. The tool function should still use LangChain's docstring
    format for argument parsing.

    Args:
        group: Functional group for this tool (e.g. ``"search"``, ``"code"``).
        name: Override name for the tool. If ``None``, uses the function name.
        description: Override description. If ``None``, extracts from docstring.

    Returns:
        The decorated function (still a valid LangChain ``BaseTool``).

    Example::

        @register_tool(group="search", description="Search the web")
        def my_search(query: str) -> str:
            \"\"\"Search the web for information.

            Args:
                query: The search query.
            \"\"\"
            return f"Results for: {query}"
    """

    def decorator(func: F) -> F:
        # Apply LangChain's @tool decorator first
        from langchain_core.tools import tool as lc_tool

        lc_wrapped = lc_tool(func)

        # Determine metadata
        tool_name = name or getattr(lc_wrapped, "name", func.__name__)
        tool_desc = description or getattr(lc_wrapped, "description", "")

        # Register in the global registry
        meta = ToolMetadata(
            name=tool_name,
            description=tool_desc,
            group=group,
            instance=lc_wrapped,
        )
        try:
            resource_registry.register_tool(meta)
        except ValueError:
            # Allow re-registration during module reload / testing
            resource_registry.unregister_tool(tool_name)
            resource_registry.register_tool(meta)

        return lc_wrapped  # type: ignore[return-value]

    return decorator


def register_tool_instance(
    tool_instance: BaseTool,
    group: str = "default",
    name: str | None = None,
    description: str | None = None,
) -> None:
    """Register an already-constructed LangChain BaseTool instance.

    Useful for tools that are created via factory functions or third-party
    libraries rather than the ``@tool`` decorator.

    Args:
        tool_instance: An existing LangChain ``BaseTool`` instance.
        group: Functional group for this tool.
        name: Override name. If ``None``, uses ``tool_instance.name``.
        description: Override description.
    """
    tool_name = name or getattr(tool_instance, "name", str(tool_instance))
    tool_desc = description or getattr(tool_instance, "description", "")

    meta = ToolMetadata(
        name=tool_name,
        description=tool_desc,
        group=group,
        instance=tool_instance,
    )
    try:
        resource_registry.register_tool(meta)
    except ValueError:
        resource_registry.unregister_tool(tool_name)
        resource_registry.register_tool(meta)


def register_skill(
    name: str,
    description: str = "",
    group: str = "default",
    file_path: Path | str | None = None,
) -> SkillMetadata:
    """Register a Skill with metadata in the ResourceRegistry.

    Args:
        name: Unique identifier for the skill.
        description: Human-readable description.
        group: Functional group this skill belongs to.
        file_path: Path to the Markdown definition file (if any).

    Returns:
        The created ``SkillMetadata`` instance.

    Example::

        register_skill(
            name="deep_research",
            description="Conduct deep multi-step research",
            group="research",
            file_path="skills/deep_research.md",
        )
    """
    meta = SkillMetadata(
        name=name,
        description=description,
        group=group,
        file_path=file_path,
    )
    try:
        resource_registry.register_skill(meta)
    except ValueError:
        resource_registry.unregister_skill(name)
        resource_registry.register_skill(meta)
    return meta
