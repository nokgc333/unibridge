from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath

from pxr import Sdf, Tf, Usd

_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


class StageOpenError(ValueError):
    pass


class ExternalReferenceError(StageOpenError):
    pass


def _is_unsafe_asset_path(asset_path: str) -> bool:
    if not asset_path:
        return False
    if _URI_SCHEME.match(asset_path):
        return True
    if PurePosixPath(asset_path).is_absolute() or PureWindowsPath(asset_path).is_absolute():
        return True
    if asset_path.startswith(("\\", "~")):
        return True
    return ".." in re.split(r"[\\/]", asset_path)


def _reject_unsafe_external_references(path: Path) -> None:
    try:
        layer = Sdf.Layer.FindOrOpen(str(path))
    except Tf.ErrorException as exc:
        raise StageOpenError(f"'{path.name}' could not be opened as a USD layer") from exc
    if layer is None:
        raise StageOpenError(f"'{path.name}' could not be opened as a USD layer")
    for asset_path in sorted(layer.GetCompositionAssetDependencies()):
        if _is_unsafe_asset_path(asset_path):
            raise ExternalReferenceError(
                f"External reference is not allowed in untrusted input: '{asset_path}'"
            )


def open_stage(path: Path, *, allow_external_references: bool = True) -> Usd.Stage:
    if not path.exists():
        raise StageOpenError(f"'{path}' does not exist")
    if not allow_external_references:
        _reject_unsafe_external_references(path)
    try:
        stage = Usd.Stage.Open(str(path))
    except Tf.ErrorException as exc:
        raise StageOpenError(
            f"'{path}' could not be opened as a USD stage (corrupt or unsupported)"
        ) from exc
    if stage is None:
        raise StageOpenError(
            f"'{path}' could not be opened as a USD stage (corrupt or unsupported)"
        )
    return stage
