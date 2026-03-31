"""Strategic thinking tool for sub-agents.

Provides a deliberate pause for reflection and decision-making during task execution.
All sub-agents can benefit from this tool for self-evaluation and planning.
"""

from langchain_core.tools import tool


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on progress and decision-making.

    Use this tool to analyze your current state and plan next steps.
    This creates a deliberate pause for quality decision-making.

    When to use:
    - After receiving intermediate results: What key information did I find?
    - Before deciding next steps: Do I have enough to proceed comprehensively?
    - When assessing gaps: What specific information or work is still missing?
    - Before concluding: Can I provide a complete and high-quality result now?

    Reflection should address:
    1. Analysis of current findings or progress
    2. Gap assessment — What crucial pieces are still missing?
    3. Quality evaluation — Is the current output sufficient?
    4. Strategic decision — Should I continue or wrap up?

    Args:
        reflection: Your detailed reflection on progress, findings, gaps, and next steps.

    Returns:
        Confirmation that reflection was recorded for decision-making.
    """
    return f"Reflection recorded: {reflection}"
