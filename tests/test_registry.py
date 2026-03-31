"""Unit tests for AgentRegistry."""

import pytest

from agents.registry import AgentRegistry, SubAgentConfig
from tools.thinking import think_tool


@pytest.fixture
def empty_registry() -> AgentRegistry:
    """Return an empty AgentRegistry."""
    return AgentRegistry()


@pytest.fixture
def sample_agent() -> SubAgentConfig:
    """Return a sample SubAgentConfig for testing."""
    return SubAgentConfig(
        name="test-agent",
        description="A test agent for unit testing.",
        system_prompt="You are a test agent. Current date: {date}.",
        tools=[think_tool],
        max_iterations=2,
        enabled=True,
    )


class TestSubAgentConfig:
    """Tests for SubAgentConfig dataclass."""

    def test_to_dict(self, sample_agent: SubAgentConfig) -> None:
        """SubAgentConfig.to_dict should produce the correct dictionary."""
        result = sample_agent.to_dict
        assert result["name"] == "test-agent"
        assert result["description"] == "A test agent for unit testing."
        assert result["system_prompt"] == "You are a test agent. Current date: {date}."
        assert len(result["tools"]) == 1

    def test_format_prompt(self, sample_agent: SubAgentConfig) -> None:
        """format_prompt should fill placeholders in the system_prompt."""
        formatted = sample_agent.format_prompt(date="2026-03-31")
        assert formatted.system_prompt == "You are a test agent. Current date: 2026-03-31."
        # Original should be unchanged
        assert "{date}" in sample_agent.system_prompt

    def test_to_dict_preserves_tools(self, sample_agent: SubAgentConfig) -> None:
        """to_dict should include the full tools list."""
        result = sample_agent.to_dict
        assert result["tools"] == [think_tool]


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def test_register_and_get(self, empty_registry: AgentRegistry, sample_agent: SubAgentConfig) -> None:
        """Register an agent and retrieve it by name."""
        empty_registry.register(sample_agent)
        retrieved = empty_registry.get_agent("test-agent")
        assert retrieved is not None
        assert retrieved.name == "test-agent"
        assert retrieved.description == "A test agent for unit testing."

    def test_register_duplicate_raises(self, empty_registry: AgentRegistry, sample_agent: SubAgentConfig) -> None:
        """Registering an agent with the same name should raise ValueError."""
        empty_registry.register(sample_agent)
        with pytest.raises(ValueError, match="already registered"):
            empty_registry.register(sample_agent)

    def test_unregister(self, empty_registry: AgentRegistry, sample_agent: SubAgentConfig) -> None:
        """Unregistering should remove the agent."""
        empty_registry.register(sample_agent)
        empty_registry.unregister("test-agent")
        assert empty_registry.get_agent("test-agent") is None

    def test_unregister_nonexistent(self, empty_registry: AgentRegistry) -> None:
        """Unregistering a nonexistent agent should not raise."""
        empty_registry.unregister("nonexistent")

    def test_list_agents_enabled_only(self, empty_registry: AgentRegistry) -> None:
        """list_agents should only return enabled agents."""
        enabled = SubAgentConfig(
            name="enabled-agent", description="Enabled", system_prompt="...", enabled=True
        )
        disabled = SubAgentConfig(
            name="disabled-agent", description="Disabled", system_prompt="...", enabled=False
        )
        empty_registry.register(enabled)
        empty_registry.register(disabled)

        agents = empty_registry.list_agents()
        assert len(agents) == 1
        assert agents[0].name == "enabled-agent"

    def test_list_all_agents(self, empty_registry: AgentRegistry) -> None:
        """list_all_agents should return both enabled and disabled agents."""
        enabled = SubAgentConfig(
            name="enabled-agent", description="Enabled", system_prompt="...", enabled=True
        )
        disabled = SubAgentConfig(
            name="disabled-agent", description="Disabled", system_prompt="...", enabled=False
        )
        empty_registry.register(enabled)
        empty_registry.register(disabled)

        agents = empty_registry.list_all_agents()
        assert len(agents) == 2

    def test_agent_names(self, empty_registry: AgentRegistry) -> None:
        """agent_names should return a list of enabled agent names."""
        a1 = SubAgentConfig(name="alpha", description="A", system_prompt="...")
        a2 = SubAgentConfig(name="beta", description="B", system_prompt="...", enabled=False)
        empty_registry.register(a1)
        empty_registry.register(a2)

        names = empty_registry.agent_names()
        assert names == ["alpha"]

    def test_capabilities_summary(self, empty_registry: AgentRegistry, sample_agent: SubAgentConfig) -> None:
        """capabilities_summary should generate a human-readable string."""
        empty_registry.register(sample_agent)
        summary = empty_registry.capabilities_summary()
        assert "test-agent" in summary
        assert "A test agent for unit testing." in summary
        assert "think_tool" in summary

    def test_capabilities_summary_empty(self, empty_registry: AgentRegistry) -> None:
        """capabilities_summary should handle empty registry gracefully."""
        summary = empty_registry.capabilities_summary()
        assert "No sub-agents" in summary

    def test_get_nonexistent_returns_none(self, empty_registry: AgentRegistry) -> None:
        """Getting a nonexistent agent should return None."""
        assert empty_registry.get_agent("nonexistent") is None
