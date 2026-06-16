"""工艺路线图纸 / 流程图生成（可打印 HTML + SVG）。"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

from app.services.drawing_annotation import (
    build_drawing_annotation,
    datums_table_html,
    roughness_table_html,
)


def attach_process_sheets(result: dict[str, Any]) -> dict[str, Any]:
    features = result.get("model_features") or {}
    routes = result.get("routes") or []
    sheets: list[dict[str, Any]] = []
    for route in routes:
        sheet = build_process_sheet(features, route)
        route["flow_diagram_svg"] = sheet["diagram_svg"]
        route["process_sheet_html"] = sheet["sheet_html"]
        route["plan_view_svg"] = sheet["plan_view_svg"]
        route["side_view_svg"] = sheet["side_view_svg"]
        route["datums"] = sheet["datums"]
        route["roughness"] = sheet["roughness"]
        sheets.append(
            {
                "route_id": route.get("route_id"),
                "route_name": route.get("route_name"),
                "diagram_svg": sheet["diagram_svg"],
                "process_sheet_html": sheet["sheet_html"],
                "plan_view_svg": sheet["plan_view_svg"],
                "side_view_svg": sheet["side_view_svg"],
            }
        )
    result["process_sheets"] = sheets
    result["sheet_version"] = "2.2.0"
    return result


def build_process_sheet(features: dict[str, Any], route: dict[str, Any]) -> dict[str, str]:
    ops = route.get("operations") or []
    drawing = build_drawing_annotation(features, route)
    diagram_svg = _flow_diagram_svg(ops, route.get("route_name", "工艺路线"))
    sheet_html = _process_sheet_html(features, route, ops, drawing)
    return {
        "diagram_svg": diagram_svg,
        "sheet_html": sheet_html,
        "plan_view_svg": drawing["plan_view_svg"],
        "side_view_svg": drawing["side_view_svg"],
        "datums": drawing["datums"],
        "roughness": drawing["roughness"],
    }


def _flow_diagram_svg(operations: list[dict], title: str) -> str:
    if not operations:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="40"><text x="4" y="24">无工序</text></svg>'

    box_w, box_h, gap = 118, 44, 28
    names = [str(o.get("operation_name") or f"工序{o.get('operation_no', '')}") for o in operations]
    width = len(names) * (box_w + gap) + 20
    height = 100
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<text x="10" y="16" font-size="12" fill="#334155">{escape(title)}</text>',
    ]
    x = 10
    y = 28
    for i, name in enumerate(names):
        label = name if len(name) <= 8 else name[:7] + "…"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="6" '
            f'fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x + box_w/2}" y="{y + 18}" text-anchor="middle" '
            f'font-size="11" fill="#1e3a8a">{escape(label)}</text>'
        )
        no = operations[i].get("operation_no")
        if no is not None:
            parts.append(
                f'<text x="{x + box_w/2}" y="{y + 34}" text-anchor="middle" '
                f'font-size="10" fill="#64748b">#{no}</text>'
            )
        if i < len(names) - 1:
            ax = x + box_w + 4
            parts.append(
                f'<line x1="{ax}" y1="{y + box_h/2}" x2="{ax + gap - 8}" y2="{y + box_h/2}" '
                f'stroke="#64748b" stroke-width="1.5" marker-end="url(#arrow)"/>'
            )
        x += box_w + gap
    parts.insert(
        2,
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" '
        'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#64748b"/></marker></defs>',
    )
    parts.append("</svg>")
    return "".join(parts)


def _process_sheet_html(
    features: dict[str, Any],
    route: dict[str, Any],
    operations: list[dict],
    drawing: dict[str, Any],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fname = escape(str(features.get("filename") or "-"))
    part_type = escape(str(features.get("part_type") or "-"))
    material = escape(str(features.get("material") or "-"))
    route_name = escape(str(route.get("route_name") or "工艺路线"))
    flow = escape(str(route.get("flow_summary") or ""))
    ref = escape(str(route.get("reference") or "-"))
    conf = int(round((route.get("confidence") or 0) * 100))

    dim_rows = _dimension_rows(features)
    op_rows = ""
    for o in operations:
        op_rows += (
            "<tr>"
            f"<td>{escape(str(o.get('operation_no', '-')))}</td>"
            f"<td>{escape(str(o.get('operation_name', '-')))}</td>"
            f"<td>{escape(str(o.get('equipment_code', '-')))}</td>"
            f"<td>{escape(str(o.get('tool_code', '-') or '-'))}</td>"
            f"<td>{escape(str(o.get('spindle_speed', '-')))}</td>"
            f"<td>{escape(str(o.get('feed_rate', '-')))}</td>"
            f"<td>{escape(str(o.get('cutting_depth', '-')))}</td>"
            "</tr>"
        )

    diagram = _flow_diagram_svg(operations, route.get("route_name", ""))
    plan_svg = drawing.get("plan_view_svg") or ""
    side_svg = drawing.get("side_view_svg") or ""
    datums_html = datums_table_html(drawing.get("datums") or [])
    rough_html = roughness_table_html(drawing.get("roughness") or [])
    draw_note = escape(str(drawing.get("drawing_note") or ""))

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>工艺路线图 — {route_name}</title>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; margin: 24px; color: #111; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 15px; margin: 20px 0 8px; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
  .sub {{ color: #555; font-size: 13px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }}
  th, td {{ border: 1px solid #333; padding: 6px 8px; text-align: left; }}
  th {{ background: #f0f0f0; }}
  .meta {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0; }}
  .meta div {{ border: 1px solid #ccc; padding: 8px; font-size: 13px; }}
  .meta .k {{ color: #666; font-size: 11px; }}
  .flow-box {{ border: 1px dashed #999; padding: 12px; margin: 12px 0; overflow-x: auto; }}
  .draw-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }}
  .draw-panel {{ border: 1px solid #999; padding: 8px; background: #fafafa; overflow: auto; }}
  .draw-table {{ font-size: 12px; }}
  .note {{ font-size: 12px; color: #666; margin-top: 16px; }}
  @media print {{ body {{ margin: 12mm; }} button {{ display: none; }} .draw-row {{ break-inside: avoid; }} }}
</style></head><body>
<button onclick="window.print()" style="margin-bottom:12px;padding:8px 16px">打印 / 另存为 PDF</button>
<h1>数控加工工艺路线图</h1>
<p class="sub">Process Knowledge Base · 自动生成 · {now}</p>
<div class="meta">
  <div><div class="k">模型文件</div>{fname}</div>
  <div><div class="k">识别类型</div>{part_type}</div>
  <div><div class="k">材料</div>{material}</div>
  <div><div class="k">推荐方案</div>{route_name}</div>
  <div><div class="k">置信度</div>{conf}%</div>
  <div><div class="k">参考</div>{ref}</div>
</div>
{dim_rows}
<h2>零件图纸 · 俯视图 / 侧视图</h2>
<p class="note">{draw_note}</p>
<div class="draw-row">
  <div class="draw-panel">{plan_svg}</div>
  <div class="draw-panel">{side_svg}</div>
</div>
<h2>基准面 / 基准轴线</h2>
{datums_html}
<h2>表面粗糙度要求</h2>
{rough_html}
<h2>工序流程</h2>
<p><strong>流程摘要：</strong>{flow}</p>
<div class="flow-box">{diagram}</div>
<table>
  <thead><tr>
    <th>工序号</th><th>工序名称</th><th>设备</th><th>刀具</th>
    <th>转速(rpm)</th><th>进给</th><th>切深(mm)</th>
  </tr></thead>
  <tbody>{op_rows or '<tr><td colspan="7">无工序</td></tr>'}</tbody>
</table>
<p class="note">本工艺路线由三维模型几何特征自动识别生成，基准与粗糙度为系统推断值，仅供工艺人员审核参考，正式下发前须签字确认。</p>
</body></html>"""


def _dimension_rows(features: dict[str, Any]) -> str:
    pt = features.get("part_type")
    items: list[tuple[str, Any]] = []
    if pt == "齿轮":
        items = [
            ("外径 mm", features.get("outer_diameter_mm")),
            ("齿宽 mm", features.get("face_width_mm")),
            ("模数", features.get("module_m")),
            ("齿数", features.get("teeth_z")),
        ]
    elif pt == "块体（带圆柱孔）":
        items = [
            ("长 mm", features.get("length_mm")),
            ("宽 mm", features.get("width_mm")),
            ("高 mm", features.get("height_mm")),
            ("孔径 mm", features.get("hole_diameter_mm")),
        ]
    elif pt == "轴类":
        items = [
            ("长度 mm", features.get("length_mm")),
            ("直径 mm", features.get("diameter_mm")),
        ]
    else:
        items = [
            ("长 mm", features.get("length_mm")),
            ("宽 mm", features.get("width_mm")),
            ("高 mm", features.get("height_mm")),
        ]
    cells = "".join(
        f'<div><div class="k">{escape(k)}</div>{escape(str(v if v is not None else "-"))}</div>'
        for k, v in items
    )
    return f'<div class="meta">{cells}</div>' if cells else ""
