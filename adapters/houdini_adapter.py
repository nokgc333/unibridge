"""hou.LopNodeからUSDステージをエクスポートするアダプタ（仕様書§2.2, FR-001, ADR-0002）。

このモジュールは Houdini 同梱の Python（hython）でのみ import 可能。
pytest（venv）環境には `hou` が存在しないため、pyproject.tomlの[tool.mypy] exclude・
[tool.coverage.run] omitにより、CIの型チェック・カバレッジ計測の対象から意図的に除外している。

--- 実機未検証、要検証 ---
本ファイルの正しさは、この開発環境（Houdiniなし、Houdini MCPも本セッションでは接続不可）
では検証できていない。仕様書§11.3 RB-002の手順、要件定義書 TC-014 に従い、
実際のHoudini上で `hython cli_houdini_entry.py export --lop <path> --output <path>`
を実行して動作確認すること。
"""

from __future__ import annotations

from pathlib import Path

import hou  # type: ignore[import-not-found]


class LopNodeNotFoundError(Exception):
    """指定パスにLOPノードが存在しない、またはLOPノードでない場合に送出（E003）。"""


def export_stage_from_lop(lop_node_path: str, output_path: str, file_format: str = "usda") -> str:
    """指定されたLOPノードが構築するUSDステージを、ファイルへエクスポートする。

    Args:
        lop_node_path: エクスポート対象のLOPノードのパス（例: "/stage/out"）。
        output_path: 出力先USDファイルパス。
        file_format: "usda"（テキスト）または"usdc"（バイナリ）。

    Returns:
        実際に書き出したファイルパス（output_pathと同一）。

    Raises:
        LopNodeNotFoundError: 指定パスのノードが存在しない、またはLOPノードでない場合。

    実機未検証: hou.LopNode.stage()の戻り値（pxr.Usd.Stage相当）を
    stage.GetRootLayer().Export()で書き出す想定だが、Houdini実機での動作確認が必要。
    """
    node = hou.node(lop_node_path)
    if node is None:
        raise LopNodeNotFoundError(f"'{lop_node_path}' does not exist")
    if not isinstance(node, hou.LopNode):
        raise LopNodeNotFoundError(f"'{lop_node_path}' is not a LOP node")

    stage = node.stage()
    if stage is None:
        raise LopNodeNotFoundError(f"'{lop_node_path}' did not produce a valid USD stage")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    stage.GetRootLayer().Export(output_path)
    return output_path


def list_lop_children(parent_path: str = "/stage") -> list[str]:
    """指定パス配下のLOPノードのパス一覧を返す（Web GUI/CLIでの選択肢提示用）。

    実機未検証。
    """
    parent = hou.node(parent_path)
    if parent is None:
        raise LopNodeNotFoundError(f"'{parent_path}' does not exist")
    return [child.path() for child in parent.children() if isinstance(child, hou.LopNode)]
