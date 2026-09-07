"""UniBridge 簡易Web GUI FastAPIアプリケーション（仕様書§5.9）。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from webui.routers import report, validate

app = FastAPI(title="UniBridge Web GUI", version="0.1.0")

# ローカル実行前提のため開発時は緩め。外部公開時はallow_originsを限定する（SEC-006関連）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(validate.router, prefix="/api", tags=["validate"])
app.include_router(report.router, prefix="/api", tags=["report"])


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="webui/static", html=True), name="static")
