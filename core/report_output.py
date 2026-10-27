"""検査結果の出力整形（CLI と Web で共有する。仕様書§5.5）。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from core.diff_report import report_to_csv_rows, report_to_html, report_to_json
from core.report_models import DiffEntry, DiffReport

REPORT_FORMATS = ("csv", "json", "html", "all")


def format_entries(entries: list[DiffEntry]) -> list[str]:
    """不整合の一覧を、1 件 1 行の表示用の文にする。"""
    if not entries:
        return ["No inconsistencies detected."]
    return [
        f"[{e.severity.value}] {e.category.value}: {e.target_path}: {e.message}" for e in entries
    ]


def report_summary_line(report: DiffReport) -> str:
    return (
        f"prim_count: {report.prim_count_before} -> {report.prim_count_after}, "
        f"material_count: {report.material_count_before} -> {report.material_count_after}, "
        f"{len(report.entries)} diff entrie(s)."
    )


def report_text(report: DiffReport, fmt: str) -> str:
    """標準出力に出す本文(csv / html / それ以外は json)。末尾は改行で終わる。"""
    if fmt == "csv":
        import io

        buffer = io.StringIO(newline="")
        csv.writer(buffer).writerows(report_to_csv_rows(report))
        return buffer.getvalue()
    if fmt == "html":
        return report_to_html(report) + "\n"
    return report_to_json(report) + "\n"


@dataclass(frozen=True)
class WrittenReports:
    directory: Path
    files: list[Path]


def write_report_files(report: DiffReport, fmt: str, out_dir: Path, stem: str) -> WrittenReports:
    """レポートをファイルに書く。書けなければ OSError を送出する。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if fmt in ("csv", "all"):
        path = out_dir / f"{stem}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(report_to_csv_rows(report))
        written.append(path)
    if fmt in ("json", "all"):
        path = out_dir / f"{stem}.json"
        path.write_text(report_to_json(report), encoding="utf-8")
        written.append(path)
    if fmt in ("html", "all"):
        path = out_dir / f"{stem}.html"
        path.write_text(report_to_html(report), encoding="utf-8")
        written.append(path)
    return WrittenReports(directory=out_dir, files=written)
