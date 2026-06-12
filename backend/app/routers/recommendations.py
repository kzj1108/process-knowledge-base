from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.models import RecommendConfirmIn, RecommendIn
from app.services.audit import write_audit
from app.services.recommendation import confirm_recommendation, get_recommendation, recommend_process
from app.utils import require_api_key

router = APIRouter(prefix="/api/v1/recommendations", tags=["工艺方案推荐"])


@router.post("/process", dependencies=[Depends(require_api_key)])
async def api_recommend_process(body: RecommendIn):
    db = await get_db()
    try:
        payload = body.model_dump(exclude_none=True)
        result = await recommend_process(db, payload)
        await db.commit()
    finally:
        await db.close()
    await write_audit("RECOMMEND", "recommendation_result", result.get("id"), payload)
    return result


@router.get("/{rec_id}", dependencies=[Depends(require_api_key)])
async def api_get_recommendation(rec_id: int):
    db = await get_db()
    try:
        data = await get_recommendation(db, rec_id)
    finally:
        await db.close()
    if not data:
        raise HTTPException(404, "recommendation not found")
    return data


@router.patch("/{rec_id}/confirm", dependencies=[Depends(require_api_key)])
async def api_confirm_recommendation(rec_id: int, body: RecommendConfirmIn):
    db = await get_db()
    try:
        data = await confirm_recommendation(db, rec_id, body.confirmed, body.note)
        await db.commit()
    finally:
        await db.close()
    if not data:
        raise HTTPException(404, "recommendation not found")
    await write_audit("CONFIRM", "recommendation_result", rec_id, {"confirmed": body.confirmed})
    return data
