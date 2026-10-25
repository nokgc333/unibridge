from __future__ import annotations

import time


def sleep_forever() -> None:
    time.sleep(600)


def add(left: int, right: int) -> int:
    return left + right


def fail() -> None:
    raise ValueError("boom")
