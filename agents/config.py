"""Global configuration for the agent system.

Centralizes model selection, concurrency limits, and other tunable parameters.
Supports multiple LLM providers (Anthropic, OpenAI, Google) with per-model config.
"""

import os
from dataclasses import dataclass, field
from typing import Literal


# --- Model Provider Aliases ---
# Maps user-friendly short names to provider:model strings for init_chat_model.
MODEL_ALIASES: dict[str, str] = {
    # Anthropic Claude
    "claude-sonnet-4-5": "anthropic:claude-sonnet-4-5-20250929",
    "claude-opus-4": "anthropic:claude-opus-4-20250514",
    "claude-haiku-3-5": "anthropic:claude-3-5-haiku-20241022",
    # OpenAI GPT
    "gpt-4o": "openai:gpt-4o",
    "gpt-4o-mini": "openai:gpt-4o-mini",
    "o3-mini": "openai:o3-mini",
    # DeepSeek
    "deepseek-chat": "openai:deepseek-chat",
    "deepseek-reasoner": "openai:deepseek-reasoner",
    # Google Gemini
    "gemini-2.5-pro": "google_genai:gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash": "google_genai:gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash": "google_genai:gemini-2.0-flash",
}


def resolve_model(model_str: str) -> str:
    """Resolve a model string, expanding aliases if needed.

    Args:
        model_str: Either a full provider:model string (e.g. ``"anthropic:claude-sonnet-4-5-20250929"``)
            or a short alias (e.g. ``"claude-sonnet-4-5"``).

    Returns:
        A fully qualified ``provider:model`` string for ``init_chat_model``.
    """
    if ":" in model_str:
        # Already a full provider:model string
        return model_str
    alias = MODEL_ALIASES.get(model_str)
    if alias:
        return alias
    # Fallback: treat as openai-compatible provider (works for DeepSeek, etc.)
    return f"openai:{model_str}"


@dataclass(frozen=True)
class AgentConfig:
    """Immutable global configuration for the agent system.

    Values are resolved from environment variables with sensible defaults.
    """

    # --- Model ---
    primary_model: str = field(
        default_factory=lambda: resolve_model(os.getenv("PRIMARY_MODEL", "claude-sonnet-4-5"))
    )
    """Model identifier for the orchestrator. Supports aliases like ``claude-sonnet-4-5``."""

    subagent_model: str = field(
        default_factory=lambda: resolve_model(os.getenv("SUBAGENT_MODEL", "claude-sonnet-4-5"))
    )
    """Model identifier for sub-agents. Can differ from primary_model."""

    research_model: str = field(
        default_factory=lambda: resolve_model(os.getenv("RESEARCH_MODEL", "claude-sonnet-4-5"))
    )
    """Model identifier for the research sub-agent."""

    fallback_model: str = field(
        default_factory=lambda: resolve_model(os.getenv("FALLBACK_MODEL", "gpt-4o-mini"))
    )
    """Lightweight model used for summarization / classification tasks."""

    model_temperature: float = field(
        default_factory=lambda: float(os.getenv("MODEL_TEMPERATURE", "0.0"))
    )
    """Default temperature for all models."""

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

    # --- Server ---
    server_host: str = field(
        default_factory=lambda: os.getenv("SERVER_HOST", "0.0.0.0")
    )
    """SSE server bind host."""

    server_port: int = field(
        default_factory=lambda: int(os.getenv("SERVER_PORT", "8000"))
    )
    """SSE server bind port."""

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
