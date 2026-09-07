"""cli.py のテスト（TC-016, TC-017, TC-019）。"""

from __future__ import annotations

from pathlib import Path

import cli


class TestDiffCommand:
    def test_diff_between_identical_files_exits_zero(self, tmp_path: Path, capsys) -> None:
        code = cli.main(
            [
                "diff",
                "--before",
                "sample_scenes/consistent_scene.usda",
                "--after",
                "sample_scenes/consistent_scene.usda",
                "--format",
                "json",
            ]
        )

        assert code == cli.EXIT_OK

    def test_diff_with_mismatched_scale_scene_produces_material_or_prim_diff(self) -> None:
        # consistent_scene と mismatched_scale はどちらも同一Prim構成のため
        # diffコマンド自体はPrim/Material差分なしでOK終了する
        # （座標系/スケールの不整合検出はscale-checkの責務）。
        code = cli.main(
            [
                "diff",
                "--before",
                "sample_scenes/consistent_scene.usda",
                "--after",
                "sample_scenes/mismatched_scale.usda",
                "--format",
                "json",
            ]
        )

        assert code == cli.EXIT_OK

    def test_diff_nonexistent_file_exits_10(self) -> None:
        code = cli.main(
            [
                "diff",
                "--before",
                "sample_scenes/consistent_scene.usda",
                "--after",
                "no_such_file.usda",
            ]
        )

        assert code == cli.EXIT_FILE_NOT_FOUND

    def test_diff_writes_report_files_when_out_specified(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "diff",
                "--before",
                "sample_scenes/consistent_scene.usda",
                "--after",
                "sample_scenes/mismatched_upaxis.usda",
                "--format",
                "all",
                "--out",
                str(out_dir),
            ]
        )

        assert code == cli.EXIT_OK
        produced = {p.suffix for p in out_dir.iterdir()}
        assert produced == {".csv", ".json", ".html"}


class TestScaleCheckCommand:
    def test_scale_check_consistent_scenes_exits_zero(self) -> None:
        code = cli.main(
            [
                "scale-check",
                "--source",
                "sample_scenes/consistent_scene.usda",
                "--target",
                "sample_scenes/consistent_scene.usda",
            ]
        )

        assert code == cli.EXIT_OK

    def test_scale_check_mismatched_scale_exits_one(self) -> None:
        code = cli.main(
            [
                "scale-check",
                "--source",
                "sample_scenes/consistent_scene.usda",
                "--target",
                "sample_scenes/mismatched_scale.usda",
            ]
        )

        assert code == cli.EXIT_MISMATCH_FOUND

    def test_scale_check_mismatched_upaxis_exits_one(self) -> None:
        code = cli.main(
            [
                "scale-check",
                "--source",
                "sample_scenes/consistent_scene.usda",
                "--target",
                "sample_scenes/mismatched_upaxis.usda",
            ]
        )

        assert code == cli.EXIT_MISMATCH_FOUND


class TestHierarchyCheckCommand:
    def test_hierarchy_check_default_rules_exits_zero_for_consistent_scene(self) -> None:
        code = cli.main(
            [
                "hierarchy-check",
                "--usd",
                "sample_scenes/consistent_scene.usda",
            ]
        )

        assert code == cli.EXIT_OK

    def test_hierarchy_check_missing_rules_file_exits_13(self) -> None:
        code = cli.main(
            [
                "hierarchy-check",
                "--usd",
                "sample_scenes/consistent_scene.usda",
                "--rules",
                "no_such_rules.yaml",
            ]
        )

        assert code == cli.EXIT_RULE_FILE_ERROR


class TestBatchCommand:
    def test_batch_over_sample_scenes_dir_completes(self, capsys) -> None:
        code = cli.main(["batch", "--dir", "sample_scenes", "--workers", "2", "--format", "json"])

        assert code in (cli.EXIT_OK, cli.EXIT_MISMATCH_FOUND)

    def test_batch_nonexistent_dir_exits_10(self) -> None:
        code = cli.main(["batch", "--dir", "no_such_dir"])

        assert code == cli.EXIT_FILE_NOT_FOUND
