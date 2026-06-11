"""Process Knowledge Base API — aligned with 实施方案5."""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.auth import require_api_key
from backend.database import (
    TARGET_TOTAL,
    get_conn,
    get_overview_stats,
    init_db,
    row_to_dict,
    write_audit,
)
from backend.recommendation import confirm_recommendation, get_recommendation, recommend_process

PKB_DB_DRIVER = os.environ.get("PKB_DB_DRIVER", "sqlite")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="工艺知识库 API",
    description="数控滚齿加工单元工艺知识库 — 实施方案5",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


# ---------- Models ----------


class PartIn(BaseModel):
    part_no: str
    part_name: str | None = None
    material: str | None = None
    drawing_no: str | None = None
    module: float | None = Field(None, alias="module_m")
    teeth_count: int | None = Field(None, alias="teeth_z")
    part_type: str | None = None
    heat_treatment: str | None = None
    accuracy_grade: str | None = None
    face_width: float | None = None

    model_config = {"populate_by_name": True}


class RecommendIn(BaseModel):
    part_no: str | None = None
    part_name: str | None = None
    material: str | None = None
    module: float | None = Field(None, alias="module_m")
    teeth_count: int | None = Field(None, alias="teeth_z")
    face_width: float | None = None
    accuracy_grade: str | None = None
    heat_treatment: str | None = None
    part_type: str | None = "齿轮"
    equipment_code: str | None = None
    tool_code: str | None = None

    model_config = {"populate_by_name": True}


class RecommendConfirmIn(BaseModel):
    confirmed: bool = True
    note: str = ""


class OptimizationIn(BaseModel):
    opt_id: str | None = None
    part_no: str
    operation_no: int | None = None
    equipment_code: str | None = None
    baseline_params: str | None = None
    recommended_params: str | None = None
    candidate_set: list[dict] | None = None
    model_version: str | None = "opt-v1.0"
    status: str = "completed"
    adopted: bool = False
    source: str = "digital_twin"


class QualityIn(BaseModel):
    part_no: str
    record_id: str | None = None
    operation_no: int | None = None
    equipment_code: str | None = None
    batch_no: str | None = None
    process_step: str | None = None
    inspection_item: str | None = None
    measured_value: float | None = None
    standard_value: float | None = None
    tolerance: str | None = None
    result: str | None = None
    profile_error: float | None = None
    pitch_error: float | None = None
    helix_error: float | None = None
    burr_status: str | None = None
    surface_wave: str | None = None
    quality_grade: str | None = None
    issue: str | None = None
    action_taken: str | None = None
    recheck_result: str | None = None
    inspector: str | None = None
    trace_source: str | None = "mes"
    status: str | None = "OPEN"


class RealtimeIn(BaseModel):
    equipment_code: str
    part_no: str | None = None
    program_no: str | None = None
    spindle_speed: float | None = None
    feed_rate: float | None = None
    load_percent: float | None = None
    status: str = "RUN"


# ---------- Health & catalog ----------


@app.get("/health")
def health():
    with get_conn() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "db_driver": PKB_DB_DRIVER, "target_total": TARGET_TOTAL}


@app.get("/api/v1/integration/catalog")
def integration_catalog():
    return {
        "platform_name": "数控滚齿加工单元工艺知识库",
        "version": "1.2.0",
        "protocol": "HTTPS + JSON",
        "auth_header": "X-API-Key",
        "openapi_docs": "/docs",
        "mes_integration_note": "数制平台可作为调用方；本系统提供工艺/知识/工况/优化/质量数据服务",
        "endpoints": [
            {"code": "INT-01", "method": "POST", "path": "/api/v1/parts", "desc": "同步零件主数据"},
            {"code": "INT-02", "method": "POST", "path": "/api/v1/process/static", "desc": "新增工序工艺（CSV 批量见 INT-08）"},
            {"code": "INT-03", "method": "GET", "path": "/api/v1/process/static", "desc": "按零件查询工艺"},
            {"code": "INT-04", "method": "GET", "path": "/api/v1/knowledge", "desc": "查询工艺知识"},
            {"code": "INT-05", "method": "POST", "path": "/api/v1/machining/realtime", "desc": "上报设备工况"},
            {"code": "INT-06", "method": "POST", "path": "/api/v1/optimization/suggest-and-save", "desc": "优化结果回写"},
            {"code": "INT-07", "method": "GET", "path": "/api/v1/process/optimized/latest", "desc": "最新优化参数"},
            {"code": "INT-08", "method": "POST", "path": "/api/v1/import/csv/{kind}", "desc": "CSV 批量导入"},
            {"code": "INT-09", "method": "GET", "path": "/api/v1/audit", "desc": "审计日志"},
            {"code": "INT-10", "method": "GET", "path": "/health", "desc": "健康检查"},
            {"code": "INT-11", "method": "POST", "path": "/api/v1/recommendations/process", "desc": "工艺方案推荐"},
            {"code": "INT-12", "method": "POST", "path": "/api/v1/quality-records", "desc": "质量记录同步"},
        ],
    }


@app.get("/api/v1/system/info")
def system_info():
    return {
        "name": "工艺知识库系统",
        "version": "1.2.0",
        "scenario": "变速箱机加车间数控滚齿加工单元",
        "db_driver": PKB_DB_DRIVER,
        "target_data_total": TARGET_TOTAL,
        "modules": [
            "综合看板", "基础数据", "工艺流程", "工艺知识", "方案推荐",
            "设备工况", "质量追溯", "数据导入", "开放API", "安全审计",
        ],
    }


# ---------- 4.1 综合看板 ----------


@app.get("/api/v1/overview")
def overview(_: str = Depends(require_api_key)):
    stats = get_overview_stats()
    with get_conn() as conn:
        recent_knowledge = [
            row_to_dict(r)
            for r in conn.execute(
                "SELECT id, category, title, part_no, created_at FROM knowledge ORDER BY id DESC LIMIT 8"
            ).fetchall()
        ]
        recent_opt = [
            row_to_dict(r)
            for r in conn.execute(
                """
                SELECT id, opt_id, part_no, recommended_params, adopted, status, created_at
                FROM optimization_record ORDER BY id DESC LIMIT 8
                """
            ).fetchall()
        ]
    stats["progress_percent"] = round(min(100, stats["effective_total"] / TARGET_TOTAL * 100), 2)
    stats["recent_knowledge"] = recent_knowledge
    stats["recent_optimization"] = recent_opt
    return stats


# ---------- Parts ----------


@app.get("/api/v1/parts")
def list_parts(limit: int = 50, _: str = Depends(require_api_key)):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM part ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}


@app.post("/api/v1/parts")
def create_part(body: PartIn, _: str = Depends(require_api_key)):
    data = body.model_dump(by_alias=False, exclude_none=True)
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    with get_conn() as conn:
        try:
            conn.execute(f"INSERT INTO part ({cols}) VALUES ({placeholders})", tuple(data.values()))
        except Exception as e:
            raise HTTPException(409, f"part_no conflict or invalid data: {e}") from e
    write_audit("create_part", "part", body.part_no)
    return {"ok": True, "part_no": body.part_no}


@app.get("/api/v1/parts/{part_no}")
def get_part_detail(part_no: str, _: str = Depends(require_api_key)):
    with get_conn() as conn:
        part = conn.execute("SELECT * FROM part WHERE part_no = ?", (part_no,)).fetchone()
        if not part:
            raise HTTPException(404, "part not found")
        processes = conn.execute(
            "SELECT * FROM process WHERE part_no = ? ORDER BY COALESCE(operation_no, step_no)",
            (part_no,),
        ).fetchall()
        knowledge = conn.execute(
            "SELECT * FROM knowledge WHERE part_no = ? ORDER BY id DESC LIMIT 20",
            (part_no,),
        ).fetchall()
        opt = conn.execute(
            """
            SELECT * FROM optimization_record WHERE part_no = ?
            ORDER BY id DESC LIMIT 1
            """,
            (part_no,),
        ).fetchone()
    return {
        **row_to_dict(part),
        "process": [row_to_dict(p) for p in processes],
        "knowledge": [row_to_dict(k) for k in knowledge],
        "latest_optimization": row_to_dict(opt),
    }


# ---------- Process ----------


@app.get("/api/v1/process/static")
def get_process_static(
    part_no: str = Query(...),
    operation_no: int | None = None,
    _: str = Depends(require_api_key),
):
    sql = "SELECT * FROM process WHERE part_no = ? AND (status IS NULL OR status = 'active')"
    params: list[Any] = [part_no]
    if operation_no is not None:
        sql += " AND (operation_no = ? OR step_no = ?)"
        params.extend([operation_no, operation_no])
    sql += " ORDER BY COALESCE(operation_no, step_no)"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}


# ---------- Knowledge ----------


@app.get("/api/v1/knowledge")
def list_knowledge(
    part_no: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
    limit: int = 50,
    _: str = Depends(require_api_key),
):
    sql = "SELECT * FROM knowledge WHERE status = 'published'"
    params: list[Any] = []
    if part_no:
        sql += " AND part_no = ?"
        params.append(part_no)
    if category:
        sql += " AND category = ?"
        params.append(category)
    if keyword:
        sql += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
        params.extend([f"%{keyword}%"] * 3)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}


# ---------- 4.5 工艺方案推荐（实施方案5 §8） ----------


@app.post("/api/v1/recommendations/process")
def api_recommend_process(body: RecommendIn, _: str = Depends(require_api_key)):
    payload = body.model_dump(by_alias=False, exclude_none=True)
    result = recommend_process(payload)
    write_audit("recommend_process", "recommendation_result", str(result.get("id")), json.dumps(payload, ensure_ascii=False))
    return result


@app.get("/api/v1/recommendations/{rec_id}")
def api_get_recommendation(rec_id: int, _: str = Depends(require_api_key)):
    data = get_recommendation(rec_id)
    if not data:
        raise HTTPException(404, "recommendation not found")
    return data


@app.patch("/api/v1/recommendations/{rec_id}/confirm")
def api_confirm_recommendation(rec_id: int, body: RecommendConfirmIn, _: str = Depends(require_api_key)):
    data = confirm_recommendation(rec_id, body.confirmed, body.note)
    if not data:
        raise HTTPException(404, "recommendation not found")
    write_audit("confirm_recommendation", "recommendation_result", str(rec_id), body.note)
    return data


# ---------- Optimization（数字孪生回写） ----------


@app.post("/api/v1/optimization/tasks")
@app.post("/api/v1/optimization/suggest-and-save")
def save_optimization(body: OptimizationIn, _: str = Depends(require_api_key)):
    opt_id = body.opt_id or f"OPT-GC-{uuid.uuid4().hex[:12].upper()}"
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO optimization_record
            (opt_id, part_no, operation_no, equipment_code, baseline_params, recommended_params,
             candidate_set, before_params, after_params, model_version, status, adopted, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(opt_id) DO UPDATE SET
              recommended_params=excluded.recommended_params,
              candidate_set=excluded.candidate_set,
              status=excluded.status,
              adopted=excluded.adopted
            """,
            (
                opt_id,
                body.part_no,
                body.operation_no,
                body.equipment_code,
                body.baseline_params,
                body.recommended_params,
                json.dumps(body.candidate_set or [], ensure_ascii=False),
                body.baseline_params,
                body.recommended_params,
                body.model_version,
                body.status,
                1 if body.adopted else 0,
                body.source,
            ),
        )
    write_audit("optimization_save", "optimization_record", opt_id)
    return {"ok": True, "opt_id": opt_id}


@app.get("/api/v1/process/optimized/latest")
def latest_optimization(
    part_no: str = Query(...),
    operation_no: int | None = None,
    _: str = Depends(require_api_key),
):
    sql = "SELECT * FROM optimization_record WHERE part_no = ?"
    params: list[Any] = [part_no]
    if operation_no is not None:
        sql += " AND operation_no = ?"
        params.append(operation_no)
    sql += " ORDER BY id DESC LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
    if not row:
        return {"part_no": part_no, "message": "no optimization record"}
    return row_to_dict(row)


# ---------- Quality（4.7） ----------


@app.post("/api/v1/quality-records")
def create_quality(body: QualityIn, _: str = Depends(require_api_key)):
    data = body.model_dump(exclude_none=True)
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    with get_conn() as conn:
        cur = conn.execute(f"INSERT INTO quality_record ({cols}) VALUES ({placeholders})", tuple(data.values()))
        rec_id = cur.lastrowid
    write_audit("quality_sync", "quality_record", str(rec_id))
    return {"ok": True, "id": rec_id}


@app.get("/api/v1/quality-records")
def list_quality(part_no: str | None = None, limit: int = 50, _: str = Depends(require_api_key)):
    sql = "SELECT * FROM quality_record"
    params: list[Any] = []
    if part_no:
        sql += " WHERE part_no = ?"
        params.append(part_no)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}


# ---------- Realtime / Equipment ----------


@app.post("/api/v1/machining/realtime")
def post_realtime(body: RealtimeIn, _: str = Depends(require_api_key)):
    with get_conn() as conn:
        for name, val, unit in [
            ("spindle_speed", body.spindle_speed, "rpm"),
            ("feed_rate", body.feed_rate, "mm/r"),
            ("load_percent", body.load_percent, "%"),
        ]:
            if val is not None:
                conn.execute(
                    """
                    INSERT INTO realtime_data (device_code, metric_name, metric_value, unit)
                    VALUES (?, ?, ?, ?)
                    """,
                    (body.equipment_code, name, val, unit),
                )
    return {"ok": True}


@app.get("/api/v1/equipment")
def list_equipment(_: str = Depends(require_api_key)):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM equipment ORDER BY id").fetchall()
    return {"items": [row_to_dict(r) for r in rows]}


@app.get("/api/v1/resources")
def list_resources(
    resource_type: str | None = None,
    _: str = Depends(require_api_key),
):
    sql = "SELECT * FROM resource WHERE status = 'active' OR status IS NULL"
    params: list[Any] = []
    if resource_type:
        sql += " AND resource_type = ?"
        params.append(resource_type)
    sql += " ORDER BY resource_type, code"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}


# ---------- CSV Import（4.8） ----------

CSV_TEMPLATES: dict[str, str] = {
    "parts": "part_no,part_name,material,drawing_no,module_m,teeth_z,part_type,heat_treatment,accuracy_grade,face_width\nGH-NEW-001,新齿轮,20CrMnTi,DW-001,2.5,32,齿轮,渗碳淬火,6级,28\n",
    "process": "part_no,operation_no,operation_name,version,status,equipment_code,spindle_rpm,feed_mm_rev,radial_depth,hob_no,nc_program_no,remark\nGH-NEW-001,50,滚齿,A,active,YK3150E-01,650,0.25,2.8,HOB-M2.5-A,O2001,\n",
    "knowledge": "category,title,content,tags,part_no\nRULE,示例规则,规则正文,毛刺;滚齿,GH-NEW-001\n",
    "equipment": "code,name,model,status\nYK3150E-01,数控滚齿机,YK3150E,RUN\n",
    "quality": "part_no,operation_no,equipment_code,profile_error,pitch_error,burr_status,quality_grade,issue,action_taken,inspector\nGH-NEW-001,50,YK3150E-01,0.01,0.008,无,合格,,,质检员A\n",
}


@app.get("/api/v1/import/template/{kind}")
def download_template(kind: str):
    if kind not in CSV_TEMPLATES:
        raise HTTPException(400, "模板类型: parts, process, knowledge, equipment, quality")
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        CSV_TEMPLATES[kind],
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{kind}_template.csv"'},
    )


@app.post("/api/v1/import/csv/{kind}")
async def import_csv(kind: str, file: UploadFile = File(...), _: str = Depends(require_api_key)):
    if kind not in ("parts", "part", "process", "knowledge", "equipment", "quality"):
        raise HTTPException(400, f"unsupported kind: {kind}")
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    success, fail = 0, 0
    errors: list[str] = []

    table_map = {"parts": "part", "part": "part", "process": "process", "knowledge": "knowledge", "equipment": "equipment"}

    with get_conn() as conn:
        for i, row in enumerate(reader, start=2):
            row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
            if not row:
                continue
            try:
                if kind in ("parts", "part"):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO part (part_no, part_name, material, module, teeth_count, part_type, accuracy_grade)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row.get("part_no"),
                            row.get("part_name"),
                            row.get("material"),
                            row.get("module_m") or row.get("module"),
                            row.get("teeth_z") or row.get("teeth_count"),
                            row.get("part_type"),
                            row.get("accuracy_grade"),
                        ),
                    )
                elif kind == "process":
                    conn.execute(
                        """
                        INSERT INTO process
                        (part_no, step_no, operation_no, operation_name, version, status, equipment_code,
                         machine_type, spindle_speed, feed_rate, depth, tool_code, nc_program_no, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row.get("part_no"),
                            row.get("step_no") or row.get("operation_no"),
                            row.get("operation_no") or row.get("step_no"),
                            row.get("operation_name"),
                            row.get("version") or "A",
                            row.get("status") or "active",
                            row.get("equipment_code"),
                            row.get("machine_type") or row.get("equipment_code"),
                            row.get("spindle_rpm") or row.get("spindle_speed"),
                            row.get("feed_mm_rev") or row.get("feed_rate"),
                            row.get("radial_depth") or row.get("depth"),
                            row.get("hob_no") or row.get("tool_code"),
                            row.get("nc_program_no"),
                            row.get("remark") or row.get("notes"),
                        ),
                    )
                elif kind == "knowledge":
                    conn.execute(
                        """
                        INSERT INTO knowledge (category, title, content, part_no, tags, status)
                        VALUES (?, ?, ?, ?, ?, 'published')
                        """,
                        (
                            row.get("category") or "RULE",
                            row.get("title"),
                            row.get("content"),
                            row.get("part_no"),
                            row.get("tags"),
                        ),
                    )
                elif kind == "equipment":
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO equipment (code, name, model, status)
                        VALUES (?, ?, ?, ?)
                        """,
                        (row.get("code"), row.get("name"), row.get("model"), row.get("status") or "idle"),
                    )
                elif kind == "quality":
                    conn.execute(
                        """
                        INSERT INTO quality_record
                        (part_no, operation_no, equipment_code, profile_error, pitch_error, helix_error,
                         burr_status, surface_wave, quality_grade, issue, action_taken, inspector, trace_source, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row.get("part_no"),
                            row.get("operation_no"),
                            row.get("equipment_code"),
                            row.get("profile_error"),
                            row.get("pitch_error"),
                            row.get("helix_error"),
                            row.get("burr_status"),
                            row.get("surface_wave"),
                            row.get("quality_grade"),
                            row.get("issue"),
                            row.get("action_taken"),
                            row.get("inspector"),
                            row.get("trace_source") or "import",
                            row.get("status") or "OPEN",
                        ),
                    )
                success += 1
            except Exception as e:
                fail += 1
                errors.append(f"line {i}: {e}")

        conn.execute(
            """
            INSERT INTO import_log (file_name, record_type, success_count, fail_count)
            VALUES (?, ?, ?, ?)
            """,
            (file.filename, kind, success, fail),
        )

    write_audit("import_csv", kind, file.filename or "", f"ok={success} fail={fail}")
    return {"imported_count": success, "failed_count": fail, "errors": errors[:20]}


@app.get("/api/v1/audit")
def audit_log(limit: int = 50, _: str = Depends(require_api_key)):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}


# ---------- Static frontend ----------


if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")


@app.get("/")
def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "message": "工艺知识库 API",
        "docs": "/docs",
        "ui": "/ui/" if FRONTEND_DIR.is_dir() else None,
        "health": "/health",
    }
