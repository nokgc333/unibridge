"""USD の標準的な整合と、マテリアル・UV・variant・purpose の検査。

`usd-core` の配布物には `UsdUtils.ComplianceChecker`(usdchecker)が含まれないため、
その主な観点のうち `usd-core` だけで確かめられるもの(既定 Prim・未解決の参照)を
ここで実装する(docs/adr/0008-compliance-checks-without-usdchecker.md)。
読み取り専用で、Stage を変更しない。
"""

from __future__ import annotations

from pxr import Sdf, Usd, UsdGeom, UsdShade, UsdUtils

from core.report_models import DiffCategory, DiffEntry, Severity

STAGE_TARGET = "(stage)"
STANDARD_PURPOSES = frozenset({"default", "render", "proxy", "guide"})
UV_PRIMVAR_NAME = "st"


def _entry(
    category: DiffCategory, target: str, message: str, severity: Severity = Severity.WARNING
) -> DiffEntry:
    return DiffEntry(category=category, target_path=target, message=message, severity=severity)


def check_default_prim(stage: Usd.Stage) -> list[DiffEntry]:
    """Prim があるのに既定 Prim が無い Stage は、参照されたときに取り込み先を決められない。"""
    if stage.HasDefaultPrim() or not any(True for _ in stage.Traverse()):
        return []
    return [
        _entry(
            DiffCategory.COMPLIANCE_VIOLATION,
            STAGE_TARGET,
            "the stage has prims but no default prim; a reference to this file cannot pick a root",
        )
    ]


def check_unresolved_references(stage: Usd.Stage) -> list[DiffEntry]:
    """sublayer・reference・payload・テクスチャなどのうち、解決できない参照を挙げる。"""
    root = stage.GetRootLayer()
    if root.anonymous:
        return []
    _, _, unresolved = UsdUtils.ComputeAllDependencies(root.identifier)
    return [
        _entry(
            DiffCategory.COMPLIANCE_VIOLATION,
            STAGE_TARGET,
            f"unresolved dependency: {path}",
            Severity.ERROR,
        )
        for path in sorted(unresolved)
    ]


def _bound_material_targets(prim: Usd.Prim) -> list[Sdf.Path]:
    rel = UsdShade.MaterialBindingAPI(prim).GetDirectBindingRel()
    return list(rel.GetTargets()) if rel else []


def _has_inherited_binding(prim: Usd.Prim) -> bool:
    current: Usd.Prim | None = prim
    while current is not None and current.IsValid() and not current.IsPseudoRoot():
        if _bound_material_targets(current):
            return True
        current = current.GetParent()
    return False


def check_materials(stage: Usd.Stage) -> list[DiffEntry]:
    """Mesh のマテリアルの割り当て(親からの継承を含む)と、割り当て先の実在を調べる。"""
    entries: list[DiffEntry] = []
    for prim in stage.Traverse():
        for target in _bound_material_targets(prim):
            if not stage.GetPrimAtPath(target):
                entries.append(
                    _entry(
                        DiffCategory.MATERIAL_BINDING,
                        prim.GetPath().pathString,
                        f"bound material '{target}' does not exist",
                        Severity.ERROR,
                    )
                )
        if prim.IsA(UsdGeom.Mesh) and not _has_inherited_binding(prim):
            entries.append(
                _entry(
                    DiffCategory.MATERIAL_BINDING,
                    prim.GetPath().pathString,
                    "mesh has no material binding",
                )
            )
    return entries


def check_uvs(stage: Usd.Stage) -> list[DiffEntry]:
    """Mesh に UV(primvar `st`)があるかを調べる。"""
    return [
        _entry(DiffCategory.UV_MISSING, prim.GetPath().pathString, "mesh has no 'st' primvar (UV)")
        for prim in stage.Traverse()
        if prim.IsA(UsdGeom.Mesh) and not UsdGeom.PrimvarsAPI(prim).HasPrimvar(UV_PRIMVAR_NAME)
    ]


def check_variants(stage: Usd.Stage) -> list[DiffEntry]:
    """variant set の選択が、未設定でも、存在しない名前でもないかを調べる。"""
    entries: list[DiffEntry] = []
    for prim in stage.Traverse():
        variant_sets = prim.GetVariantSets()
        for set_name in variant_sets.GetNames():
            vset = variant_sets.GetVariantSet(set_name)
            selection = vset.GetVariantSelection()
            target = prim.GetPath().pathString
            if not selection:
                entries.append(
                    _entry(
                        DiffCategory.VARIANT_SELECTION,
                        target,
                        f"variant set '{set_name}' has no selection",
                    )
                )
            elif selection not in vset.GetVariantNames():
                entries.append(
                    _entry(
                        DiffCategory.VARIANT_SELECTION,
                        target,
                        f"variant set '{set_name}' selects '{selection}', which does not exist",
                        Severity.ERROR,
                    )
                )
    return entries


def _purpose_of(prim: Usd.Prim) -> str | None:
    attr = UsdGeom.Imageable(prim).GetPurposeAttr() if prim.IsA(UsdGeom.Imageable) else None
    if not attr or not attr.HasAuthoredValue():
        return None
    value = attr.Get()
    return str(value) if value is not None else None


def check_purposes(stage: Usd.Stage) -> list[DiffEntry]:
    """purpose が標準の 4 種かと、guide の下に render を置いていないかを調べる。"""
    entries: list[DiffEntry] = []
    for prim in stage.Traverse():
        purpose = _purpose_of(prim)
        if purpose is None:
            continue
        path = prim.GetPath().pathString
        if purpose not in STANDARD_PURPOSES:
            entries.append(
                _entry(
                    DiffCategory.PURPOSE_INVALID,
                    path,
                    f"purpose '{purpose}' is not one of {sorted(STANDARD_PURPOSES)}",
                    Severity.ERROR,
                )
            )
        elif purpose == "render" and _purpose_of(prim.GetParent()) == "guide":
            entries.append(
                _entry(
                    DiffCategory.PURPOSE_INVALID,
                    path,
                    "render purpose under a guide parent is never rendered",
                )
            )
    return entries


def run_integrity_checks(stage: Usd.Stage) -> list[DiffEntry]:
    """すべての整合検査を、決まった順で実行する。"""
    return [
        *check_default_prim(stage),
        *check_unresolved_references(stage),
        *check_materials(stage),
        *check_uvs(stage),
        *check_variants(stage),
        *check_purposes(stage),
    ]
