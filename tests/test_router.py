"""Unit tests for IntentRouter."""

import pytest

from agents.config import AgentConfig
from agents.registry import AgentRegistry, SubAgentConfig
from agents.router import IntentRouter, RouteMatch, RoutingRule
from tools.thinking import think_tool


@pytest.fixture
def config() -> AgentConfig:
    """Return an AgentConfig with rule_first strategy and known rules path."""
    return AgentConfig(
        routing_strategy="rule_first",
        routing_rules_path="config/agent_rules.yaml",
    )


@pytest.fixture
def registry() -> AgentRegistry:
    """Return a registry with one registered agent."""
    reg = AgentRegistry()
    reg.register(
        SubAgentConfig(
            name="general",
            description="A general-purpose assistant.",
            system_prompt="You are a general assistant.",
            tools=[think_tool],
            enabled=True,
        )
    )
    return reg


@pytest.fixture
def router(config: AgentConfig, registry: AgentRegistry) -> IntentRouter:
    """Return an IntentRouter (without LLM model)."""
    return IntentRouter(config=config, registry=registry, llm_model=None)


class TestRouteMatch:
    """Tests for the RouteMatch dataclass."""

    def test_route_match_fields(self) -> None:
        match = RouteMatch(
            agent_name="general",
            confidence=0.9,
            source="rule",
            reasoning="Matched pattern 'test'.",
        )
        assert match.agent_name == "general"
        assert match.confidence == 0.9
        assert match.source == "rule"
        assert match.reasoning == "Matched pattern 'test'."

    def test_route_match_is_frozen(self) -> None:
        match = RouteMatch(agent_name="test", confidence=0.5, source="llm")
        with pytest.raises(AttributeError):
            match.agent_name = "other"


class TestIntentRouterRuleBased:
    """Tests for rule-based routing."""

    def test_route_with_custom_rule(self, router: IntentRouter) -> None:
        """A custom rule should match the corresponding agent."""
        router.add_rule(RoutingRule(
            patterns=["hello|hi|你好"],
            agent_name="general",
            description="Greeting",
        ))
        match = router.route("hello there!")
        assert match.agent_name == "general"
        assert match.source == "rule"
        assert match.confidence == 0.9

    def test_route_no_match_falls_back(self, router: IntentRouter) -> None:
        """When no rule matches and no LLM, should fall back to first agent."""
        match = router.route("some random query")
        assert match.agent_name == "general"
        assert match.confidence < 0.5

    def test_route_rule_only_no_match(self, registry: AgentRegistry) -> None:
        """rule_only strategy should return fallback even without LLM."""
        config = AgentConfig(routing_strategy="rule_only")
        router = IntentRouter(config=config, registry=registry, llm_model=None)
        match = router.route("some random query")
        assert match.source == "rule"
        assert match.confidence == 0.1

    def test_route_invalid_agent_skipped(self, router: IntentRouter) -> None:
        """Rules targeting unregistered agents should be skipped."""
        router.add_rule(RoutingRule(
            patterns=["test"],
            agent_name="nonexistent",
            description="Test rule for nonexistent agent",
        ))
        match = router.route("test query")
        # Should fall back to default, not crash
        assert match.agent_name == "general"

    def test_rule_case_insensitive(self, router: IntentRouter) -> None:
        """Rule matching should be case-insensitive."""
        router.add_rule(RoutingRule(
            patterns=["CODE|编程"],
            agent_name="general",
        ))
        match = router.route("Please write some CODE")
        assert match.agent_name == "general"
        assert match.source == "rule"


class TestIntentRouterClearRules:
    """Tests for rule management."""

    def test_clear_rules(self, router: IntentRouter) -> None:
        """clear_rules should remove all dynamically added rules."""
        router.add_rule(RoutingRule(
            patterns=["test"],
            agent_name="general",
        ))
        router.clear_rules()
        # After clearing, should fall back to LLM/default
        match = router.route("test")
        assert match.source != "rule"
