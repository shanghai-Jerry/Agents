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
from pathlib import Path

from dotenv import load_dotenv

from agents.config import AgentConfig
from agents.orchestrator import create_orchestrator
from agents.registry import AgentRegistry, SubAgentConfig
from agents.permissions import PermissionManager
from agents.resources import resource_registry
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
    4. Create a ``permissions.yaml`` in the subagent directory
    """
    from pathlib import Path as _Path

    # --- Register all resources FIRST ---
    # This must happen before create_*_subagent() calls so that
    # get_default_tools() returns the complete set of tools.
    import tools  # noqa: F401 — registers core tools via @register_tool
    tools.import_optional_tools()  # registers tavily, sandbox, etc.

    from skills import discover_skills
    discover_skills()

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
            permissions_path=_Path("subagents/general/permissions.yaml"),
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
                permissions_path=_Path("subagents/researcher/permissions.yaml"),
            )
        )
    except ImportError as e:
        logging.getLogger(__name__).warning(
            "Research sub-agent not available: %s. "
            "Install tavily-python to enable: pip install tavily-python",
            e,
        )

    # --- Coder sub-agent (Modal sandbox) ---
    try:
        from subagents.coder import create_coder_subagent

        coder_config = create_coder_subagent(model=config.coder_model)
        registry.register(
            SubAgentConfig(
                name=coder_config["name"],
                description=coder_config["description"],
                system_prompt=coder_config["system_prompt"],
                tools=coder_config["tools"],
                max_iterations=10,
                enabled=True,
                model=config.coder_model,
                permissions_path=_Path("subagents/coder/permissions.yaml"),
            )
        )
    except ImportError as e:
        logging.getLogger(__name__).warning(
            "Coder sub-agent not available: %s. "
            "Install modal to enable: pip install modal",
            e,
        )

    # --- Apply permissions ---
    permission_manager = PermissionManager(registry=resource_registry)
    registry.apply_permissions(permission_manager)

    return registry


# Build the registry (module-level, cached)
_registry = _build_registry()

# --- Load orchestrator skill permissions ---
_orchestrator_perm_path = Path(__file__).parent / "agents" / "permissions.yaml"
_orchestrator_skills: list[str] | None = None

if _orchestrator_perm_path.exists():
    _orch_pm = PermissionManager(registry=resource_registry)
    _orch_pm.load_from_yaml("orchestrator", _orchestrator_perm_path)
    _orchestrator_skills = _orch_pm.get_allowed_skill_paths("orchestrator")
    if _orchestrator_skills:
        logger.info(
            "Orchestrator authorized skills (%d): %s",
            len(_orchestrator_skills),
            ", ".join(s for s in _orchestrator_skills),
        )

# Create the orchestrator agent
agent = create_orchestrator(
    config=AgentConfig(),
    registry=_registry,
    skills=_orchestrator_skills,
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
        print(f"  Coder:     {cfg.coder_model}")
        print(f"  Fallback:  {cfg.fallback_model}")
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--list-resources":
        print("=== Registered Resources ===\n")
        print(resource_registry.summary())
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--list-skills":
        print("=== Discovered Skills ===\n")
        from skills import discover_skills as _disc
        from agents.resources import resource_registry as _reg

        # Run discovery (idempotent — re-registering is a no-op)
        _disc()
        skills = _reg.list_skills()
        if not skills:
            print("  (no skills discovered)")
        else:
            for s in skills:
                print(f"  - {s.name}: {s.description}")
                print(f"    group: {s.group}")
                print(f"    path:  {s.file_path}")
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--list-permissions":
        # Rebuild to ensure permissions are loaded
        print("=== Permission Summary ===\n")
        # Load permissions for display
        from agents.permissions import PermissionConfig
        from pathlib import Path as _Path

        pm = PermissionManager(registry=resource_registry)
        for agent in _registry.list_all_agents():
            if agent.permissions_path:
                perm_path = _Path(agent.permissions_path)
                if perm_path.exists():
                    pm.load_from_yaml(agent.name, perm_path)
        print(pm.summary())
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        print("Starting SSE server...")
        import uvicorn
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
        sys.exit(0)

    print("Agent system initialized.")
    print("  python agent.py --list-agents       # List registered sub-agents")
    print("  python agent.py --list-models       # List model aliases")
    print("  python agent.py --list-resources    # List all registered tools/skills")
    print("  python agent.py --list-skills       # List discovered skills")
    print("  python agent.py --list-permissions  # Show permission configuration")
    print("  python agent.py --serve             # Start SSE chat server")
    print("  langgraph dev                       # LangGraph server mode")
