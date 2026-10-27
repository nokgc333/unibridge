"""各コマンドが共有する処理。"""

from __future__ import annotations

import sys
from pathlib import Path

from pxr import Usd

from commands.exit_codes import EXIT_FILE_NOT_FOUND
from core.report_models import DiffEntry
from core.report_output import format_entries
from core.stage_loader import open_stage


def print_entries(entries: list[DiffEntry]) -> None:
    for line in format_entries(entries):
        print(line)


def error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)


def open_stages(*paths: Path) -> list[Usd.Stage] | int:
    """ステージを開く。開けなければ原因を表示して終了コード(E001)を返す。"""
    stages = []
    for path in paths:
        try:
            stages.append(open_stage(path))
        except ValueError as exc:
            error(str(exc))
            return EXIT_FILE_NOT_FOUND
    return stages
