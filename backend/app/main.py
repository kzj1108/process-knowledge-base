from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from app.db import TARGET_TOTAL, init_db
from app.services.model_parser import supported_formats
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
APP_VERSION = "2.2.0"
SHEET_VERSION = "2.2.0"


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="工艺知识库系统",
    description="数控滚齿加工单元 · 实施方案5 · 静态工艺 + 知识 + 推荐 + 质量追溯",
    version="2.2.0",
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
    app.mount("/assets", NoCacheStaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/health")
async def health():
    fmt = supported_formats()
    return {
        "status": "ok",
        "service": "process-knowledge-base",
        "version": APP_VERSION,
        "target_total": TARGET_TOTAL,
        "cad_available": fmt.get("cad_available"),
    }


@app.get("/api/v1/system/info")
async def system_info():
    return {
        "name": "工艺知识库系统",
        "version": APP_VERSION,
        "sheet_version": SHEET_VERSION,
        "features": ["plan_view", "datum_faces", "surface_roughness"],
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
