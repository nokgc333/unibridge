"""性質テスト(Hypothesis)。入力の範囲全体で成り立つべき性質を確かめる。"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from core.report_models import DiffCategory, DiffEntry, Severity, StageMetadataSnapshot
from core.report_output import format_entries
from core.scale_check import (
    SCALE_MISMATCH_ERROR_RATIO,
    _up_axis_rotation_matrix,
    check_scale_mismatch,
    check_up_axis_mismatch,
)
from core.stage_loader import _is_unsafe_asset_path

POSITIVE = st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False)
AXES = st.sampled_from(["Y", "Z"])


def _meta(
    up_axis: str = "Y",
    mpu: float = 1.0,
    *,
    up_explicit: bool = True,
) -> StageMetadataSnapshot:
    return StageMetadataSnapshot(
        source_path="x.usda",
        up_axis=up_axis,
        up_axis_is_explicit=up_explicit,
        meters_per_unit=mpu,
        meters_per_unit_is_explicit=True,
        prim_count=1,
        default_prim_path="/root",
    )


class TestScaleMismatch:
    @given(POSITIVE)
    def test_the_same_scale_is_never_reported(self, mpu: float) -> None:
        assert check_scale_mismatch(_meta(mpu=mpu), _meta(mpu=mpu)) == []

    @given(POSITIVE, POSITIVE)
    def test_the_result_does_not_depend_on_which_side_is_the_source(
        self, a: float, b: float
    ) -> None:
        forward = check_scale_mismatch(_meta(mpu=a), _meta(mpu=b))
        backward = check_scale_mismatch(_meta(mpu=b), _meta(mpu=a))

        assert [e.severity for e in forward] == [e.severity for e in backward]

    @given(POSITIVE, st.floats(min_value=1.0001, max_value=SCALE_MISMATCH_ERROR_RATIO - 0.001))
    def test_a_ratio_below_the_limit_is_a_warning(self, base: float, ratio: float) -> None:
        entries = check_scale_mismatch(_meta(mpu=base), _meta(mpu=base * ratio))

        assert [e.severity for e in entries] == [Severity.WARNING]

    @given(POSITIVE, st.floats(min_value=SCALE_MISMATCH_ERROR_RATIO * 1.001, max_value=1e3))
    def test_a_ratio_at_or_above_the_limit_is_an_error(self, base: float, ratio: float) -> None:
        entries = check_scale_mismatch(_meta(mpu=base), _meta(mpu=base * ratio))

        assert [e.severity for e in entries] == [Severity.ERROR]

    @given(POSITIVE, POSITIVE)
    def test_at_most_one_entry_and_it_is_a_scale_mismatch(self, a: float, b: float) -> None:
        entries = check_scale_mismatch(_meta(mpu=a), _meta(mpu=b))

        assert len(entries) <= 1
        assert all(e.category == DiffCategory.SCALE_MISMATCH for e in entries)


class TestUpAxis:
    @given(AXES)
    def test_the_same_explicit_axis_is_never_reported(self, axis: str) -> None:
        assert check_up_axis_mismatch(_meta(axis), _meta(axis)) == []

    @given(AXES, AXES, st.booleans(), st.booleans())
    def test_a_difference_is_always_reported_as_an_error_whatever_is_authored(
        self, a: str, b: str, a_explicit: bool, b_explicit: bool
    ) -> None:
        entries = check_up_axis_mismatch(
            _meta(a, up_explicit=a_explicit), _meta(b, up_explicit=b_explicit)
        )
        categories = [e.category for e in entries]

        assert (DiffCategory.UP_AXIS_MISMATCH in categories) == (a != b)

    @given(AXES, AXES)
    def test_converting_there_and_back_gives_the_identity(self, a: str, b: str) -> None:
        there = _up_axis_rotation_matrix(a, b)
        back = _up_axis_rotation_matrix(b, a)
        product = there * back

        for row in range(4):
            for col in range(4):
                expected = 1.0 if row == col else 0.0
                assert abs(product[row][col] - expected) < 1e-9


SEGMENT = st.from_regex(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,8}", fullmatch=True).filter(
    lambda s: s not in {".", ".."}
)


class TestAssetPaths:
    @given(st.lists(SEGMENT, min_size=1, max_size=5))
    def test_a_plain_relative_path_is_safe(self, parts: list[str]) -> None:
        assert _is_unsafe_asset_path("/".join(parts)) is False

    @given(
        st.lists(SEGMENT, max_size=3), st.lists(SEGMENT, max_size=3), st.sampled_from(["/", "\\"])
    )
    def test_a_path_that_goes_up_a_level_is_unsafe(
        self, before: list[str], after: list[str], sep: str
    ) -> None:
        assert _is_unsafe_asset_path(sep.join([*before, "..", *after])) is True

    @given(st.from_regex(r"[a-z][a-z0-9+.-]{1,8}", fullmatch=True), SEGMENT)
    def test_a_path_with_a_scheme_is_unsafe(self, scheme: str, name: str) -> None:
        assert _is_unsafe_asset_path(f"{scheme}://{name}/a.usd") is True

    @given(st.lists(SEGMENT, min_size=1, max_size=4))
    def test_an_absolute_path_is_unsafe(self, parts: list[str]) -> None:
        assert _is_unsafe_asset_path("/" + "/".join(parts)) is True


class TestFormatEntries:
    @given(st.integers(min_value=0, max_value=20))
    def test_there_is_one_line_for_each_entry_and_one_for_none(self, n: int) -> None:
        entries = [
            DiffEntry(
                category=DiffCategory.NAMING_VIOLATION,
                target_path=f"/p{i}",
                message="m",
                severity=Severity.INFO,
            )
            for i in range(n)
        ]

        assert len(format_entries(entries)) == max(1, n)
