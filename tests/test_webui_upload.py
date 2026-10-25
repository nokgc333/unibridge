from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import cast

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from tests import sandbox_helpers
from webui import limits
from webui.main import app
from webui.routers import validate
from webui.sandbox import ParseTimeoutError, run_in_process

client = TestClient(app)

CONSISTENT = Path("sample_scenes/consistent_scene.usda")


def _save(upload: "_CountingUpload", directory: Path) -> Path:
    return asyncio.run(validate._save_upload_to_tempfile(cast(UploadFile, upload), directory))


class _CountingUpload:
    def __init__(self, total: int, filename: str = "big.usda") -> None:
        self.filename = filename
        self.remaining = total
        self.bytes_read = 0

    async def read(self, size: int = -1) -> bytes:
        take = self.remaining if size < 0 else min(size, self.remaining)
        self.remaining -= take
        self.bytes_read += take
        return b"a" * take


class TestLimits:
    def test_defaults_are_used_when_the_environment_is_empty(self, monkeypatch) -> None:
        for name in (
            "UNIBRIDGE_MAX_UPLOAD_BYTES",
            "UNIBRIDGE_MAX_CONCURRENT_UPLOADS",
            "UNIBRIDGE_PARSE_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(name, raising=False)

        loaded = limits.load_limits()

        assert loaded.max_upload_bytes == 200 * 1024 * 1024
        assert loaded.max_concurrent_uploads == 4
        assert loaded.parse_timeout_seconds == 30

    def test_environment_overrides_the_defaults(self, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", "1024")
        monkeypatch.setenv("UNIBRIDGE_MAX_CONCURRENT_UPLOADS", "2")
        monkeypatch.setenv("UNIBRIDGE_PARSE_TIMEOUT_SECONDS", "1.5")

        loaded = limits.load_limits()

        assert (loaded.max_upload_bytes, loaded.max_concurrent_uploads) == (1024, 2)
        assert loaded.parse_timeout_seconds == 1.5

    @pytest.mark.parametrize("value", ["0", "-5", "abc"])
    def test_invalid_values_are_rejected_with_the_variable_name(
        self, monkeypatch, value: str
    ) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", value)

        with pytest.raises(ValueError, match="UNIBRIDGE_MAX_UPLOAD_BYTES"):
            limits.load_limits()


class TestChunkedSave:
    def test_reading_stops_shortly_after_the_limit_is_exceeded(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", str(limits.CHUNK_SIZE))
        upload = _CountingUpload(total=limits.CHUNK_SIZE * 50)

        with pytest.raises(HTTPException) as exc:
            _save(upload, tmp_path)

        assert exc.value.status_code == 413
        assert upload.bytes_read <= limits.CHUNK_SIZE * 2

    def test_an_oversized_partial_file_is_not_left_behind(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", "1000")
        upload = _CountingUpload(total=5000)

        with pytest.raises(HTTPException):
            _save(upload, tmp_path)

        assert list(tmp_path.iterdir()) == []

    def test_a_file_within_the_limit_is_saved(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", "1000")
        upload = _CountingUpload(total=900, filename="ok.usda")

        saved = _save(upload, tmp_path)

        assert saved.suffix == ".usda"
        assert saved.stat().st_size == 900


class TestRequestSizeLimit:
    def test_declared_content_length_over_the_limit_gets_413(self, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", "1000")
        payload = b"a" * 10_000

        res = client.post(
            "/api/validate", files={"file": ("big.usda", payload, "application/octet-stream")}
        )

        assert res.status_code == 413

    def test_a_chunked_body_over_the_limit_gets_413(self, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", "1000")

        def body():
            for _ in range(200):
                yield b"x" * 1024

        res = client.post(
            "/api/validate",
            content=body(),
            headers={"content-type": "multipart/form-data; boundary=zzz"},
        )

        assert res.status_code == 413

    def test_a_normal_upload_still_succeeds_under_the_limit(self, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
        with CONSISTENT.open("rb") as f:
            res = client.post(
                "/api/validate", files={"file": ("consistent_scene.usda", f, "text/plain")}
            )

        assert res.status_code == 200


class TestTemporaryFileCleanup:
    @pytest.fixture
    def tmp_root(self, tmp_path: Path, monkeypatch) -> Path:
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        return tmp_path

    def test_nothing_is_left_after_a_successful_request(self, tmp_root: Path) -> None:
        with CONSISTENT.open("rb") as f:
            res = client.post("/api/validate", files={"file": ("a.usda", f, "text/plain")})

        assert res.status_code == 200
        assert list(tmp_root.iterdir()) == []

    def test_nothing_is_left_after_a_corrupt_upload(self, tmp_root: Path) -> None:
        res = client.post("/api/validate", files={"file": ("a.usda", b"{{{", "text/plain")})

        assert res.status_code == 422
        assert list(tmp_root.iterdir()) == []

    def test_nothing_is_left_after_an_oversized_upload(self, tmp_root: Path, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_UPLOAD_BYTES", "500")
        res = client.post("/api/validate", files={"file": ("a.usda", b"a" * 5000, "text/plain")})

        assert res.status_code == 413
        assert list(tmp_root.iterdir()) == []


class TestConcurrencyGate:
    def test_requests_over_the_limit_get_503(self, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_CONCURRENT_UPLOADS", "1")
        monkeypatch.setattr(limits.upload_gate, "active", 1)

        with CONSISTENT.open("rb") as f:
            res = client.post("/api/validate", files={"file": ("a.usda", f, "text/plain")})

        assert res.status_code == 503

    def test_the_slot_is_released_after_each_request(self, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_CONCURRENT_UPLOADS", "1")
        before = limits.upload_gate.active

        for _ in range(2):
            with CONSISTENT.open("rb") as f:
                res = client.post("/api/validate", files={"file": ("a.usda", f, "text/plain")})
            assert res.status_code == 200

        assert limits.upload_gate.active == before

    def test_the_slot_is_released_after_a_failed_request(self, monkeypatch) -> None:
        monkeypatch.setenv("UNIBRIDGE_MAX_CONCURRENT_UPLOADS", "1")
        before = limits.upload_gate.active

        client.post("/api/validate", files={"file": ("a.usda", b"{{{", "text/plain")})

        assert limits.upload_gate.active == before


class TestExternalReferences:
    def _upload(self, text: str, name: str = "scene.usda"):
        return client.post(
            "/api/validate", files={"file": (name, text.encode("utf-8"), "text/plain")}
        )

    def test_a_sublayer_with_an_absolute_path_is_rejected(self, tmp_path: Path) -> None:
        secret = tmp_path / "secret.usda"
        secret.write_text('#usda 1.0\ndef Xform "Leak"\n{\n}\n', encoding="utf-8")

        res = self._upload(f"#usda 1.0\n(\n    subLayers = [@{secret.as_posix()}@]\n)\n")

        assert res.status_code == 422
        assert "External reference" in res.json()["detail"]

    def test_a_reference_to_a_parent_directory_is_rejected(self) -> None:
        res = self._upload('#usda 1.0\ndef Xform "A" (\n    references = @../x.usda@\n)\n{\n}\n')

        assert res.status_code == 422

    def test_diff_rejects_external_references_in_either_file(self, tmp_path: Path) -> None:
        bad = b'#usda 1.0\ndef Xform "A" (\n    payload = @/etc/passwd.usda@\n)\n{\n}\n'
        with CONSISTENT.open("rb") as f:
            res = client.post(
                "/api/diff",
                files={
                    "before": ("a.usda", f, "text/plain"),
                    "after": ("b.usda", bad, "text/plain"),
                },
            )

        assert res.status_code == 422


class TestParseTimeout:
    def test_a_slow_worker_is_stopped_at_the_timeout(self) -> None:
        with pytest.raises(ParseTimeoutError):
            run_in_process(sandbox_helpers.sleep_forever, (), timeout=0.5)

    def test_the_result_of_a_fast_worker_is_returned(self) -> None:
        assert run_in_process(sandbox_helpers.add, (2, 3), timeout=20) == 5

    def test_an_error_inside_the_worker_surfaces_as_a_worker_error(self) -> None:
        from webui.sandbox import ParseWorkerError

        with pytest.raises(ParseWorkerError, match="ValueError"):
            run_in_process(sandbox_helpers.fail, (), timeout=20)

    def test_the_endpoint_maps_a_timeout_to_504(self, monkeypatch) -> None:
        def raise_timeout(*_args, **_kwargs):
            raise ParseTimeoutError("too slow")

        monkeypatch.setattr(validate, "run_in_process", raise_timeout)
        with CONSISTENT.open("rb") as f:
            res = client.post("/api/validate", files={"file": ("a.usda", f, "text/plain")})

        assert res.status_code == 504
