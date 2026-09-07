"""DiffEntry / DiffReport / StageMetadataSnapshot 等のデータクラス定義（仕様書§4.2, §4.3）。

usd-core（pxr）にすら依存しない、純粋なデータ構造のみを定義する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class StageMetadataSnapshot:
    """USD Stageから検証に用いるメタデータのスナップショット。"""

    source_path: str
    up_axis: str  # "Y" | "Z"（pxr.UsdGeom.GetStageUpAxis()の戻り値）
    up_axis_is_explicit: bool  # Stageに明示設定されているか（暗黙依存の警告判定に使用）
    meters_per_unit: float  # pxr.UsdGeom.GetStageMetersPerUnit()の戻り値
    meters_per_unit_is_explicit: bool
    prim_count: int
    default_prim_path: str | None


@dataclass(frozen=True)
class PrimRecord:
    """階層走査（hierarchy_check）で収集する単一Primの情報。"""

    path: str  # 例: "/root/geo/char_hero"
    type_name: str  # 例: "Xform", "Mesh", "Material"
    parent_path: str | None
    has_authored_xform: bool


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DiffCategory(str, Enum):
    UP_AXIS_MISMATCH = "up_axis_mismatch"
    SCALE_MISMATCH = "scale_mismatch"
    IMPLICIT_METADATA = "implicit_metadata"
    NAMING_VIOLATION = "naming_violation"
    PRIM_COUNT_DIFF = "prim_count_diff"
    MATERIAL_COUNT_DIFF = "material_count_diff"
    PRIM_REMOVED = "prim_removed"
    PRIM_ADDED = "prim_added"


@dataclass(frozen=True)
class DiffEntry:
    category: DiffCategory
    target_path: str  # Primパス、またはStage全体を指す "(stage)"
    message: str
    severity: Severity
    before_value: str | None = None
    after_value: str | None = None


@dataclass
class DiffReport:
    source_stage: str
    target_stage: str
    generated_at: str  # UTC ISO 8601
    prim_count_before: int
    prim_count_after: int
    material_count_before: int
    material_count_after: int
    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(e.severity == Severity.ERROR for e in self.entries)
