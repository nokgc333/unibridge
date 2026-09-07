"""USDアップロード→検証エンドポイント（仕様書§5.9, FR-007）。"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pxr import Tf, Usd

from core.diff_report import build_diff_report, report_to_json
from core.hierarchy_check import check_naming
from core.report_models import DiffEntry, DiffReport
from core.rules import RuleFileError, load_naming_rules
from core.scale_check import (
    check_scale_mismatch,
    check_up_axis_mismatch,
    extract_metadata,
)
from webui.store import save_report

router = APIRouter()

ALLOWED_EXTENSIONS = {".usd", ".usda", ".usdc", ".usdz"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB（SEC-006、要件定義書NFR-006のusdz読込を考慮）
DEFAULT_RULES_PATH = Path("rules/default.yaml")


async def _save_upload_to_tempfile(file: UploadFile, tmp_dir: Path) -> Path:
    """アップロードされたファイルを検証し、一時ディレクトリへUUIDベースの名前で保存する。

    SEC-006: 拡張子検証・サイズ検証・UUIDベースのファイル名（パストラバーサル・衝突防止）。
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 200MB)")

    saved_path = tmp_dir / f"{uuid.uuid4()}{ext}"
    saved_path.write_bytes(contents)
    return saved_path


def _open_stage_or_422(path: Path) -> Usd.Stage:
    """USDファイルを開く。破損ファイルはpxr.Tf.ErrorExceptionを送出しうるため、
    Noneが返る場合(拡張子はUSDだが内容が空等)と合わせて422へ正規化する(E001相当)。
    """
    try:
        stage = Usd.Stage.Open(str(path))
    except Tf.ErrorException as exc:
        raise HTTPException(status_code=422, detail="Failed to open USD stage (E001)") from exc
    if stage is None:
        raise HTTPException(status_code=422, detail="Failed to open USD stage (E001)")
    return stage


def _entries_to_json(entries: list[DiffEntry]) -> list[dict[str, object]]:
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


@router.post("/validate")
async def validate_usd(file: UploadFile) -> dict[str, object]:
    """単一のUSDファイルをアップロードし、座標系/スケール/命名を検証する。"""
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        saved_path = await _save_upload_to_tempfile(file, tmp_dir)

        stage = _open_stage_or_422(saved_path)

        metadata = extract_metadata(stage, source_path=file.filename or "uploaded.usd")

        entries: list[DiffEntry] = []
        # 単一ファイル検証では自分自身と比較する形で暗黙依存の警告のみ判定できる
        # （up_axis/metersPerUnitの「不一致」は2ファイル比較(diff)側の責務）。
        if not metadata.up_axis_is_explicit or not metadata.meters_per_unit_is_explicit:
            entries.extend(check_up_axis_mismatch(metadata, metadata))

        try:
            rules, exclude_patterns = load_naming_rules(DEFAULT_RULES_PATH)
            entries.extend(check_naming(stage, rules, exclude_patterns))
        except RuleFileError:
            pass  # 命名規則読込失敗時は当該チェックのみスキップする（座標系検証は継続）

    return {
        "up_axis": metadata.up_axis,
        "up_axis_is_explicit": metadata.up_axis_is_explicit,
        "meters_per_unit": metadata.meters_per_unit,
        "meters_per_unit_is_explicit": metadata.meters_per_unit_is_explicit,
        "prim_count": metadata.prim_count,
        "entries": _entries_to_json(entries),
    }


@router.post("/diff")
async def diff_usd(before: UploadFile, after: UploadFile) -> dict[str, object]:
    """2つのUSDファイルをアップロードし、差分レポートを生成する。"""
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        before_path = await _save_upload_to_tempfile(before, tmp_dir)
        after_path = await _save_upload_to_tempfile(after, tmp_dir)

        before_stage = _open_stage_or_422(before_path)
        after_stage = _open_stage_or_422(after_path)

        before_meta = extract_metadata(before_stage, before.filename or "before.usd")
        after_meta = extract_metadata(after_stage, after.filename or "after.usd")

        report: DiffReport = build_diff_report(
            before_stage,
            after_stage,
            before.filename or "before.usd",
            after.filename or "after.usd",
        )
        report.entries.extend(check_up_axis_mismatch(before_meta, after_meta))
        report.entries.extend(check_scale_mismatch(before_meta, after_meta))

    report_id = save_report(report)

    return {"report_id": report_id, **_json_payload(report)}


def _json_payload(report: DiffReport) -> dict[str, object]:
    import json

    return dict(json.loads(report_to_json(report)))
