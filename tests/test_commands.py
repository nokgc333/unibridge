"""commands/ のテスト(共有処理と batch の部品)。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commands import batch
from commands.common import open_stages, print_entries
from commands.exit_codes import EXIT_FILE_NOT_FOUND
from core.report_models import DiffCategory, DiffEntry, Severity

SAMPLES = Path("sample_scenes")


class TestOpenStages:
    def test_opens_every_path_and_keeps_the_order(self) -> None:
        a = SAMPLES / "consistent_scene.usda"
        b = SAMPLES / "mismatched_scale.usda"

        stages = open_stages(a, b)

        assert isinstance(stages, list)
        assert [s.GetRootLayer().realPath for s in stages] == [
            str(a.resolve()),
            str(b.resolve()),
        ]

    def test_a_path_that_cannot_be_opened_gives_the_file_error_code_and_the_reason(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "missing.usda"

        result = open_stages(SAMPLES / "consistent_scene.usda", missing)

        assert result == EXIT_FILE_NOT_FOUND
        assert "does not exist" in capsys.readouterr().err

    def test_stops_at_the_first_path_that_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = open_stages(tmp_path / "first.usda", tmp_path / "second.usda")

        assert result == EXIT_FILE_NOT_FOUND
        err = capsys.readouterr().err
        assert "first.usda" in err
        assert "second.usda" not in err


class TestPrintEntries:
    def test_prints_one_line_for_each_entry(self, capsys: pytest.CaptureFixture[str]) -> None:
        entry = DiffEntry(
            category=DiffCategory.NAMING_VIOLATION,
            severity=Severity.ERROR,
            target_path="/a",
            message="bad",
            before_value=None,
            after_value=None,
        )

        print_entries([entry, entry])

        assert len(capsys.readouterr().out.strip().splitlines()) == 2


class TestBatchParts:
    def test_finds_usd_files_of_the_three_extensions_in_sorted_order(self, tmp_path: Path) -> None:
        for name in ["b.usd", "a.usda", "c.usdc", "d.txt", "e.usdz"]:
            (tmp_path / name).write_text("x", encoding="utf-8")

        names = [p.name for p in batch.find_usd_files(tmp_path)]

        assert names == ["a.usda", "b.usd", "c.usdc"]

    def test_a_directory_without_usd_files_gives_an_empty_list(self, tmp_path: Path) -> None:
        assert batch.find_usd_files(tmp_path) == []

    def test_one_broken_file_does_not_stop_the_others(self, tmp_path: Path) -> None:
        good = SAMPLES / "consistent_scene.usda"
        bad = tmp_path / "bad.usda"
        bad.write_text("not usd {{{", encoding="utf-8")

        results, failures = batch.validate_all([good, bad], "rules/default.yaml", 2)

        assert [r.path for r in results] == [str(good)]
        assert [f["path"] for f in failures] == [str(bad)]

    def test_a_missing_rule_file_only_skips_the_naming_check(self, tmp_path: Path) -> None:
        result = batch.validate_single_file(
            str(SAMPLES / "consistent_scene.usda"), str(tmp_path / "no-rules.yaml")
        )

        assert result.violation_count == 0
        assert result.prim_count > 0

    def test_json_output_has_results_failures_and_the_total(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = batch.BatchResult("a.usda", "Y", 1.0, 3, 2, ["x", "y"])

        batch.render([result], [{"path": "b.usda", "error": "boom"}], "json", 2)

        payload = json.loads(capsys.readouterr().out)
        assert payload["total_violations"] == 2
        assert payload["results"][0]["violations"] == ["x", "y"]
        assert payload["failures"] == [{"path": "b.usda", "error": "boom"}]

    def test_csv_output_has_a_header_a_row_per_result_and_a_row_per_failure(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = batch.BatchResult("a.usda", "Z", 0.01, 5, 0, [])

        batch.render([result], [{"path": "b.usda", "error": "boom"}], "csv", 0)

        lines = capsys.readouterr().out.strip().splitlines()
        assert lines[0].startswith("path,up_axis,meters_per_unit")
        assert lines[1].startswith("a.usda,Z,0.01,5,0")
        assert lines[2].startswith("b.usda,ERROR")
