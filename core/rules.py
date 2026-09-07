"""命名規則YAML読込・バリデーション（仕様書§5.8）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from core.hierarchy_check import NamingRule

REQUIRED_KEYS = {"schema_version", "project_type", "naming_rules"}


class RuleFileError(Exception):
    """命名規則YAMLの読込・検証エラー（E004に対応）。"""


def load_naming_rules(path: Path) -> tuple[list[NamingRule], list[re.Pattern[str]]]:
    """命名規則YAMLを読み込み、NamingRuleのリストとexclude_patternsを返す。

    yaml.safe_load のみを使用する（SEC-001、任意コード実行を防止するため
    yaml.load/full_load/unsafe_loadは使用しない）。
    """
    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuleFileError(f"{path} contains invalid YAML: {exc}") from exc
    except OSError as exc:
        raise RuleFileError(f"{path} could not be read: {exc}") from exc

    if not isinstance(raw, dict):
        raise RuleFileError(f"{path} must be a YAML mapping at the top level")

    missing = REQUIRED_KEYS - raw.keys()
    if missing:
        raise RuleFileError(f"{path} is missing required key(s): {', '.join(sorted(missing))}")

    try:
        rules = [
            NamingRule(
                pattern=re.compile(entry["pattern"]),
                applies_to_prim_type=entry["applies_to_prim_type"],
                description=entry["description"],
                rename_hint=entry.get("rename_hint"),
            )
            for entry in raw["naming_rules"]
        ]
        exclude_patterns = [re.compile(p) for p in raw.get("exclude_patterns", [])]
    except (KeyError, TypeError, re.error) as exc:
        raise RuleFileError(f"{path} has a malformed naming_rules entry: {exc}") from exc

    return rules, exclude_patterns
