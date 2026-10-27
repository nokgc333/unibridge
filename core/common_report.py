"""ツール間で共通の検査レポート(JSON)。docs/schema/common-report.schema.json に対応する。

scene-doctor など、同じ形式で出力するツールと並べて読めるようにするための最小の形。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from core.report_models import DiffEntry, Severity

SCHEMA_VERSION = "1"
TOOL_NAME = "unibridge"


def build_common_report(
    subject: str, entries: list[DiffEntry], generated_at: datetime | None = None
) -> dict[str, object]:
    when = generated_at or datetime.now(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": when.isoformat(),
        "subject": subject,
        "has_errors": any(e.severity == Severity.ERROR for e in entries),
        "findings": [
            {
                "rule": e.category.value,
                "severity": e.severity.value,
                "target": e.target_path,
                "message": e.message,
            }
            for e in entries
        ],
    }


def common_report_json(
    subject: str, entries: list[DiffEntry], generated_at: datetime | None = None
) -> str:
    return json.dumps(
        build_common_report(subject, entries, generated_at), ensure_ascii=False, indent=2
    )
