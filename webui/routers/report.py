"""差分レポート取得エンドポイント・命名規則参照エンドポイント（仕様書§5.9）。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from core.diff_report import report_to_json
from webui.store import get_report

router = APIRouter()

DEFAULT_RULES_PATH = Path("rules/default.yaml")


@router.get("/reports/{report_id}")
def get_report_by_id(report_id: str) -> dict[str, object]:
    """過去に生成した差分レポートを取得する。存在しない場合はRFC 9457形式の404。"""
    report = get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/probs/404",
                "title": f"Report {report_id} not found",
                "status": 404,
            },
        )
    return dict(json.loads(report_to_json(report)))


@router.get("/rules")
def get_rules() -> dict[str, object]:
    """現在の命名規則YAMLの内容を表示用に取得する（yaml.safe_loadのみ使用、SEC-001）。"""
    if not DEFAULT_RULES_PATH.exists():
        raise HTTPException(status_code=404, detail="rules/default.yaml not found")
    raw = yaml.safe_load(DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
    return dict(raw)
