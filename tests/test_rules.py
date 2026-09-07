"""core/rules.py のテスト（TC-016, SEC-001）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.rules import RuleFileError, load_naming_rules


class TestLoadNamingRules:
    def test_default_rules_file_loads_successfully(self) -> None:
        rules, exclude_patterns = load_naming_rules(Path("rules/default.yaml"))

        assert len(rules) == 3
        assert len(exclude_patterns) == 1

    def test_missing_required_key_raises_rule_file_error(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("schema_version: 1\n", encoding="utf-8")

        with pytest.raises(RuleFileError):
            load_naming_rules(bad_yaml)

    def test_invalid_yaml_syntax_raises_rule_file_error(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("naming_rules: [unterminated", encoding="utf-8")

        with pytest.raises(RuleFileError):
            load_naming_rules(bad_yaml)

    def test_non_mapping_top_level_raises_rule_file_error(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("- just\n- a\n- list\n", encoding="utf-8")

        with pytest.raises(RuleFileError):
            load_naming_rules(bad_yaml)

    def test_nonexistent_file_raises_rule_file_error(self, tmp_path: Path) -> None:
        with pytest.raises(RuleFileError):
            load_naming_rules(tmp_path / "does_not_exist.yaml")

    def test_uses_safe_load_only(self) -> None:
        """SEC-001: yaml.safe_loadのみを使用していることをソース走査で確認する。"""
        source = Path("core/rules.py").read_text(encoding="utf-8")

        assert "yaml.safe_load" in source
        assert "yaml.load(" not in source
        assert "yaml.unsafe_load" not in source
        assert "yaml.full_load" not in source
