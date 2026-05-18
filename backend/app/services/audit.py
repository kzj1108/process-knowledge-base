from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.db import get_db


async def write_audit(
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
    operator: str = "system",
) -> None:
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO audit_log (action, entity, entity_id, detail, operator)
            VALUES (?, ?, ?, ?, ?)
            """,
            (action, entity, entity_id, json.dumps(detail, ensure_ascii=False) if detail else None, operator),
        )
        await db.commit()
    finally:
        await db.close()
