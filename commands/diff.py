"""diff コマンド: 2 つの USD ステージの差分レポート。"""

from __future__ import annotations

import argparse
from pathlib import Path

from commands.common import error, open_stages
from commands.exit_codes import (
    EXIT_MISMATCH_FOUND,
    EXIT_OK,
    EXIT_OUTPUT_NOT_WRITABLE,
)
from core.diff_report import build_diff_report
from core.report_output import report_summary_line, report_text, write_report_files


def run(args: argparse.Namespace) -> int:
    before_path = Path(args.before)
    after_path = Path(args.after)
    stages = open_stages(before_path, after_path)
    if isinstance(stages, int):
        return stages
    before_stage, after_stage = stages

    report = build_diff_report(before_stage, after_stage, str(before_path), str(after_path))

    if args.out:
        out_dir = Path(args.out)
        try:
            write_report_files(
                report, args.format, out_dir, f"{before_path.stem}_vs_{after_path.stem}"
            )
        except OSError as exc:
            error(f"cannot write to '{out_dir}': {exc}")
            return EXIT_OUTPUT_NOT_WRITABLE
    else:
        print(report_text(report, args.format), end="")

    print(report_summary_line(report))
    return EXIT_MISMATCH_FOUND if report.entries else EXIT_OK
