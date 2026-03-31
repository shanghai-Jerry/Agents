"""Agent System - Main Entry Point.

Creates the orchestrator agent with all registered sub-agents.
This module is the primary entry point for LangGraph deployment.

Usage:
    from agent import agent
    # or run directly: python -m agent
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv

from agents.config import AgentConfig
from agents.orchestrator import create_orchestrator
from agents.registry import AgentRegistry, SubAgentConfig
from subagents.general import create_general_subagent

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _build_registry() -> AgentRegistry:
    """Build and populate the sub-agent registry.

    To add a new sub-agent:
    1. Create a new module under ``subagents/`` (e.g., ``subagents/researcher/``)
    2. Define a ``create_*_subagent()`` factory function
    3. Import and register it here
    """
    registry = AgentRegistry()

    # --- Register sub-agents ---

    # General-purpose sub-agent (default fallback)
    general_config = create_general_subagent()
    registry.register(
        SubAgentConfig(
            name=general_config["name"],
            description=general_config["description"],
            system_prompt=general_config["system_prompt"],
            tools=general_config["tools"],
            max_iterations=3,
            enabled=True,
        )
    )

    # --- Add more sub-agents below ---
    # Example:
    # from subagents.researcher import create_researcher_subagent
    # researcher_config = create_researcher_subagent()
    # registry.register(SubAgentConfig(
    #     name=researcher_config["name"],
    #     description=researcher_config["description"],
    #     system_prompt=researcher_config["system_prompt"],
    #     tools=researcher_config["tools"],
    #     max_iterations=3,
    # ))

    return registry


# Build the registry (module-level, cached)
_registry = _build_registry()

# Create the orchestrator agent
agent = create_orchestrator(
    config=AgentConfig(),
    registry=_registry,
)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--list-agents":
        print("Registered sub-agents:")
        for a in _registry.list_agents():
            tools_names = [getattr(t, "name", str(t)) for t in a.tools]
            print(f"  - {a.name}: {a.description}")
            print(f"    Tools: {', '.join(tools_names) if tools_names else '(default)'}")
            print(f"    Max iterations: {a.max_iterations}")
        sys.exit(0)

    print("Agent system initialized. Use 'python agent.py --list-agents' to see registered sub-agents.")
    print("For LangGraph server, run: langgraph dev")
