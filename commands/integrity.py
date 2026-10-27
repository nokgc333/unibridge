"""integrity-check コマンド: 標準的な整合と、マテリアル・UV・variant・purpose の検査。"""

from __future__ import annotations

import argparse
from pathlib import Path

from commands.common import open_stages, print_entries
from commands.exit_codes import EXIT_MISMATCH_FOUND, EXIT_OK
from core.integrity_check import run_integrity_checks


def run(args: argparse.Namespace) -> int:
    stages = open_stages(Path(args.usd))
    if isinstance(stages, int):
        return stages

    entries = run_integrity_checks(stages[0])
    print_entries(entries)
    return EXIT_MISMATCH_FOUND if entries else EXIT_OK
