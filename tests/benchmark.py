"""NFR-001(Prim数2,000規模で15秒以内)と、より大きな規模の性能測定(仕様書§6.10, §12.6)。

CI組み込みはしない(手動実行、`python tests/benchmark.py`)。usd-coreのみで完結し、
Houdini/Blender実機は不要。結果は `docs/benchmarks.md` に載せる。
"""

from __future__ import annotations

import platform
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pxr import Usd  # noqa: E402

from core.diff_report import build_diff_report  # noqa: E402
from core.hierarchy_check import check_naming  # noqa: E402
from core.integrity_check import run_integrity_checks  # noqa: E402
from core.rules import DEFAULT_RULES_PATH, load_naming_rules  # noqa: E402
from core.scale_check import (  # noqa: E402
    check_scale_mismatch,
    check_up_axis_mismatch,
    extract_metadata,
)
from tests.fixtures.large_scene.generate import generate  # noqa: E402

NFR_001_TARGET_SECONDS = 15.0
PRIM_COUNTS = (2_000, 20_000, 100_000)


def _timed(action: Callable[[], object]) -> float:
    start = time.perf_counter()
    action()
    return time.perf_counter() - start


def measure(prim_count: int, directory: Path) -> dict[str, float | int]:
    path = generate(directory / f"scene_{prim_count}.usda", prim_count)
    rules, exclude_patterns = load_naming_rules(DEFAULT_RULES_PATH)
    results: dict[str, float | int] = {}
    stage: list[Usd.Stage] = []
    results["open"] = _timed(lambda: stage.append(Usd.Stage.Open(str(path))))
    opened = stage[0]
    meta = extract_metadata(opened, str(path))
    results["prims"] = meta.prim_count
    results["metadata"] = _timed(
        lambda: (
            extract_metadata(opened, str(path)),
            check_up_axis_mismatch(meta, meta),
            check_scale_mismatch(meta, meta),
        )
    )
    results["naming"] = _timed(lambda: check_naming(opened, rules, exclude_patterns))
    results["integrity"] = _timed(lambda: run_integrity_checks(opened))
    results["diff"] = _timed(lambda: build_diff_report(opened, opened, str(path), str(path)))
    return results


def to_markdown(rows: list[dict[str, float | int]]) -> str:
    header = (
        "| Prim 数 | open | metadata | naming | integrity | diff |\n"
        "| ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    lines = [
        f"| {int(r['prims']):,} | {r['open']:.3f} s | {r['metadata']:.3f} s | "
        f"{r['naming']:.3f} s | {r['integrity']:.3f} s | {r['diff']:.3f} s |"
        for r in rows
    ]
    return "\n".join([header, *lines])


def run_benchmark() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        rows = [measure(count, Path(tmp)) for count in PRIM_COUNTS]
    print(f"python {platform.python_version()} / {platform.system()} {platform.machine()}")
    print(to_markdown(rows))
    first_total = sum(v for k, v in rows[0].items() if k != "prims")
    print(f"2,000 prims total: {first_total:.3f}s (target: {NFR_001_TARGET_SECONDS}s)")
    print(
        "OK: within NFR-001 target"
        if first_total <= NFR_001_TARGET_SECONDS
        else "WARNING: NFR-001 target exceeded"
    )


if __name__ == "__main__":
    run_benchmark()
