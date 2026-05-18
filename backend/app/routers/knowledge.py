from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.models import KnowledgeIn, KnowledgeUpdate
from app.services.audit import write_audit
from app.utils import now_iso, require_api_key, row_to_dict

router = APIRouter(prefix="/api/v1/knowledge", tags=["工艺知识"])


@router.get("")
async def list_knowledge(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = await get_db()
    try:
        clauses = ["1=1"]
        params: List[Any] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if part_no:
            clauses.append("related_part_no = ?")
            params.append(part_no)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if q:
            clauses.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like, like])

        where = " AND ".join(clauses)
        count_cur = await db.execute(
            f"SELECT COUNT(*) AS c FROM process_knowledge WHERE {where}", params
        )
        total = (await count_cur.fetchone())["c"]

        offset = (page - 1) * page_size
        cur = await db.execute(
            f"""
            SELECT * FROM process_knowledge
            WHERE {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        items = [row_to_dict(r) for r in await cur.fetchall()]
        return {"total": total, "page": page, "page_size": page_size, "items": items}
    finally:
        await db.close()


@router.get("/search")
async def search_knowledge_legacy(
    q: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    """兼容旧版 Unity 客户端"""
    result = await list_knowledge(q=q, part_no=part_no, page=1, page_size=limit)
    return result["items"]


@router.get("/{kid}")
async def get_knowledge(kid: int):
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM process_knowledge WHERE id = ?", (kid,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "知识条目不存在")
        return row_to_dict(row)
    finally:
        await db.close()


@router.post("", dependencies=[Depends(require_api_key)])
async def create_knowledge(body: KnowledgeIn):
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            """
            INSERT INTO process_knowledge (
                category, title, content, tags, related_part_no, related_op_no,
                source, author, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.category,
                body.title,
                body.content,
                body.tags,
                body.related_part_no,
                body.related_op_no,
                body.source,
                body.author,
                body.status,
                ts,
                ts,
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid() AS id")
        kid = (await cur.fetchone())["id"]
        await write_audit("CREATE", "knowledge", kid, body.model_dump(), body.author or "admin")
        return {"ok": True, "id": kid}
    finally:
        await db.close()


@router.put("/{kid}", dependencies=[Depends(require_api_key)])
async def update_knowledge(kid: int, body: KnowledgeUpdate):
    db = await get_db()
    try:
        cur = await db.execute("SELECT id FROM process_knowledge WHERE id = ?", (kid,))
        if not await cur.fetchone():
            raise HTTPException(404, "知识条目不存在")

        data = body.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(400, "无更新字段")

        data["updated_at"] = now_iso()
        cols = ", ".join(f"{k} = ?" for k in data)
        await db.execute(
            f"UPDATE process_knowledge SET {cols} WHERE id = ?",
            [*data.values(), kid],
        )
        await db.commit()
        await write_audit("UPDATE", "knowledge", kid, data)
        return {"ok": True, "id": kid}
    finally:
        await db.close()


@router.delete("/{kid}", dependencies=[Depends(require_api_key)])
async def delete_knowledge(kid: int):
    db = await get_db()
    try:
        cur = await db.execute("DELETE FROM process_knowledge WHERE id = ?", (kid,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "知识条目不存在")
        await write_audit("DELETE", "knowledge", kid)
        return {"ok": True}
    finally:
        await db.close()
