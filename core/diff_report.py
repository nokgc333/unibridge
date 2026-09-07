"""変換前後のUSDステージ間でPrim数・Material数を比較する差分レポート生成（仕様書§5.4, §8.3）。

CSV/JSON/HTML出力関数（report_to_csv_rows/report_to_json/report_to_html）を提供する。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape

from pxr import Usd, UsdShade

from core.report_models import DiffCategory, DiffEntry, DiffReport, Severity


def _count_prims_by_type(stage: Usd.Stage) -> dict[str, int]:
    counts: dict[str, int] = {}
    for prim in stage.Traverse():
        counts[prim.GetTypeName()] = counts.get(prim.GetTypeName(), 0) + 1
    return counts


def _material_count(stage: Usd.Stage) -> int:
    return sum(1 for prim in stage.Traverse() if prim.IsA(UsdShade.Material))


def _prim_paths(stage: Usd.Stage) -> set[str]:
    return {prim.GetPath().pathString for prim in stage.Traverse()}


def build_diff_report(
    before_stage: Usd.Stage, after_stage: Usd.Stage, source_path: str, target_path: str
) -> DiffReport:
    """2つのUSDステージ間のPrim数・Material数の差分を比較する（O(N)、N=総Prim数）。"""
    before_paths = _prim_paths(before_stage)
    after_paths = _prim_paths(after_stage)

    entries: list[DiffEntry] = []

    for removed in sorted(before_paths - after_paths):
        entries.append(
            DiffEntry(
                category=DiffCategory.PRIM_REMOVED,
                target_path=removed,
                message=f"prim {removed} exists in before but missing in after",
                severity=Severity.ERROR,
            )
        )
    for added in sorted(after_paths - before_paths):
        entries.append(
            DiffEntry(
                category=DiffCategory.PRIM_ADDED,
                target_path=added,
                message=f"prim {added} newly appears in after (not present in before)",
                severity=Severity.INFO,
            )
        )

    before_material_count = _material_count(before_stage)
    after_material_count = _material_count(after_stage)
    if before_material_count != after_material_count:
        entries.append(
            DiffEntry(
                category=DiffCategory.MATERIAL_COUNT_DIFF,
                target_path="(stage)",
                message=(
                    f"material count changed: {before_material_count} -> {after_material_count}"
                ),
                severity=Severity.WARNING,
                before_value=str(before_material_count),
                after_value=str(after_material_count),
            )
        )

    return DiffReport(
        source_stage=source_path,
        target_stage=target_path,
        generated_at=datetime.now(timezone.utc).isoformat(),
        prim_count_before=len(before_paths),
        prim_count_after=len(after_paths),
        material_count_before=before_material_count,
        material_count_after=after_material_count,
        entries=entries,
    )


_CSV_HEADER = [
    "category",
    "severity",
    "target_path",
    "message",
    "before_value",
    "after_value",
]


def report_to_csv_rows(report: DiffReport) -> list[list[str]]:
    """DiffReportをCSV書き出し用の行リスト（ヘッダ行含む）に変換する。"""
    rows: list[list[str]] = [_CSV_HEADER]
    for entry in report.entries:
        rows.append(
            [
                entry.category.value,
                entry.severity.value,
                entry.target_path,
                entry.message,
                entry.before_value or "",
                entry.after_value or "",
            ]
        )
    return rows


def report_to_json(report: DiffReport) -> str:
    """DiffReportをJSON文字列に変換する。"""
    payload = {
        "source_stage": report.source_stage,
        "target_stage": report.target_stage,
        "generated_at": report.generated_at,
        "prim_count_before": report.prim_count_before,
        "prim_count_after": report.prim_count_after,
        "material_count_before": report.material_count_before,
        "material_count_after": report.material_count_after,
        "has_errors": report.has_errors,
        "entries": [
            {
                "category": e.category.value,
                "target_path": e.target_path,
                "message": e.message,
                "severity": e.severity.value,
                "before_value": e.before_value,
                "after_value": e.after_value,
            }
            for e in report.entries
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def report_to_html(report: DiffReport) -> str:
    """DiffReportを簡易HTMLテーブルに変換する（webui/CLIの--format html用）。"""
    rows_html = "\n".join(
        "<tr>"
        f"<td>{escape(e.category.value)}</td>"
        f"<td>{escape(e.severity.value)}</td>"
        f"<td>{escape(e.target_path)}</td>"
        f"<td>{escape(e.message)}</td>"
        f"<td>{escape(e.before_value or '')}</td>"
        f"<td>{escape(e.after_value or '')}</td>"
        "</tr>"
        for e in report.entries
    )
    return f"""<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>UniBridge Diff Report</title></head>
<body>
<h1>UniBridge Diff Report</h1>
<p>source: {escape(report.source_stage)} / target: {escape(report.target_stage)}</p>
<p>generated_at: {escape(report.generated_at)}</p>
<p>prim_count: {report.prim_count_before} -> {report.prim_count_after} /
material_count: {report.material_count_before} -> {report.material_count_after}</p>
<table border="1" cellpadding="4" cellspacing="0">
<thead>
<tr><th>category</th><th>severity</th><th>target_path</th><th>message</th>
<th>before</th><th>after</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</body>
</html>
"""
