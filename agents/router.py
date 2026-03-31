"""Hybrid intent router.

Implements a two-stage routing strategy:
1. **Rule layer** — fast keyword / regex matching against configurable rules.
2. **LLM layer** — intelligent intent classification as fallback.

The router is used by the orchestrator to decide which sub-agent should
handle a given user request.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agents.config import AgentConfig
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteMatch:
    """Result of a routing decision."""

    agent_name: str
    confidence: float  # 0.0 - 1.0
    source: str  # "rule" or "llm"
    reasoning: str = ""


@dataclass
class RoutingRule:
    """A single routing rule entry."""

    patterns: list[str]  # keyword or regex patterns
    agent_name: str
    description: str = ""


class IntentRouter:
    """Hybrid intent router with rule-first, LLM-fallback strategy.

    Usage::

        router = IntentRouter(config, registry, llm_model)
        match = router.route("帮我写一个 Python 排序算法")
        # -> RouteMatch(agent_name="coder", confidence=0.9, source="rule")
    """

    def __init__(
        self,
        config: AgentConfig,
        registry: AgentRegistry,
        llm_model: BaseChatModel | None = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._llm = llm_model
        self._rules: list[RoutingRule] = []
        self._load_rules()

    # --- Rule management ---

    def _load_rules(self) -> None:
        """Load routing rules from the YAML configuration file."""
        rules_path = Path(self._config.routing_rules_path)
        if not rules_path.exists():
            logger.warning(
                "Routing rules file not found: %s — rule-based routing disabled.",
                rules_path,
            )
            return

        with open(rules_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        rules_data = data.get("rules", [])
        for entry in rules_data:
            patterns = entry.get("patterns", [])
            agent_name = entry.get("agent", "")
            description = entry.get("description", "")
            if agent_name and patterns:
                self._rules.append(
                    RoutingRule(
                        patterns=patterns,
                        agent_name=agent_name,
                        description=description,
                    )
                )

        logger.info("Loaded %d routing rules from %s", len(self._rules), rules_path)

    def add_rule(self, rule: RoutingRule) -> None:
        """Dynamically add a routing rule at runtime."""
        self._rules.append(rule)

    def clear_rules(self) -> None:
        """Remove all routing rules."""
        self._rules.clear()

    # --- Routing ---

    def route(self, user_input: str) -> RouteMatch:
        """Route a user input to the best matching sub-agent.

        Strategy depends on ``config.routing_strategy``:
        - ``rule_first`` (default): Try rules first, fall back to LLM.
        - ``llm_first``: Always use LLM.
        - ``rule_only``: Only use rules; return a low-confidence match if no rule hits.

        Args:
            user_input: The user's natural language request.

        Returns:
            A ``RouteMatch`` indicating the selected sub-agent and routing metadata.
        """
        if self._config.routing_strategy == "llm_first":
            return self._route_llm(user_input)

        # Try rule-based routing first
        rule_match = self._route_rules(user_input)
        if rule_match is not None:
            logger.info(
                "Rule match: agent=%s confidence=%.2f",
                rule_match.agent_name,
                rule_match.confidence,
            )
            return rule_match

        # Fall back to LLM or rule-only
        if self._config.routing_strategy == "rule_only":
            # Return the first enabled agent with low confidence as fallback
            agents = self._registry.list_agents()
            fallback_name = agents[0].name if agents else "general"
            return RouteMatch(
                agent_name=fallback_name,
                confidence=0.1,
                source="rule",
                reasoning="No rule matched; using default fallback.",
            )

        return self._route_llm(user_input)

    def _route_rules(self, user_input: str) -> RouteMatch | None:
        """Attempt to match the user input against configured rules.

        Returns ``None`` if no rule matches.
        """
        input_lower = user_input.lower()
        for rule in self._rules:
            for pattern in rule.patterns:
                if re.search(pattern, input_lower, re.IGNORECASE):
                    # Validate that the target agent exists and is enabled
                    agent = self._registry.get_agent(rule.agent_name)
                    if agent and agent.enabled:
                        return RouteMatch(
                            agent_name=rule.agent_name,
                            confidence=0.9,
                            source="rule",
                            reasoning=f"Matched pattern '{pattern}' from rule targeting '{rule.agent_name}'.",
                        )
                    else:
                        logger.warning(
                            "Rule matched '%s' but agent '%s' is not available.",
                            pattern,
                            rule.agent_name,
                        )
        return None

    def _route_llm(self, user_input: str) -> RouteMatch:
        """Use LLM to classify the user input and select a sub-agent.

        Falls back to the first enabled agent if LLM fails.
        """
        if self._llm is None:
            logger.warning("No LLM model provided for routing; using default agent.")
            agents = self._registry.list_agents()
            fallback_name = agents[0].name if agents else "general"
            return RouteMatch(
                agent_name=fallback_name,
                confidence=0.0,
                source="llm",
                reasoning="No LLM model available; using default fallback.",
            )

        agents = self._registry.list_agents()
        if not agents:
            return RouteMatch(
                agent_name="general",
                confidence=0.0,
                source="llm",
                reasoning="No sub-agents registered.",
            )

        # Build the classification prompt
        agent_options = "\n".join(
            f"- {a.name}: {a.description}" for a in agents
        )

        system_prompt = (
            "You are an intent router for a multi-agent system. "
            "Given a user request, select the most appropriate sub-agent to handle it.\n\n"
            f"Available sub-agents:\n{agent_options}\n\n"
            "Respond with ONLY the agent name, nothing else. "
            "If no agent is a good fit, respond with the name of the most general agent."
        )

        try:
            response = self._llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_input),
                ]
            )
            selected = response.content.strip().lower()
            # Validate the selection
            valid_names = {a.name for a in agents}
            if selected in valid_names:
                return RouteMatch(
                    agent_name=selected,
                    confidence=0.7,
                    source="llm",
                    reasoning=f"LLM classified request and selected '{selected}'.",
                )
            # Try partial match
            for name in valid_names:
                if name in selected or selected in name:
                    return RouteMatch(
                        agent_name=name,
                        confidence=0.5,
                        source="llm",
                        reasoning=f"LLM returned '{selected}', matched to '{name}'.",
                    )

            logger.warning(
                "LLM returned unknown agent '%s'; falling back to first agent.", selected
            )
        except Exception as e:
            logger.error("LLM routing failed: %s", e)

        return RouteMatch(
            agent_name=agents[0].name,
            confidence=0.0,
            source="llm",
            reasoning="LLM routing failed; using first available agent as fallback.",
        )
