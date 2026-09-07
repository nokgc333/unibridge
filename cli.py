"""UniBridge CLIエントリポイント（core層のみで完結、仕様書§5.5）。

使い方:
  python cli.py diff --before <path> --after <path> [--format {csv,json,html,all}] [--out <dir>]
  python cli.py scale-check --source <path> --target <path> [--apply] [--target-axis Y|Z]
                             [--target-mpu <float>] [--out <path>]
  python cli.py hierarchy-check --usd <path> [--rules <path>]
  python cli.py batch --dir <path> [--format {csv,json}] [--workers <int>]

終了コード（仕様書§5.7）:
  0: 検証OK（不整合0件）
  1: 不整合N件検出（N>=1）
  10: E001 対象USDファイルが存在しない/読み込めない
  11: E002 不正なパラメータ値
  12: E003 指定ノードが期待する種別でない（本CLIでは未使用、Houdini側専用）
  13: E004 命名規則YAMLの構文エラー
  14: E005 出力先ディレクトリへの書き込み権限がない
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from pxr import Usd

from core.diff_report import (
    build_diff_report,
    report_to_csv_rows,
    report_to_html,
    report_to_json,
)
from core.hierarchy_check import check_naming
from core.report_models import DiffEntry
from core.rules import RuleFileError, load_naming_rules
from core.scale_check import (
    check_scale_mismatch,
    check_up_axis_mismatch,
    extract_metadata,
)

EXIT_OK = 0
EXIT_MISMATCH_FOUND = 1
EXIT_FILE_NOT_FOUND = 10
EXIT_INVALID_PARAMETER = 11
EXIT_INVALID_TARGET_NODE = 12
EXIT_RULE_FILE_ERROR = 13
EXIT_OUTPUT_NOT_WRITABLE = 14

DEFAULT_RULES_PATH = Path("rules/default.yaml")
USD_GLOB_PATTERNS = ("*.usd", "*.usda", "*.usdc")


def _open_stage(path: Path) -> Usd.Stage:
    """USDファイルを開く。存在しない/読み込めない場合はValueErrorを送出する（E001対応）。"""
    if not path.exists():
        raise ValueError(f"'{path}' does not exist")
    stage = Usd.Stage.Open(str(path))
    if stage is None:
        raise ValueError(f"'{path}' could not be opened as a USD stage (corrupt or unsupported)")
    return stage


def _print_entries(entries: list[DiffEntry]) -> None:
    if not entries:
        print("No inconsistencies detected.")
        return
    for entry in entries:
        print(
            f"[{entry.severity.value}] {entry.category.value}: "
            f"{entry.target_path}: {entry.message}"
        )


def _cmd_diff(args: argparse.Namespace) -> int:
    before_path = Path(args.before)
    after_path = Path(args.after)
    try:
        before_stage = _open_stage(before_path)
        after_stage = _open_stage(after_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_FILE_NOT_FOUND

    report = build_diff_report(before_stage, after_stage, str(before_path), str(after_path))

    fmt = args.format
    if args.out:
        out_dir = Path(args.out)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = f"{before_path.stem}_vs_{after_path.stem}"
            if fmt in ("csv", "all"):
                with (out_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerows(report_to_csv_rows(report))
            if fmt in ("json", "all"):
                (out_dir / f"{stem}.json").write_text(report_to_json(report), encoding="utf-8")
            if fmt in ("html", "all"):
                (out_dir / f"{stem}.html").write_text(report_to_html(report), encoding="utf-8")
        except OSError as exc:
            print(f"Error: cannot write to '{out_dir}': {exc}", file=sys.stderr)
            return EXIT_OUTPUT_NOT_WRITABLE
    elif fmt == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerows(report_to_csv_rows(report))
    elif fmt == "html":
        print(report_to_html(report))
    else:
        print(report_to_json(report))

    print(
        f"prim_count: {report.prim_count_before} -> {report.prim_count_after}, "
        f"material_count: {report.material_count_before} -> {report.material_count_after}, "
        f"{len(report.entries)} diff entrie(s)."
    )
    return EXIT_MISMATCH_FOUND if report.entries else EXIT_OK


def _cmd_scale_check(args: argparse.Namespace) -> int:
    source_path = Path(args.source)
    target_path = Path(args.target)
    try:
        source_stage = _open_stage(source_path)
        target_stage = _open_stage(target_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_FILE_NOT_FOUND

    source_meta = extract_metadata(source_stage, str(source_path))
    target_meta = extract_metadata(target_stage, str(target_path))

    entries: list[DiffEntry] = []
    entries.extend(check_up_axis_mismatch(source_meta, target_meta))
    try:
        entries.extend(check_scale_mismatch(source_meta, target_meta))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INVALID_PARAMETER

    _print_entries(entries)

    if args.apply:
        if not args.out:
            print("Error: --apply requires --out", file=sys.stderr)
            return EXIT_INVALID_PARAMETER
        from core.scale_check import apply_scale_conversion, apply_up_axis_conversion

        try:
            if source_meta.up_axis != target_meta.up_axis:
                apply_up_axis_conversion(source_stage, target_meta.up_axis, args.out)
            if source_meta.meters_per_unit != target_meta.meters_per_unit:
                apply_scale_conversion(source_stage, target_meta.meters_per_unit, args.out)
        except OSError as exc:
            print(f"Error: cannot write to '{args.out}': {exc}", file=sys.stderr)
            return EXIT_OUTPUT_NOT_WRITABLE
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_INVALID_PARAMETER

    return EXIT_MISMATCH_FOUND if entries else EXIT_OK


def _cmd_hierarchy_check(args: argparse.Namespace) -> int:
    usd_path = Path(args.usd)
    rules_path = Path(args.rules) if args.rules else DEFAULT_RULES_PATH

    try:
        stage = _open_stage(usd_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_FILE_NOT_FOUND

    try:
        rules, exclude_patterns = load_naming_rules(rules_path)
    except RuleFileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_RULE_FILE_ERROR

    entries = check_naming(stage, rules, exclude_patterns)
    _print_entries(entries)
    return EXIT_MISMATCH_FOUND if entries else EXIT_OK


@dataclass(frozen=True)
class BatchResult:
    path: str
    up_axis: str
    meters_per_unit: float
    prim_count: int
    violation_count: int
    violations: list[str]


def _validate_single_file(path_str: str, rules_path_str: str) -> BatchResult:
    """batchコマンドのワーカー関数（プロセスプールに渡すためモジュールトップレベルに定義）。

    1ファイルの検証で例外が発生しても、呼び出し側がFuture.exception()経由で捕捉できるよう
    例外はそのまま送出する（SEC-004: 他ワーカーへの波及防止は呼び出し側のFuture単位の分離で担保）。
    """
    path = Path(path_str)
    stage = _open_stage(path)
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


def _cmd_batch(args: argparse.Namespace) -> int:
    target_dir = Path(args.dir)
    if not target_dir.is_dir():
        print(f"Error: '{target_dir}' is not a directory", file=sys.stderr)
        return EXIT_FILE_NOT_FOUND

    files = sorted({p for pattern in USD_GLOB_PATTERNS for p in target_dir.glob(pattern)})
    if not files:
        print(f"Error: no USD files found under '{target_dir}'", file=sys.stderr)
        return EXIT_INVALID_PARAMETER

    rules_path = args.rules if args.rules else str(DEFAULT_RULES_PATH)
    results: list[BatchResult] = []
    failures: list[dict[str, str]] = []

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_validate_single_file, str(f), rules_path): f for f in files}
        for future, path in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 - SEC-004: 1ファイルの失敗を他に波及させない
                failures.append({"path": str(path), "error": str(exc)})

    total_violations = sum(r.violation_count for r in results)

    if args.format == "json":
        payload = {
            "results": [asdict(r) for r in results],
            "failures": failures,
            "total_violations": total_violations,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["path", "up_axis", "meters_per_unit", "prim_count", "violation_count"])
        for r in results:
            writer.writerow([r.path, r.up_axis, r.meters_per_unit, r.prim_count, r.violation_count])
        for f in failures:
            writer.writerow([f["path"], "ERROR", "", "", f["error"]])

    return EXIT_MISMATCH_FOUND if (total_violations or failures) else EXIT_OK


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UniBridge: DCC間USD検証ツール")
    sub = parser.add_subparsers(dest="command", required=True)

    diff_p = sub.add_parser("diff", help="2つのUSDステージ間の差分レポートを生成")
    diff_p.add_argument("--before", required=True)
    diff_p.add_argument("--after", required=True)
    diff_p.add_argument("--format", choices=["csv", "json", "html", "all"], default="json")
    diff_p.add_argument("--out", default=None, help="出力先ディレクトリ（省略時は標準出力）")
    diff_p.set_defaults(func=_cmd_diff)

    scale_p = sub.add_parser("scale-check", help="座標系・スケール単位の不整合をチェック")
    scale_p.add_argument("--source", required=True)
    scale_p.add_argument("--target", required=True)
    scale_p.add_argument("--apply", action="store_true", help="不整合の変換を明示的に適用する")
    scale_p.add_argument("--out", default=None, help="--apply時の出力先USDファイルパス")
    scale_p.set_defaults(func=_cmd_scale_check)

    hier_p = sub.add_parser("hierarchy-check", help="命名規則チェック")
    hier_p.add_argument("--usd", required=True)
    hier_p.add_argument("--rules", default=None)
    hier_p.set_defaults(func=_cmd_hierarchy_check)

    batch_p = sub.add_parser("batch", help="ディレクトリ配下のUSDファイルを一括検証")
    batch_p.add_argument("--dir", required=True)
    batch_p.add_argument("--format", choices=["csv", "json"], default="json")
    batch_p.add_argument("--workers", type=int, default=4)
    batch_p.add_argument("--rules", default=None)
    batch_p.set_defaults(func=_cmd_batch)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
