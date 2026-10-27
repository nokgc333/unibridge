from __future__ import annotations

from pathlib import Path

import pytest
from pxr import Usd

from core.stage_loader import ExternalReferenceError, StageOpenError, open_stage

VALID = Path("sample_scenes/consistent_scene.usda")


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestOpenStage:
    def test_opens_a_valid_stage(self) -> None:
        stage = open_stage(VALID)

        assert isinstance(stage, Usd.Stage)

    def test_missing_file_raises_with_the_path_in_the_message(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.usda"

        with pytest.raises(StageOpenError, match="does not exist"):
            open_stage(missing)

    def test_empty_file_raises_stage_open_error(self, tmp_path: Path) -> None:
        empty = _write(tmp_path / "empty.usda", "")

        with pytest.raises(StageOpenError, match="corrupt or unsupported"):
            open_stage(empty)

    def test_garbage_text_with_usd_extension_raises_stage_open_error(self, tmp_path: Path) -> None:
        garbage = _write(tmp_path / "garbage.usda", "this is not valid usda content{{{")

        with pytest.raises(StageOpenError):
            open_stage(garbage)

    def test_extension_only_binary_file_raises_stage_open_error(self, tmp_path: Path) -> None:
        fake = tmp_path / "fake.usdc"
        fake.write_bytes(b"")

        with pytest.raises(StageOpenError):
            open_stage(fake)

    def test_truncated_crate_file_raises_stage_open_error(
        self, tmp_path: Path, stage_y_up_meters: Path
    ) -> None:
        crate = tmp_path / "scene.usdc"
        Usd.Stage.Open(str(stage_y_up_meters)).Export(str(crate))
        truncated = tmp_path / "truncated.usdc"
        truncated.write_bytes(crate.read_bytes()[: crate.stat().st_size // 2])

        with pytest.raises(StageOpenError):
            open_stage(truncated)

    def test_large_garbage_file_raises_stage_open_error(self, tmp_path: Path) -> None:
        big = tmp_path / "big.usdc"
        big.write_bytes(b"\x00" * (8 * 1024 * 1024))

        with pytest.raises(StageOpenError):
            open_stage(big)


EXTERNAL_LAYER = """#usda 1.0
(
    subLayers = [@{path}@]
)
def Xform "Root"
{{
}}
"""


class TestExternalReferencePolicy:
    @pytest.mark.parametrize(
        "asset_path",
        ["/etc/hosts.usda", "../outside.usda", "https://example.com/a.usda", "C:/data/a.usda"],
    )
    def test_unsafe_sublayer_is_rejected_when_externals_are_disallowed(
        self, tmp_path: Path, asset_path: str
    ) -> None:
        layer = _write(tmp_path / "scene.usda", EXTERNAL_LAYER.format(path=asset_path))

        with pytest.raises(ExternalReferenceError, match="External reference"):
            open_stage(layer, allow_external_references=False)

    def test_unsafe_reference_nested_in_a_variant_is_rejected(self, tmp_path: Path) -> None:
        layer = _write(
            tmp_path / "scene.usda",
            """#usda 1.0
def Xform "A" (
    variantSets = ["v"]
    variants = {string v = "a"}
)
{
    variantSet "v" = {
        "a" (
            references = @/abs/y.usda@
        ) {
        }
    }
}
""",
        )

        with pytest.raises(ExternalReferenceError):
            open_stage(layer, allow_external_references=False)

    def test_unsafe_payload_is_rejected(self, tmp_path: Path) -> None:
        layer = _write(
            tmp_path / "scene.usda",
            '#usda 1.0\ndef Xform "A" (\n    payload = @../secret.usda@\n)\n{\n}\n',
        )

        with pytest.raises(ExternalReferenceError):
            open_stage(layer, allow_external_references=False)

    def test_plain_relative_reference_is_allowed(self, tmp_path: Path) -> None:
        layer = _write(
            tmp_path / "scene.usda",
            '#usda 1.0\ndef Xform "A" (\n    references = @./sibling.usda@\n)\n{\n}\n',
        )

        stage = open_stage(layer, allow_external_references=False)

        assert stage.GetPrimAtPath("/A").IsValid()

    def test_content_of_a_rejected_external_file_is_not_loaded(self, tmp_path: Path) -> None:
        secret = _write(tmp_path / "secret.usda", '#usda 1.0\ndef Xform "Leak"\n{\n}\n')
        layer = _write(
            tmp_path / "scene.usda", EXTERNAL_LAYER.format(path=secret.resolve().as_posix())
        )

        with pytest.raises(ExternalReferenceError):
            open_stage(layer, allow_external_references=False)

    def test_externals_are_resolved_by_default(self, tmp_path: Path) -> None:
        secret = _write(tmp_path / "other.usda", '#usda 1.0\ndef Xform "FromOther"\n{\n}\n')
        layer = _write(
            tmp_path / "scene.usda", EXTERNAL_LAYER.format(path=secret.resolve().as_posix())
        )

        stage = open_stage(layer)

        assert stage.GetPrimAtPath("/FromOther").IsValid()


class TestUnsafeAssetPaths:
    @pytest.mark.parametrize(
        "asset_path",
        [
            "https://example.com/a.usd",
            "file:///etc/passwd",
            "/etc/passwd",
            "C:\\Windows\\a.usd",
            "\\\\server\\share\\a.usd",
            "~/a.usd",
            "../a.usd",
            "a/../../b.usd",
            "a\\..\\b.usd",
        ],
    )
    def test_is_unsafe(self, asset_path: str) -> None:
        from core.stage_loader import _is_unsafe_asset_path

        assert _is_unsafe_asset_path(asset_path) is True

    @pytest.mark.parametrize("asset_path", ["", "a.usd", "sub/dir/a.usd", "./a.usd", "a..b.usd"])
    def test_is_safe(self, asset_path: str) -> None:
        from core.stage_loader import _is_unsafe_asset_path

        assert _is_unsafe_asset_path(asset_path) is False


class TestUntrustedInputBranches:
    def test_a_layer_that_cannot_be_found_is_reported_as_unopenable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pxr import Sdf

        monkeypatch.setattr(Sdf.Layer, "FindOrOpen", staticmethod(lambda _path: None))
        path = _write(tmp_path / "a.usda", "#usda 1.0\n")

        with pytest.raises(StageOpenError, match="could not be opened as a USD layer"):
            open_stage(path, allow_external_references=False)

    def test_a_layer_that_raises_while_opening_is_reported_as_unopenable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pxr import Sdf, Tf

        def boom(_path: str) -> None:
            raise Tf.ErrorException("boom")

        monkeypatch.setattr(Sdf.Layer, "FindOrOpen", staticmethod(boom))
        path = _write(tmp_path / "a.usda", "#usda 1.0\n")

        with pytest.raises(StageOpenError, match="could not be opened as a USD layer"):
            open_stage(path, allow_external_references=False)

    def test_a_stage_that_comes_back_empty_is_reported_as_corrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Usd.Stage, "Open", staticmethod(lambda _path: None))
        path = _write(tmp_path / "a.usda", "#usda 1.0\n")

        with pytest.raises(StageOpenError, match="corrupt or unsupported"):
            open_stage(path)
