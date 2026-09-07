"""NFR-001（Prim数2,000規模で15秒以内）の性能測定（仕様書§6.10, §12.6）。

CI組み込みはしない（手動実行、`python tests/benchmark.py`）。usd-coreのみで完結し、
Houdini/Blender実機は不要。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# `python tests/benchmark.py`のように直接実行された場合でもリポジトリルートを
# sys.pathへ含める（`python -m tests.benchmark`実行時は不要だが、
# 仕様書§1のquick-referenceが直接実行の形式を示しているため両対応する）。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pxr import Usd  # noqa: E402

from core.diff_report import build_diff_report  # noqa: E402
from core.hierarchy_check import check_naming  # noqa: E402
from core.rules import load_naming_rules  # noqa: E402
from core.scale_check import (  # noqa: E402
    check_scale_mismatch,
    check_up_axis_mismatch,
    extract_metadata,
)
from tests.fixtures.large_scene.generate import generate  # noqa: E402

NFR_001_TARGET_SECONDS = 15.0


def run_benchmark() -> None:
    fixture_path = generate()
    stage = Usd.Stage.Open(str(fixture_path))
    assert stage is not None

    rules, exclude_patterns = load_naming_rules(Path("rules/default.yaml"))

    start = time.perf_counter()

    meta = extract_metadata(stage, str(fixture_path))
    check_up_axis_mismatch(meta, meta)
    check_scale_mismatch(meta, meta)
    check_naming(stage, rules, exclude_patterns)
    build_diff_report(stage, stage, str(fixture_path), str(fixture_path))

    elapsed = time.perf_counter() - start

    print(
        f"prim_count={meta.prim_count}, elapsed={elapsed:.3f}s (target: {NFR_001_TARGET_SECONDS}s)"
    )
    if elapsed > NFR_001_TARGET_SECONDS:
        print("WARNING: NFR-001 target exceeded")
    else:
        print("OK: within NFR-001 target")


if __name__ == "__main__":
    run_benchmark()
