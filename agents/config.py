"""Global configuration for the agent system.

Centralizes model selection, concurrency limits, and other tunable parameters.
"""

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class AgentConfig:
    """Immutable global configuration for the agent system.

    Values are resolved from environment variables with sensible defaults.
    """

    # --- Model ---
    primary_model: str = field(
        default_factory=lambda: os.getenv(
            "PRIMARY_MODEL", "anthropic:claude-sonnet-4-5-20250929"
        )
    )
    """Model identifier for the orchestrator and sub-agents."""

    fallback_model: str = field(
        default_factory=lambda: os.getenv(
            "FALLBACK_MODEL", "openai:gpt-4o-mini"
        )
    )
    """Lightweight model used for summarization / classification tasks."""

    # --- Limits ---
    max_concurrent_subagents: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_SUBAGENTS", "3"))
    )
    """Maximum number of sub-agents that can run in parallel."""

    max_subagent_iterations: int = field(
        default_factory=lambda: int(os.getenv("MAX_SUBAGENT_ITERATIONS", "3"))
    )
    """Maximum iterations per sub-agent execution."""

    max_routing_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_ROUTING_RETRIES", "2"))
    )
    """Maximum times the router will re-attempt LLM classification on failure."""

    # --- Routing ---
    routing_strategy: Literal["rule_first", "llm_first", "rule_only"] = field(
        default_factory=lambda: os.getenv("ROUTING_STRATEGY", "rule_first")
    )
    """Intent routing strategy: rule_first (default), llm_first, or rule_only."""

    routing_rules_path: str = field(
        default_factory=lambda: os.getenv(
            "ROUTING_RULES_PATH", "config/agent_rules.yaml"
        )
    )
    """Path to the YAML file containing routing rules."""

    # --- Logging ---
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    """Logging level (DEBUG, INFO, WARNING, ERROR)."""

    # --- LangSmith ---
    langsmith_tracing: bool = field(
        default_factory=lambda: os.getenv("LANGSMITH_TRACING", "false").lower()
        == "true"
    )
    """Whether to enable LangSmith tracing."""

    langsmith_project: str = field(
        default_factory=lambda: os.getenv("LANGSMITH_PROJECT", "agents")
    )
    """LangSmith project name for tracing."""
