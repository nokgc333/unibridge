"""core/scale_check.py のテスト（TC-001〜007）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pxr import Usd

from core.report_models import DiffCategory, Severity
from core.scale_check import (
    SCALE_MISMATCH_ERROR_RATIO,
    apply_scale_conversion,
    apply_up_axis_conversion,
    check_scale_mismatch,
    check_up_axis_mismatch,
    extract_metadata,
)
from tests.conftest import open_stage


class TestExtractMetadata:
    def test_explicit_up_axis_and_mpu_are_flagged_explicit(self, stage_y_up_meters: Path) -> None:
        stage = open_stage(stage_y_up_meters)
        meta = extract_metadata(stage, str(stage_y_up_meters))

        assert meta.up_axis == "Y"
        assert meta.up_axis_is_explicit is True
        assert meta.meters_per_unit == 1.0
        assert meta.meters_per_unit_is_explicit is True
        assert meta.default_prim_path == "/root"

    def test_implicit_metadata_uses_usd_defaults_but_flags_false(
        self, stage_implicit_metadata: Path
    ) -> None:
        stage = open_stage(stage_implicit_metadata)
        meta = extract_metadata(stage, str(stage_implicit_metadata))

        # USD既定値: upAxis="Y", metersPerUnit=0.01（実測値、core/scale_check.py参照）
        assert meta.up_axis == "Y"
        assert meta.up_axis_is_explicit is False
        assert meta.meters_per_unit == 0.01
        assert meta.meters_per_unit_is_explicit is False

    def test_prim_count_reflects_all_traversed_prims(self, stage_y_up_meters: Path) -> None:
        stage = open_stage(stage_y_up_meters)
        meta = extract_metadata(stage, str(stage_y_up_meters))

        # /root, /root/xform_hero, /root/xform_hero/geo_body, /root/mat_hero = 4
        assert meta.prim_count == 4


class TestCheckUpAxisMismatch:
    def test_same_up_axis_produces_no_mismatch_entry(
        self, stage_y_up_meters: Path, stage_y_up_meters_v2: Path
    ) -> None:
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = extract_metadata(open_stage(stage_y_up_meters_v2), "target")

        entries = check_up_axis_mismatch(source, target)

        assert all(e.category != DiffCategory.UP_AXIS_MISMATCH for e in entries)

    def test_different_up_axis_produces_error_entry(
        self, stage_y_up_meters: Path, stage_z_up_centimeters: Path
    ) -> None:
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = extract_metadata(open_stage(stage_z_up_centimeters), "target")

        entries = check_up_axis_mismatch(source, target)
        mismatch = [e for e in entries if e.category == DiffCategory.UP_AXIS_MISMATCH]

        assert len(mismatch) == 1
        assert mismatch[0].severity == Severity.ERROR
        assert mismatch[0].before_value == "Y"
        assert mismatch[0].after_value == "Z"

    def test_implicit_metadata_on_either_side_warns(
        self, stage_y_up_meters: Path, stage_implicit_metadata: Path
    ) -> None:
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = extract_metadata(open_stage(stage_implicit_metadata), "target")

        entries = check_up_axis_mismatch(source, target)
        implicit = [e for e in entries if e.category == DiffCategory.IMPLICIT_METADATA]

        assert len(implicit) == 1
        assert implicit[0].severity == Severity.WARNING

    def test_explicit_both_sides_produces_no_implicit_warning(
        self, stage_y_up_meters: Path, stage_y_up_meters_v2: Path
    ) -> None:
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = extract_metadata(open_stage(stage_y_up_meters_v2), "target")

        entries = check_up_axis_mismatch(source, target)

        assert all(e.category != DiffCategory.IMPLICIT_METADATA for e in entries)


class TestCheckScaleMismatch:
    def test_ratio_of_one_produces_no_entry(
        self, stage_y_up_meters: Path, stage_y_up_meters_v2: Path
    ) -> None:
        """境界値: metersPerUnitが完全一致（ratio=1.0）の場合は変換不要で警告なし。"""
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = extract_metadata(open_stage(stage_y_up_meters_v2), "target")

        entries = check_scale_mismatch(source, target)

        assert entries == []

    def test_ratio_below_error_threshold_is_warning(self, stage_y_up_meters: Path) -> None:
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = source.__class__(
            source_path="target",
            up_axis=source.up_axis,
            up_axis_is_explicit=True,
            meters_per_unit=0.5,  # ratio = 1.0/0.5 = 2.0 < 10.0
            meters_per_unit_is_explicit=True,
            prim_count=0,
            default_prim_path=None,
        )

        entries = check_scale_mismatch(source, target)

        assert len(entries) == 1
        assert entries[0].severity == Severity.WARNING

    def test_ratio_at_error_threshold_is_error(self, stage_y_up_meters: Path) -> None:
        """境界値: ratio == SCALE_MISMATCH_ERROR_RATIO(10.0)はerror。"""
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = source.__class__(
            source_path="target",
            up_axis=source.up_axis,
            up_axis_is_explicit=True,
            meters_per_unit=1.0 / SCALE_MISMATCH_ERROR_RATIO,
            meters_per_unit_is_explicit=True,
            prim_count=0,
            default_prim_path=None,
        )

        entries = check_scale_mismatch(source, target)

        assert len(entries) == 1
        assert entries[0].severity == Severity.ERROR

    def test_zero_meters_per_unit_raises_value_error(self, stage_y_up_meters: Path) -> None:
        source = extract_metadata(open_stage(stage_y_up_meters), "source")
        target = source.__class__(
            source_path="target",
            up_axis=source.up_axis,
            up_axis_is_explicit=True,
            meters_per_unit=0.0,
            meters_per_unit_is_explicit=True,
            prim_count=0,
            default_prim_path=None,
        )

        with pytest.raises(ValueError):
            check_scale_mismatch(source, target)


class TestApplyUpAxisConversion:
    def test_converted_file_has_target_up_axis(
        self, stage_z_up_centimeters: Path, tmp_path: Path
    ) -> None:
        stage = open_stage(stage_z_up_centimeters)
        output_path = tmp_path / "converted.usda"

        apply_up_axis_conversion(stage, "Y", str(output_path))

        converted = Usd.Stage.Open(str(output_path))
        assert converted is not None
        from pxr import UsdGeom

        assert UsdGeom.GetStageUpAxis(converted) == "Y"

    def test_does_not_overwrite_original_file(
        self, stage_z_up_centimeters: Path, tmp_path: Path
    ) -> None:
        """SEC-003: 既存ファイルへの上書きは行わない。"""
        original_bytes = stage_z_up_centimeters.read_bytes()
        stage = open_stage(stage_z_up_centimeters)
        output_path = tmp_path / "converted.usda"

        apply_up_axis_conversion(stage, "Y", str(output_path))

        assert stage_z_up_centimeters.read_bytes() == original_bytes


class TestApplyScaleConversion:
    def test_converted_file_has_target_meters_per_unit(
        self, stage_z_up_centimeters: Path, tmp_path: Path
    ) -> None:
        stage = open_stage(stage_z_up_centimeters)
        output_path = tmp_path / "converted.usda"

        apply_scale_conversion(stage, 1.0, str(output_path))

        converted = Usd.Stage.Open(str(output_path))
        assert converted is not None
        from pxr import UsdGeom

        assert UsdGeom.GetStageMetersPerUnit(converted) == 1.0

    def test_zero_target_meters_per_unit_raises_value_error(
        self, stage_y_up_meters: Path, tmp_path: Path
    ) -> None:
        stage = open_stage(stage_y_up_meters)

        with pytest.raises(ValueError):
            apply_scale_conversion(stage, 0.0, str(tmp_path / "out.usda"))
