import os

from fastapi import APIRouter, HTTPException

from app.models import LoginIn
from app.utils import API_KEY

router = APIRouter(prefix="/api/v1/auth", tags=["鉴权"])

ADMIN_USER = os.environ.get("PKB_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("PKB_ADMIN_PASS", "admin123")


@router.post("/login")
async def login(body: LoginIn):
    if body.username != ADMIN_USER or body.password != ADMIN_PASS:
        raise HTTPException(401, "用户名或密码错误")
    return {
        "ok": True,
        "api_key": API_KEY,
        "username": body.username,
        "message": "请在管理端请求头携带 X-API-Key",
    }
