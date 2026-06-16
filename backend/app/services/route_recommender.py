"""根据三维模型特征生成多条候选加工工艺路线。"""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.services.process_sheet import attach_process_sheets
from app.services.recommendation import _calc_demo_params, recommend_process
from app.utils import row_to_dict


async def recommend_routes_from_features(
    db: aiosqlite.Connection,
    features: dict[str, Any],
    *,
    route_count: int = 3,
) -> dict[str, Any]:
    criteria = {
        "part_type": features.get("part_type", "齿轮"),
        "material": features.get("material"),
        "module_m": features.get("module_m"),
        "teeth_z": features.get("teeth_z"),
        "face_width": features.get("face_width_mm"),
        "heat_treatment": features.get("heat_treatment"),
    }
    criteria = {k: v for k, v in criteria.items() if v is not None}

    base = await recommend_process(db, criteria)
    params = _calc_demo_params(criteria, base.get("recommended_process") or {})
    module = float(criteria.get("module_m") or 3)
    similar = base.get("similar_cases") or []
    ref_part = similar[0].get("part_no") if similar else None

    hist_route: list[dict] = []
    if ref_part:
        cur = await db.execute(
            """
            SELECT operation_no, operation_name, equipment_code, tool_code,
                   spindle_speed, feed_rate, cutting_depth
            FROM part_process WHERE part_no = ? AND is_active = 1
            ORDER BY operation_no ASC
            """,
            (ref_part,),
        )
        hist_route = [row_to_dict(r) for r in await cur.fetchall()]

    routes = _build_route_candidates(
        params=params,
        module=module,
        criteria=criteria,
        features=features,
        hist_route=hist_route,
        ref_part=ref_part,
        route_count=route_count,
    )

    result = {
        "model_features": features,
        "criteria": criteria,
        "base_recommendation": {
            "confidence": base.get("confidence"),
            "equipment": params["equipment_code"],
            "spindle_speed": params["spindle_speed"],
            "feed_rate": params["feed_rate"],
        },
        "route_count": len(routes),
        "routes": routes,
        "similar_cases": similar,
        "disclaimer": "系统根据模型形状自动匹配工艺类型并生成路线图纸，正式下发前须工艺人员审核确认。",
        "recommendation_id": base.get("id"),
    }
    return attach_process_sheets(result)


def _build_route_candidates(
    *,
    params: dict[str, Any],
    module: float,
    criteria: dict[str, Any],
    features: dict[str, Any],
    hist_route: list[dict],
    ref_part: str | None,
    route_count: int,
) -> list[dict]:
    part_type = features.get("part_type") or criteria.get("part_type") or "齿轮"
    material = criteria.get("material") or "42CrMo"
    heat = features.get("heat_treatment") or criteria.get("heat_treatment")
    rpm = params["spindle_speed"]
    feed = params["feed_rate"]
    depth = params["cutting_depth"]

    cnc = "CNC-01"
    cnc2 = "CNC-02"
    hob_line = "LINE-01"
    robot = "ROBOT-01"

    if part_type == "轴类":
        return _shaft_routes(cnc, cnc2, route_count)[:route_count]

    if part_type == "曲面件":
        return _surface_routes(cnc, route_count)[:route_count]

    if part_type in ("块体件", "块体（带圆柱孔）", "箱体件"):
        hole_d = features.get("hole_diameter_mm")
        return _block_routes(cnc, cnc2, features, hole_d, route_count)[:route_count]

    if part_type != "齿轮":
        return _block_routes(cnc, cnc2, features, None, route_count)[:route_count]

    candidates: list[dict] = []

    # 路线 A：标准机加 — 粗铣 → 精铣 → 粗滚 → 精滚 → 去毛刺
    ops_a = [
        _op(10, "下料与装夹", cnc, None, None, None, "备料"),
        _op(20, "粗铣齿形", cnc, 1200, 800, 2.5, "T-MILL-20"),
        _op(30, "精铣齿形", cnc, 1800, 600, 0.8, "T-MILL-20"),
        _op(40, "粗滚齿", hob_line, round(rpm * 1.1), round(feed * 1.15, 2), depth, "T-HOB-32"),
        _op(50, "精滚齿", hob_line, rpm, feed, round(depth * 0.85, 2), "T-HOB-32"),
        _op(60, "去毛刺", robot, 3000, 200, 0.1, "T-DEBUR"),
    ]
    candidates.append(
        {
            "route_id": "R-A",
            "route_name": "标准加工路线",
            "strategy": "效率优先",
            "confidence": 0.91,
            "description": "粗铣 → 精铣 → 粗滚 → 精滚 → 去毛刺，适用于批量齿轮",
            "flow_summary": _flow(ops_a),
            "reference": ref_part or "PART-GEAR-001 工艺模板",
            "operations": ops_a,
        }
    )

    # 路线 B：含热处理 — 粗铣 → 热处理 → 精铣 → 滚齿 → 检测
    heat_step = heat or ("渗碳淬火" if "20CrMnTi" in material else "调质")
    ops_b = [
        _op(10, "下料与装夹", cnc, None, None, None, None),
        _op(20, "粗铣齿形", cnc, 1100, 750, 2.8, "T-MILL-20"),
        _op(30, heat_step, "热处理炉", None, None, None, None),
        _op(40, "精铣齿形", cnc, 1700, 550, 0.7, "T-MILL-20"),
        _op(50, "半精滚齿", hob_line, rpm, round(feed * 0.85, 2), round(depth * 0.9, 2), "T-HOB-32"),
        _op(60, "精滚齿", hob_line, round(rpm * 0.88), round(feed * 0.7, 2), round(depth * 0.75, 2), "T-HOB-32"),
        _op(70, "齿形检测", "齿轮检测仪", None, None, None, None),
    ]
    candidates.append(
        {
            "route_id": "R-B",
            "route_name": "热处理完整路线",
            "strategy": "质量优先",
            "confidence": 0.87,
            "description": f"粗铣 → {heat_step} → 精铣 → 滚齿 → 检测，适用于 {material} 高精度件",
            "flow_summary": _flow(ops_b),
            "reference": ref_part or "高精度工艺规范",
            "operations": ops_b,
        }
    )

    # 路线 C：历史案例复用 或 快速试制（仅铣+滚）
    if hist_route:
        ops_c = [
            {
                "operation_no": r.get("operation_no"),
                "operation_name": r.get("operation_name"),
                "equipment_code": r.get("equipment_code"),
                "spindle_speed": r.get("spindle_speed"),
                "feed_rate": r.get("feed_rate"),
                "cutting_depth": r.get("cutting_depth"),
                "tool_code": r.get("tool_code"),
            }
            for r in hist_route
        ]
        candidates.append(
            {
                "route_id": "R-C",
                "route_name": "历史案例路线",
                "strategy": "案例复用",
                "confidence": 0.89,
                "description": f"复用相似零件 {ref_part} 的已验证工序链",
                "flow_summary": _flow(ops_c),
                "reference": ref_part,
                "operations": ops_c,
            }
        )
    else:
        ops_c = [
            _op(10, "装夹准备", cnc, None, None, None, None),
            _op(20, "粗铣齿形", cnc, 1300, 850, 3.0, "T-MILL-20"),
            _op(30, "精铣齿形", cnc, 1900, 620, 0.9, "T-MILL-20"),
            _op(40, "滚齿加工", hob_line, rpm, feed, depth, "T-HOB-32"),
        ]
        candidates.append(
            {
                "route_id": "R-C",
                "route_name": "快速试制路线",
                "strategy": "周期优先",
                "confidence": 0.78,
                "description": "粗铣 → 精铣 → 滚齿，适用于试制与小批量",
                "flow_summary": _flow(ops_c),
                "reference": "试制工艺模板",
                "operations": ops_c,
            }
        )

    if module >= 5:
        candidates[0]["description"] += "；大模数件建议降低精滚进给"
        candidates[0]["confidence"] = 0.86

    return candidates[:route_count]


def _surface_routes(cnc: str, route_count: int) -> list[dict]:
    ops = [
        _op(10, "装夹与找正", cnc, None, None, None, None),
        _op(20, "粗加工型面", cnc, 5500, 320, 0.25, "T-BALL-10"),
        _op(30, "半精加工型面", cnc, 6200, 280, 0.15, "T-BALL-6"),
        _op(40, "精加工型面", cnc, 6800, 220, 0.08, "T-BALL-4"),
        _op(50, "三坐标检测", "CMM", None, None, None, None),
    ]
    return [
        {
            "route_id": "R-A",
            "route_name": "五轴曲面加工路线",
            "strategy": "曲面优先",
            "confidence": 0.83,
            "description": "粗铣型面 → 半精 → 精铣 → 检测",
            "flow_summary": _flow(ops),
            "reference": "PART-TURBINE-005",
            "operations": ops,
        }
    ][:route_count]


def _block_routes(
    cnc: str,
    cnc2: str,
    features: dict[str, Any],
    hole_d: float | None,
    route_count: int,
) -> list[dict]:
    """块体 / 带圆柱孔块体的铣削、钻孔工艺路线。"""
    hole_txt = f"Ø{hole_d} mm" if hole_d else "待确认"
    candidates: list[dict] = []

    if hole_d:
        ops_a = [
            _op(10, "装夹与找正", cnc2, None, None, None, None),
            _op(20, "粗铣上下面", cnc2, 800, 600, 2.0, "T-FACE-50"),
            _op(30, "精铣基准面", cnc2, 1200, 400, 0.4, "T-FACE-50"),
            _op(40, "钻中心孔", cnc2, 2500, 120, None, "T-DRILL-CEN"),
            _op(50, "钻孔", cnc2, 1800, 180, None, "T-DRILL-8"),
            _op(60, "扩孔/镗孔", cnc2, 900, 80, 0.3, "T-BORE"),
            _op(70, "去毛刺", "手工", None, None, None, None),
        ]
        candidates.append(
            {
                "route_id": "R-A",
                "route_name": "标准铣钻镗路线",
                "strategy": "效率优先",
                "confidence": 0.88,
                "description": f"粗铣 → 精铣 → 钻孔 → 镗孔（孔径 {hole_txt}）",
                "flow_summary": _flow(ops_a),
                "reference": "PART-HOUSING-003 类模板",
                "operations": ops_a,
            }
        )
        ops_b = [
            _op(10, "装夹与找正", cnc2, None, None, None, None),
            _op(20, "粗铣六面", cnc2, 750, 550, 2.5, "T-FACE-50"),
            _op(30, "精铣各基准面", cnc2, 1100, 380, 0.35, "T-FACE-50"),
            _op(40, "数控镗孔", cnc, 650, 60, 0.2, "T-BORE-NC"),
            _op(50, "三坐标检测", "CMM", None, None, None, None),
        ]
        candidates.append(
            {
                "route_id": "R-B",
                "route_name": "高精度镗孔路线",
                "strategy": "质量优先",
                "confidence": 0.84,
                "description": f"铣削定基准后数控镗孔，适用于孔径 {hole_txt} 精度要求较高",
                "flow_summary": _flow(ops_b),
                "reference": "箱体/夹具块工艺规范",
                "operations": ops_b,
            }
        )
        ops_c = [
            _op(10, "装夹", cnc2, None, None, None, None),
            _op(20, "铣面", cnc2, 900, 650, 1.5, "T-FACE-50"),
            _op(30, "钻孔", cnc2, 1600, 200, None, "T-DRILL-8"),
            _op(40, "铰孔", cnc2, 400, 50, None, "T-REAM"),
        ]
        candidates.append(
            {
                "route_id": "R-C",
                "route_name": "快速试制路线",
                "strategy": "周期优先",
                "confidence": 0.76,
                "description": "铣面 → 钻孔 → 铰孔，试制件适用",
                "flow_summary": _flow(ops_c),
                "reference": "试制工艺模板",
                "operations": ops_c,
            }
        )
    else:
        ops_a = [
            _op(10, "装夹", cnc2, None, None, None, None),
            _op(20, "粗铣平面", cnc2, 800, 600, 3.0, "T-FACE-50"),
            _op(30, "精铣各面", cnc2, 1200, 400, 0.4, "T-FACE-50"),
            _op(40, "去毛刺", "手工", None, None, None, None),
        ]
        candidates.append(
            {
                "route_id": "R-A",
                "route_name": "块体铣削路线",
                "strategy": "效率优先",
                "confidence": 0.86,
                "description": "粗铣 → 精铣 → 去毛刺",
                "flow_summary": _flow(ops_a),
                "reference": "PART-HOUSING-003",
                "operations": ops_a,
            }
        )
        ops_b = [
            _op(10, "装夹", cnc2, None, None, None, None),
            _op(20, "粗铣", cnc2, 850, 620, 2.8, "T-FACE-50"),
            _op(30, "半精铣", cnc2, 1050, 450, 0.8, "T-FACE-50"),
            _op(40, "精铣", cnc2, 1300, 350, 0.25, "T-FACE-50"),
        ]
        candidates.append(
            {
                "route_id": "R-B",
                "route_name": "多序精铣路线",
                "strategy": "质量优先",
                "confidence": 0.82,
                "description": "粗铣 → 半精铣 → 精铣",
                "flow_summary": _flow(ops_b),
                "reference": "平面度要求高时选用",
                "operations": ops_b,
            }
        )
        ops_c = [
            _op(10, "装夹", cnc2, None, None, None, None),
            _op(20, "粗铣", cnc2, 900, 700, 3.0, "T-FACE-50"),
            _op(30, "精铣", cnc2, 1250, 420, 0.5, "T-FACE-50"),
        ]
        candidates.append(
            {
                "route_id": "R-C",
                "route_name": "快速试制路线",
                "strategy": "周期优先",
                "confidence": 0.78,
                "description": "粗铣 → 精铣两序",
                "flow_summary": _flow(ops_c),
                "reference": "试制模板",
                "operations": ops_c,
            }
        )

    hint = features.get("shape_hint")
    if hint:
        for r in candidates:
            r["description"] += f"（{hint}）"

    return candidates[:route_count]


def _shaft_routes(cnc: str, cnc2: str, route_count: int) -> list[dict]:
    ops = [
        _op(10, "下料", cnc, None, None, None, None),
        _op(20, "粗车外圆", cnc, 900, 500, 1.2, "T-TURN-12"),
        _op(30, "精车外圆", cnc, 1200, 380, 0.5, "T-TURN-12"),
        _op(40, "铣键槽", cnc2, 1100, 350, 0.6, "T-END-10"),
    ]
    return [
        {
            "route_id": "R-A",
            "route_name": "轴类标准路线",
            "strategy": "效率优先",
            "confidence": 0.85,
            "description": "粗车 → 精车 → 铣键槽",
            "flow_summary": _flow(ops),
            "reference": "PART-SHAFT-002",
            "operations": ops,
        }
    ][:route_count]


def _housing_routes(cnc: str, route_count: int) -> list[dict]:
    return _block_routes(cnc, cnc, {}, None, route_count)


def _flow(ops: list[dict]) -> str:
    names = [o.get("operation_name", "") for o in ops if o.get("operation_name")]
    return " → ".join(names)


def _op(
    no: int,
    name: str,
    equip: str,
    rpm: float | None,
    feed: float | None,
    depth: float | None,
    tool: str | None = None,
) -> dict[str, Any]:
    return {
        "operation_no": no,
        "operation_name": name,
        "equipment_code": equip,
        "spindle_speed": rpm,
        "feed_rate": feed,
        "cutting_depth": depth,
        "tool_code": tool,
    }
