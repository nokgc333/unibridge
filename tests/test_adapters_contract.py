"""adapters/ の契約テスト。実機の代わりに、呼び出しを記録する偽の hou / bpy を使う。

実機(Houdini / Blender)での検証は、README の「実機検証結果」に版ごとに残す。
ここでは、実機で見つかった不具合(匿名サブレイヤーのため空のファイルになる)が、
再び入り込まないことと、DCC に出す呼び出しの順序・引数を固定する。
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fake_dcc import (
    FakeBlender,
    FakeLopNode,
    FakeOtherNode,
    FakeStage,
    load_blender_adapter,
    load_houdini_adapter,
)


@pytest.fixture(autouse=True)
def _restore_modules() -> Iterator[None]:
    saved = {k: sys.modules.get(k) for k in ("hou", "bpy")}
    yield
    for name, module in saved.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module
    sys.modules.pop("adapters.houdini_adapter", None)
    sys.modules.pop("adapters.blender_adapter", None)


class TestHoudiniExport:
    def test_exports_the_composed_stage_not_only_the_root_layer(self, tmp_path: Path) -> None:
        stage = FakeStage()
        adapter = load_houdini_adapter({"/stage/out": FakeLopNode("/stage/out", stage)})
        out = str(tmp_path / "out.usda")

        adapter.export_stage_from_lop("/stage/out", out)

        assert stage.exported == [out]
        assert stage.root_layer_exports == []

    def test_returns_the_path_it_wrote_and_the_file_exists(self, tmp_path: Path) -> None:
        stage = FakeStage()
        adapter = load_houdini_adapter({"/stage/out": FakeLopNode("/stage/out", stage)})
        out = str(tmp_path / "deep" / "dir" / "out.usda")

        result = adapter.export_stage_from_lop("/stage/out", out)

        assert result == out
        assert Path(out).exists()

    def test_a_missing_node_is_reported_with_its_path(self, tmp_path: Path) -> None:
        adapter = load_houdini_adapter({})

        with pytest.raises(adapter.LopNodeNotFoundError, match="/stage/none' does not exist"):
            adapter.export_stage_from_lop("/stage/none", str(tmp_path / "o.usda"))

    def test_a_node_that_is_not_a_lop_node_is_refused(self, tmp_path: Path) -> None:
        adapter = load_houdini_adapter({"/obj/geo": FakeOtherNode("/obj/geo")})

        with pytest.raises(adapter.LopNodeNotFoundError, match="is not a LOP node"):
            adapter.export_stage_from_lop("/obj/geo", str(tmp_path / "o.usda"))

    def test_a_node_without_a_stage_is_refused_and_nothing_is_written(self, tmp_path: Path) -> None:
        adapter = load_houdini_adapter({"/stage/out": FakeLopNode("/stage/out", None)})
        out = tmp_path / "o.usda"

        with pytest.raises(adapter.LopNodeNotFoundError, match="did not produce a valid USD stage"):
            adapter.export_stage_from_lop("/stage/out", str(out))

        assert not out.exists()


class TestHoudiniListing:
    def test_lists_only_the_lop_children(self) -> None:
        stage = FakeStage()
        parent = FakeOtherNode(
            "/stage",
            [
                FakeLopNode("/stage/a", stage),
                FakeOtherNode("/stage/note"),
                FakeLopNode("/stage/b", stage),
            ],
        )
        adapter = load_houdini_adapter({"/stage": parent})

        assert adapter.list_lop_children("/stage") == ["/stage/a", "/stage/b"]

    def test_the_default_parent_is_stage(self) -> None:
        adapter = load_houdini_adapter({"/stage": FakeOtherNode("/stage", [])})

        assert adapter.list_lop_children() == []

    def test_a_missing_parent_is_reported(self) -> None:
        adapter = load_houdini_adapter({})

        with pytest.raises(adapter.LopNodeNotFoundError, match="does not exist"):
            adapter.list_lop_children("/stage")


class TestBlenderImport:
    def test_clears_the_default_scene_before_it_imports(self, tmp_path: Path) -> None:
        usd = tmp_path / "a.usda"
        usd.write_text("#usda 1.0\n", encoding="utf-8")
        fake = FakeBlender(["Mesh"])
        adapter = load_blender_adapter(fake)

        names = adapter.import_usd(str(usd))

        kinds = [kind for kind, _ in fake.calls]
        assert kinds == ["remove", "remove", "usd_import"]
        assert fake.calls[0][1] == ("Cube", True)
        assert names == ["Mesh"]

    def test_a_missing_file_is_refused_before_blender_is_touched(self, tmp_path: Path) -> None:
        fake = FakeBlender([])
        adapter = load_blender_adapter(fake)

        with pytest.raises(adapter.UsdImportError, match="does not exist"):
            adapter.import_usd(str(tmp_path / "missing.usda"))

        assert fake.calls == []

    def test_an_import_that_does_not_finish_is_an_error_with_the_operator_result(
        self, tmp_path: Path
    ) -> None:
        usd = tmp_path / "a.usda"
        usd.write_text("#usda 1.0\n", encoding="utf-8")
        adapter = load_blender_adapter(FakeBlender([], {"CANCELLED"}))

        with pytest.raises(adapter.UsdImportError, match="CANCELLED"):
            adapter.import_usd(str(usd))


class TestBlenderReexport:
    def test_exports_to_the_path_and_creates_its_directory(self, tmp_path: Path) -> None:
        fake = FakeBlender([])
        adapter = load_blender_adapter(fake)
        out = tmp_path / "new" / "dir" / "out.usda"

        result = adapter.reexport_usd(str(out))

        assert result == str(out)
        assert out.parent.is_dir()
        assert fake.calls == [("usd_export", str(out))]

    def test_an_export_that_does_not_finish_is_an_error(self, tmp_path: Path) -> None:
        adapter = load_blender_adapter(FakeBlender([], {"CANCELLED"}))

        with pytest.raises(adapter.UsdImportError, match="failed to export"):
            adapter.reexport_usd(str(tmp_path / "out.usda"))


class TestBlenderRoundTrip:
    def test_imports_and_then_exports_in_that_order(self, tmp_path: Path) -> None:
        usd = tmp_path / "a.usda"
        usd.write_text("#usda 1.0\n", encoding="utf-8")
        fake = FakeBlender(["Mesh"])
        adapter = load_blender_adapter(fake)
        out = str(tmp_path / "re.usda")

        names, written = adapter.import_and_validate(str(usd), out)

        assert names == ["Mesh"]
        assert written == out
        assert [k for k, _ in fake.calls][-2:] == ["usd_import", "usd_export"]

    def test_without_a_path_it_only_imports(self, tmp_path: Path) -> None:
        usd = tmp_path / "a.usda"
        usd.write_text("#usda 1.0\n", encoding="utf-8")
        fake = FakeBlender(["Mesh"])
        adapter = load_blender_adapter(fake)

        names, written = adapter.import_and_validate(str(usd))

        assert written is None
        assert "usd_export" not in [k for k, _ in fake.calls]
        assert names == ["Mesh"]
