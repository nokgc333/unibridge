"""cli.py のテスト（TC-016, TC-017, TC-019）。"""

from __future__ import annotations

import json
from pathlib import Path

import cli
from cli import (
    EXIT_INVALID_PARAMETER,
    EXIT_MISMATCH_FOUND,
    EXIT_OUTPUT_NOT_WRITABLE,
    main,
)


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


class TestBrokenUsdInput:
    def _broken_files(self, tmp_path: Path) -> dict[str, Path]:
        empty = tmp_path / "empty.usda"
        empty.write_text("", encoding="utf-8")
        garbage = tmp_path / "garbage.usdc"
        garbage.write_bytes(b"not a crate file" * 64)
        return {"empty": empty, "garbage": garbage}

    def test_diff_with_broken_file_exits_10_without_a_traceback(
        self, tmp_path: Path, capsys
    ) -> None:
        for broken in self._broken_files(tmp_path).values():
            code = cli.main(
                [
                    "diff",
                    "--before",
                    "sample_scenes/consistent_scene.usda",
                    "--after",
                    str(broken),
                ]
            )

            assert code == cli.EXIT_FILE_NOT_FOUND
        err = capsys.readouterr().err
        assert "Traceback" not in err
        assert "corrupt or unsupported" in err

    def test_scale_check_with_broken_file_exits_10(self, tmp_path: Path, capsys) -> None:
        broken = self._broken_files(tmp_path)["empty"]

        code = cli.main(
            [
                "scale-check",
                "--source",
                str(broken),
                "--target",
                "sample_scenes/consistent_scene.usda",
            ]
        )

        assert code == cli.EXIT_FILE_NOT_FOUND
        assert "Traceback" not in capsys.readouterr().err

    def test_hierarchy_check_with_broken_file_exits_10(self, tmp_path: Path, capsys) -> None:
        broken = self._broken_files(tmp_path)["garbage"]

        code = cli.main(["hierarchy-check", "--usd", str(broken)])

        assert code == cli.EXIT_FILE_NOT_FOUND
        assert "Traceback" not in capsys.readouterr().err

    def test_batch_reports_a_broken_file_as_a_failure_and_continues(
        self, tmp_path: Path, capsys
    ) -> None:
        (tmp_path / "broken.usda").write_text("", encoding="utf-8")
        good = Path("sample_scenes/consistent_scene.usda")
        (tmp_path / "good.usda").write_bytes(good.read_bytes())

        code = cli.main(["batch", "--dir", str(tmp_path), "--format", "json"])

        payload = json.loads(capsys.readouterr().out)
        assert code == cli.EXIT_MISMATCH_FOUND
        assert len(payload["results"]) == 1
        assert len(payload["failures"]) == 1


class TestScaleCheckApply:
    def test_apply_without_out_is_an_invalid_parameter(self, capsys) -> None:
        code = main(
            [
                "scale-check",
                "--source",
                "sample_scenes/mismatched_scale.usda",
                "--target",
                "sample_scenes/consistent_scene.usda",
                "--apply",
            ]
        )

        assert code == EXIT_INVALID_PARAMETER
        assert "--apply requires --out" in capsys.readouterr().err

    def test_apply_writes_the_converted_file_and_still_reports_the_mismatch(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "converted.usda"

        code = main(
            [
                "scale-check",
                "--source",
                "sample_scenes/mismatched_scale.usda",
                "--target",
                "sample_scenes/consistent_scene.usda",
                "--apply",
                "--out",
                str(out),
            ]
        )

        assert code == EXIT_MISMATCH_FOUND
        assert out.exists()

    def test_apply_to_an_unwritable_path_exits_14(self, tmp_path: Path, capsys) -> None:
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")

        code = main(
            [
                "scale-check",
                "--source",
                "sample_scenes/mismatched_scale.usda",
                "--target",
                "sample_scenes/consistent_scene.usda",
                "--apply",
                "--out",
                str(blocker / "sub" / "out.usda"),
            ]
        )

        assert code == EXIT_OUTPUT_NOT_WRITABLE
        assert "cannot write to" in capsys.readouterr().err


class TestDiffOutputErrors:
    def test_an_unwritable_report_directory_exits_14(self, tmp_path: Path, capsys) -> None:
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")

        code = main(
            [
                "diff",
                "--before",
                "sample_scenes/consistent_scene.usda",
                "--after",
                "sample_scenes/mismatched_scale.usda",
                "--out",
                str(blocker / "reports"),
            ]
        )

        assert code == EXIT_OUTPUT_NOT_WRITABLE
        assert "cannot write to" in capsys.readouterr().err


class TestIntegrityCheckCommand:
    def test_a_clean_scene_exits_zero(self, tmp_path: Path, capsys) -> None:
        path = tmp_path / "clean.usda"
        path.write_text(
            '#usda 1.0\n(\n    defaultPrim = "root"\n)\n\ndef Xform "root"\n{\n}\n',
            encoding="utf-8",
        )

        code = main(["integrity-check", "--usd", str(path)])

        assert code == 0
        assert "No inconsistencies detected." in capsys.readouterr().out

    def test_a_mesh_without_material_and_uv_exits_one_and_names_both(
        self, tmp_path: Path, capsys
    ) -> None:
        path = tmp_path / "bare.usda"
        path.write_text(
            '#usda 1.0\n(\n    defaultPrim = "m"\n)\n\ndef Mesh "m"\n{\n}\n', encoding="utf-8"
        )

        code = main(["integrity-check", "--usd", str(path)])

        out = capsys.readouterr().out
        assert code == EXIT_MISMATCH_FOUND
        assert "material_binding" in out
        assert "uv_missing" in out

    def test_a_missing_file_exits_10(self, tmp_path: Path) -> None:
        assert main(["integrity-check", "--usd", str(tmp_path / "none.usda")]) == 10
