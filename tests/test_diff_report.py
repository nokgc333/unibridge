"""core/diff_report.py のテスト（TC-011〜013）。"""

from __future__ import annotations

import json
from pathlib import Path

from pxr import Usd, UsdGeom, UsdShade

from core.diff_report import (
    build_diff_report,
    report_to_csv_rows,
    report_to_html,
    report_to_json,
)
from core.report_models import DiffCategory


def _make_stage(path: Path) -> Usd.Stage:
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    return stage


class TestBuildDiffReport:
    def test_identical_stages_produce_no_diff_entries(self, tmp_path: Path) -> None:
        before = _make_stage(tmp_path / "before.usda")
        before.DefinePrim("/root/geo_body", "Mesh")
        after = _make_stage(tmp_path / "after.usda")
        after.DefinePrim("/root/geo_body", "Mesh")

        report = build_diff_report(before, after, "before", "after")

        assert report.entries == []
        assert report.prim_count_before == report.prim_count_after == 2
        assert report.has_errors is False

    def test_removed_prim_is_reported_as_error(self, tmp_path: Path) -> None:
        before = _make_stage(tmp_path / "before.usda")
        before.DefinePrim("/root/geo_body", "Mesh")
        after = _make_stage(tmp_path / "after.usda")

        report = build_diff_report(before, after, "before", "after")

        removed = [e for e in report.entries if e.category == DiffCategory.PRIM_REMOVED]
        assert len(removed) == 1
        assert removed[0].target_path == "/root/geo_body"
        assert report.has_errors is True

    def test_added_prim_is_reported_as_info(self, tmp_path: Path) -> None:
        before = _make_stage(tmp_path / "before.usda")
        after = _make_stage(tmp_path / "after.usda")
        after.DefinePrim("/root/geo_new", "Mesh")

        report = build_diff_report(before, after, "before", "after")

        added = [e for e in report.entries if e.category == DiffCategory.PRIM_ADDED]
        assert len(added) == 1
        assert added[0].target_path == "/root/geo_new"

    def test_material_count_diff_is_reported_as_warning(self, tmp_path: Path) -> None:
        before = _make_stage(tmp_path / "before.usda")
        after = _make_stage(tmp_path / "after.usda")
        UsdShade.Material.Define(after, "/root/mat_new")

        report = build_diff_report(before, after, "before", "after")

        mat_diff = [e for e in report.entries if e.category == DiffCategory.MATERIAL_COUNT_DIFF]
        assert len(mat_diff) == 1
        assert report.material_count_before == 0
        assert report.material_count_after == 1


class TestReportOutputFormats:
    def test_csv_rows_include_header_and_entries(self, tmp_path: Path) -> None:
        before = _make_stage(tmp_path / "before.usda")
        after = _make_stage(tmp_path / "after.usda")
        after.DefinePrim("/root/geo_new", "Mesh")
        report = build_diff_report(before, after, "before", "after")

        rows = report_to_csv_rows(report)

        assert rows[0] == [
            "category",
            "severity",
            "target_path",
            "message",
            "before_value",
            "after_value",
        ]
        assert len(rows) == 1 + len(report.entries)

    def test_json_output_round_trips_entry_count(self, tmp_path: Path) -> None:
        before = _make_stage(tmp_path / "before.usda")
        after = _make_stage(tmp_path / "after.usda")
        after.DefinePrim("/root/geo_new", "Mesh")
        report = build_diff_report(before, after, "before", "after")

        payload = json.loads(report_to_json(report))

        assert len(payload["entries"]) == len(report.entries)
        assert payload["prim_count_after"] == report.prim_count_after

    def test_html_output_contains_target_paths(self, tmp_path: Path) -> None:
        before = _make_stage(tmp_path / "before.usda")
        after = _make_stage(tmp_path / "after.usda")
        after.DefinePrim("/root/geo_new", "Mesh")
        report = build_diff_report(before, after, "before", "after")

        html = report_to_html(report)

        assert "/root/geo_new" in html
        assert "<table" in html
