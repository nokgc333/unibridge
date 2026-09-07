"""hou.LopNodeからUSDステージをエクスポートするアダプタ（仕様書§2.2, FR-001, ADR-0002）。

このモジュールは Houdini 同梱の Python（hython）でのみ import 可能。
pytest（venv）環境には `hou` が存在しないため、pyproject.tomlの[tool.mypy] exclude・
[tool.coverage.run] omitにより、CIの型チェック・カバレッジ計測の対象から意図的に除外している。

--- 実機検証済み（2026-09-08） ---
Steam版Houdini Indie 22.0.429同梱のhythonで、`/stage`配下に新規構築したLOPsネットワーク
（sphere/cube LOPノード + merge）に対し`export_stage_from_lop`/`list_lop_children`を
実際に実行して検証した。検証中に`stage.GetRootLayer().Export()`が空の（匿名sublayer参照
のみの）ファイルを書き出すバグを発見し、`stage.Export()`に修正して解消した
（詳細はREADME「実機検証結果」参照）。
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

    実機検証済み（2026-09-08、hython 22.0.429 + usd-core 26.8）: 当初
    `stage.GetRootLayer().Export()` を使用していたが、Houdini実機で検証したところ、
    LOPノードの`stage()`が返す合成済みStageは複数の匿名sublayer（Houdiniセッション内
    メモリ上にのみ存在するレイヤー）から構成されており、ルートレイヤーのみをExportすると
    それらの匿名sublayerへの参照(`subLayers`)だけが書き出され、実際のプリム内容
    （ジオメトリ等）が一切含まれない空のファイルになることが判明した。
    `stage.Export()`（`Usd.Stage.Export`、合成結果をフラット化して書き出す）に修正し、
    実データ（sphere/cubeプリムを含むLOPsネットワーク）で往復検証して解消を確認した。
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
    # 合成済みStageをフラット化して書き出す（GetRootLayer().Export()は
    # 匿名sublayerへの参照しか書き出さず内容が失われるため使用しない。実機検証で判明）。
    stage.Export(output_path)
    return output_path


def list_lop_children(parent_path: str = "/stage") -> list[str]:
    """指定パス配下のLOPノードのパス一覧を返す（Web GUI/CLIでの選択肢提示用）。

    実機検証済み（2026-09-08、hython 22.0.429）。
    """
    parent = hou.node(parent_path)
    if parent is None:
        raise LopNodeNotFoundError(f"'{parent_path}' does not exist")
    return [child.path() for child in parent.children() if isinstance(child, hou.LopNode)]
