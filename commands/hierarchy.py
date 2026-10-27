"""hierarchy-check コマンド: 命名規則の検査。"""

from __future__ import annotations

import argparse
from pathlib import Path

from commands.common import error, open_stages, print_entries
from commands.exit_codes import EXIT_MISMATCH_FOUND, EXIT_OK, EXIT_RULE_FILE_ERROR
from core.hierarchy_check import check_naming
from core.rules import DEFAULT_RULES_PATH, RuleFileError, load_naming_rules


def run(args: argparse.Namespace) -> int:
    rules_path = Path(args.rules) if args.rules else DEFAULT_RULES_PATH
    stages = open_stages(Path(args.usd))
    if isinstance(stages, int):
        return stages

    try:
        rules, exclude_patterns = load_naming_rules(rules_path)
    except RuleFileError as exc:
        error(str(exc))
        return EXIT_RULE_FILE_ERROR

    entries = check_naming(stages[0], rules, exclude_patterns)
    print_entries(entries)
    return EXIT_MISMATCH_FOUND if entries else EXIT_OK
