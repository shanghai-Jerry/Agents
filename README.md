# Agents

A multi-agent system built on [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents), featuring an orchestrator-driven task routing architecture with extensible sub-agents.

## Architecture

```
User Request
    │
    ▼
┌──────────────────────┐
│   Main Agent (Orch.)  │  ← Unified entry point
│  ┌─────────────────┐  │
│  │  Intent Router   │  │  ← Rule-based classifier + LLM fallback
│  └────────┬────────┘  │
└───────────┼──────────┘
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
┌──────┐ ┌──────┐ ┌──────┐
│Sub-A │ │Sub-B │ │Sub-C │  ← Independent tool sets
│      │ │      │ │ ...  │
└──────┘ └──────┘ └──────┘
```

### Key Design Decisions

- **Hybrid Routing**: Rule/keyword matching first, LLM intent classification as fallback
- **Sub-Agent Isolation**: Each sub-agent has its own `system_prompt` and `tools` whitelist
- **Declarative Registration**: Sub-agents defined as dictionaries (`name`, `description`, `system_prompt`, `tools`)
- **YAML-based Rules**: Intent routing rules configured in `config/agent_rules.yaml`, no code changes needed

## Quick Start

### Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
# Clone the repo
git clone https://github.com/shanghai-Jerry/Agents.git
cd Agents

# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your API keys
```

### Run

**Option 1: Jupyter Notebook**
```bash
uv run jupyter notebook notebooks/explore.ipynb
```

**Option 2: LangGraph Server**
```bash
uv pip install -e ".[langgraph]"
langgraph dev
```

## Project Structure

```
├── agent.py                # Main entry point - creates the orchestrator agent
├── agents/                 # Core package
│   ├── config.py           # Global configuration
│   ├── registry.py         # Sub-agent registry
│   ├── router.py           # Hybrid intent router
│   ├── orchestrator.py     # Main agent builder
│   └── prompts/            # Prompt templates
├── subagents/              # Sub-agent definitions
│   └── general/            # General-purpose sub-agent (example)
├── tools/                  # Shared tools
│   ├── thinking.py         # think_tool
│   └── utils.py            # Utility helpers
├── skills/                 # Skill definitions (Markdown)
├── config/
│   └── agent_rules.yaml    # Intent routing rules
├── tests/                  # Unit tests
└── notebooks/              # Jupyter notebooks
```

## Adding a New Sub-Agent

1. Create a new directory under `subagents/` (e.g., `subagents/coder/`)
2. Define `prompts.py` with the system prompt
3. Define `tools.py` with agent-specific tools
4. Register in `subagents/__init__.py`
5. Add routing rules in `config/agent_rules.yaml` (optional)

## Adding a New Tool

1. Add tool function in `tools/` using the `@tool` decorator
2. Import and include in the desired sub-agent's tools list

## License

Apache License 2.0
