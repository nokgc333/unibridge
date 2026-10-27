"""scale-check コマンド: 座標系・スケール単位の不整合を検出し、必要なら変換して書き出す。"""

from __future__ import annotations

import argparse
from pathlib import Path

from pxr import Tf, Usd

from commands.common import error, open_stages, print_entries
from commands.exit_codes import (
    EXIT_INVALID_PARAMETER,
    EXIT_MISMATCH_FOUND,
    EXIT_OK,
    EXIT_OUTPUT_NOT_WRITABLE,
)
from core.report_models import DiffEntry, StageMetadataSnapshot
from core.scale_check import (
    apply_scale_conversion,
    apply_up_axis_conversion,
    check_scale_mismatch,
    check_up_axis_mismatch,
    extract_metadata,
)


def _apply_conversions(
    source_stage: Usd.Stage,
    source_meta: StageMetadataSnapshot,
    target_meta: StageMetadataSnapshot,
    out: str,
) -> int | None:
    """変換を書き出す。失敗したときは終了コードを返し、成功したら None を返す。"""
    try:
        if source_meta.up_axis != target_meta.up_axis:
            apply_up_axis_conversion(source_stage, target_meta.up_axis, out)
        if source_meta.meters_per_unit != target_meta.meters_per_unit:
            apply_scale_conversion(source_stage, target_meta.meters_per_unit, out)
    except (OSError, Tf.ErrorException) as exc:
        error(f"cannot write to '{out}': {exc}")
        return EXIT_OUTPUT_NOT_WRITABLE
    except ValueError as exc:
        error(str(exc))
        return EXIT_INVALID_PARAMETER
    return None


def run(args: argparse.Namespace) -> int:
    source_path = Path(args.source)
    target_path = Path(args.target)
    stages = open_stages(source_path, target_path)
    if isinstance(stages, int):
        return stages
    source_stage, target_stage = stages

    source_meta = extract_metadata(source_stage, str(source_path))
    target_meta = extract_metadata(target_stage, str(target_path))

    entries: list[DiffEntry] = list(check_up_axis_mismatch(source_meta, target_meta))
    try:
        entries.extend(check_scale_mismatch(source_meta, target_meta))
    except ValueError as exc:
        error(str(exc))
        return EXIT_INVALID_PARAMETER

    print_entries(entries)

    if args.apply:
        if not args.out:
            error("--apply requires --out")
            return EXIT_INVALID_PARAMETER
        failed = _apply_conversions(source_stage, source_meta, target_meta, args.out)
        if failed is not None:
            return failed

    return EXIT_MISMATCH_FOUND if entries else EXIT_OK
