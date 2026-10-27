"""Blender 実機の検証。`blender --background --python scripts/verify_blender.py` で実行する。

結果は 1 行 1 項目の `CHECK <名前> <PASS|FAIL> <詳細>` で出力する。
docs/verification/ の記録は、この出力から作る。
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.blender_adapter import UsdImportError, import_usd, reexport_usd  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "sample_scenes" / "consistent_scene.usda"


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"CHECK {name} {'PASS' if ok else 'FAIL'} {detail}")


def main() -> None:
    print(f"BLENDER_VERSION {bpy.app.version_string}")
    names = import_usd(str(SAMPLE))
    check("import_creates_objects", len(names) > 0, f"objects={sorted(names)}")
    check("default_scene_is_cleared", "Cube" not in names and "Camera" not in names, "")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sub" / "re.usda"
        written = reexport_usd(str(out))
        check("reexport_writes_file", out.exists() and written == str(out), str(out.name))
        text = out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""
        match = re.search(r'upAxis = "(\w)"', text)
        check(
            "reexport_up_axis_is_z",
            bool(match) and match.group(1) == "Z",
            match.group(0) if match else "none",
        )

    try:
        import_usd(str(SAMPLE.with_name("missing.usda")))
        check("missing_file_is_refused", False, "no error")
    except UsdImportError as exc:
        check("missing_file_is_refused", "does not exist" in str(exc), str(exc)[:60])


main()
