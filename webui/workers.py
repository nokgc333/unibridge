from __future__ import annotations

from pathlib import Path

from core.diff_report import build_diff_report
from core.hierarchy_check import check_naming
from core.report_models import DiffEntry, DiffReport
from core.rules import DEFAULT_RULES_PATH, RuleFileError, load_naming_rules
from core.scale_check import (
    check_scale_mismatch,
    check_up_axis_mismatch,
    extract_metadata,
)
from core.stage_loader import open_stage


def entries_to_json(entries: list[DiffEntry]) -> list[dict[str, object]]:
    return [
        {
            "category": e.category.value,
            "target_path": e.target_path,
            "message": e.message,
            "severity": e.severity.value,
            "before_value": e.before_value,
            "after_value": e.after_value,
        }
        for e in entries
    ]


def validate_worker(path: str, display_name: str) -> dict[str, object]:
    stage = open_stage(Path(path), allow_external_references=False)
    metadata = extract_metadata(stage, source_path=display_name)

    entries: list[DiffEntry] = []
    if not metadata.up_axis_is_explicit or not metadata.meters_per_unit_is_explicit:
        entries.extend(check_up_axis_mismatch(metadata, metadata))

    try:
        rules, exclude_patterns = load_naming_rules(DEFAULT_RULES_PATH)
        entries.extend(check_naming(stage, rules, exclude_patterns))
    except RuleFileError:
        pass

    return {
        "up_axis": metadata.up_axis,
        "up_axis_is_explicit": metadata.up_axis_is_explicit,
        "meters_per_unit": metadata.meters_per_unit,
        "meters_per_unit_is_explicit": metadata.meters_per_unit_is_explicit,
        "prim_count": metadata.prim_count,
        "entries": entries_to_json(entries),
    }


def diff_worker(before_path: str, after_path: str, before_name: str, after_name: str) -> DiffReport:
    before_stage = open_stage(Path(before_path), allow_external_references=False)
    after_stage = open_stage(Path(after_path), allow_external_references=False)

    before_meta = extract_metadata(before_stage, before_name)
    after_meta = extract_metadata(after_stage, after_name)

    report = build_diff_report(before_stage, after_stage, before_name, after_name)
    report.entries.extend(check_up_axis_mismatch(before_meta, after_meta))
    report.entries.extend(check_scale_mismatch(before_meta, after_meta))
    return report
