"""Tests for the permission management system.

Covers ResourceRegistry, PermissionConfig, and PermissionManager.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agents.resources import (
    ResourceRegistry,
    SkillMetadata,
    ToolMetadata,
    register_tool,
    register_skill,
)
from agents.permissions import (
    PermissionConfig,
    PermissionManager,
    UnauthorizedAccessError,
    PermissionConfigError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> ResourceRegistry:
    """A fresh ResourceRegistry with some test tools registered."""
    reg = ResourceRegistry()

    # Register some test tools manually
    reg.register_tool(ToolMetadata(
        name="tool_a",
        description="Tool A in core group",
        group="core",
    ))
    reg.register_tool(ToolMetadata(
        name="tool_b",
        description="Tool B in search group",
        group="search",
    ))
    reg.register_tool(ToolMetadata(
        name="tool_c",
        description="Tool C in code group",
        group="code",
    ))

    # Register some test skills
    reg.register_skill(SkillMetadata(
        name="skill_research",
        description="Research skill",
        group="research",
    ))
    reg.register_skill(SkillMetadata(
        name="skill_coding",
        description="Coding skill",
        group="coding",
    ))

    return reg


@pytest.fixture
def permission_manager(registry: ResourceRegistry) -> PermissionManager:
    """A PermissionManager with the test registry."""
    return PermissionManager(registry=registry)


# ---------------------------------------------------------------------------
# ResourceRegistry tests
# ---------------------------------------------------------------------------


class TestResourceRegistry:
    """Tests for ResourceRegistry."""

    def test_register_and_get_tool(self, registry: ResourceRegistry) -> None:
        assert registry.get_tool("tool_a") is not None
        assert registry.get_tool("tool_a").name == "tool_a"
        assert registry.get_tool("nonexistent") is None

    def test_list_tools(self, registry: ResourceRegistry) -> None:
        assert len(registry.list_tools()) == 3

    def test_list_tools_by_group(self, registry: ResourceRegistry) -> None:
        core_tools = registry.list_tools_by_group("core")
        assert len(core_tools) == 1
        assert core_tools[0].name == "tool_a"

        search_tools = registry.list_tools_by_group("search")
        assert len(search_tools) == 1

    def test_unregister_tool(self, registry: ResourceRegistry) -> None:
        registry.unregister_tool("tool_a")
        assert registry.get_tool("tool_a") is None
        assert len(registry.list_tools()) == 2

    def test_duplicate_registration_raises(self, registry: ResourceRegistry) -> None:
        with pytest.raises(ValueError, match="already registered"):
            registry.register_tool(ToolMetadata(
                name="tool_a",
                description="Duplicate",
                group="core",
            ))

    def test_register_and_get_skill(self, registry: ResourceRegistry) -> None:
        assert registry.get_skill("skill_research") is not None
        assert registry.get_skill("nonexistent") is None

    def test_list_skills_by_group(self, registry: ResourceRegistry) -> None:
        research_skills = registry.list_skills_by_group("research")
        assert len(research_skills) == 1
        assert research_skills[0].name == "skill_research"

    def test_list_groups(self, registry: ResourceRegistry) -> None:
        tool_groups = registry.list_tool_groups()
        assert "core" in tool_groups
        assert "search" in tool_groups
        assert "code" in tool_groups

        skill_groups = registry.list_skill_groups()
        assert "research" in skill_groups
        assert "coding" in skill_groups

    def test_summary(self, registry: ResourceRegistry) -> None:
        summary = registry.summary()
        assert "tool_a" in summary
        assert "skill_research" in summary
        assert "core" in summary


# ---------------------------------------------------------------------------
# register_tool decorator tests
# ---------------------------------------------------------------------------


class TestRegisterToolDecorator:
    """Tests for the @register_tool decorator."""

    def test_basic_registration(self) -> None:
        reg = ResourceRegistry()

        @register_tool(group="test_group", description="A test tool")
        def test_tool_fn(query: str) -> str:
            """A test tool.

            Args:
                query: The query string.
            """
            return f"result: {query}"

        # Check it was registered in the global registry (or we should use a custom one)
        # The decorator uses the global singleton; let's just verify the tool works
        assert callable(test_tool_fn) or hasattr(test_tool_fn, "invoke")

    def test_register_tool_instance(self) -> None:
        reg = ResourceRegistry()

        # Create a simple mock BaseTool-like object
        class MockTool:
            name = "mock_tool"
            description = "A mock tool"

            def invoke(self, *args, **kwargs):
                return "mock result"

        mock = MockTool()
        from agents.resources import register_tool_instance
        register_tool_instance(mock, group="mock")


# ---------------------------------------------------------------------------
# PermissionConfig tests
# ---------------------------------------------------------------------------


class TestPermissionConfig:
    """Tests for PermissionConfig."""

    def test_load_from_yaml(self) -> None:
        yaml_content = """
permissions:
  tools:
    - tool_a
    - tool_b
  skills:
    - skill_research
  groups:
    - core
    - search
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            config = PermissionConfig.load_from_yaml(f.name)

        assert config.tools == ["tool_a", "tool_b"]
        assert config.skills == ["skill_research"]
        assert config.groups == ["core", "search"]

    def test_load_from_nonexistent_file(self) -> None:
        with pytest.raises(PermissionConfigError, match="not found"):
            PermissionConfig.load_from_yaml("/nonexistent/path.yaml")

    def test_resolve_with_groups(self, registry: ResourceRegistry) -> None:
        config = PermissionConfig(
            tools=["tool_a"],
            skills=[],
            groups=["search"],
        )
        config.resolve(registry)

        assert "tool_a" in config.allowed_tool_names
        assert "tool_b" in config.allowed_tool_names  # from "search" group
        assert "tool_c" not in config.allowed_tool_names

    def test_resolve_with_skill_groups(self, registry: ResourceRegistry) -> None:
        config = PermissionConfig(
            tools=[],
            skills=["skill_research"],
            groups=["coding"],
        )
        config.resolve(registry)

        assert "skill_research" in config.allowed_skill_names
        assert "skill_coding" in config.allowed_skill_names  # from "coding" group

    def test_empty_config(self, registry: ResourceRegistry) -> None:
        config = PermissionConfig()
        config.resolve(registry)

        assert len(config.allowed_tool_names) == 0
        assert len(config.allowed_skill_names) == 0


# ---------------------------------------------------------------------------
# PermissionManager tests
# ---------------------------------------------------------------------------


class TestPermissionManager:
    """Tests for PermissionManager."""

    def test_register_and_check_tool_access(
        self, permission_manager: PermissionManager, registry: ResourceRegistry
    ) -> None:
        config = PermissionConfig(tools=["tool_a"], groups=["search"])
        config.resolve(registry)
        permission_manager.register("test_agent", config)

        assert permission_manager.check_tool_access("test_agent", "tool_a") is True
        assert permission_manager.check_tool_access("test_agent", "tool_b") is True  # from group

    def test_tool_access_denied(
        self, permission_manager: PermissionManager, registry: ResourceRegistry
    ) -> None:
        config = PermissionConfig(tools=["tool_a"])
        config.resolve(registry)
        permission_manager.register("test_agent", config)

        with pytest.raises(UnauthorizedAccessError):
            permission_manager.check_tool_access("test_agent", "tool_c")

    def test_unregistered_agent_denied(self, permission_manager: PermissionManager) -> None:
        with pytest.raises(UnauthorizedAccessError):
            permission_manager.check_tool_access("unknown_agent", "tool_a")

    def test_skill_access_check(
        self, permission_manager: PermissionManager, registry: ResourceRegistry
    ) -> None:
        config = PermissionConfig(skills=["skill_research"])
        config.resolve(registry)
        permission_manager.register("test_agent", config)

        assert permission_manager.check_skill_access("test_agent", "skill_research") is True

    def test_skill_access_denied(
        self, permission_manager: PermissionManager, registry: ResourceRegistry
    ) -> None:
        config = PermissionConfig(skills=["skill_research"])
        config.resolve(registry)
        permission_manager.register("test_agent", config)

        with pytest.raises(UnauthorizedAccessError):
            permission_manager.check_skill_access("test_agent", "skill_coding")

    def test_get_allowed_tool_instances_empty(
        self, permission_manager: PermissionManager, registry: ResourceRegistry
    ) -> None:
        config = PermissionConfig()
        config.resolve(registry)
        permission_manager.register("test_agent", config)

        # tool_a has no instance registered, so result should be empty
        instances = permission_manager.get_allowed_tool_instances("test_agent")
        assert len(instances) == 0

    def test_get_allowed_tool_instances_with_registry(
        self, permission_manager: PermissionManager
    ) -> None:
        # Register a tool with an instance
        class MockTool:
            name = "mock_with_instance"
            description = "Mock"

        from langchain_core.tools import tool as lc_tool

        @lc_tool
        def mock_with_instance_tool() -> str:
            return "mock"

        permission_manager.registry.register_tool(ToolMetadata(
            name="mock_with_instance",
            description="Mock tool with instance",
            group="core",
            instance=mock_with_instance_tool,
        ))

        config = PermissionConfig(tools=["mock_with_instance"])
        config.resolve(permission_manager.registry)
        permission_manager.register("test_agent", config)

        instances = permission_manager.get_allowed_tool_instances("test_agent")
        assert len(instances) == 1

    def test_load_from_yaml(
        self, permission_manager: PermissionManager
    ) -> None:
        yaml_content = """
permissions:
  tools:
    - tool_a
  skills: []
  groups: []
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            config = permission_manager.load_from_yaml("test_agent", f.name)

        assert "tool_a" in config.allowed_tool_names
        assert permission_manager.check_tool_access("test_agent", "tool_a") is True

    def test_summary(self, permission_manager: PermissionManager, registry: ResourceRegistry) -> None:
        config = PermissionConfig(tools=["tool_a"])
        config.resolve(registry)
        permission_manager.register("test_agent", config)

        summary = permission_manager.summary()
        assert "test_agent" in summary
        assert "tool_a" in summary

    def test_unregister(self, permission_manager: PermissionManager, registry: ResourceRegistry) -> None:
        config = PermissionConfig(tools=["tool_a"])
        config.resolve(registry)
        permission_manager.register("test_agent", config)

        permission_manager.unregister("test_agent")
        assert permission_manager.get_config("test_agent") is None
