"""座標系(upAxis)・スケール単位(metersPerUnit)の検出・変換・不整合警告（仕様書§5.2, §8.1, §8.2）。

read-only（副作用なし、SEC-003）な検出系関数と、`apply_*`接頭辞を持つ
明示オプトインでのみ実行される変換系関数を分離している
（docs/adr/0005-report-only-no-autofix.md）。
"""

from __future__ import annotations

from pxr import Gf, Usd, UsdGeom

from core.report_models import DiffCategory, DiffEntry, Severity, StageMetadataSnapshot

SCALE_MISMATCH_ERROR_RATIO = 10.0  # この倍率以上の不一致はseverity=errorに引き上げる（FR-003 AC-3）


def extract_metadata(stage: Usd.Stage, source_path: str) -> StageMetadataSnapshot:
    """Stageから座標系・スケール単位のメタデータを抽出する。

    未設定時はUSD既定値を採用しつつis_explicitフラグをFalseにし、
    暗黙依存であることを呼び出し側が判定できるようにする。
    """
    up_axis_authored = stage.HasAuthoredMetadata("upAxis")
    up_axis = UsdGeom.GetStageUpAxis(stage)  # 未設定時は既定 "Y"

    mpu_authored = stage.HasAuthoredMetadata("metersPerUnit")
    # 未設定時のUSD既定値は0.01（centimeters）。仕様書§5.2は「既定1.0」と記載しているが、
    # usd-core 24.11で実測した結果、実際のpxr既定値は0.01であることを確認した
    # （ドキュメントと実装の乖離。UsdGeom.GetStageMetersPerUnit()の実挙動を正とする）。
    meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)

    return StageMetadataSnapshot(
        source_path=source_path,
        up_axis=up_axis,
        up_axis_is_explicit=up_axis_authored,
        meters_per_unit=meters_per_unit,
        meters_per_unit_is_explicit=mpu_authored,
        prim_count=sum(1 for _ in stage.Traverse()),
        default_prim_path=(
            stage.GetDefaultPrim().GetPath().pathString if stage.HasDefaultPrim() else None
        ),
    )


def check_up_axis_mismatch(
    source: StageMetadataSnapshot, target: StageMetadataSnapshot
) -> list[DiffEntry]:
    """upAxisの不一致・暗黙依存を検出する。

    upAxisが同一であれば不一致エントリは生成されない（境界値: 一致時は警告なし）。
    """
    entries: list[DiffEntry] = []
    if not source.up_axis_is_explicit or not target.up_axis_is_explicit:
        entries.append(
            DiffEntry(
                category=DiffCategory.IMPLICIT_METADATA,
                target_path="(stage)",
                message="upAxis is not explicitly authored on one or both stages; "
                "relying on USD default (Y) can silently cause mismatches",
                severity=Severity.WARNING,
            )
        )
    if source.up_axis != target.up_axis:
        entries.append(
            DiffEntry(
                category=DiffCategory.UP_AXIS_MISMATCH,
                target_path="(stage)",
                message=f"upAxis mismatch: source={source.up_axis}, target={target.up_axis}",
                severity=Severity.ERROR,
                before_value=source.up_axis,
                after_value=target.up_axis,
            )
        )
    return entries


def check_scale_mismatch(
    source: StageMetadataSnapshot, target: StageMetadataSnapshot
) -> list[DiffEntry]:
    """metersPerUnitの不一致を検出する。

    比率(ratio)が1.0（完全一致、metersPerUnit=1.0同士を含む）の場合はエントリを生成しない
    （境界値: 変換不要）。ratio >= SCALE_MISMATCH_ERROR_RATIO の場合はseverity=error、
    それ以外（1.0 < ratio < 10.0）はseverity=warningとする。
    """
    entries: list[DiffEntry] = []
    if source.meters_per_unit == 0 or target.meters_per_unit == 0:
        raise ValueError("metersPerUnit must be non-zero")

    ratio = max(source.meters_per_unit, target.meters_per_unit) / min(
        source.meters_per_unit, target.meters_per_unit
    )
    if ratio > 1.0:
        severity = Severity.ERROR if ratio >= SCALE_MISMATCH_ERROR_RATIO else Severity.WARNING
        entries.append(
            DiffEntry(
                category=DiffCategory.SCALE_MISMATCH,
                target_path="(stage)",
                message=(
                    f"metersPerUnit mismatch: source={source.meters_per_unit}, "
                    f"target={target.meters_per_unit} (ratio={ratio:.2f}x)"
                ),
                severity=severity,
                before_value=str(source.meters_per_unit),
                after_value=str(target.meters_per_unit),
            )
        )
    return entries


def _up_axis_rotation_matrix(source_axis: str, target_axis: str) -> Gf.Matrix4d:
    """Y-up <-> Z-up の変換行列を返す。それ以外の組み合わせは恒等行列。"""
    if source_axis == target_axis:
        return Gf.Matrix4d(1.0)  # 恒等行列
    if source_axis == "Y" and target_axis == "Z":
        # X軸周りに+90度回転（Y-upのY軸をZ-upのZ軸位置へ）
        return Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), 90.0))
    if source_axis == "Z" and target_axis == "Y":
        # X軸周りに-90度回転（逆変換）
        return Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), -90.0))
    raise ValueError(f"unsupported axis combination: {source_axis} -> {target_axis}")


def apply_up_axis_conversion(stage: Usd.Stage, target_axis: str, output_path: str) -> None:
    """Stageのデフォルトプリムのルートに変換用XformOpを挿入し、新規ファイルへ書き出す。

    既存ファイルへの上書きは行わない（SEC-003）。明示的にapply_conversion=trueを
    指定した場合のみ呼び出される想定（docs/adr/0005-report-only-no-autofix.md）。
    """
    current_axis = UsdGeom.GetStageUpAxis(stage)
    matrix = _up_axis_rotation_matrix(current_axis, target_axis)

    if not stage.HasDefaultPrim():
        raise ValueError("stage has no default prim; cannot apply up-axis conversion")

    default_prim = stage.GetDefaultPrim()
    xformable = UsdGeom.Xformable(default_prim)
    xformable.AddTransformOp().Set(matrix)
    UsdGeom.SetStageUpAxis(stage, target_axis)

    stage.GetRootLayer().Export(output_path)


def apply_scale_conversion(
    stage: Usd.Stage, target_meters_per_unit: float, output_path: str
) -> None:
    """sourceのmetersPerUnitをtargetに合わせるスケール変換を適用し、新規ファイルへ書き出す。

    scale_factor = source.metersPerUnit / target.metersPerUnit（仕様書§8.2）。
    既存ファイルへの上書きは行わない（SEC-003）。
    """
    if target_meters_per_unit == 0:
        raise ValueError("target_meters_per_unit must be non-zero")

    current_mpu = UsdGeom.GetStageMetersPerUnit(stage)
    scale_factor = current_mpu / target_meters_per_unit

    if not stage.HasDefaultPrim():
        raise ValueError("stage has no default prim; cannot apply scale conversion")

    default_prim = stage.GetDefaultPrim()
    xformable = UsdGeom.Xformable(default_prim)
    xformable.AddScaleOp().Set(Gf.Vec3f(scale_factor, scale_factor, scale_factor))
    UsdGeom.SetStageMetersPerUnit(stage, target_meters_per_unit)

    stage.GetRootLayer().Export(output_path)
