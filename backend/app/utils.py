from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

API_KEY = os.environ.get("PKB_API_KEY", "pkb-dev-key-change-me")


def row_to_dict(row: Any) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_json_field(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


async def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="无效 API Key")
    return x_api_key
