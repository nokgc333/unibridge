"""NFR-001計測用の大規模USDフィクスチャ生成スクリプト（仕様書§3.2, §12.6）。

Prim数2,000規模のStageをusd-coreでコード生成する。Houdini/Blender不要で
`python tests/fixtures/large_scene/generate.py` により再生成できる
（生成物自体は.gitignoreで除外し、リポジトリには含めない）。
"""

from __future__ import annotations

from pathlib import Path

from pxr import Usd, UsdGeom, UsdShade

PRIM_COUNT_TARGET = 2000
OUTPUT_PATH = Path(__file__).parent / "large_scene.usda"


def generate(output_path: Path = OUTPUT_PATH, prim_count_target: int = PRIM_COUNT_TARGET) -> Path:
    stage = Usd.Stage.CreateNew(str(output_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = stage.DefinePrim("/root", "Scope")
    stage.SetDefaultPrim(root)

    # 1体あたり Xform + Mesh + Material = 3 Prim。目標数に達するまで繰り返す。
    per_asset = 3
    asset_count = prim_count_target // per_asset
    for i in range(asset_count):
        stage.DefinePrim(f"/root/xform_asset_{i:04d}", "Xform")
        stage.DefinePrim(f"/root/geo_asset_{i:04d}", "Mesh")
        UsdShade.Material.Define(stage, f"/root/mat_asset_{i:04d}")

    stage.GetRootLayer().Save()
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Generated {path}")
