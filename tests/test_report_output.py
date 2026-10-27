"""core/report_output.py のテスト（CLI と Web が共有する出力整形）。"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from core.diff_report import build_diff_report
from core.report_models import DiffCategory, DiffEntry, DiffReport, Severity
from core.report_output import (
    format_entries,
    report_summary_line,
    report_text,
    write_report_files,
)
from tests.conftest import open_stage

SAMPLES = Path("sample_scenes")


@pytest.fixture
def report() -> DiffReport:
    before = SAMPLES / "consistent_scene.usda"
    after = SAMPLES / "mismatched_scale.usda"
    return build_diff_report(open_stage(before), open_stage(after), str(before), str(after))


def _entry(message: str = "m") -> DiffEntry:
    return DiffEntry(
        category=DiffCategory.SCALE_MISMATCH,
        severity=Severity.WARNING,
        target_path="/root",
        message=message,
        before_value="1",
        after_value="2",
    )


class TestFormatEntries:
    def test_no_entries_gives_the_all_clear_line(self) -> None:
        assert format_entries([]) == ["No inconsistencies detected."]

    def test_each_entry_is_one_line_with_severity_category_path_and_message(self) -> None:
        lines = format_entries([_entry("a"), _entry("b")])

        assert len(lines) == 2
        assert lines[0].startswith(
            f"[{Severity.WARNING.value}] {DiffCategory.SCALE_MISMATCH.value}: /root:"
        )
        assert lines[0].endswith(": a")
        assert lines[1].endswith(": b")


class TestReportText:
    def test_json_is_valid_json_and_ends_with_a_newline(self, report: DiffReport) -> None:
        text = report_text(report, "json")

        assert text.endswith("\n")
        assert "entries" in json.loads(text)

    def test_html_is_a_document_and_ends_with_a_newline(self, report: DiffReport) -> None:
        text = report_text(report, "html")

        assert "<html" in text.lower()
        assert text.endswith("\n")

    def test_csv_has_a_header_and_one_row_per_entry(self, report: DiffReport) -> None:
        rows = list(csv.reader(io.StringIO(report_text(report, "csv"))))

        assert len(rows) == len(report.entries) + 1

    def test_any_other_format_falls_back_to_json(self, report: DiffReport) -> None:
        assert report_text(report, "all") == report_text(report, "json")


class TestSummaryLine:
    def test_counts_and_entry_number_are_in_the_line(self, report: DiffReport) -> None:
        line = report_summary_line(report)

        assert f"{report.prim_count_before} -> {report.prim_count_after}" in line
        assert f"{len(report.entries)} diff entrie(s)." in line


class TestWriteReportFiles:
    @pytest.mark.parametrize(
        ("fmt", "suffixes"),
        [
            ("csv", [".csv"]),
            ("json", [".json"]),
            ("html", [".html"]),
            ("all", [".csv", ".json", ".html"]),
        ],
    )
    def test_writes_the_files_of_the_format(
        self, report: DiffReport, tmp_path: Path, fmt: str, suffixes: list[str]
    ) -> None:
        written = write_report_files(report, fmt, tmp_path / "out", "a_vs_b")

        assert [p.suffix for p in written.files] == suffixes
        assert all(p.exists() and p.stat().st_size > 0 for p in written.files)
        assert written.directory == tmp_path / "out"

    def test_creates_the_directory_when_it_is_missing(
        self, report: DiffReport, tmp_path: Path
    ) -> None:
        target = tmp_path / "a" / "b"

        write_report_files(report, "json", target, "r")

        assert target.is_dir()

    def test_a_path_that_cannot_be_a_directory_raises_os_error(
        self, report: DiffReport, tmp_path: Path
    ) -> None:
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")

        with pytest.raises(OSError):
            write_report_files(report, "json", blocker / "sub", "r")
