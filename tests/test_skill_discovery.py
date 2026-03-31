"""Tests for skill auto-discovery.

Covers:
- discover_skills() scanning and registration
- YAML frontmatter parsing
- Error tolerance (bad YAML, missing files, no frontmatter)
- Edge cases (directory fallback naming, hidden directories)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.resources import resource_registry
from skills import _parse_frontmatter, discover_skills


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with test skill sub-directories."""
    # valid skill with full frontmatter
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "SKILL.md").write_text(
        "---\nname: deep_research\ndescription: Deep multi-step research\ngroup: research\n---\n\n# Deep Research\n",
        encoding="utf-8",
    )

    # minimal frontmatter (no description, no group)
    minimal_dir = tmp_path / "minimal_skill"
    minimal_dir.mkdir()
    (minimal_dir / "SKILL.md").write_text(
        "---\nname: minimal\n---\n\n# Minimal\n", encoding="utf-8",
    )

    # no name — fallback to directory name
    no_name_dir = tmp_path / "fallback_name"
    no_name_dir.mkdir()
    (no_name_dir / "SKILL.md").write_text(
        "---\ndescription: Uses directory name\n---\n\n# Fallback\n", encoding="utf-8",
    )

    # no frontmatter at all — fallback to directory name
    no_fm_dir = tmp_path / "no_frontmatter"
    no_fm_dir.mkdir()
    (no_fm_dir / "SKILL.md").write_text(
        "# Just Markdown\nNo frontmatter here.\n", encoding="utf-8",
    )

    # invalid YAML in frontmatter
    bad_yaml_dir = tmp_path / "bad_yaml"
    bad_yaml_dir.mkdir()
    (bad_yaml_dir / "SKILL.md").write_text(
        "---\nname: [invalid yaml\n---\n\n# Bad\n", encoding="utf-8",
    )

    # directory with no SKILL.md (should be skipped)
    (tmp_path / "empty_dir").mkdir()

    # hidden directory (should be skipped)
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "SKILL.md").write_text("---\nname: hidden\n---\n\n", encoding="utf-8")

    return tmp_path


class TestParseFrontmatter:

    def test_valid_frontmatter(self) -> None:
        content = "---\nname: test\ndescription: A test skill\n---\n\n# Body\n"
        result = _parse_frontmatter(content)
        assert result["name"] == "test"
        assert result["description"] == "A test skill"

    def test_no_frontmatter(self) -> None:
        result = _parse_frontmatter("# Just a header\nSome text\n")
        assert result == {}

    def test_empty_frontmatter(self) -> None:
        result = _parse_frontmatter("---\n---\n\n# Body\n")
        assert result == {}

    def test_invalid_yaml(self) -> None:
        result = _parse_frontmatter("---\nname: [broken\n---\n\n")
        assert result == {}

    def test_multiline_description(self) -> None:
        content = "---\nname: my_skill\ndescription: >\n  Line 1\n  Line 2\n---\n"
        result = _parse_frontmatter(content)
        assert result["name"] == "my_skill"
        assert "Line 1" in result["description"]


class TestDiscoverSkills:

    def test_discovers_valid_skills(self, skills_dir: Path) -> None:
        names = discover_skills(skills_dir=skills_dir)
        assert "deep_research" in names
        assert "minimal" in names
        assert "fallback_name" in names

    def test_skips_missing_skill_file(self, skills_dir: Path) -> None:
        names = discover_skills(skills_dir=skills_dir)
        assert "empty_dir" not in names

    def test_skips_hidden_directories(self, skills_dir: Path) -> None:
        names = discover_skills(skills_dir=skills_dir)
        assert "hidden" not in names

    def test_fallback_to_directory_name(self, skills_dir: Path) -> None:
        names = discover_skills(skills_dir=skills_dir)
        assert "fallback_name" in names

    def test_no_frontmatter_uses_dir_name(self, skills_dir: Path) -> None:
        names = discover_skills(skills_dir=skills_dir)
        assert "no_frontmatter" in names

    def test_bad_yaml_skipped(self, skills_dir: Path) -> None:
        names = discover_skills(skills_dir=skills_dir)
        # bad YAML → parse returns {} → name fallback to dir name
        assert "bad_yaml" in names

    def test_nonexistent_directory(self) -> None:
        names = discover_skills(skills_dir="/nonexistent/path")
        assert names == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        empty = tmp_path / "no_skills"
        empty.mkdir()
        names = discover_skills(skills_dir=empty)
        assert names == []

    def test_registered_in_resource_registry(self, skills_dir: Path) -> None:
        discover_skills(skills_dir=skills_dir)
        meta = resource_registry.get_skill("deep_research")
        assert meta is not None
        assert meta.group == "research"
        assert "Deep multi-step research" in meta.description
        assert str(meta.file_path).endswith("research/SKILL.md")

    def test_idempotent_registration(self, skills_dir: Path) -> None:
        discover_skills(skills_dir=skills_dir)
        discover_skills(skills_dir=skills_dir)  # should not raise
