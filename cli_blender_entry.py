"""UniBridge Blender CLIエントリポイント（blender --backgroundから起動、仕様書§5.6）。

使い方（Blender自体の引数分離規約に従い "--" 以降を渡す）:
  blender --background --python cli_blender_entry.py -- --usd <path> [--reexport] [--out <path>]

実bpy呼び出しは adapters.blender_adapter にのみ存在させ、本モジュールの他のロジックは
bpy非依存に保つ（Ports & Adapters, ADR-0002, ADR-0003）。

--- 実機未検証、要検証 ---
このモジュール自体はBlender本体がない環境ではimport時にエラーになる
（adapters.blender_adapterがbpyをimportするため）。仕様書§11.3 RB-002・
要件定義書TC-015に従い、実際のBlender（`blender --background`）で動作確認すること。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Blenderの`--python`実行では、スクリプト自身のディレクトリが必ずしもsys.pathに
# 含まれるとは限らない（実機検証で`ModuleNotFoundError: No module named 'adapters'`を
# 確認）。リポジトリルート（本ファイルの場所）を明示的に追加する。
sys.path.insert(0, str(Path(__file__).resolve().parent))

EXIT_OK = 0
EXIT_FILE_NOT_FOUND = 10
EXIT_INVALID_PARAMETER = 11
EXIT_OUTPUT_NOT_WRITABLE = 14


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UniBridge Blender import/validate CLI")
    parser.add_argument("--usd", required=True, help="読込対象のUSDファイルパス")
    parser.add_argument(
        "--reexport", action="store_true", help="読込直後に再エクスポートする（往復検証）"
    )
    parser.add_argument("--out", default=None, help="--reexport時の出力先パス")
    return parser


def _parse_blender_argv(argv: list[str] | None) -> list[str]:
    """Blenderの `--` 以降の引数だけを取り出す。

    `blender --background --python cli_blender_entry.py -- --usd a.usda` のように
    Blender自体の引数と分離するため、sys.argvの"--"より後ろのみを対象とする。
    """
    raw = argv if argv is not None else sys.argv
    if "--" in raw:
        return raw[raw.index("--") + 1 :]
    return raw[1:]


def main(argv: list[str] | None = None) -> int:
    """`blender --background`上で実行する本番エントリポイント（実機未検証）。"""
    args = _build_arg_parser().parse_args(_parse_blender_argv(argv))

    if args.reexport and not args.out:
        print("Error: --reexport requires --out", file=sys.stderr)
        return EXIT_INVALID_PARAMETER

    try:
        # bpy への依存はこの1行に閉じ込める（実機でのみ実行可能）。
        from adapters.blender_adapter import UsdImportError, import_and_validate
    except ImportError as exc:
        print(
            f"Error: bpy module unavailable (run via blender --background): {exc}", file=sys.stderr
        )
        return EXIT_INVALID_PARAMETER

    try:
        object_names, reexported_path = import_and_validate(
            args.usd, args.out if args.reexport else None
        )
    except UsdImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_FILE_NOT_FOUND
    except OSError as exc:
        print(f"Error: cannot write to '{args.out}': {exc}", file=sys.stderr)
        return EXIT_OUTPUT_NOT_WRITABLE

    print(f"Imported {len(object_names)} object(s) from '{args.usd}'")
    if reexported_path:
        print(f"Re-exported to '{reexported_path}'")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
