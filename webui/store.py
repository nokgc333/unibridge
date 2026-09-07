"""簡易Web GUIのプロセス内インメモリレポートストア。

DBを使わない設計（仕様書§4.1）のため、生成した差分レポートをプロセスメモリ上に
保持し、`GET /api/reports/{report_id}`から参照できるようにする。プロセス再起動で
消える点はローカル実行ツールとして許容する。
"""

from __future__ import annotations

import uuid
from threading import Lock

from core.report_models import DiffReport

_lock = Lock()
_reports: dict[str, DiffReport] = {}


def save_report(report: DiffReport) -> str:
    """レポートを保存し、参照用のreport_idを返す。"""
    report_id = str(uuid.uuid4())
    with _lock:
        _reports[report_id] = report
    return report_id


def get_report(report_id: str) -> DiffReport | None:
    with _lock:
        return _reports.get(report_id)
