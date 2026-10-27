"""core/integrity_check.py のテスト(標準寄りの検査と、マテリアル・UV・variant・purpose の整合)。"""

from __future__ import annotations

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdShade

from core.integrity_check import (
    check_default_prim,
    check_materials,
    check_purposes,
    check_unresolved_references,
    check_uvs,
    check_variants,
    run_integrity_checks,
)
from core.report_models import DiffCategory, Severity


def _stage() -> Usd.Stage:
    return Usd.Stage.CreateInMemory()


def _mesh(stage: Usd.Stage, path: str) -> UsdGeom.Mesh:
    return UsdGeom.Mesh.Define(stage, path)


def _material(stage: Usd.Stage, path: str) -> UsdShade.Material:
    return UsdShade.Material.Define(stage, path)


def _add_st(mesh: UsdGeom.Mesh, interpolation: str = "vertex") -> None:
    pv = UsdGeom.PrimvarsAPI(mesh.GetPrim()).CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, interpolation
    )
    pv.Set([(0.0, 0.0)])


class TestDefaultPrim:
    def test_a_stage_with_prims_but_no_default_prim_is_a_warning(self) -> None:
        stage = _stage()
        UsdGeom.Xform.Define(stage, "/root")

        entries = check_default_prim(stage)

        assert [e.category for e in entries] == [DiffCategory.COMPLIANCE_VIOLATION]
        assert entries[0].severity == Severity.WARNING
        assert entries[0].target_path == "(stage)"

    def test_a_stage_with_a_default_prim_has_no_finding(self) -> None:
        stage = _stage()
        stage.SetDefaultPrim(UsdGeom.Xform.Define(stage, "/root").GetPrim())

        assert check_default_prim(stage) == []

    def test_an_empty_stage_has_no_finding(self) -> None:
        assert check_default_prim(_stage()) == []


class TestUnresolvedReferences:
    def test_a_reference_to_a_missing_file_is_an_error(self, tmp_path: Path) -> None:
        layer_path = tmp_path / "scene.usda"
        stage = Usd.Stage.CreateNew(str(layer_path))
        prim = stage.DefinePrim("/a")
        prim.GetReferences().AddReference("./missing.usda")
        stage.GetRootLayer().Save()

        entries = check_unresolved_references(Usd.Stage.Open(str(layer_path)))

        assert len(entries) == 1
        assert entries[0].severity == Severity.ERROR
        assert "missing.usda" in entries[0].message

    def test_a_missing_sublayer_is_an_error(self, tmp_path: Path) -> None:
        layer_path = tmp_path / "scene.usda"
        layer = Sdf.Layer.CreateNew(str(layer_path))
        layer.subLayerPaths.append("./gone.usda")
        layer.Save()

        entries = check_unresolved_references(Usd.Stage.Open(str(layer_path)))

        assert any("gone.usda" in e.message for e in entries)

    def test_resolvable_references_have_no_finding(self, tmp_path: Path) -> None:
        other = tmp_path / "other.usda"
        other_stage = Usd.Stage.CreateNew(str(other))
        other_stage.GetRootLayer().Save()
        layer_path = tmp_path / "scene.usda"
        stage = Usd.Stage.CreateNew(str(layer_path))
        stage.DefinePrim("/a").GetReferences().AddReference("./other.usda")
        stage.GetRootLayer().Save()

        assert check_unresolved_references(Usd.Stage.Open(str(layer_path))) == []


class TestMaterials:
    def test_a_mesh_without_a_material_binding_is_a_warning(self) -> None:
        stage = _stage()
        _mesh(stage, "/m")

        entries = check_materials(stage)

        assert [e.category for e in entries] == [DiffCategory.MATERIAL_BINDING]
        assert entries[0].target_path == "/m"
        assert entries[0].severity == Severity.WARNING

    def test_a_bound_mesh_has_no_finding(self) -> None:
        stage = _stage()
        mesh = _mesh(stage, "/m")
        mat = _material(stage, "/mat")
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)

        assert check_materials(stage) == []

    def test_a_binding_to_a_missing_material_is_an_error(self) -> None:
        stage = _stage()
        mesh = _mesh(stage, "/m")
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).GetDirectBindingRel().SetTargets(
            [Sdf.Path("/nope")]
        )

        entries = check_materials(stage)

        assert [e.severity for e in entries] == [Severity.ERROR]
        assert "/nope" in entries[0].message

    def test_a_mesh_inherits_the_binding_of_its_parent(self) -> None:
        stage = _stage()
        group = UsdGeom.Xform.Define(stage, "/g")
        _mesh(stage, "/g/m")
        UsdShade.MaterialBindingAPI.Apply(group.GetPrim()).Bind(_material(stage, "/mat"))

        assert check_materials(stage) == []


class TestUvs:
    def test_a_mesh_without_st_is_a_warning(self) -> None:
        stage = _stage()
        _mesh(stage, "/m")

        entries = check_uvs(stage)

        assert [e.category for e in entries] == [DiffCategory.UV_MISSING]
        assert entries[0].target_path == "/m"

    def test_a_mesh_with_st_has_no_finding(self) -> None:
        stage = _stage()
        _add_st(_mesh(stage, "/m"))

        assert check_uvs(stage) == []

    def test_a_non_mesh_prim_is_not_checked(self) -> None:
        stage = _stage()
        UsdGeom.Xform.Define(stage, "/x")

        assert check_uvs(stage) == []


class TestVariants:
    def test_a_variant_set_without_a_selection_is_a_warning(self) -> None:
        stage = _stage()
        prim = stage.DefinePrim("/a")
        vset = prim.GetVariantSets().AddVariantSet("look")
        vset.AddVariant("red")

        entries = check_variants(stage)

        assert [e.category for e in entries] == [DiffCategory.VARIANT_SELECTION]
        assert "look" in entries[0].message

    def test_a_selected_variant_has_no_finding(self) -> None:
        stage = _stage()
        prim = stage.DefinePrim("/a")
        vset = prim.GetVariantSets().AddVariantSet("look")
        vset.AddVariant("red")
        vset.SetVariantSelection("red")

        assert check_variants(stage) == []

    def test_a_selection_that_names_no_variant_is_an_error(self) -> None:
        stage = _stage()
        prim = stage.DefinePrim("/a")
        vset = prim.GetVariantSets().AddVariantSet("look")
        vset.AddVariant("red")
        vset.SetVariantSelection("blue")

        entries = check_variants(stage)

        assert [e.severity for e in entries] == [Severity.ERROR]
        assert "blue" in entries[0].message


class TestPurposes:
    def test_an_unknown_purpose_token_is_an_error(self) -> None:
        stage = _stage()
        imageable = UsdGeom.Xform.Define(stage, "/x")
        imageable.GetPurposeAttr().Set("final")

        entries = check_purposes(stage)

        assert [e.category for e in entries] == [DiffCategory.PURPOSE_INVALID]
        assert entries[0].severity == Severity.ERROR

    def test_the_four_standard_purposes_are_accepted(self) -> None:
        stage = _stage()
        for name in ("default", "render", "proxy", "guide"):
            UsdGeom.Xform.Define(stage, f"/{name}").GetPurposeAttr().Set(name)

        assert check_purposes(stage) == []

    def test_a_render_purpose_child_under_a_guide_parent_is_a_warning(self) -> None:
        stage = _stage()
        UsdGeom.Xform.Define(stage, "/p").GetPurposeAttr().Set("guide")
        UsdGeom.Xform.Define(stage, "/p/c").GetPurposeAttr().Set("render")

        entries = check_purposes(stage)

        assert [e.severity for e in entries] == [Severity.WARNING]
        assert entries[0].target_path == "/p/c"


class TestRunAll:
    def test_combines_every_check_in_a_stable_order(self) -> None:
        stage = _stage()
        UsdGeom.Xform.Define(stage, "/root")
        _mesh(stage, "/root/m")

        categories = [e.category for e in run_integrity_checks(stage)]

        assert categories == [
            DiffCategory.COMPLIANCE_VIOLATION,
            DiffCategory.MATERIAL_BINDING,
            DiffCategory.UV_MISSING,
        ]
