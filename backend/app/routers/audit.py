from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.utils import require_api_key, row_to_dict

router = APIRouter(prefix="/api/v1/audit", tags=["审计"])


@router.get("", dependencies=[Depends(require_api_key)])
async def list_audit(limit: int = Query(50, le=200)):
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
    finally:
        await db.close()
    return {"items": [row_to_dict(r) for r in rows]}
