from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.db import get_db
from app.models import RecommendConfirmIn, RecommendIn
from app.services.audit import write_audit
from app.services.model_parser import merge_features, parse_model_file
from app.services.recommendation import confirm_recommendation, get_recommendation, recommend_process
from app.services.route_recommender import recommend_routes_from_features
from app.utils import require_api_key

router = APIRouter(prefix="/api/v1/recommendations", tags=["工艺方案推荐"])

ALLOWED_MODEL_EXT = {".stl", ".obj"}
MAX_MODEL_BYTES = 20 * 1024 * 1024


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


@router.post("/from-model", dependencies=[Depends(require_api_key)])
async def api_recommend_from_model(
    file: UploadFile = File(..., description="STL 或 OBJ 三维模型"),
    material: Optional[str] = Form(None),
    teeth_z: Optional[int] = Form(None),
    module_m: Optional[float] = Form(None),
    heat_treatment: Optional[str] = Form(None),
    route_count: int = Form(3, ge=1, le=5),
):
    filename = file.filename or "model.stl"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_MODEL_EXT:
        raise HTTPException(400, f"仅支持 {', '.join(sorted(ALLOWED_MODEL_EXT))} 格式")

    content = await file.read()
    if len(content) > MAX_MODEL_BYTES:
        raise HTTPException(400, "模型文件不能超过 20MB")
    if not content:
        raise HTTPException(400, "文件为空")

    try:
        parsed = parse_model_file(content, filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    features = merge_features(
        parsed,
        material=material,
        teeth_z=teeth_z,
        module_m=module_m,
        heat_treatment=heat_treatment,
    )

    db = await get_db()
    try:
        result = await recommend_routes_from_features(db, features, route_count=route_count)
        await db.commit()
    finally:
        await db.close()

    result["upload"] = {"filename": filename, "size_bytes": len(content)}
    await write_audit(
        "RECOMMEND_MODEL",
        "model_route_recommendation",
        result.get("recommendation_id"),
        {"filename": filename, "features": features},
    )
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
