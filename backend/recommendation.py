"""Rule + case based process recommendation (实施方案5 §4.2)."""

from __future__ import annotations

import json
from typing import Any

from backend.database import get_conn, row_to_dict


def _parse_json(text: str | None) -> dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _match_rule(criteria: dict[str, Any], match: dict[str, Any]) -> tuple[bool, float]:
    """Simple field matching with partial score."""
    if not match:
        return False, 0.0
    hits = 0
    total = len(match)
    for key, expected in match.items():
        if key.endswith("_min") or key.endswith("_max"):
            continue
        actual = criteria.get(key)
        if actual is None:
            continue
        if str(actual).lower() == str(expected).lower():
            hits += 1
    module = criteria.get("module")
    if module is not None:
        if "module_max" in match and float(module) <= float(match["module_max"]):
            hits += 1
            total += 1
        if "module_min" in match and float(module) >= float(match["module_min"]):
            hits += 1
            total += 1
    if total == 0:
        return False, 0.0
    score = hits / total
    return score >= 0.5, score


def _find_similar_cases(criteria: dict[str, Any], limit: int = 3) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.*, o.after_params
            FROM part p
            LEFT JOIN optimization_record o ON o.part_no = p.part_no
            WHERE p.part_type = ? OR p.material = ?
            ORDER BY p.id DESC
            LIMIT ?
            """,
            (criteria.get("part_type"), criteria.get("material"), limit),
        ).fetchall()
    return [row_to_dict(r) for r in rows if r]


def recommend_process(payload: dict[str, Any]) -> dict[str, Any]:
    criteria = {k: v for k, v in payload.items() if v is not None}
    matched: list[dict] = []

    with get_conn() as conn:
        rules = conn.execute(
            "SELECT * FROM recommendation_rule WHERE enabled = 1 ORDER BY priority ASC"
        ).fetchall()

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

    # Case-based: use latest process for same part_no if exists
    part_no = criteria.get("part_no")
    process_from_case = None
    if part_no:
        with get_conn() as conn:
            proc = conn.execute(
                """
                SELECT * FROM process WHERE part_no = ?
                ORDER BY step_no ASC LIMIT 1
                """,
                (part_no,),
            ).fetchone()
            if proc:
                process_from_case = row_to_dict(proc)

    similar_cases = _find_similar_cases(criteria)
    cited_knowledge = _find_cited_knowledge(criteria)
    risk_hints = _build_risk_hints(criteria, matched)

    recommended = best_action or {}
    if process_from_case:
        recommended = {
            "machine_type": process_from_case.get("machine_type"),
            "spindle_speed": process_from_case.get("spindle_speed"),
            "feed_rate": process_from_case.get("feed_rate"),
            "depth": process_from_case.get("depth"),
            "tool_code": process_from_case.get("tool_code"),
            "source": "historical_process",
        }
    elif best_action:
        recommended["source"] = "rule_engine"
    elif similar_cases:
        recommended = {
            "reference_part_no": similar_cases[0].get("part_no"),
            "source": "similar_case",
        }

    confidence = best_score if best_action else (0.6 if process_from_case else 0.4 if similar_cases else 0.2)

    process_route = _suggest_process_route(criteria, recommended)

    result = {
        "criteria": criteria,
        "matched_rules": matched,
        "recommended_process": recommended,
        "process_route": process_route,
        "similar_cases": similar_cases,
        "cited_knowledge": cited_knowledge,
        "risk_hints": risk_hints,
        "confidence": round(confidence, 3),
        "human_confirmed": False,
        "disclaimer": "本结果为工艺建议，需工艺人员审核确认后方可作为正式工艺下发。",
    }

    with get_conn() as conn:
        cur = conn.execute(
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


def _find_cited_knowledge(criteria: dict[str, Any], limit: int = 5) -> list[dict]:
    part_no = criteria.get("part_no")
    material = criteria.get("material")
    with get_conn() as conn:
        if part_no:
            rows = conn.execute(
                """
                SELECT id, category, title, content, part_no
                FROM knowledge WHERE part_no = ? AND status = 'published'
                ORDER BY id DESC LIMIT ?
                """,
                (part_no, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, category, title, content, part_no
                FROM knowledge
                WHERE status = 'published' AND (tags LIKE ? OR content LIKE ?)
                ORDER BY id DESC LIMIT ?
                """,
                (f"%{material or ''}%", f"%{material or ''}%", limit),
            ).fetchall()
    return [row_to_dict(r) for r in rows if r]


def _build_risk_hints(criteria: dict[str, Any], matched: list[dict]) -> list[str]:
    hints: list[str] = []
    if not matched:
        hints.append("未匹配到企业规则，建议补充材料、模数、热处理等字段或参考相似案例。")
    module = criteria.get("module")
    if module is not None and float(module) >= 6:
        hints.append("大模数零件建议降低进给并关注机床负载与刀具寿命。")
    if criteria.get("accuracy_grade") in ("6级", "5级", "4级"):
        hints.append("高精度等级建议精滚阶段降速，并加强齿形检测。")
    return hints


def _suggest_process_route(criteria: dict[str, Any], recommended: dict) -> list[dict]:
    part_no = criteria.get("part_no")
    if not part_no:
        return [{"operation_name": "滚齿", **recommended}]
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT step_no, operation_no, operation_name, machine_type, equipment_code,
                   spindle_speed, feed_rate, depth, tool_code, status
            FROM process WHERE part_no = ? AND (status IS NULL OR status = 'active')
            ORDER BY COALESCE(operation_no, step_no) ASC
            """,
            (part_no,),
        ).fetchall()
    if rows:
        return [row_to_dict(r) for r in rows]
    return [
        {
            "operation_name": "滚齿",
            "machine_type": recommended.get("machine_type", "数控滚齿机"),
            "spindle_speed": recommended.get("spindle_speed"),
            "feed_rate": recommended.get("feed_rate"),
            "depth": recommended.get("depth"),
            "tool_code": recommended.get("tool_code"),
            "status": "suggested",
        }
    ]


def confirm_recommendation(rec_id: int, confirmed: bool, note: str = "") -> dict | None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE recommendation_result
            SET human_confirmed = ?, confirm_note = ?
            WHERE id = ?
            """,
            (1 if confirmed else 0, note, rec_id),
        )
    return get_recommendation(rec_id)


def get_recommendation(rec_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM recommendation_result WHERE id = ?", (rec_id,)
        ).fetchone()
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
        if field in data:
            data[field] = _parse_json(data.get(field)) if isinstance(data.get(field), str) else data.get(field)
    return data
