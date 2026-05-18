#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成可在网站「数据上传」里导入的 CSV 文件"""
from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "upload_data"
MATERIALS = ["40Cr", "45钢", "20CrMnTi", "HT250", "Q235", "42CrMo"]
CATEGORIES = ["齿轮件", "轴类件", "箱体件", "结构件"]
EQUIPMENT = ["CNC-01", "CNC-02", "ROBOT-01", "LINE-01"]
OPS = ["粗铣", "精铣", "车外圆", "滚齿", "钻孔", "磨削"]
KNOW_CATS = ["RULE", "FAQ", "CASE", "STANDARD"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    parts = []
    for i in range(1, 201):
        parts.append(
            {
                "part_no": f"PART-BULK-{i:05d}",
                "part_name": f"批量零件-{i}",
                "material": MATERIALS[i % len(MATERIALS)],
                "drawing_no": f"DW-B-{i:05d}",
                "category": CATEGORIES[i % len(CATEGORIES)],
                "remark": "批量导入",
            }
        )

    with open(OUT / "1_parts_200.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["part_no", "part_name", "material", "drawing_no", "category", "remark"],
        )
        w.writeheader()
        w.writerows(parts)

    processes = []
    for p in parts:
        for op in range(1, 11):
            speed = 700 + (hash(p["part_no"]) % 3500) + op * 20
            depth = round(0.2 + (op % 6) * 0.3, 2)
            feed = 220 + op * 45
            processes.append(
                {
                    "part_no": p["part_no"],
                    "part_name": p["part_name"],
                    "material": p["material"],
                    "operation_no": op * 10,
                    "operation_name": OPS[op % len(OPS)],
                    "equipment_code": EQUIPMENT[op % len(EQUIPMENT)],
                    "tool_code": f"T-{op:02d}",
                    "spindle_speed": speed,
                    "cutting_depth": depth,
                    "feed_rate": feed,
                    "speed_min": round(speed * 0.7, 1),
                    "speed_max": round(speed * 1.3, 1),
                    "depth_min": round(depth * 0.5, 2),
                    "depth_max": round(depth * 2, 2),
                    "feed_min": round(feed * 0.6, 1),
                    "feed_max": round(feed * 1.4, 1),
                    "approved_by": "批量导入",
                    "remark": "",
                }
            )

    with open(OUT / "2_process_2000.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "part_no", "part_name", "material", "operation_no", "operation_name",
                "equipment_code", "tool_code", "spindle_speed", "cutting_depth", "feed_rate",
                "speed_min", "speed_max", "depth_min", "depth_max", "feed_min", "feed_max",
                "approved_by", "remark",
            ],
        )
        w.writeheader()
        w.writerows(processes)

    knowledge = []
    for i in range(700):
        cat = KNOW_CATS[i % 4]
        p = parts[i % len(parts)]
        op = (i % 12 + 1) * 10
        knowledge.append(
            {
                "category": cat,
                "title": f"{p['part_name']}-知识条目-{i + 1}",
                "content": f"材料{p['material']}，工序{op}：按工艺卡片控制转速与切深，进给可在±10%内调整。",
                "tags": f"{p['material']},批量,{cat}",
                "related_part_no": p["part_no"],
                "related_op_no": op,
                "author": f"工艺员{(i % 8) + 1}",
                "source": "CSV导入",
            }
        )

    with open(OUT / "3_knowledge_700.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "category", "title", "content", "tags",
                "related_part_no", "related_op_no", "author", "source",
            ],
        )
        w.writeheader()
        w.writerows(knowledge)

    print(f"已生成到: {OUT}")
    print("  1_parts_200.csv      (200 条)")
    print("  2_process_2000.csv   (2000 条)")
    print("  3_knowledge_700.csv  (700 条)")
    print("  合计约 2900 条")


if __name__ == "__main__":
    main()
