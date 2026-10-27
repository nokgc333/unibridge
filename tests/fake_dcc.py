"""hou と bpy の呼び出し記録つきの偽物。実機が無くても、アダプタが DCC に出す呼び出しの契約を確かめる。"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any


class FakeStage:
    def __init__(self) -> None:
        self.exported: list[str] = []
        self.root_layer_exports: list[str] = []

    def Export(self, path: str) -> bool:  # noqa: N802 - Usd.Stage.Export と同じ名前
        self.exported.append(path)
        Path(path).write_text("#usda 1.0\n", encoding="utf-8")
        return True

    def GetRootLayer(self) -> FakeRootLayer:  # noqa: N802
        return FakeRootLayer(self)


class FakeRootLayer:
    def __init__(self, stage: FakeStage) -> None:
        self._stage = stage

    def Export(self, path: str) -> bool:  # noqa: N802
        self._stage.root_layer_exports.append(path)
        return True


class FakeLopNode:
    def __init__(self, path: str, stage: FakeStage | None) -> None:
        self._path = path
        self._stage = stage

    def path(self) -> str:
        return self._path

    def stage(self) -> FakeStage | None:
        return self._stage

    def children(self) -> list[Any]:
        return []


class FakeOtherNode:
    def __init__(self, path: str, children: list[Any] | None = None) -> None:
        self._path = path
        self._children = children or []

    def path(self) -> str:
        return self._path

    def children(self) -> list[Any]:
        return self._children


def install_fake_hou(nodes: dict[str, Any]) -> types.ModuleType:
    hou = types.ModuleType("hou")
    hou.LopNode = FakeLopNode  # type: ignore[attr-defined]
    hou.node = lambda path: nodes.get(path)  # type: ignore[attr-defined]
    sys.modules["hou"] = hou
    sys.modules.pop("adapters.houdini_adapter", None)
    return hou


def load_houdini_adapter(nodes: dict[str, Any]) -> types.ModuleType:
    install_fake_hou(nodes)
    return importlib.import_module("adapters.houdini_adapter")


class FakeBlenderObject:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeBlender:
    """bpy の呼び出しを、順番つきで記録する。"""

    def __init__(self, imported: list[str], result: set[str] | None = None) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._imported = imported
        self.result = result if result is not None else {"FINISHED"}
        self.objects = [FakeBlenderObject("Cube"), FakeBlenderObject("Camera")]

    def module(self) -> types.ModuleType:
        bpy = types.ModuleType("bpy")
        outer = self

        class _Objects(list):  # type: ignore[type-arg]
            def remove(self, obj: Any, do_unlink: bool = False) -> None:
                outer.calls.append(("remove", (obj.name, do_unlink)))
                super().remove(obj)

        objects = _Objects(self.objects)
        bpy.data = types.SimpleNamespace(objects=objects)  # type: ignore[attr-defined]

        def usd_import(filepath: str) -> set[str]:
            self.calls.append(("usd_import", filepath))
            if "FINISHED" in self.result:
                objects.extend(FakeBlenderObject(n) for n in self._imported)
            return self.result

        def usd_export(filepath: str) -> set[str]:
            self.calls.append(("usd_export", filepath))
            return self.result

        bpy.ops = types.SimpleNamespace(  # type: ignore[attr-defined]
            wm=types.SimpleNamespace(usd_import=usd_import, usd_export=usd_export)
        )
        return bpy


def load_blender_adapter(fake: FakeBlender) -> types.ModuleType:
    sys.modules["bpy"] = fake.module()
    sys.modules.pop("adapters.blender_adapter", None)
    return importlib.import_module("adapters.blender_adapter")
