from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import PartCatalogIn, PartCatalogUpdate
from app.services.audit import write_audit
from app.utils import now_iso, require_api_key, row_to_dict

router = APIRouter(prefix="/api/v1/parts", tags=["零件主数据"])


@router.get("")
async def list_parts(q: Optional[str] = Query(None)):
    db = await get_db()
    try:
        if q:
            like = f"%{q}%"
            cur = await db.execute(
                """
                SELECT * FROM part_catalog
                WHERE part_no LIKE ? OR part_name LIKE ? OR material LIKE ?
                ORDER BY part_no
                """,
                (like, like, like),
            )
        else:
            cur = await db.execute("SELECT * FROM part_catalog ORDER BY part_no")
        return [row_to_dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


@router.get("/{part_no}")
async def get_part(part_no: str):
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM part_catalog WHERE part_no = ?", (part_no,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "零件不存在")
        data = row_to_dict(row)
        proc = await db.execute(
            "SELECT * FROM part_process WHERE part_no = ? AND is_active = 1 ORDER BY operation_no",
            (part_no,),
        )
        know = await db.execute(
            "SELECT id, category, title, tags, status FROM process_knowledge WHERE related_part_no = ?",
            (part_no,),
        )
        data["processes"] = [row_to_dict(r) for r in await proc.fetchall()]
        data["knowledge"] = [row_to_dict(r) for r in await know.fetchall()]
        return data
    finally:
        await db.close()


@router.post("", dependencies=[Depends(require_api_key)])
async def create_part(body: PartCatalogIn):
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            """
            INSERT INTO part_catalog (part_no, part_name, material, drawing_no, category, remark, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.part_no,
                body.part_name,
                body.material,
                body.drawing_no,
                body.category,
                body.remark,
                ts,
                ts,
            ),
        )
        await db.commit()
        await write_audit("CREATE", "part", detail=body.model_dump())
        return {"ok": True, "part_no": body.part_no}
    except Exception as e:
        if "UNIQUE" in str(e).upper():
            raise HTTPException(409, "零件号已存在") from e
        raise
    finally:
        await db.close()


@router.put("/{part_no}", dependencies=[Depends(require_api_key)])
async def update_part(part_no: str, body: PartCatalogUpdate):
    db = await get_db()
    try:
        data = body.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(400, "无更新字段")
        data["updated_at"] = now_iso()
        cols = ", ".join(f"{k} = ?" for k in data)
        cur = await db.execute(
            f"UPDATE part_catalog SET {cols} WHERE part_no = ?",
            [*data.values(), part_no],
        )
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "零件不存在")
        return {"ok": True}
    finally:
        await db.close()


@router.delete("/{part_no}", dependencies=[Depends(require_api_key)])
async def delete_part(part_no: str):
    db = await get_db()
    try:
        cur = await db.execute("DELETE FROM part_catalog WHERE part_no = ?", (part_no,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "零件不存在")
        await write_audit("DELETE", "part", detail={"part_no": part_no})
        return {"ok": True}
    finally:
        await db.close()
