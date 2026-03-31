"""Orchestrator — main agent builder.

Assembles the primary orchestrator agent that serves as the unified entry point
for all user requests. It uses the :class:`IntentRouter` for task routing and
the :class:`AgentRegistry` for sub-agent discovery, then delegates to deepagents'
``create_deep_agent`` under the hood.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from agents.config import AgentConfig
from agents.prompts import (
    DELEGATION_INSTRUCTIONS,
    ORCHESTRATOR_INSTRUCTIONS,
)
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


def create_orchestrator(
    config: AgentConfig | None = None,
    registry: AgentRegistry | None = None,
    extra_tools: list[BaseTool | Any] | None = None,
    model: BaseChatModel | str | None = None,
    skills: list[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Create the main orchestrator agent.

    This is the primary public API for building the agent system. It:
    1. Initializes the model (or uses the one provided).
    2. Builds the system prompt from templates, injecting sub-agent descriptions.
    3. Collects all sub-agent configs from the registry.
    4. Calls ``create_deep_agent`` with the assembled configuration.

    Args:
        config: Global configuration. Uses defaults if not provided.
        registry: Sub-agent registry. Creates an empty one if not provided.
        extra_tools: Additional tools for the orchestrator itself (beyond routing).
        model: Override model. Can be a string (e.g. ``"anthropic:claude-sonnet-4-5-20250929"``)
            or a ``BaseChatModel`` instance. Falls back to ``config.primary_model``.
        skills: Skill file paths to load via ``SkillsMiddleware``.
        **kwargs: Additional keyword arguments forwarded to ``create_deep_agent``.

    Returns:
        A compiled LangGraph state graph (``CompiledStateGraph``).
    """
    if config is None:
        config = AgentConfig()
    if registry is None:
        registry = AgentRegistry()

    # --- Model ---
    if model is None:
        model = init_chat_model(model=config.primary_model, temperature=0.0)
    elif isinstance(model, str):
        model = init_chat_model(model=model, temperature=0.0)

    # --- System prompt ---
    current_date = datetime.now().strftime("%Y-%m-%d")
    capabilities = registry.capabilities_summary()

    system_prompt = (
        ORCHESTRATOR_INSTRUCTIONS
        + "\n\n"
        + capabilities
        + "\n\n"
        + "=" * 80
        + "\n\n"
        + DELEGATION_INSTRUCTIONS.format(
            max_concurrent=config.max_concurrent_subagents,
            max_iterations=config.max_subagent_iterations,
        )
    )

    # --- Sub-agents ---
    subagent_dicts: list[dict[str, Any]] = []
    for agent_config in registry.list_agents():
        formatted = agent_config.format_prompt(date=current_date)
        subagent_dicts.append(formatted.to_dict)

    logger.info(
        "Creating orchestrator with %d sub-agents: %s",
        len(subagent_dicts),
        [d["name"] for d in subagent_dicts],
    )

    # --- Tools ---
    orchestrator_tools = extra_tools or []

    # --- Build the agent ---
    agent = create_deep_agent(
        model=model,
        tools=orchestrator_tools,
        system_prompt=system_prompt,
        subagents=subagent_dicts,
        skills=skills,
        name="orchestrator",
        **kwargs,
    )

    logger.info("Orchestrator agent created successfully.")
    return agent
