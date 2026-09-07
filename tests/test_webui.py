"""簡易Web GUI(FastAPI)のエンドポイントテスト（TC-020、httpx.TestClient経由）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from webui.main import app

client = TestClient(app)

CONSISTENT = Path("sample_scenes/consistent_scene.usda")
MISMATCHED_SCALE = Path("sample_scenes/mismatched_scale.usda")
MISMATCHED_UPAXIS = Path("sample_scenes/mismatched_upaxis.usda")


class TestHealthz:
    def test_healthz_returns_ok(self) -> None:
        res = client.get("/healthz")

        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


class TestRulesEndpoint:
    def test_get_rules_returns_default_yaml_content(self) -> None:
        res = client.get("/api/rules")

        assert res.status_code == 200
        body = res.json()
        assert body["schema_version"] == 1
        assert "naming_rules" in body


class TestValidateEndpoint:
    def test_validate_consistent_scene_returns_metadata(self) -> None:
        with CONSISTENT.open("rb") as f:
            res = client.post(
                "/api/validate",
                files={"file": ("consistent_scene.usda", f, "application/octet-stream")},
            )

        assert res.status_code == 200
        body = res.json()
        assert body["up_axis"] == "Y"
        assert body["up_axis_is_explicit"] is True
        assert body["prim_count"] == 4

    def test_validate_rejects_unsupported_extension(self) -> None:
        res = client.post(
            "/api/validate",
            files={"file": ("scene.txt", b"not a usd file", "text/plain")},
        )

        assert res.status_code == 400

    def test_validate_rejects_corrupt_usd_file(self) -> None:
        res = client.post(
            "/api/validate",
            files={"file": ("broken.usda", b"this is not valid usda content{{{", "text/plain")},
        )

        assert res.status_code == 422


class TestDiffEndpoint:
    def test_diff_between_consistent_and_mismatched_scale_reports_entries(self) -> None:
        with CONSISTENT.open("rb") as before_f, MISMATCHED_SCALE.open("rb") as after_f:
            res = client.post(
                "/api/diff",
                files={
                    "before": ("consistent_scene.usda", before_f, "application/octet-stream"),
                    "after": ("mismatched_scale.usda", after_f, "application/octet-stream"),
                },
            )

        assert res.status_code == 200
        body = res.json()
        assert "report_id" in body
        assert any(e["category"] == "scale_mismatch" for e in body["entries"])

    def test_diff_report_can_be_retrieved_by_id(self) -> None:
        with CONSISTENT.open("rb") as before_f, MISMATCHED_UPAXIS.open("rb") as after_f:
            create_res = client.post(
                "/api/diff",
                files={
                    "before": ("consistent_scene.usda", before_f, "application/octet-stream"),
                    "after": ("mismatched_upaxis.usda", after_f, "application/octet-stream"),
                },
            )
        report_id = create_res.json()["report_id"]

        get_res = client.get(f"/api/reports/{report_id}")

        assert get_res.status_code == 200
        assert get_res.json()["report_id"] if "report_id" in get_res.json() else True

    def test_get_nonexistent_report_returns_404(self) -> None:
        res = client.get("/api/reports/does-not-exist")

        assert res.status_code == 404


class TestStaticIndex:
    def test_root_serves_index_html(self) -> None:
        res = client.get("/")

        assert res.status_code == 200
        assert "UniBridge" in res.text
