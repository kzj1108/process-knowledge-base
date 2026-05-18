from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.models import EquipmentIn, EquipmentUpdate
from app.services.audit import write_audit
from app.utils import now_iso, require_api_key, row_to_dict

router = APIRouter(prefix="/api/v1/equipment", tags=["设备"])


@router.get("")
async def list_equipment():
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM equipment ORDER BY code")
        return [row_to_dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


@router.post("", dependencies=[Depends(require_api_key)])
async def create_equipment(body: EquipmentIn):
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            """
            INSERT INTO equipment (code, name, type, model, workshop, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (body.code, body.name, body.type, body.model, body.workshop, body.status, ts, ts),
        )
        await db.commit()
        await write_audit("CREATE", "equipment", detail=body.model_dump())
        return {"ok": True, "code": body.code}
    except Exception as e:
        if "UNIQUE" in str(e).upper():
            raise HTTPException(409, "设备编码已存在") from e
        raise
    finally:
        await db.close()


@router.put("/{code}", dependencies=[Depends(require_api_key)])
async def update_equipment(code: str, body: EquipmentUpdate):
    db = await get_db()
    try:
        data = body.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(400, "无更新字段")
        data["updated_at"] = now_iso()
        cols = ", ".join(f"{k} = ?" for k in data)
        cur = await db.execute(
            f"UPDATE equipment SET {cols} WHERE code = ?",
            [*data.values(), code],
        )
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "设备不存在")
        return {"ok": True}
    finally:
        await db.close()
