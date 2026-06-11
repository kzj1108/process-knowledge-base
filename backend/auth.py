"""API Key and admin auth helpers."""

from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

PKB_API_KEY = os.environ.get("PKB_API_KEY", "dev-api-key-change-me")
PKB_ADMIN_USER = os.environ.get("PKB_ADMIN_USER", "admin")
PKB_ADMIN_PASS = os.environ.get("PKB_ADMIN_PASS", "admin123")


def require_api_key(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> str:
    if not x_api_key or not secrets.compare_digest(x_api_key, PKB_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-API-Key")
    return x_api_key


def optional_api_key(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> str | None:
    if x_api_key and not secrets.compare_digest(x_api_key, PKB_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-API-Key")
    return x_api_key
