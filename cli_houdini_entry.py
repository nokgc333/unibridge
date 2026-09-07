"""UniBridge Houdini CLIエントリポイント（hythonから起動、仕様書§5.6）。

使い方:
  hython cli_houdini_entry.py export --lop <lop_node_path> --output <path> [--format {usda,usdc}]

実hou呼び出しは adapters.houdini_adapter にのみ存在させ、本モジュールの他のロジックは
hou非依存に保つ（Ports & Adapters, ADR-0002）。

--- 実機未検証、要検証 ---
このモジュール自体はHoudini本体がない環境ではimport時にエラーになる
（adapters.houdini_adapterがhouをimportするため）。Houdini MCPが本セッションでは
接続不可のため、実機（hython）での動作確認は行えていない。仕様書§11.3 RB-002を参照。
"""

from __future__ import annotations

import argparse
import sys

EXIT_OK = 0
EXIT_INVALID_PARAMETER = 11
EXIT_INVALID_TARGET_NODE = 12
EXIT_OUTPUT_NOT_WRITABLE = 14


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UniBridge Houdini export CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export", help="LOPノードからUSDをエクスポート")
    export_p.add_argument("--lop", required=True, help="エクスポート対象のLOPノードパス")
    export_p.add_argument("--output", required=True, help="出力先USDファイルパス")
    export_p.add_argument("--format", choices=["usda", "usdc"], default="usda")

    return parser


def main(argv: list[str] | None = None) -> int:
    """hython上で実行する本番エントリポイント（実機未検証）。"""
    args = _build_arg_parser().parse_args(argv)

    if not args.output.lower().endswith((".usda", ".usdc", ".usd")):
        print(f"Error: unsupported output extension '{args.output}'", file=sys.stderr)
        return EXIT_INVALID_PARAMETER

    try:
        # hou への依存はこの1行に閉じ込める（実機でのみ実行可能）。
        from adapters.houdini_adapter import LopNodeNotFoundError, export_stage_from_lop
    except ImportError as exc:
        print(f"Error: hou module unavailable (run via hython): {exc}", file=sys.stderr)
        return EXIT_INVALID_PARAMETER

    try:
        output_path = export_stage_from_lop(args.lop, args.output, args.format)
    except LopNodeNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INVALID_TARGET_NODE
    except OSError as exc:
        print(f"Error: cannot write to '{args.output}': {exc}", file=sys.stderr)
        return EXIT_OUTPUT_NOT_WRITABLE

    print(f"Exported '{args.lop}' -> '{output_path}'")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
