"""Tests for skill discovery."""

import logging
from pathlib import Path

from framework.skills.discovery import DiscoveryConfig, SkillDiscovery
from framework.skills.parser import ParsedSkill


def _write_skill(base: Path, name: str, description: str = "A test skill.") -> Path:
    """Create a minimal skill directory with SKILL.md."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nInstructions.\n",
        encoding="utf-8",
    )
    return skill_dir


class TestSkillDiscovery:
    def test_discover_project_skills(self, tmp_path):
        # Create project-level skills
        agents_skills = tmp_path / ".agents" / "skills"
        _write_skill(agents_skills, "skill-a")
        _write_skill(agents_skills, "skill-b")

        discovery = SkillDiscovery(
            DiscoveryConfig(
                project_root=tmp_path,
                skip_user_scope=True,
                skip_framework_scope=True,
            )
        )
        skills = discovery.discover()

        names = {s.name for s in skills}
        assert "skill-a" in names
        assert "skill-b" in names
        assert all(s.source_scope == "project" for s in skills)

    def test_hive_skills_path(self, tmp_path):
        hive_skills = tmp_path / ".hive" / "skills"
        _write_skill(hive_skills, "hive-skill")

        discovery = SkillDiscovery(
            DiscoveryConfig(
                project_root=tmp_path,
                skip_user_scope=True,
                skip_framework_scope=True,
            )
        )
        skills = discovery.discover()

        assert len(skills) == 1
        assert skills[0].name == "hive-skill"

    def test_collision_project_overrides_user(self, tmp_path, monkeypatch):
        # User-level skill
        user_skills = tmp_path / "home" / ".agents" / "skills"
        _write_skill(user_skills, "shared-skill", "User version")

        # Project-level skill with same name
        project_skills = tmp_path / "project" / ".agents" / "skills"
        _write_skill(project_skills, "shared-skill", "Project version")

        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        discovery = SkillDiscovery(
            DiscoveryConfig(
                project_root=tmp_path / "project",
                skip_framework_scope=True,
            )
        )
        skills = discovery.discover()

        matching = [s for s in skills if s.name == "shared-skill"]
        assert len(matching) == 1
        assert matching[0].description == "Project version"

    def test_collision_hive_overrides_agents(self, tmp_path):
        # Cross-client path
        agents_skills = tmp_path / ".agents" / "skills"
        _write_skill(agents_skills, "override-test", "Agents version")

        # Hive-specific path (higher precedence)
        hive_skills = tmp_path / ".hive" / "skills"
        _write_skill(hive_skills, "override-test", "Hive version")

        discovery = SkillDiscovery(
            DiscoveryConfig(
                project_root=tmp_path,
                skip_user_scope=True,
                skip_framework_scope=True,
            )
        )
        skills = discovery.discover()

        matching = [s for s in skills if s.name == "override-test"]
        assert len(matching) == 1
        assert matching[0].description == "Hive version"

    def test_skips_git_and_node_modules(self, tmp_path):
        skills_dir = tmp_path / ".agents" / "skills"
        _write_skill(skills_dir / ".git", "git-skill")
        _write_skill(skills_dir / "node_modules", "npm-skill")
        _write_skill(skills_dir, "real-skill")

        discovery = SkillDiscovery(
            DiscoveryConfig(
                project_root=tmp_path,
                skip_user_scope=True,
                skip_framework_scope=True,
            )
        )
        skills = discovery.discover()

        names = {s.name for s in skills}
        assert "real-skill" in names
        assert "git-skill" not in names
        assert "npm-skill" not in names

    def test_empty_scan(self, tmp_path):
        discovery = SkillDiscovery(
            DiscoveryConfig(
                project_root=tmp_path,
                skip_user_scope=True,
                skip_framework_scope=True,
            )
        )
        skills = discovery.discover()
        assert skills == []

    def test_framework_scope_loads_defaults(self):
        """Framework scope should find the built-in default skills."""
        discovery = SkillDiscovery(
            DiscoveryConfig(
                skip_user_scope=True,
            )
        )
        skills = discovery.discover()

        framework_skills = [s for s in skills if s.source_scope == "framework"]
        names = {s.name for s in framework_skills}
        assert "hive.note-taking" in names
        assert "hive.colony-progress-tracker" in names

    def test_max_depth_limit(self, tmp_path):
        # Create a skill nested beyond max_depth
        deep = tmp_path / ".agents" / "skills" / "a" / "b" / "c" / "d" / "e"
        _write_skill(deep, "too-deep")

        discovery = SkillDiscovery(
            DiscoveryConfig(
                project_root=tmp_path,
                skip_user_scope=True,
                skip_framework_scope=True,
                max_depth=2,
            )
        )
        skills = discovery.discover()
        assert not any(s.name == "too-deep" for s in skills)

    def test_framework_preset_collision_is_suppressed(self, caplog):
        discovery = SkillDiscovery(DiscoveryConfig(skip_user_scope=True))
        framework_skill = ParsedSkill(
            name="hive.browser-automation",
            description="framework",
            location="/framework/_default_skills/browser-automation/SKILL.md",
            base_dir="/framework/_default_skills/browser-automation",
            source_scope="framework",
            body="framework",
        )
        preset_skill = ParsedSkill(
            name="hive.browser-automation",
            description="preset",
            location="/framework/_preset_skills/browser-automation/SKILL.md",
            base_dir="/framework/_preset_skills/browser-automation",
            source_scope="preset",
            body="preset",
        )

        with caplog.at_level(logging.WARNING):
            resolved = discovery._resolve_collisions([framework_skill, preset_skill])

        assert len(resolved) == 1
        assert resolved[0].source_scope == "preset"
        assert all(
            (record.__dict__.get("skill_error_code") or "") != "SKILL_COLLISION"
            for record in caplog.records
        )

    def test_user_project_collision_still_warns(self, caplog):
        discovery = SkillDiscovery(DiscoveryConfig(skip_user_scope=True))
        user_skill = ParsedSkill(
            name="shared-skill",
            description="user",
            location="/home/.agents/skills/shared-skill/SKILL.md",
            base_dir="/home/.agents/skills/shared-skill",
            source_scope="user",
            body="user",
        )
        project_skill = ParsedSkill(
            name="shared-skill",
            description="project",
            location="/project/.agents/skills/shared-skill/SKILL.md",
            base_dir="/project/.agents/skills/shared-skill",
            source_scope="project",
            body="project",
        )

        with caplog.at_level(logging.WARNING):
            resolved = discovery._resolve_collisions([user_skill, project_skill])

        assert len(resolved) == 1
        assert resolved[0].source_scope == "project"
        assert any(
            record.__dict__.get("skill_error_code") == "SKILL_COLLISION"
            for record in caplog.records
        )
