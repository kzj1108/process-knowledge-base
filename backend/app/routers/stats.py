from fastapi import APIRouter

from app.db import get_db
from app.utils import row_to_dict

router = APIRouter(prefix="/api/v1/stats", tags=["统计"])


@router.get("/dashboard")
async def dashboard():
    db = await get_db()
    try:
        async def count(table: str) -> int:
            cur = await db.execute(f"SELECT COUNT(*) AS c FROM {table}")
            return (await cur.fetchone())["c"]

        recent_knowledge = await db.execute(
            """
            SELECT id, category, title, related_part_no, updated_at
            FROM process_knowledge ORDER BY updated_at DESC LIMIT 5
            """
        )
        recent_opt = await db.execute(
            """
            SELECT id, equipment_code, part_no, pred_spindle, pred_depth, pred_feed, adopted, created_at
            FROM optimization_run ORDER BY created_at DESC LIMIT 5
            """
        )
        return {
            "counts": {
                "parts": await count("part_catalog"),
                "equipment": await count("equipment"),
                "processes": await count("part_process"),
                "knowledge": await count("process_knowledge"),
                "realtime_records": await count("machining_realtime"),
                "optimization_runs": await count("optimization_run"),
            },
            "recent_knowledge": [row_to_dict(r) for r in await recent_knowledge.fetchall()],
            "recent_optimization": [row_to_dict(r) for r in await recent_opt.fetchall()],
        }
    finally:
        await db.close()
