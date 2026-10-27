"""core/common_report.py と共通スキーマのテスト。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from core.common_report import build_common_report, common_report_json
from core.report_models import DiffCategory, DiffEntry, Severity

SCHEMA = json.loads(Path("docs/schema/common-report.schema.json").read_text(encoding="utf-8"))
FIXED_TIME = datetime(2026, 10, 27, 1, 2, 3, tzinfo=timezone.utc)


def _entry(severity: Severity) -> DiffEntry:
    return DiffEntry(
        category=DiffCategory.UV_MISSING, target_path="/m", message="no uv", severity=severity
    )


def test_a_report_with_findings_matches_the_schema() -> None:
    report = build_common_report("a.usda", [_entry(Severity.WARNING)], FIXED_TIME)

    jsonschema.validate(report, SCHEMA)


def test_an_empty_report_matches_the_schema_and_has_no_errors() -> None:
    report = build_common_report("a.usda", [], FIXED_TIME)

    jsonschema.validate(report, SCHEMA)
    assert report["has_errors"] is False
    assert report["findings"] == []


def test_has_errors_is_true_only_for_an_error_finding() -> None:
    warning = build_common_report("a", [_entry(Severity.WARNING)], FIXED_TIME)
    error = build_common_report("a", [_entry(Severity.WARNING), _entry(Severity.ERROR)], FIXED_TIME)

    assert warning["has_errors"] is False
    assert error["has_errors"] is True


def test_a_finding_carries_the_rule_target_and_message() -> None:
    report = build_common_report("a", [_entry(Severity.ERROR)], FIXED_TIME)

    assert report["findings"] == [
        {"rule": "uv_missing", "severity": "error", "target": "/m", "message": "no uv"}
    ]


def test_the_time_is_written_in_iso_8601_with_the_offset() -> None:
    report = build_common_report("a", [], FIXED_TIME)

    assert report["generated_at"] == "2026-10-27T01:02:03+00:00"


def test_the_json_text_round_trips() -> None:
    text = common_report_json("a", [_entry(Severity.INFO)], FIXED_TIME)

    assert json.loads(text) == build_common_report("a", [_entry(Severity.INFO)], FIXED_TIME)


@pytest.mark.parametrize("missing", ["tool", "findings", "has_errors"])
def test_the_schema_rejects_a_report_without_a_required_key(missing: str) -> None:
    report = build_common_report("a", [], FIXED_TIME)
    del report[missing]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(report, SCHEMA)


def test_the_schema_rejects_an_unknown_severity() -> None:
    report = build_common_report("a", [_entry(Severity.INFO)], FIXED_TIME)
    report["findings"][0]["severity"] = "fatal"  # type: ignore[index]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(report, SCHEMA)
