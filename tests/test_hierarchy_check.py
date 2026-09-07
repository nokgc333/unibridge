"""core/hierarchy_check.py のテスト（TC-008〜010）。"""

from __future__ import annotations

import re
from pathlib import Path

from pxr import Usd, UsdGeom

from core.hierarchy_check import NamingRule, check_naming
from core.report_models import DiffCategory


def _make_stage(path: Path) -> Usd.Stage:
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    # rootはScope（命名規則が「/親/xform_xxx」の2階層のみを想定するため、
    # rootそのものはXform型にしない。"all"フォールバック規則(パターン'.*')の対象になる）。
    root = stage.DefinePrim("/root", "Scope")
    stage.SetDefaultPrim(root)
    return stage


DEFAULT_RULES = [
    NamingRule(
        pattern=re.compile(r"^/[a-zA-Z0-9_]+/xform_[a-z0-9_]+$"),
        applies_to_prim_type="Xform",
        description="Xform naming",
        rename_hint="xform_{seq:03d}",
    ),
    NamingRule(
        pattern=re.compile(r"^/[a-zA-Z0-9_]+/geo_[a-z0-9_]+$"),
        applies_to_prim_type="Mesh",
        description="Mesh naming",
        rename_hint="geo_{seq:03d}",
    ),
]


class TestCheckNaming:
    def test_conforming_names_produce_no_violation(self, tmp_path: Path) -> None:
        stage = _make_stage(tmp_path / "a.usda")
        stage.DefinePrim("/root/xform_hero", "Xform")
        stage.DefinePrim("/root/geo_body", "Mesh")

        entries = check_naming(stage, DEFAULT_RULES, exclude_patterns=[])

        assert entries == []

    def test_non_conforming_xform_name_is_reported(self, tmp_path: Path) -> None:
        stage = _make_stage(tmp_path / "b.usda")
        stage.DefinePrim("/root/Hero", "Xform")

        entries = check_naming(stage, DEFAULT_RULES, exclude_patterns=[])

        violations = [e for e in entries if e.category == DiffCategory.NAMING_VIOLATION]
        assert len(violations) == 1
        assert violations[0].target_path == "/root/Hero"
        assert "hint" in violations[0].message

    def test_excluded_path_pattern_is_skipped(self, tmp_path: Path) -> None:
        stage = _make_stage(tmp_path / "c.usda")
        stage.DefinePrim("/root/Hero_WIP", "Xform")

        entries = check_naming(stage, DEFAULT_RULES, exclude_patterns=[re.compile(r"^/.*_WIP.*$")])

        assert entries == []

    def test_prim_type_without_applicable_rule_is_skipped(self, tmp_path: Path) -> None:
        stage = _make_stage(tmp_path / "d.usda")
        stage.DefinePrim("/root/SomeCamera", "Camera")

        rules = [DEFAULT_RULES[0]]  # Xformのみの規則、Cameraには適用規則なし
        entries = check_naming(stage, rules, exclude_patterns=[])

        assert entries == []

    def test_all_fallback_rule_applies_to_unmatched_type(self, tmp_path: Path) -> None:
        stage = _make_stage(tmp_path / "e.usda")
        stage.DefinePrim("/root/SomeCamera", "Camera")

        rules = DEFAULT_RULES + [
            NamingRule(
                pattern=re.compile(r"^/root/cam_.*$"),
                applies_to_prim_type="all",
                description="fallback",
            )
        ]
        entries = check_naming(stage, rules, exclude_patterns=[])

        violations = [e for e in entries if e.target_path == "/root/SomeCamera"]
        assert len(violations) == 1
