from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.db import get_db
from app.models import RealtimeIn
from app.services.audit import write_audit
from app.services.bulk_seed import run_bulk_seed
from app.utils import now_iso, require_api_key

router = APIRouter(prefix="/api/v1/import", tags=["数据导入"])


TEMPLATES: Dict[str, str] = {
    "knowledge": "category,title,content,tags,related_part_no,related_op_no,author,source\nRULE,示例规则,规则正文内容,标签1;标签2,PART-GEAR-001,10,工艺员A,导入\n",
    "process": "part_no,part_name,material,operation_no,operation_name,equipment_code,tool_code,spindle_speed,cutting_depth,feed_rate,speed_min,speed_max,depth_min,depth_max,feed_min,feed_max,approved_by,remark\nPART-NEW-001,新零件,45钢,10,粗铣,CNC-01,T-01,1000,2.0,500,800,1500,1.0,3.0,300,800,工艺员,备注\n",
    "parts": "part_no,part_name,material,drawing_no,category,remark\nPART-NEW-002,新零件名,40Cr,DW-001,齿轮件,\n",
    "realtime": "equipment_code,part_no,spindle_speed,cutting_depth,feed_rate,axis_x,axis_y,axis_z,status,program_no\nCNC-01,PART-GEAR-001,1200,2.0,750,10.5,20.3,5.1,RUN,O1234\n",
}


@router.get("/template/{kind}")
async def download_template(kind: str):
    if kind not in TEMPLATES:
        raise HTTPException(404, "模板类型: knowledge, process, parts, realtime")
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        TEMPLATES[kind],
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{kind}_template.csv"'},
    )


def _decode_upload(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(400, "无法识别文件编码，请使用 UTF-8 或 GBK CSV")


def _normalize_row(row: dict) -> dict[str, str]:
    """去除表头 BOM/空格，统一为字符串"""
    return {str(k).strip().lstrip("\ufeff"): ("" if v is None else str(v).strip()) for k, v in row.items()}


def _to_int(val: Any) -> Optional[int]:
    if val is None or str(val).strip() == "":
        return None
    return int(float(str(val).strip()))


def _to_float(val: Any) -> Optional[float]:
    if val is None or str(val).strip() == "":
        return None
    return float(str(val).strip())


async def _import_knowledge_rows(rows: List[Dict[str, str]]) -> int:
    db = await get_db()
    n = 0
    try:
        ts = now_iso()
        for raw in rows:
            row = _normalize_row(raw)
            title = row.get("title") or ""
            if not title:
                continue
            await db.execute(
                """
                INSERT INTO process_knowledge (
                    category, title, content, tags, related_part_no, related_op_no,
                    source, author, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PUBLISHED', ?, ?)
                """,
                (
                    (row.get("category") or "RULE").strip().upper(),
                    title,
                    (row.get("content") or title).strip(),
                    row.get("tags"),
                    row.get("related_part_no") or None,
                    int(row["related_op_no"]) if row.get("related_op_no") else None,
                    row.get("source") or "CSV导入",
                    row.get("author") or "import",
                    ts,
                    ts,
                ),
            )
            n += 1
        await db.commit()
    finally:
        await db.close()
    return n


async def _import_process_rows(rows: List[Dict[str, str]]) -> int:
    db = await get_db()
    imported = 0
    skipped = 0
    try:
        ts = now_iso()
        for raw in rows:
            row = _normalize_row(raw)
            part_no = row.get("part_no") or ""
            op_no = _to_int(row.get("operation_no"))
            if not part_no or op_no is None:
                skipped += 1
                continue

            cur = await db.execute(
                """
                INSERT OR IGNORE INTO part_process (
                    part_no, part_name, material, operation_no, operation_name,
                    equipment_code, tool_code,
                    spindle_speed, cutting_depth, feed_rate,
                    speed_min, speed_max, depth_min, depth_max, feed_min, feed_max,
                    version, approved_by, remark, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, '1.0', ?, ?, ?, ?)
                """,
                (
                    part_no,
                    row.get("part_name") or None,
                    row.get("material") or None,
                    op_no,
                    (row.get("operation_name") or f"工序{op_no}").strip(),
                    row.get("equipment_code") or None,
                    row.get("tool_code") or None,
                    _to_float(row.get("spindle_speed")),
                    _to_float(row.get("cutting_depth")),
                    _to_float(row.get("feed_rate")),
                    _to_float(row.get("speed_min")),
                    _to_float(row.get("speed_max")),
                    _to_float(row.get("depth_min")),
                    _to_float(row.get("depth_max")),
                    _to_float(row.get("feed_min")),
                    _to_float(row.get("feed_max")),
                    row.get("approved_by") or None,
                    row.get("remark") or None,
                    ts,
                    ts,
                ),
            )
            if cur.rowcount:
                imported += 1
            else:
                skipped += 1
        await db.commit()
    finally:
        await db.close()
    return {"imported": imported, "skipped": skipped, "total_rows": len(rows)}


async def _import_parts_rows(rows: List[Dict[str, str]]) -> int:
    db = await get_db()
    n = 0
    try:
        ts = now_iso()
        for raw in rows:
            row = _normalize_row(raw)
            part_no = row.get("part_no") or ""
            part_name = row.get("part_name") or ""
            if not part_no or not part_name:
                continue
            cur = await db.execute(
                """
                INSERT OR IGNORE INTO part_catalog
                (part_no, part_name, material, drawing_no, category, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    part_no,
                    part_name,
                    row.get("material"),
                    row.get("drawing_no"),
                    row.get("category"),
                    row.get("remark"),
                    ts,
                    ts,
                ),
            )
            n += cur.rowcount
        await db.commit()
    finally:
        await db.close()
    return n


async def _import_realtime_rows(rows: List[Dict[str, str]]) -> int:
    n = 0
    for row in rows:
        eq = (row.get("equipment_code") or "").strip()
        if not eq:
            continue

        def f(key: str) -> Optional[float]:
            v = row.get(key)
            if v is None or str(v).strip() == "":
                return None
            return float(v)

        body = RealtimeIn(
            equipment_code=eq,
            part_no=row.get("part_no"),
            spindle_speed=f("spindle_speed"),
            cutting_depth=f("cutting_depth"),
            feed_rate=f("feed_rate"),
            axis_x=f("axis_x"),
            axis_y=f("axis_y"),
            axis_z=f("axis_z"),
            status=(row.get("status") or "RUN").strip(),
            program_no=row.get("program_no"),
        )
        from app.routers.realtime import post_realtime

        await post_realtime(body)
        n += 1
    return n


IMPORTERS = {
    "knowledge": _import_knowledge_rows,
    "process": _import_process_rows,
    "parts": _import_parts_rows,
    "realtime": _import_realtime_rows,
}


@router.post("/csv/{kind}", dependencies=[Depends(require_api_key)])
async def import_csv(kind: str, file: UploadFile = File(...)):
    if kind not in IMPORTERS:
        raise HTTPException(404, "类型: knowledge, process, parts, realtime")
    raw = await file.read()
    text = _decode_upload(raw)
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(400, "CSV 无数据行")
    result = await IMPORTERS[kind](rows)
    if isinstance(result, dict):
        detail = {"file": file.filename, **result}
        await write_audit("IMPORT", kind, detail=detail)
        payload: Dict[str, Any] = {"ok": True, "kind": kind, **result}
        if result.get("imported", 0) == 0 and result.get("total_rows", 0) > 0:
            sample = _normalize_row(rows[0])
            payload["hint"] = (
                "未新增任何行：可能已全部存在（重复 part_no+工序号+版本），"
                "或缺少 part_no/operation_no 列。请先在「静态工艺」列表确认数量，"
                f"或对照模板表头。当前首行列名: {', '.join(sample.keys())}"
            )
        return payload
    await write_audit("IMPORT", kind, detail={"file": file.filename, "rows": result})
    return {"ok": True, "imported": result, "kind": kind}


@router.post("/json", dependencies=[Depends(require_api_key)])
async def import_json(payload: Dict[str, Any]):
    """批量 JSON: { "knowledge": [...], "process": [...], "parts": [...], "realtime": [...] }"""
    result: Dict[str, int] = {}
    for key, importer in IMPORTERS.items():
        items = payload.get(key)
        if not items:
            continue
        if not isinstance(items, list):
            raise HTTPException(400, f"{key} 必须是数组")
        rows = [_normalize_row(dict(x)) for x in items]
        r = await importer(rows)
        result[key] = r.get("imported", r) if isinstance(r, dict) else r
    await write_audit("IMPORT", "json", detail=result)
    return {"ok": True, "imported": result}


@router.post("/seed-bulk", dependencies=[Depends(require_api_key)])
async def seed_bulk(total: int = 3000):
    """一键生成约 3000 条演示数据（零件/工序/知识/优化）"""
    if total > 10000:
        raise HTTPException(400, "单次最多 10000 条")
    stats = await run_bulk_seed(total)
    await write_audit("SEED_BULK", "database", detail=stats)
    return {"ok": True, "imported": stats}


@router.post("/reseed", dependencies=[Depends(require_api_key)])
async def reseed_database():
    """重新导入演示数据（不删表，INSERT OR IGNORE）"""
    from pathlib import Path

    from app.db import ROOT, get_db

    seed_path = ROOT / "database" / "seed.sql"
    if not seed_path.exists():
        raise HTTPException(404, "seed.sql 不存在")
    db = await get_db()
    try:
        await db.executescript(seed_path.read_text(encoding="utf-8"))
        await db.commit()
    finally:
        await db.close()
    await write_audit("RESEED", "database")
    return {"ok": True, "message": "演示数据已合并导入"}


@router.post("/realtime/ingest", dependencies=[Depends(require_api_key)])
async def ingest_realtime_batch(items: List[RealtimeIn]):
    """实时规则化数据批量写入（机床/产线推送）"""
    from app.routers.realtime import post_realtime

    for item in items:
        await post_realtime(item)
    return {"ok": True, "count": len(items)}
