"""Agent System - Main Entry Point.

Creates the orchestrator agent with all registered sub-agents.
This module is the primary entry point for LangGraph deployment.

Usage:
    from agent import agent
    # or run directly: python agent.py
    # or start SSE server: python server.py
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
    config = AgentConfig()
    registry = AgentRegistry()

    # --- General-purpose sub-agent (default fallback) ---
    general_config = create_general_subagent()
    registry.register(
        SubAgentConfig(
            name=general_config["name"],
            description=general_config["description"],
            system_prompt=general_config["system_prompt"],
            tools=general_config["tools"],
            max_iterations=3,
            enabled=True,
            model=config.subagent_model,
        )
    )

    # --- Research sub-agent ---
    try:
        from subagents.researcher import create_researcher_subagent

        researcher_config = create_researcher_subagent(model=config.research_model)
        registry.register(
            SubAgentConfig(
                name=researcher_config["name"],
                description=researcher_config["description"],
                system_prompt=researcher_config["system_prompt"],
                tools=researcher_config["tools"],
                max_iterations=5,
                enabled=True,
                model=config.research_model,
            )
        )
    except ImportError as e:
        logging.getLogger(__name__).warning(
            "Research sub-agent not available: %s. "
            "Install tavily-python to enable: pip install tavily-python",
            e,
        )

    # --- Add more sub-agents below ---
    # Example:
    # from subagents.coder import create_coder_subagent
    # coder_config = create_coder_subagent()
    # registry.register(SubAgentConfig(
    #     name=coder_config["name"],
    #     description=coder_config["description"],
    #     system_prompt=coder_config["system_prompt"],
    #     tools=coder_config["tools"],
    #     max_iterations=10,
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
            if a.model:
                print(f"    Model: {a.model}")
            print(f"    Tools: {', '.join(tools_names) if tools_names else '(default)'}")
            print(f"    Max iterations: {a.max_iterations}")
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--list-models":
        from agents.config import MODEL_ALIASES, resolve_model

        print("Available model aliases:")
        for alias, full in MODEL_ALIASES.items():
            print(f"  {alias:25s} -> {full}")
        print(f"\nCurrent config:")
        cfg = AgentConfig()
        print(f"  Primary:   {cfg.primary_model}")
        print(f"  SubAgent:  {cfg.subagent_model}")
        print(f"  Research:  {cfg.research_model}")
        print(f"  Fallback:  {cfg.fallback_model}")
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        print("Starting SSE server...")
        import uvicorn
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
        sys.exit(0)

    print("Agent system initialized.")
    print("  python agent.py --list-agents   # List registered sub-agents")
    print("  python agent.py --list-models   # List model aliases")
    print("  python agent.py --serve         # Start SSE chat server")
    print("  langgraph dev                   # LangGraph server mode")
