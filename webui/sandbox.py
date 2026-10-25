from __future__ import annotations

import multiprocessing
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

from core.stage_loader import ExternalReferenceError, StageOpenError

KILL_GRACE_SECONDS = 5


class ParseTimeoutError(Exception):
    pass


class ParseWorkerError(Exception):
    pass


def _entry(conn: Connection, func: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        conn.send(("ok", func(*args)))
    except ExternalReferenceError as exc:
        conn.send(("external_reference_error", str(exc)))
    except StageOpenError as exc:
        conn.send(("stage_open_error", str(exc)))
    except BaseException as exc:  # noqa: BLE001
        conn.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


def run_in_process(func: Callable[..., Any], args: tuple[Any, ...], timeout: float) -> Any:
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_entry, args=(sender, func, args), daemon=True)
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            raise ParseTimeoutError(f"USD analysis exceeded {timeout} seconds")
        try:
            status, payload = receiver.recv()
        except EOFError as exc:
            raise ParseWorkerError("USD analysis worker exited without a result") from exc
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
        process.join(KILL_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join()

    if status == "ok":
        return payload
    if status == "external_reference_error":
        raise ExternalReferenceError(payload)
    if status == "stage_open_error":
        raise StageOpenError(payload)
    raise ParseWorkerError(payload)
