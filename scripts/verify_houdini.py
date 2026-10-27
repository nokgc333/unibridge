"""Houdini 実機の検証。`hython scripts/verify_houdini.py` で実行する。

結果は 1 行 1 項目の `CHECK <名前> <PASS|FAIL> <詳細>` で出力する。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import hou

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.houdini_adapter import (  # noqa: E402
    LopNodeNotFoundError,
    export_stage_from_lop,
    list_lop_children,
)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"CHECK {name} {'PASS' if ok else 'FAIL'} {detail}")


def main() -> None:
    print(f"HOUDINI_VERSION {hou.applicationVersionString()}")
    stage_net = hou.node("/stage")
    sphere = stage_net.createNode("sphere")
    cube = stage_net.createNode("cube")
    merge = stage_net.createNode("merge")
    merge.setInput(0, sphere)
    merge.setInput(1, cube)

    children = list_lop_children("/stage")
    check("list_lop_children", len(children) == 3, f"count={len(children)}")

    with tempfile.TemporaryDirectory() as tmp:
        for ext in ("usda", "usdc"):
            out = Path(tmp) / "nested" / f"out.{ext}"
            export_stage_from_lop(merge.path(), str(out), ext)
            ok = out.exists() and out.stat().st_size > 0
            check(f"export_{ext}", ok, out.name)
        text = (Path(tmp) / "nested" / "out.usda").read_text(encoding="utf-8", errors="replace")
        check("export_has_real_prims", "sphere1" in text and "cube1" in text, "")
        check("export_has_no_anonymous_sublayer", "anon:" not in text, "")

    for label, path in (("missing_node", "/stage/none"), ("not_a_lop_node", "/obj")):
        try:
            export_stage_from_lop(path, "/tmp/never.usda")
            check(label, False, "no error")
        except LopNodeNotFoundError as exc:
            check(label, True, str(exc)[:60])


main()
