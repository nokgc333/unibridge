"""共通フィクスチャ（仕様書§12.5）。usd-coreでStageをコード生成し、Houdini/Blender不要でCI完結する。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pxr import Usd, UsdGeom, UsdShade


def _build_stage(
    path: Path,
    up_axis: str,
    meters_per_unit: float,
    *,
    author_up_axis: bool = True,
    author_mpu: bool = True,
    # rules/default.yamlの命名パターンは「/親/xform_xxx」「/親/geo_xxx」の2階層のみに
    # マッチするため、直下の子として配置する（rootはScopeにして規則対象外にする）。
    prim_paths: tuple[str, ...] = ("/root/xform_hero", "/root/geo_body"),
    material_paths: tuple[str, ...] = ("/root/mat_hero",),
) -> Path:
    stage = Usd.Stage.CreateNew(str(path))
    if author_up_axis:
        UsdGeom.SetStageUpAxis(stage, up_axis)
    if author_mpu:
        UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit)
    root = stage.DefinePrim("/root", "Scope")
    stage.SetDefaultPrim(root)
    for p in prim_paths:
        stage.DefinePrim(p, "Mesh" if "geo_" in p else "Xform")
    for m in material_paths:
        UsdShade.Material.Define(stage, m)
    stage.GetRootLayer().Save()
    return path


@pytest.fixture
def stage_y_up_meters(tmp_path: Path) -> Path:
    """upAxis=Y, metersPerUnit=1.0 の最小構成Stageを生成する。"""
    return _build_stage(tmp_path / "y_up_m.usda", UsdGeom.Tokens.y, 1.0)


@pytest.fixture
def stage_z_up_centimeters(tmp_path: Path) -> Path:
    """upAxis=Z, metersPerUnit=0.01 の最小構成Stageを生成する（不整合検証用）。"""
    return _build_stage(tmp_path / "z_up_cm.usda", UsdGeom.Tokens.z, 0.01)


@pytest.fixture
def stage_y_up_meters_v2(tmp_path: Path) -> Path:
    """stage_y_up_metersと同一の座標系・スケールで、upAxis/metersPerUnit一致確認用。"""
    return _build_stage(tmp_path / "y_up_m_v2.usda", UsdGeom.Tokens.y, 1.0)


@pytest.fixture
def stage_implicit_metadata(tmp_path: Path) -> Path:
    """upAxis/metersPerUnitを一切authorしていないStage（暗黙依存の警告確認用）。"""
    return _build_stage(
        tmp_path / "implicit.usda",
        UsdGeom.Tokens.y,
        1.0,
        author_up_axis=False,
        author_mpu=False,
    )


def open_stage(path: Path) -> Usd.Stage:
    stage = Usd.Stage.Open(str(path))
    assert stage is not None
    return stage
