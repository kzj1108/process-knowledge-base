from __future__ import annotations

import random
from typing import Any, Dict, List

from app.db import get_db
from app.utils import now_iso

MATERIALS = ["40Cr", "45钢", "20CrMnTi", "HT250", "Q235", "42CrMo", "38CrMoAl", "GH4169", "铝合金7075", "不锈钢304"]
CATEGORIES = ["齿轮件", "轴类件", "箱体件", "结构件", "航空件", "法兰件", "盘类件"]
EQUIPMENT = ["CNC-01", "CNC-02", "ROBOT-01", "ROBOT-02", "LINE-01"]
OPS = ["粗铣", "精铣", "车外圆", "钻孔", "攻丝", "滚齿", "插齿", "磨削", "去毛刺", "五轴型面铣"]
KNOW_CATS = ["RULE", "FAQ", "CASE", "STANDARD"]
KNOW_TITLES = {
    "RULE": ["切深控制建议", "转速选择规则", "进给修正规则", "冷却液使用规则", "刀具寿命规则"],
    "FAQ": ["表面粗糙度问题", "振动排查", "刀具选型", "参数如何换算", "首件检验要点"],
    "CASE": ["振动优化案例", "效率提升案例", "刀具磨损案例", "尺寸超差案例", "节拍缩短案例"],
    "STANDARD": ["安全转速上限", "工艺审批制度", "参数下发规范", "设备点检标准", "质量检验标准"],
}


def _build_parts(count: int) -> List[Dict[str, Any]]:
    rows = []
    for i in range(1, count + 1):
        pno = f"PART-BULK-{i:05d}"
        mat = MATERIALS[i % len(MATERIALS)]
        rows.append(
            {
                "part_no": pno,
                "part_name": f"批量零件-{i}",
                "material": mat,
                "drawing_no": f"DW-B-{i:05d}",
                "category": CATEGORIES[i % len(CATEGORIES)],
                "remark": "批量导入",
            }
        )
    return rows


def _build_processes(part_rows: List[Dict[str, Any]], per_part: int) -> List[Dict[str, Any]]:
    rows = []
    ts = now_iso()
    for p in part_rows:
        for op in range(1, per_part + 1):
            speed = 600 + (hash(p["part_no"]) % 4000) + op * 17
            depth = round(0.2 + (op % 5) * 0.35, 2)
            feed = 200 + (op % 8) * 80
            rows.append(
                {
                    "part_no": p["part_no"],
                    "part_name": p["part_name"],
                    "material": p["material"],
                    "operation_no": op * 10,
                    "operation_name": OPS[op % len(OPS)],
                    "equipment_code": EQUIPMENT[op % len(EQUIPMENT)],
                    "tool_code": f"T-{op % 20:02d}",
                    "spindle_speed": float(speed),
                    "cutting_depth": depth,
                    "feed_rate": float(feed),
                    "speed_min": float(speed * 0.7),
                    "speed_max": float(speed * 1.3),
                    "depth_min": round(depth * 0.5, 2),
                    "depth_max": round(depth * 2, 2),
                    "feed_min": float(feed * 0.6),
                    "feed_max": float(feed * 1.4),
                    "version": "1.0",
                    "approved_by": "批量导入",
                    "remark": None,
                    "created_at": ts,
                    "updated_at": ts,
                }
            )
    return rows


def _build_knowledge(part_rows: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    rows = []
    ts = now_iso()
    for i in range(count):
        cat = KNOW_CATS[i % len(KNOW_CATS)]
        title_tpl = KNOW_TITLES[cat][i % len(KNOW_TITLES[cat])]
        part = part_rows[i % len(part_rows)]
        op_no = (i % 15 + 1) * 10
        rows.append(
            {
                "category": cat,
                "title": f"{part['part_name']}-{title_tpl}-{i + 1}",
                "content": f"针对材料 {part['material']}、工序 {op_no}：建议转速区间参考工艺卡片，"
                f"切深不超过 {1 + (i % 4) * 0.5:.1f} mm，进给按机床负载微调 5–15%。",
                "tags": f"{part['material']},{cat},批量",
                "related_part_no": part["part_no"],
                "related_op_no": op_no,
                "source": "批量生成",
                "author": f"工艺员{(i % 9) + 1}",
                "status": "PUBLISHED",
                "created_at": ts,
                "updated_at": ts,
            }
        )
    return rows


def _build_optimization(part_rows: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    rows = []
    ts = now_iso()
    for i in range(count):
        part = part_rows[i % len(part_rows)]
        rows.append(
            {
                "equipment_code": EQUIPMENT[i % len(EQUIPMENT)],
                "part_no": part["part_no"],
                "operation_no": (i % 12 + 1) * 10,
                "pred_spindle": float(800 + (i * 37) % 3000),
                "pred_depth": round(0.3 + (i % 10) * 0.15, 2),
                "pred_feed": float(250 + (i % 20) * 25),
                "model_version": f"opt-v{(i % 5) + 1}.0",
                "score": round(0.75 + random.random() * 0.24, 3),
                "adopted": 1 if i % 3 == 0 else 0,
                "remark": "批量生成",
                "created_at": ts,
            }
        )
    return rows


async def run_bulk_seed(total: int = 3000) -> Dict[str, int]:
    """
    默认 3000 条：200 零件 + 2000 工序 + 700 知识 + 100 优化
    """
    if total < 100:
        total = 100
    part_count = max(30, min(250, total // 15))
    opt_count = max(20, min(150, total // 30))
    know_count = max(50, (total * 7) // 30)
    proc_total = max(part_count, total - part_count - know_count - opt_count)
    per_part = max(1, proc_total // part_count)

    part_rows = _build_parts(part_count)
    proc_rows = _build_processes(part_rows, per_part)
    know_rows = _build_knowledge(part_rows, know_count)
    opt_rows = _build_optimization(part_rows, opt_count)

    db = await get_db()
    try:
        ts = now_iso()
        for p in part_rows:
            await db.execute(
                """
                INSERT OR IGNORE INTO part_catalog
                (part_no, part_name, material, drawing_no, category, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (p["part_no"], p["part_name"], p["material"], p["drawing_no"], p["category"], p["remark"], ts, ts),
            )

        await db.executemany(
            """
            INSERT INTO part_process (
                part_no, part_name, material, operation_no, operation_name,
                equipment_code, tool_code,
                spindle_speed, cutting_depth, feed_rate,
                speed_min, speed_max, depth_min, depth_max, feed_min, feed_max,
                version, approved_by, remark, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    r["part_no"],
                    r["part_name"],
                    r["material"],
                    r["operation_no"],
                    r["operation_name"],
                    r["equipment_code"],
                    r["tool_code"],
                    r["spindle_speed"],
                    r["cutting_depth"],
                    r["feed_rate"],
                    r["speed_min"],
                    r["speed_max"],
                    r["depth_min"],
                    r["depth_max"],
                    r["feed_min"],
                    r["feed_max"],
                    r["version"],
                    r["approved_by"],
                    r["remark"],
                    r["created_at"],
                    r["updated_at"],
                )
                for r in proc_rows
            ],
        )

        await db.executemany(
            """
            INSERT INTO process_knowledge (
                category, title, content, tags, related_part_no, related_op_no,
                source, author, status, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    r["category"],
                    r["title"],
                    r["content"],
                    r["tags"],
                    r["related_part_no"],
                    r["related_op_no"],
                    r["source"],
                    r["author"],
                    r["status"],
                    r["created_at"],
                    r["updated_at"],
                )
                for r in know_rows
            ],
        )

        await db.executemany(
            """
            INSERT INTO optimization_run (
                equipment_code, part_no, operation_no,
                pred_spindle, pred_depth, pred_feed, model_version, score, adopted, remark, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    r["equipment_code"],
                    r["part_no"],
                    r["operation_no"],
                    r["pred_spindle"],
                    r["pred_depth"],
                    r["pred_feed"],
                    r["model_version"],
                    r["score"],
                    r["adopted"],
                    r["remark"],
                    r["created_at"],
                )
                for r in opt_rows
            ],
        )

        await db.commit()
    finally:
        await db.close()

    actual = part_count + len(proc_rows) + len(know_rows) + len(opt_rows)
    return {
        "parts": part_count,
        "processes": len(proc_rows),
        "knowledge": len(know_rows),
        "optimization": len(opt_rows),
        "total": actual,
    }
