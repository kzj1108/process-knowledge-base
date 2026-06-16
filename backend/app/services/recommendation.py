"""规则 + 案例工艺方案推荐（实施方案5 §4.5）"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.utils import row_to_dict


def _parse_json(text: str | None) -> Any:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _match_rule(criteria: dict[str, Any], match: dict[str, Any]) -> tuple[bool, float]:
    if not match:
        return False, 0.0
    hits = 0
    total = len([k for k in match if not k.endswith("_min") and not k.endswith("_max")])
    for key, expected in match.items():
        if key.endswith("_min") or key.endswith("_max"):
            continue
        actual = criteria.get(key) or criteria.get("category" if key == "part_type" else key)
        if actual is None:
            continue
        if str(actual).lower() == str(expected).lower():
            hits += 1
    module = criteria.get("module") or criteria.get("module_m")
    if module is not None:
        if "module_max" in match and float(module) <= float(match["module_max"]):
            hits += 1
            total += 1
        if "module_min" in match and float(module) >= float(match["module_min"]):
            hits += 1
            total += 1
    if total == 0:
        return False, 0.0
    return hits / total >= 0.5, hits / total


async def recommend_process(db: aiosqlite.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    criteria = {k: v for k, v in payload.items() if v is not None}
    if criteria.get("part_type") and not criteria.get("category"):
        criteria["category"] = criteria["part_type"]

    cur = await db.execute(
        "SELECT * FROM recommendation_rule WHERE enabled = 1 ORDER BY priority ASC"
    )
    rules = await cur.fetchall()

    matched: list[dict] = []
    best_action: dict | None = None
    best_score = 0.0
    for rule in rules:
        match_spec = _parse_json(rule["match_json"])
        ok, score = _match_rule(criteria, match_spec)
        if ok:
            matched.append(
                {
                    "rule_code": rule["rule_code"],
                    "rule_name": rule["rule_name"],
                    "score": round(score, 3),
                }
            )
            if score > best_score:
                best_score = score
                best_action = _parse_json(rule["action_json"])

    part_no = criteria.get("part_no")
    process_from_case = None
    if part_no:
        cur = await db.execute(
            """
            SELECT * FROM part_process WHERE part_no = ? AND is_active = 1
            ORDER BY operation_no ASC LIMIT 1
            """,
            (part_no,),
        )
        row = await cur.fetchone()
        if row:
            process_from_case = row_to_dict(row)

    similar_cases = await _find_similar_cases(db, criteria)
    cited_knowledge = await _find_cited_knowledge(db, criteria)
    risk_hints = _build_risk_hints(criteria, matched)

    recommended: dict = best_action or {}
    if process_from_case:
        recommended = {
            "equipment_code": process_from_case.get("equipment_code"),
            "spindle_speed": process_from_case.get("spindle_speed"),
            "feed_rate": process_from_case.get("feed_rate"),
            "cutting_depth": process_from_case.get("cutting_depth"),
            "tool_code": process_from_case.get("tool_code"),
            "source": "historical_process",
        }
    elif best_action:
        recommended["source"] = "rule_engine"
    elif similar_cases:
        recommended = {"reference_part_no": similar_cases[0].get("part_no"), "source": "similar_case"}

    confidence = best_score if best_action else (0.75 if process_from_case else 0.55 if similar_cases else 0.35)
    if matched:
        confidence = max(confidence, min(0.95, 0.7 + best_score * 0.25))

    process_route = await _suggest_process_route(db, criteria, recommended)
    summary, detail_rows = _build_presentation(
        criteria, recommended, matched, similar_cases, cited_knowledge, risk_hints, confidence
    )

    result: dict[str, Any] = {
        "criteria": criteria,
        "matched_rules": matched,
        "recommended_process": recommended,
        "process_route": process_route,
        "similar_cases": similar_cases,
        "cited_knowledge": cited_knowledge,
        "risk_hints": risk_hints,
        "confidence": round(confidence, 3),
        "summary": summary,
        "detail_rows": detail_rows,
        "human_confirmed": False,
        "disclaimer": "本结果为工艺建议，需工艺人员审核确认后方可作为正式工艺下发。",
    }

    cur = await db.execute(
        """
        INSERT INTO recommendation_result
        (request_json, matched_rules, recommended_process, similar_cases,
         cited_knowledge, risk_hints, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            json.dumps(criteria, ensure_ascii=False),
            json.dumps(matched, ensure_ascii=False),
            json.dumps(recommended, ensure_ascii=False),
            json.dumps(similar_cases, ensure_ascii=False),
            json.dumps(cited_knowledge, ensure_ascii=False),
            json.dumps(risk_hints, ensure_ascii=False),
            confidence,
        ),
    )
    result["id"] = cur.lastrowid
    return result


async def _find_similar_cases(db: aiosqlite.Connection, criteria: dict[str, Any], limit: int = 3) -> list[dict]:
    cat = criteria.get("category") or criteria.get("part_type")
    material = criteria.get("material")
    cur = await db.execute(
        """
        SELECT part_no, part_name, material, category, module_m, teeth_z
        FROM part_catalog
        WHERE category = ? OR material = ?
        ORDER BY id DESC LIMIT ?
        """,
        (cat, material, limit),
    )
    return [row_to_dict(r) for r in await cur.fetchall()]


async def _find_cited_knowledge(db: aiosqlite.Connection, criteria: dict[str, Any], limit: int = 5) -> list[dict]:
    part_no = criteria.get("part_no")
    material = criteria.get("material")
    if part_no:
        cur = await db.execute(
            """
            SELECT id, category, title, content, related_part_no
            FROM process_knowledge
            WHERE related_part_no = ? AND status = 'PUBLISHED'
            ORDER BY id DESC LIMIT ?
            """,
            (part_no, limit),
        )
    else:
        cur = await db.execute(
            """
            SELECT id, category, title, content, related_part_no
            FROM process_knowledge
            WHERE status = 'PUBLISHED' AND (tags LIKE ? OR content LIKE ?)
            ORDER BY id DESC LIMIT ?
            """,
            (f"%{material or ''}%", f"%{material or ''}%", limit),
        )
    return [row_to_dict(r) for r in await cur.fetchall()]


def _calc_demo_params(criteria: dict[str, Any], recommended: dict) -> dict[str, Any]:
    """规则未给出完整参数时，按模数/材料估算演示用工艺参数。"""
    module = float(criteria.get("module_m") or criteria.get("module") or 3)
    material = str(criteria.get("material") or "")
    grade = criteria.get("accuracy_grade") or criteria.get("precision_grade") or ""

    spindle = recommended.get("spindle_speed")
    if spindle is None:
        spindle = round(680 / max(module, 1.2))
        if "42CrMo" in material:
            spindle = round(spindle * 0.95)
        if str(grade).startswith("6"):
            spindle = round(spindle * 0.9)

    feed = recommended.get("feed_rate")
    if feed is None:
        feed = 0.6 if module >= 4 else 0.45 if module >= 2.5 else 0.35

    equipment = (
        recommended.get("equipment_code")
        or recommended.get("machine_type")
        or "YK3150E"
    )
    if equipment and "YK3150" in str(equipment):
        equipment = "YK3150E"

    return {
        "equipment_code": equipment,
        "spindle_speed": spindle,
        "feed_rate": feed,
        "cutting_depth": recommended.get("cutting_depth") or round(module * 0.65, 2),
    }


def _build_presentation(
    criteria: dict[str, Any],
    recommended: dict,
    matched: list[dict],
    similar_cases: list[dict],
    cited_knowledge: list[dict],
    risk_hints: list[str],
    confidence: float,
) -> tuple[dict, list[dict]]:
    params = _calc_demo_params(criteria, recommended)
    equipment = params["equipment_code"]
    module = criteria.get("module_m") or criteria.get("module") or "-"

    tip = f"模数 M{module}，建议首件试切后微调转速与进给。"
    if matched:
        tip = f"参考规则 {matched[0]['rule_code']}，{tip}"
    elif similar_cases:
        tip = f"参考历史案例 {similar_cases[0].get('part_no', '')}，{tip}"

    summary = {
        "recommended_equipment": equipment,
        "spindle_speed": params["spindle_speed"],
        "feed_rate": params["feed_rate"],
        "tip": tip,
    }
    return summary, []


def _build_risk_hints(criteria: dict[str, Any], matched: list[dict]) -> list[str]:
    hints: list[str] = []
    if not matched:
        hints.append("未匹配到企业规则，建议补充材料、模数、热处理等字段或参考相似案例。")
    module = criteria.get("module") or criteria.get("module_m")
    if module is not None and float(module) >= 6:
        hints.append("大模数零件建议降低进给并关注机床负载与刀具寿命。")
    grade = criteria.get("accuracy_grade") or criteria.get("precision_grade")
    if grade in ("6级", "5级", "4级"):
        hints.append("高精度等级建议精滚阶段降速，并加强齿形检测。")
    return hints


async def _suggest_process_route(db: aiosqlite.Connection, criteria: dict[str, Any], recommended: dict) -> list[dict]:
    part_no = criteria.get("part_no")
    if not part_no:
        return [{"operation_name": "滚齿", **recommended}]
    cur = await db.execute(
        """
        SELECT operation_no, operation_name, equipment_code, tool_code,
               spindle_speed, feed_rate, cutting_depth, version
        FROM part_process WHERE part_no = ? AND is_active = 1
        ORDER BY operation_no ASC
        """,
        (part_no,),
    )
    rows = await cur.fetchall()
    if rows:
        return [row_to_dict(r) for r in rows]
    return [
        {
            "operation_name": "滚齿",
            "equipment_code": recommended.get("equipment_code", "数控滚齿机"),
            "spindle_speed": recommended.get("spindle_speed"),
            "feed_rate": recommended.get("feed_rate"),
            "cutting_depth": recommended.get("cutting_depth"),
            "tool_code": recommended.get("tool_code"),
            "status": "suggested",
        }
    ]


async def get_recommendation(db: aiosqlite.Connection, rec_id: int) -> dict | None:
    cur = await db.execute("SELECT * FROM recommendation_result WHERE id = ?", (rec_id,))
    row = await cur.fetchone()
    if not row:
        return None
    data = row_to_dict(row)
    for field in (
        "request_json",
        "matched_rules",
        "recommended_process",
        "similar_cases",
        "cited_knowledge",
        "risk_hints",
    ):
        if isinstance(data.get(field), str):
            data[field] = _parse_json(data[field])
    return data


async def confirm_recommendation(
    db: aiosqlite.Connection, rec_id: int, confirmed: bool, note: str = ""
) -> dict | None:
    await db.execute(
        """
        UPDATE recommendation_result SET human_confirmed = ?, confirm_note = ? WHERE id = ?
        """,
        (1 if confirmed else 0, note, rec_id),
    )
    return await get_recommendation(db, rec_id)
