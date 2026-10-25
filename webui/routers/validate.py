"""USDアップロード→検証エンドポイント（仕様書§5.9, FR-007）。"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile

from core.diff_report import report_to_json
from core.report_models import DiffReport
from core.stage_loader import ExternalReferenceError, StageOpenError
from webui import workers
from webui.limits import CHUNK_SIZE, load_limits, upload_gate
from webui.sandbox import ParseTimeoutError, ParseWorkerError, run_in_process
from webui.store import save_report

router = APIRouter()

ALLOWED_EXTENSIONS = {".usd", ".usda", ".usdc", ".usdz"}


async def _save_upload_to_tempfile(file: UploadFile, tmp_dir: Path) -> Path:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    max_bytes = load_limits().max_upload_bytes
    saved_path = tmp_dir / f"{uuid.uuid4()}{ext}"
    written = 0
    try:
        with saved_path.open("wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (max {max_bytes} bytes)",
                    )
                out.write(chunk)
    except HTTPException:
        saved_path.unlink(missing_ok=True)
        raise
    return saved_path


async def _run_analysis(func: Callable[..., Any], *args: Any) -> Any:
    timeout = load_limits().parse_timeout_seconds
    try:
        return await asyncio.to_thread(run_in_process, func, args, timeout)
    except ParseTimeoutError as exc:
        raise HTTPException(status_code=504, detail="USD analysis timed out") from exc
    except ExternalReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StageOpenError as exc:
        raise HTTPException(status_code=422, detail="Failed to open USD stage (E001)") from exc
    except ParseWorkerError as exc:
        raise HTTPException(status_code=500, detail="USD analysis failed") from exc


@router.post("/validate")
async def validate_usd(file: UploadFile) -> dict[str, object]:
    """単一のUSDファイルをアップロードし、座標系/スケール/命名を検証する。"""
    with upload_gate.acquire(load_limits().max_concurrent_uploads):
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            saved_path = await _save_upload_to_tempfile(file, Path(tmp_dir_str))
            result: dict[str, object] = await _run_analysis(
                workers.validate_worker, str(saved_path), file.filename or "uploaded.usd"
            )
    return result


@router.post("/diff")
async def diff_usd(before: UploadFile, after: UploadFile) -> dict[str, object]:
    """2つのUSDファイルをアップロードし、差分レポートを生成する。"""
    with upload_gate.acquire(load_limits().max_concurrent_uploads):
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            before_path = await _save_upload_to_tempfile(before, tmp_dir)
            after_path = await _save_upload_to_tempfile(after, tmp_dir)
            report: DiffReport = await _run_analysis(
                workers.diff_worker,
                str(before_path),
                str(after_path),
                before.filename or "before.usd",
                after.filename or "after.usd",
            )

    report_id = save_report(report)
    return {"report_id": report_id, **_json_payload(report)}


def _json_payload(report: DiffReport) -> dict[str, object]:
    return dict(json.loads(report_to_json(report)))
