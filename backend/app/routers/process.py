from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import PartProcessIn, PartProcessUpdate, ProcessQuery
from app.services.audit import write_audit
from app.utils import now_iso, require_api_key, row_to_dict

router = APIRouter(prefix="/api/v1/process", tags=["静态工艺"])


@router.get("/static")
async def get_static_process(
    part_no: str = Query(...),
    operation_no: Optional[int] = Query(None),
    version: Optional[str] = Query(None),
):
    db = await get_db()
    try:
        if operation_no is not None:
            sql = """
                SELECT * FROM part_process
                WHERE part_no = ? AND operation_no = ? AND is_active = 1
            """
            params: List[Any] = [part_no, operation_no]
            if version:
                sql += " AND version = ?"
                params.append(version)
            else:
                sql += " ORDER BY version DESC LIMIT 1"
            cur = await db.execute(sql, params)
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "未找到工艺")
            return row_to_dict(row)

        cur = await db.execute(
            """
            SELECT * FROM part_process
            WHERE part_no = ? AND is_active = 1
            ORDER BY operation_no
            """,
            (part_no,),
        )
        rows = await cur.fetchall()
        if not rows:
            raise HTTPException(404, "未找到工艺")
        return [row_to_dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/list")
async def list_processes(
    part_no: Optional[str] = Query(None),
    equipment_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    db = await get_db()
    try:
        clauses = ["is_active = 1"]
        params: List[Any] = []
        if part_no:
            clauses.append("part_no = ?")
            params.append(part_no)
        if equipment_code:
            clauses.append("equipment_code = ?")
            params.append(equipment_code)
        where = " AND ".join(clauses)

        count_cur = await db.execute(
            f"SELECT COUNT(*) AS c FROM part_process WHERE {where}", params
        )
        total = (await count_cur.fetchone())["c"]
        offset = (page - 1) * page_size
        cur = await db.execute(
            f"""
            SELECT * FROM part_process WHERE {where}
            ORDER BY part_no, operation_no
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [row_to_dict(r) for r in await cur.fetchall()],
        }
    finally:
        await db.close()


@router.get("/{pid}")
async def get_process(pid: int):
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM part_process WHERE id = ?", (pid,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "工艺不存在")
        return row_to_dict(row)
    finally:
        await db.close()


@router.post("/static", dependencies=[Depends(require_api_key)])
async def create_process(body: PartProcessIn):
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            """
            INSERT INTO part_process (
                part_no, part_name, material, operation_no, operation_name,
                equipment_code, tool_code,
                spindle_speed, cutting_depth, feed_rate,
                speed_min, speed_max, depth_min, depth_max, feed_min, feed_max,
                version, approved_by, remark, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                body.part_no,
                body.part_name,
                body.material,
                body.operation_no,
                body.operation_name,
                body.equipment_code,
                body.tool_code,
                body.spindle_speed,
                body.cutting_depth,
                body.feed_rate,
                body.speed_min,
                body.speed_max,
                body.depth_min,
                body.depth_max,
                body.feed_min,
                body.feed_max,
                body.version,
                body.approved_by,
                body.remark,
                ts,
                ts,
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid() AS id")
        pid = (await cur.fetchone())["id"]
        await write_audit("CREATE", "process", pid, body.model_dump(), body.approved_by or "admin")
        return {"ok": True, "id": pid}
    finally:
        await db.close()


@router.put("/{pid}", dependencies=[Depends(require_api_key)])
async def update_process(pid: int, body: PartProcessUpdate):
    db = await get_db()
    try:
        cur = await db.execute("SELECT id FROM part_process WHERE id = ?", (pid,))
        if not await cur.fetchone():
            raise HTTPException(404, "工艺不存在")

        data = body.model_dump(exclude_unset=True)
        if "is_active" in data:
            data["is_active"] = 1 if data["is_active"] else 0
        if not data:
            raise HTTPException(400, "无更新字段")
        data["updated_at"] = now_iso()
        cols = ", ".join(f"{k} = ?" for k in data)
        await db.execute(
            f"UPDATE part_process SET {cols} WHERE id = ?",
            [*data.values(), pid],
        )
        await db.commit()
        await write_audit("UPDATE", "process", pid, data)
        return {"ok": True, "id": pid}
    finally:
        await db.close()


@router.delete("/{pid}", dependencies=[Depends(require_api_key)])
async def delete_process(pid: int, soft: bool = Query(True)):
    db = await get_db()
    try:
        if soft:
            await db.execute(
                "UPDATE part_process SET is_active = 0, updated_at = ? WHERE id = ?",
                (now_iso(), pid),
            )
        else:
            await db.execute("DELETE FROM part_process WHERE id = ?", (pid,))
        await db.commit()
        await write_audit("DELETE", "process", pid, {"soft": soft})
        return {"ok": True}
    finally:
        await db.close()


@router.post("/query")
async def process_query(body: ProcessQuery):
    return await get_static_process(part_no=body.part_no, operation_no=body.operation_no)
