"""bpy.ops.wm.usd_import/usd_export経由でのBlender読込検証アダプタ（仕様書§2.2, FR-002, ADR-0003）。

このモジュールは Blender 同梱の Python（`blender --background`実行時）でのみ import 可能。
pytest（venv）環境には `bpy` が存在しないため、pyproject.tomlの[tool.mypy] exclude・
[tool.coverage.run] omitにより、CIの型チェック・カバレッジ計測の対象から意図的に除外している。

--- 実機未検証、要検証 ---
本ファイルの正しさは、この開発環境（Blenderアプリが/Applications/Blender.appに
存在しない、または実行未確認）では検証できていない。仕様書§11.3 RB-002の手順、
要件定義書 TC-015 に従い、実際のBlender上で
`blender --background --python cli_blender_entry.py -- --usd <path> --reexport`
を実行して動作確認すること。ADR-0003が定義する「往復(round-trip)検証」の設計
（読込→即座に再エクスポート→core.diff_reportで元ファイルと比較）が
意図通りに機能するかは、Blenderのバージョンごとの USD I/O 実装の挙動に依存するため
実機検証なしには保証できない。
"""

from __future__ import annotations

from pathlib import Path

import bpy  # type: ignore[import-not-found]


class UsdImportError(Exception):
    """USDファイルのBlenderへの読込に失敗した場合に送出（E001相当）。"""


def _clear_default_scene() -> None:
    """Blenderの既定スタートアップシーン（Cube/Camera/Light）を全て削除する。

    実機検証で判明: `blender --background --python ...` は既定の startup.blend
    （Cube/Camera/Lightを含む）をロードした状態から始まるため、これをクリアせずに
    usd_importすると、インポート結果のオブジェクト一覧に既定オブジェクトが混入する
    （検証結果が不正確になる、TC-015実機検証で確認）。
    """
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def import_usd(usd_path: str) -> list[str]:
    """既定シーンをクリアした上でUSDファイルをBlenderシーンへインポートし、
    読込後のオブジェクト名一覧を返す。

    実機検証済み（Blender 4.0.0, --background）: `bpy.ops.wm.usd_import(filepath=...)`
    は成功時 `{'FINISHED'}` を返すことを確認した。
    """
    path = Path(usd_path)
    if not path.exists():
        raise UsdImportError(f"'{usd_path}' does not exist")

    _clear_default_scene()

    result = bpy.ops.wm.usd_import(filepath=str(path))
    if "FINISHED" not in result:
        raise UsdImportError(f"failed to import '{usd_path}': operator result={result}")

    return [obj.name for obj in bpy.data.objects]


def reexport_usd(output_path: str) -> str:
    """現在のBlenderシーンをUSDとして再エクスポートする（往復検証、ADR-0003）。

    実機未検証。
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result = bpy.ops.wm.usd_export(filepath=output_path)
    if "FINISHED" not in result:
        raise UsdImportError(f"failed to export to '{output_path}': operator result={result}")
    return output_path


def import_and_validate(
    usd_path: str, reexport_path: str | None = None
) -> tuple[list[str], str | None]:
    """USDをインポートし、reexport_pathが指定されていれば往復検証のため再エクスポートする。

    Returns:
        (読込後のオブジェクト名一覧, 再エクスポート先パス or None)

    実機未検証。
    """
    object_names = import_usd(usd_path)
    reexported_path = reexport_usd(reexport_path) if reexport_path else None
    return object_names, reexported_path
