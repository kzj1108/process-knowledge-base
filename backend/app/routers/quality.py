from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import QualityRecordIn
from app.services.audit import write_audit
from app.utils import require_api_key, row_to_dict

router = APIRouter(prefix="/api/v1/quality-records", tags=["质量追溯"])


@router.post("", dependencies=[Depends(require_api_key)])
async def create_quality(body: QualityRecordIn):
    data = body.model_dump(exclude_none=True)
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    db = await get_db()
    try:
        cur = await db.execute(
            f"INSERT INTO quality_record ({cols}) VALUES ({placeholders})",
            tuple(data.values()),
        )
        await db.commit()
        rec_id = cur.lastrowid
    finally:
        await db.close()
    await write_audit("CREATE", "quality_record", rec_id, data)
    return {"ok": True, "id": rec_id}


@router.get("")
async def list_quality(
    part_no: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    _: str = Depends(require_api_key),
):
    sql = "SELECT * FROM quality_record"
    params: list = []
    if part_no:
        sql += " WHERE part_no = ?"
        params.append(part_no)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    db = await get_db()
    try:
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
    finally:
        await db.close()
    return {"items": [row_to_dict(r) for r in rows]}


@router.get("/{rec_id}")
async def get_quality(rec_id: int, _: str = Depends(require_api_key)):
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM quality_record WHERE id = ?", (rec_id,))
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row:
        raise HTTPException(404, "quality record not found")
    return row_to_dict(row)
