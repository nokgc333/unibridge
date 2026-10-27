"""UniBridge CLIエントリポイント（core層のみで完結、仕様書§5.5）。

使い方:
  python cli.py diff --before <path> --after <path> [--format {csv,json,html,all}] [--out <dir>]
  python cli.py scale-check --source <path> --target <path> [--apply] [--target-axis Y|Z]
                             [--target-mpu <float>] [--out <path>]
  python cli.py integrity-check --usd <path> [--format {text,json}]
  python cli.py hierarchy-check --usd <path> [--rules <path>]
  python cli.py batch --dir <path> [--format {csv,json}] [--workers <int>]

終了コード（仕様書§5.7）:
  0: 検証OK（不整合0件）
  1: 不整合N件検出（N>=1）
  10: E001 対象USDファイルが存在しない/読み込めない（破損・非対応フォーマットを含む）
  11: E002 不正なパラメータ値
  12: E003 指定ノードが期待する種別でない（本CLIでは未使用、Houdini側専用）
  13: E004 命名規則YAMLの構文エラー
  14: E005 出力先ディレクトリへの書き込み権限がない
"""

from __future__ import annotations

import argparse
import sys

from commands import batch, diff, hierarchy, integrity, scale_check
from commands.exit_codes import (
    EXIT_FILE_NOT_FOUND,
    EXIT_INVALID_PARAMETER,
    EXIT_INVALID_TARGET_NODE,
    EXIT_MISMATCH_FOUND,
    EXIT_OK,
    EXIT_OUTPUT_NOT_WRITABLE,
    EXIT_RULE_FILE_ERROR,
)

__all__ = [
    "EXIT_FILE_NOT_FOUND",
    "EXIT_INVALID_PARAMETER",
    "EXIT_INVALID_TARGET_NODE",
    "EXIT_MISMATCH_FOUND",
    "EXIT_OK",
    "EXIT_OUTPUT_NOT_WRITABLE",
    "EXIT_RULE_FILE_ERROR",
    "main",
]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UniBridge: DCC間USD検証ツール")
    sub = parser.add_subparsers(dest="command", required=True)

    diff_p = sub.add_parser("diff", help="2つのUSDステージ間の差分レポートを生成")
    diff_p.add_argument("--before", required=True)
    diff_p.add_argument("--after", required=True)
    diff_p.add_argument("--format", choices=["csv", "json", "html", "all"], default="json")
    diff_p.add_argument("--out", default=None, help="出力先ディレクトリ（省略時は標準出力）")
    diff_p.set_defaults(func=diff.run)

    scale_p = sub.add_parser("scale-check", help="座標系・スケール単位の不整合をチェック")
    scale_p.add_argument("--source", required=True)
    scale_p.add_argument("--target", required=True)
    scale_p.add_argument("--apply", action="store_true", help="不整合の変換を明示的に適用する")
    scale_p.add_argument("--out", default=None, help="--apply時の出力先USDファイルパス")
    scale_p.set_defaults(func=scale_check.run)

    hier_p = sub.add_parser("hierarchy-check", help="命名規則チェック")
    hier_p.add_argument("--usd", required=True)
    hier_p.add_argument("--rules", default=None)
    hier_p.set_defaults(func=hierarchy.run)

    integ_p = sub.add_parser(
        "integrity-check", help="既定Prim・参照・マテリアル・UV・variant・purposeの整合をチェック"
    )
    integ_p.add_argument("--usd", required=True)
    integ_p.add_argument("--format", choices=["text", "json"], default="text")
    integ_p.set_defaults(func=integrity.run)

    batch_p = sub.add_parser("batch", help="ディレクトリ配下のUSDファイルを一括検証")
    batch_p.add_argument("--dir", required=True)
    batch_p.add_argument("--format", choices=["csv", "json"], default="json")
    batch_p.add_argument("--workers", type=int, default=4)
    batch_p.add_argument("--rules", default=None)
    batch_p.set_defaults(func=batch.run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
