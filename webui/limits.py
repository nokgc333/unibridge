from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import HTTPException

CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 200 * 1024 * 1024
DEFAULT_MAX_CONCURRENT_UPLOADS = 4
DEFAULT_PARSE_TIMEOUT_SECONDS = 30.0
MULTIPART_OVERHEAD_BYTES = 64 * 1024
MAX_FILES_PER_REQUEST = 2


@dataclass(frozen=True)
class UploadLimits:
    max_upload_bytes: int
    max_concurrent_uploads: int
    parse_timeout_seconds: float

    @property
    def max_request_bytes(self) -> int:
        return self.max_upload_bytes * MAX_FILES_PER_REQUEST + MULTIPART_OVERHEAD_BYTES


def _positive_number(name: str, default: float, kind: type[int] | type[float]) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = kind(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive {kind.__name__}, got '{raw}'") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive {kind.__name__}, got '{raw}'")
    return value


def load_limits() -> UploadLimits:
    return UploadLimits(
        max_upload_bytes=int(
            _positive_number("UNIBRIDGE_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES, int)
        ),
        max_concurrent_uploads=int(
            _positive_number(
                "UNIBRIDGE_MAX_CONCURRENT_UPLOADS", DEFAULT_MAX_CONCURRENT_UPLOADS, int
            )
        ),
        parse_timeout_seconds=float(
            _positive_number(
                "UNIBRIDGE_PARSE_TIMEOUT_SECONDS", DEFAULT_PARSE_TIMEOUT_SECONDS, float
            )
        ),
    )


class UploadGate:
    def __init__(self) -> None:
        self.active = 0

    @contextmanager
    def acquire(self, max_concurrent: int) -> Iterator[None]:
        if self.active >= max_concurrent:
            raise HTTPException(status_code=503, detail="Too many concurrent uploads")
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1


upload_gate = UploadGate()
