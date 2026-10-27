"""batch コマンド: ディレクトリ配下の USD を並列に検査する。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from commands.common import error
from commands.exit_codes import (
    EXIT_FILE_NOT_FOUND,
    EXIT_INVALID_PARAMETER,
    EXIT_MISMATCH_FOUND,
    EXIT_OK,
)
from core.hierarchy_check import check_naming
from core.report_models import DiffEntry
from core.rules import DEFAULT_RULES_PATH, RuleFileError, load_naming_rules
from core.scale_check import extract_metadata
from core.stage_loader import open_stage

USD_GLOB_PATTERNS = ("*.usd", "*.usda", "*.usdc")


@dataclass(frozen=True)
class BatchResult:
    path: str
    up_axis: str
    meters_per_unit: float
    prim_count: int
    violation_count: int
    violations: list[str]


def validate_single_file(path_str: str, rules_path_str: str) -> BatchResult:
    """batchコマンドのワーカー関数（プロセスプールに渡すためモジュールトップレベルに定義）。

    1ファイルの検証で例外が発生しても、呼び出し側がFuture.exception()経由で捕捉できるよう
    例外はそのまま送出する（SEC-004: 他ワーカーへの波及防止は呼び出し側のFuture単位の分離で担保）。
    """
    path = Path(path_str)
    stage = open_stage(path)
    metadata = extract_metadata(stage, str(path))

    entries: list[DiffEntry] = []
    try:
        rules, exclude_patterns = load_naming_rules(Path(rules_path_str))
        entries.extend(check_naming(stage, rules, exclude_patterns))
    except RuleFileError:
        pass  # batch実行では命名規則の読込失敗は当該チェックのみスキップする

    return BatchResult(
        path=str(path),
        up_axis=metadata.up_axis,
        meters_per_unit=metadata.meters_per_unit,
        prim_count=metadata.prim_count,
        violation_count=len(entries),
        violations=[e.message for e in entries],
    )


def find_usd_files(target_dir: Path) -> list[Path]:
    return sorted({p for pattern in USD_GLOB_PATTERNS for p in target_dir.glob(pattern)})


def validate_all(
    files: list[Path], rules_path: str, workers: int
) -> tuple[list[BatchResult], list[dict[str, str]]]:
    results: list[BatchResult] = []
    failures: list[dict[str, str]] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(validate_single_file, str(f), rules_path): f for f in files}
        for future, path in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 - SEC-004: 1ファイルの失敗を他に波及させない
                failures.append({"path": str(path), "error": str(exc)})
    return results, failures


def render(
    results: list[BatchResult], failures: list[dict[str, str]], fmt: str, total_violations: int
) -> None:
    if fmt == "json":
        payload = {
            "results": [asdict(r) for r in results],
            "failures": failures,
            "total_violations": total_violations,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    writer = csv.writer(sys.stdout)
    writer.writerow(["path", "up_axis", "meters_per_unit", "prim_count", "violation_count"])
    for r in results:
        writer.writerow([r.path, r.up_axis, r.meters_per_unit, r.prim_count, r.violation_count])
    for f in failures:
        writer.writerow([f["path"], "ERROR", "", "", f["error"]])


def run(args: argparse.Namespace) -> int:
    target_dir = Path(args.dir)
    if not target_dir.is_dir():
        error(f"'{target_dir}' is not a directory")
        return EXIT_FILE_NOT_FOUND

    files = find_usd_files(target_dir)
    if not files:
        error(f"no USD files found under '{target_dir}'")
        return EXIT_INVALID_PARAMETER

    rules_path = args.rules if args.rules else str(DEFAULT_RULES_PATH)
    results, failures = validate_all(files, rules_path, args.workers)
    total_violations = sum(r.violation_count for r in results)
    render(results, failures, args.format, total_violations)
    return EXIT_MISMATCH_FOUND if (total_violations or failures) else EXIT_OK
