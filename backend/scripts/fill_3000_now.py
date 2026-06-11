#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接向已上线的 Render 站点写入约 3000 条数据（无需 seed-bulk 新接口）。
用法:
  python fill_3000_now.py
按提示输入网址和 API Key；或在 Render 环境变量里复制 PKB_API_KEY。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

MATERIALS = ["40Cr", "45钢", "20CrMnTi", "HT250", "Q235", "42CrMo"]
CATEGORIES = ["齿轮件", "轴类件", "箱体件", "结构件"]
EQUIPMENT = ["CNC-01", "CNC-02", "ROBOT-01", "LINE-01"]
OPS = ["粗铣", "精铣", "车外圆", "滚齿", "钻孔", "磨削"]
KNOW_CATS = ["RULE", "FAQ", "CASE", "STANDARD"]


def post_json(url: str, api_key: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())


def gen_parts(n: int) -> list:
    return [
        {
            "part_no": f"PART-BULK-{i:05d}",
            "part_name": f"批量零件-{i}",
            "material": MATERIALS[i % len(MATERIALS)],
            "drawing_no": f"DW-B-{i:05d}",
            "category": CATEGORIES[i % len(CATEGORIES)],
        }
        for i in range(1, n + 1)
    ]


def gen_process(parts: list, per_part: int) -> list:
    rows = []
    for p in parts:
        for op in range(1, per_part + 1):
            speed = 700 + (hash(p["part_no"]) % 3500)
            depth = round(0.2 + (op % 6) * 0.3, 2)
            feed = 220 + op * 45
            rows.append(
                {
                    "part_no": p["part_no"],
                    "part_name": p["part_name"],
                    "material": p["material"],
                    "operation_no": op * 10,
                    "operation_name": OPS[op % len(OPS)],
                    "equipment_code": EQUIPMENT[op % len(EQUIPMENT)],
                    "tool_code": f"T-{op:02d}",
                    "spindle_speed": float(speed),
                    "cutting_depth": depth,
                    "feed_rate": float(feed),
                    "speed_min": float(speed * 0.7),
                    "speed_max": float(speed * 1.3),
                    "approved_by": "批量导入",
                }
            )
    return rows


def gen_knowledge(parts: list, n: int) -> list:
    rows = []
    for i in range(n):
        cat = KNOW_CATS[i % 4]
        p = parts[i % len(parts)]
        op = (i % 12 + 1) * 10
        rows.append(
            {
                "category": cat,
                "title": f"{p['part_name']}-知识-{i + 1}",
                "content": f"材料{p['material']} 工序{op}：转速与切深按卡片执行，进给可调±10%。",
                "tags": f"{p['material']},批量",
                "related_part_no": p["part_no"],
                "related_op_no": op,
                "author": f"工艺员{(i % 8) + 1}",
                "source": "批量导入",
            }
        )
    return rows


def chunk(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def main() -> None:
    print("=== 工艺知识库：远程填充约 3000 条 ===\n")
    base = input("站点地址 (例 https://process-knowledge-base-1.onrender.com): ").strip().rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base
    api_key = input("PKB_API_KEY (Render 环境变量里复制): ").strip()
    if not api_key:
        print("必须填写 API Key")
        sys.exit(1)

    url = base + "/api/v1/import/json"
    part_count = 200
    per_part = 10
    know_count = 700

    parts = gen_parts(part_count)
    processes = gen_process(parts, per_part)
    knowledge = gen_knowledge(parts, know_count)

    print(f"计划: 零件 {len(parts)} + 工序 {len(processes)} + 知识 {len(knowledge)} = {len(parts)+len(processes)+len(knowledge)}")

    done = {"parts": 0, "process": 0, "knowledge": 0}
    for i, batch in enumerate(chunk(parts, 50)):
        print(f"  零件批次 {i + 1}...", end=" ", flush=True)
        r = post_json(url, api_key, {"parts": batch})
        done["parts"] += r.get("imported", {}).get("parts", 0)
        print(r.get("imported", {}))

    for i, batch in enumerate(chunk(processes, 80)):
        print(f"  工序批次 {i + 1}...", end=" ", flush=True)
        r = post_json(url, api_key, {"process": batch})
        done["process"] += r.get("imported", {}).get("process", 0)
        print(r.get("imported", {}))

    for i, batch in enumerate(chunk(knowledge, 80)):
        print(f"  知识批次 {i + 1}...", end=" ", flush=True)
        r = post_json(url, api_key, {"knowledge": batch})
        done["knowledge"] += r.get("imported", {}).get("knowledge", 0)
        print(r.get("imported", {}))

    total = done["parts"] + done["process"] + done["knowledge"]
    print(f"\n完成! 写入约 {total} 条")
    print("请刷新网站总览页查看统计。")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print("\n错误:", e.read().decode())
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已取消")
