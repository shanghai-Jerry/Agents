"""Agent system core package.

Public API:
    - :class:`AgentConfig` — global configuration
    - :func:`create_orchestrator` — build the main orchestrator agent
    - :class:`AgentRegistry` / :class:`SubAgentConfig` — sub-agent management
    - :func:`resolve_model` — model alias resolution
"""

from agents.config import AgentConfig, MODEL_ALIASES, resolve_model
from agents.orchestrator import create_orchestrator
from agents.registry import AgentRegistry, SubAgentConfig
from agents.router import IntentRouter, RouteMatch

__all__ = [
    "AgentConfig",
    "AgentRegistry",
    "MODEL_ALIASES",
    "IntentRouter",
    "RouteMatch",
    "SubAgentConfig",
    "create_orchestrator",
    "resolve_model",
]
