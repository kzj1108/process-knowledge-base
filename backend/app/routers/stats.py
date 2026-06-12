from fastapi import APIRouter

from app.db import TARGET_TOTAL, get_db
from app.utils import row_to_dict

router = APIRouter(prefix="/api/v1/stats", tags=["统计"])


@router.get("/dashboard")
async def dashboard():
    db = await get_db()
    try:
        async def count(table: str) -> int:
            cur = await db.execute(f"SELECT COUNT(*) AS c FROM {table}")
            return (await cur.fetchone())["c"]

        async def safe_count(table: str) -> int:
            try:
                return await count(table)
            except Exception:
                return 0

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
        parts_c = await count("part_catalog")
        proc_c = await count("part_process")
        know_c = await count("process_knowledge")
        equip_c = await count("equipment")
        opt_c = await count("optimization_run")
        qual_c = await safe_count("quality_record")
        rec_c = await safe_count("recommendation_result")
        effective = parts_c + proc_c + know_c + equip_c + opt_c + qual_c + rec_c

        return {
            "target_total": TARGET_TOTAL,
            "progress_percent": round(min(100, effective / TARGET_TOTAL * 100), 2),
            "effective_total": effective,
            "counts": {
                "parts": parts_c,
                "equipment": equip_c,
                "processes": proc_c,
                "knowledge": know_c,
                "realtime_records": await count("machining_realtime"),
                "optimization_runs": opt_c,
                "quality_records": qual_c,
                "recommendation_results": rec_c,
            },
            "recent_knowledge": [row_to_dict(r) for r in await recent_knowledge.fetchall()],
            "recent_optimization": [row_to_dict(r) for r in await recent_opt.fetchall()],
        }
    finally:
        await db.close()
