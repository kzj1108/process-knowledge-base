from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import TARGET_TOTAL, init_db
from app.routers import (
    audit,
    auth,
    equipment,
    import_data,
    integration,
    knowledge,
    parts,
    process,
    quality,
    realtime,
    recommendations,
    stats,
    stream,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="工艺知识库系统",
    description="数控滚齿加工单元 · 实施方案5 · 静态工艺 + 知识 + 推荐 + 质量追溯",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(parts.router)
app.include_router(equipment.router)
app.include_router(process.router)
app.include_router(knowledge.router)
app.include_router(realtime.router)
app.include_router(stats.router)
app.include_router(import_data.router)
app.include_router(stream.router)
app.include_router(integration.router)
app.include_router(recommendations.router)
app.include_router(quality.router)
app.include_router(audit.router)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "process-knowledge-base",
        "version": "2.1.0",
        "target_total": TARGET_TOTAL,
    }


@app.get("/api/v1/system/info")
async def system_info():
    return {
        "name": "工艺知识库系统",
        "version": "2.1.0",
        "scenario": "变速箱机加车间数控滚齿加工单元",
        "target_data_total": TARGET_TOTAL,
    }


_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}


@app.get("/")
async def admin_home():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, headers=_NO_CACHE)
    return {"message": "工艺知识库 API 运行中", "docs": "/docs"}


@app.get("/admin")
async def admin_redirect():
    return await admin_home()
