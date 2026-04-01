"""Strategic thinking tool for sub-agents.

Provides a deliberate pause for reflection and decision-making during task execution.
All sub-agents can benefit from this tool for self-evaluation and planning.
"""

from agents.resources import register_tool


@register_tool(
    group="core",
    description="Tool for strategic reflection on progress and decision-making.",
)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on progress and decision-making.

    Use this tool to analyze your current state and plan next steps.
    IMPORTANT: Use this tool sparingly — at most ONCE per task, typically
    after gathering initial information. Do NOT call it repeatedly.

    When to use:
    - When you are unsure which approach to take and need to weigh options
    - After gathering all available information, to decide if you have enough

    When NOT to use:
    - After every single action — this wastes time
    - When you already know what to do next — just do it
    - After another think_tool call — one reflection is enough

    Args:
        reflection: Your concise reflection on progress, findings, gaps, and next steps.

    Returns:
        Confirmation with action guidance.
    """
    return (
        f"Reflection recorded: {reflection}\n\n"
        "Now proceed with your next action or deliver your final response. "
        "Do not call think_tool again."
    )
