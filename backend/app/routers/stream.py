from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.db import get_db
from app.utils import parse_json_field, row_to_dict

router = APIRouter(prefix="/api/v1/stream", tags=["实时推送"])


@router.get("/realtime")
async def stream_realtime(
    equipment_code: str = Query(...),
    interval_ms: int = Query(1000, ge=200, le=5000),
):
    """SSE：订阅设备最新工况（管理端/大屏用）"""

    async def event_generator():
        last_ts = ""
        while True:
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
            finally:
                await db.close()

            if row:
                data = row_to_dict(row)
                data["joint_angles"] = parse_json_field(data.get("joint_angles"))
                ts = str(data.get("ts", ""))
                if ts != last_ts:
                    last_ts = ts
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'equipment_code': equipment_code, 'status': 'NO_DATA'})}\n\n"

            await asyncio.sleep(interval_ms / 1000.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
