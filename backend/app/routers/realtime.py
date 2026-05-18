import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db import get_db
from app.models import OptimizationIn, RealtimeIn
from app.utils import parse_json_field, row_to_dict

router = APIRouter(prefix="/api/v1", tags=["动态数据"])


@router.post("/machining/realtime")
async def post_realtime(body: RealtimeIn):
    ts = body.ts or datetime.now(timezone.utc)
    joint_json = json.dumps(body.joint_angles) if body.joint_angles else None
    raw_json = json.dumps(body.raw_payload) if body.raw_payload else None

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO machining_realtime (
                equipment_code, part_no, ts,
                spindle_speed, cutting_depth, feed_rate,
                axis_x, axis_y, axis_z, joint_angles,
                program_no, status, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.equipment_code,
                body.part_no,
                ts.isoformat(),
                body.spindle_speed,
                body.cutting_depth,
                body.feed_rate,
                body.axis_x,
                body.axis_y,
                body.axis_z,
                joint_json,
                body.program_no,
                body.status,
                raw_json,
            ),
        )
        await db.commit()
        return {"ok": True, "ts": ts.isoformat()}
    finally:
        await db.close()


@router.get("/machining/realtime/latest")
async def get_realtime_latest(equipment_code: str):
    db = await get_db()
    try:
        cur = await db.execute(
            """
            SELECT * FROM machining_realtime
            WHERE equipment_code = ?
            ORDER BY ts DESC LIMIT 1
            """,
            (equipment_code,),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "无实时数据")
        data = row_to_dict(row)
        data["joint_angles"] = parse_json_field(data.get("joint_angles"))
        return data
    finally:
        await db.close()


@router.get("/machining/realtime/history")
async def get_realtime_history(
    equipment_code: str,
    limit: int = Query(100, le=500),
):
    db = await get_db()
    try:
        cur = await db.execute(
            """
            SELECT id, equipment_code, part_no, ts, spindle_speed, cutting_depth, feed_rate, status
            FROM machining_realtime
            WHERE equipment_code = ?
            ORDER BY ts DESC LIMIT ?
            """,
            (equipment_code, limit),
        )
        return [row_to_dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


@router.post("/optimization/run")
async def post_optimization(body: OptimizationIn):
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO optimization_run (
                equipment_code, part_no, operation_no, input_snapshot,
                pred_spindle, pred_depth, pred_feed,
                model_version, score, adopted, remark
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.equipment_code,
                body.part_no,
                body.operation_no,
                json.dumps(body.input_snapshot) if body.input_snapshot else None,
                body.pred_spindle,
                body.pred_depth,
                body.pred_feed,
                body.model_version,
                body.score,
                1 if body.adopted else 0,
                body.remark,
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid() AS id")
        return {"ok": True, "id": (await cur.fetchone())["id"]}
    finally:
        await db.close()


@router.get("/process/optimized/latest")
async def get_latest_optimized(
    equipment_code: str,
    part_no: Optional[str] = None,
):
    db = await get_db()
    try:
        if part_no:
            cur = await db.execute(
                """
                SELECT * FROM optimization_run
                WHERE equipment_code = ? AND part_no = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (equipment_code, part_no),
            )
        else:
            cur = await db.execute(
                """
                SELECT * FROM optimization_run
                WHERE equipment_code = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (equipment_code,),
            )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "暂无优化记录")
        data = row_to_dict(row)
        data["input_snapshot"] = parse_json_field(data.get("input_snapshot"))
        return data
    finally:
        await db.close()


@router.get("/optimization/history")
async def optimization_history(
    equipment_code: Optional[str] = None,
    part_no: Optional[str] = None,
    limit: int = Query(50, le=200),
):
    db = await get_db()
    try:
        clauses = ["1=1"]
        params = []
        if equipment_code:
            clauses.append("equipment_code = ?")
            params.append(equipment_code)
        if part_no:
            clauses.append("part_no = ?")
            params.append(part_no)
        params.append(limit)
        cur = await db.execute(
            f"""
            SELECT * FROM optimization_run
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC LIMIT ?
            """,
            params,
        )
        rows = []
        for r in await cur.fetchall():
            d = row_to_dict(r)
            d["input_snapshot"] = parse_json_field(d.get("input_snapshot"))
            rows.append(d)
        return rows
    finally:
        await db.close()
