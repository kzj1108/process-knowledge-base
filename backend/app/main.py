from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import (
    auth,
    equipment,
    import_data,
    knowledge,
    parts,
    process,
    realtime,
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
    description="静态结构化工艺 + 动态优化数据 + 工艺知识条目管理",
    version="2.0.0",
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

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "process-knowledge-base", "version": "2.0.0"}


@app.get("/")
async def admin_home():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "工艺知识库 API 运行中", "docs": "/docs"}


@app.get("/admin")
async def admin_redirect():
    return await admin_home()
