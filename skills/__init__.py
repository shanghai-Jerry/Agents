"""Skills package — auto-discovery from directory structure.

Skills are Markdown-based capability templates loaded by deepagents' SkillsMiddleware.
Each skill lives in its own sub-directory under ``skills/`` with a ``SKILL.md`` file
containing YAML frontmatter metadata.

**Directory layout**::

    skills/
    ├── __init__.py              # this file
    ├── deep_research/
    │   └── SKILL.md             # YAML frontmatter + markdown body
    └── code_review/
        └── SKILL.md

**SKILL.md format**::

    ---
    name: deep_research          # unique identifier (required)
    description: Deep research    # human-readable description (optional)
    group: research               # functional group (optional, default "default")
    ---

    # Deep Research

    Instructions for the agent when this skill is activated...

To add a new skill:
1. Create a sub-directory under ``skills/`` (e.g. ``skills/my_skill/``)
2. Add a ``SKILL.md`` file with YAML frontmatter
3. Optionally authorize the skill in the agent's ``permissions.yaml``
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from agents.resources import register_skill

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SKILLS_DIR = Path(__file__).parent.resolve()
"""Root directory for skill auto-discovery."""

_SKILL_FILENAME = "SKILL.md"
"""Expected filename inside each skill sub-directory (uppercase)."""

_FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)
"""Regex to extract the YAML frontmatter block from a markdown file."""


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Extract and parse YAML frontmatter from a markdown string.

    Args:
        content: Full content of a ``SKILL.md`` file.

    Returns:
        Parsed frontmatter as a dictionary. Returns an empty dict if no
        frontmatter block is found or if parsing fails.
    """
    match = _FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}

    raw = match.group(1)
    try:
        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        logger.warning("Failed to parse YAML frontmatter:\n%s", raw)
        return {}


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------


def discover_skills(
    skills_dir: Path | str | None = None,
) -> list[str]:
    """Scan a directory for skill definitions and register them.

    Walks the target directory looking for sub-directories that contain a
    ``SKILL.md`` file. For each file found:

    1. Parse the YAML frontmatter to extract metadata (name, description, group).
    2. Call :func:`~agents.resources.register_skill` to register the skill
       in the global :class:`~agents.resources.ResourceRegistry`.

    Args:
        skills_dir: Directory to scan. Defaults to the package's own directory
            (``skills/``).

    Returns:
        List of skill names that were successfully discovered and registered.
    """
    if skills_dir is None:
        skills_dir = _SKILLS_DIR
    else:
        skills_dir = Path(skills_dir).resolve()

    if not skills_dir.is_dir():
        logger.warning("Skills directory does not exist: %s", skills_dir)
        return []

    discovered: list[str] = []

    for child in sorted(skills_dir.iterdir()):
        # Skip non-directories and hidden directories
        if not child.is_dir() or child.name.startswith("."):
            continue

        skill_file = child / _SKILL_FILENAME
        if not skill_file.is_file():
            # Also support SKILL.md directly in skills/ (flat layout)
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
            meta = _parse_frontmatter(content)

            # Determine skill metadata
            name = meta.get("name") or child.name
            description = meta.get("description", "")
            group = meta.get("group", "default")

            if not name:
                logger.warning(
                    "Skill in %s has no 'name' in frontmatter and directory "
                    "name is empty. Skipping.",
                    child,
                )
                continue

            register_skill(
                name=str(name),
                description=str(description) if description else "",
                group=str(group),
                file_path=str(skill_file),
            )
            discovered.append(str(name))
            logger.info(
                "Discovered skill '%s' (group='%s') from %s",
                name,
                group,
                skill_file,
            )

        except Exception as e:
            logger.warning(
                "Failed to load skill from %s: %s. Skipping.",
                skill_file,
                e,
            )
            continue

    if discovered:
        logger.info(
            "Skill auto-discovery complete: %d skill(s) found in %s",
            len(discovered),
            skills_dir,
        )
    else:
        logger.debug("No skills discovered in %s", skills_dir)

    return discovered
