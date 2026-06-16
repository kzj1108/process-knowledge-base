"""工艺图纸标注：俯视图、基准面、表面粗糙度（基于特征与工序推断）。"""

from __future__ import annotations

import math
from html import escape
from typing import Any


def build_drawing_annotation(features: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    """生成图纸标注数据与俯视图 SVG。"""
    part_type = features.get("part_type") or "块体件"
    ops = route.get("operations") or []
    datums = _infer_datums(features, part_type)
    roughness = _infer_roughness(features, part_type, ops)
    plan_svg = _plan_view_svg(features, part_type, datums, roughness)
    side_svg = _side_view_svg(features, part_type, datums, roughness)
    return {
        "datums": datums,
        "roughness": roughness,
        "plan_view_svg": plan_svg,
        "side_view_svg": side_svg,
        "drawing_note": _drawing_note(features, part_type),
    }


def _drawing_note(features: dict[str, Any], part_type: str) -> str:
    fam = features.get("format_family")
    src = "CAD 实体" if fam == "cad_brep" else "网格包围盒"
    return f"俯视图/侧视图按 {src} 尺寸比例绘制，基准与粗糙度由工序链自动推断，正式图纸须工艺员审定。"


def _infer_datums(features: dict[str, Any], part_type: str) -> list[dict[str, str]]:
    lx = _dim(features, "x")
    ly = _dim(features, "y")
    lz = _dim(features, "z")
    hole = features.get("hole_diameter_mm")

    if part_type == "齿轮":
        return [
            {"id": "A", "face": "右端面", "type": "平面", "note": "装夹基准，控制齿宽方向定位"},
            {"id": "B", "face": "内孔轴线", "type": "轴线", "note": "径向基准，与滚齿分度圆同轴"},
            {"id": "C", "face": "外圆柱面", "type": "圆柱", "note": "齿顶圆定位辅助基准"},
        ]
    if part_type == "轴类":
        return [
            {"id": "A", "face": "中心孔/外圆轴线", "type": "轴线", "note": "车削主基准"},
            {"id": "B", "face": "左端面", "type": "平面", "note": "轴向定位基准"},
            {"id": "C", "face": "键槽底面", "type": "平面", "note": "二次装夹找正基准"},
        ]
    if part_type == "曲面件":
        return [
            {"id": "A", "face": "底面安装面", "type": "平面", "note": "五轴装夹基准"},
            {"id": "B", "face": "侧面定位面", "type": "平面", "note": "角度找正基准"},
        ]
    if part_type == "块体（带圆柱孔）" and hole:
        return [
            {"id": "A", "face": "底面（最大平面）", "type": "平面", "note": f"第一基准，尺寸 {lx}×{ly} mm"},
            {"id": "B", "face": "长侧面", "type": "平面", "note": f"第二基准，高度方向 {lz} mm"},
            {"id": "C", "face": f"孔轴线 Ø{hole}", "type": "轴线", "note": "孔系加工基准，镗孔同轴度依据"},
        ]
    return [
        {"id": "A", "face": "底面", "type": "平面", "note": f"铣削装夹面，约 {lx}×{ly} mm"},
        {"id": "B", "face": "长侧面", "type": "平面", "note": f"垂直于 A 的侧面，高 {lz} mm"},
        {"id": "C", "face": "端面", "type": "平面", "note": "辅助定位面"},
    ]


def _infer_roughness(
    features: dict[str, Any],
    part_type: str,
    operations: list[dict],
) -> list[dict[str, str]]:
    """根据末序加工推断各表面粗糙度 Ra (μm)。"""
    op_names = " ".join(str(o.get("operation_name") or "") for o in operations)
    ra_finish = _ra_from_ops(op_names, finish=True)
    ra_semi = _ra_from_ops(op_names, finish=False)
    ra_hole = _ra_hole_from_ops(op_names)
    items: list[dict[str, str]] = []

    if part_type == "齿轮":
        items = [
            {"surface": "齿面", "ra": ra_finish, "symbol": f"Ra {ra_finish}", "process": "滚齿/精铣"},
            {"surface": "端面 A", "ra": ra_semi, "symbol": f"Ra {ra_semi}", "process": "铣削"},
            {"surface": "内孔", "ra": "3.2", "symbol": "Ra 3.2", "process": "镗/铰"},
        ]
    elif part_type == "轴类":
        items = [
            {"surface": "外圆", "ra": ra_finish, "symbol": f"Ra {ra_finish}", "process": "精车"},
            {"surface": "端面 B", "ra": ra_semi, "symbol": f"Ra {ra_semi}", "process": "车/铣"},
            {"surface": "键槽", "ra": "3.2", "symbol": "Ra 3.2", "process": "铣键槽"},
        ]
    elif part_type == "曲面件":
        items = [
            {"surface": "型面", "ra": ra_finish, "symbol": f"Ra {ra_finish}", "process": "五轴精铣"},
            {"surface": "底面 A", "ra": ra_semi, "symbol": f"Ra {ra_semi}", "process": "铣基准"},
        ]
    elif part_type == "块体（带圆柱孔）":
        hole = features.get("hole_diameter_mm")
        items = [
            {"surface": "平面 A/B", "ra": ra_finish, "symbol": f"Ra {ra_finish}", "process": "精铣"},
            {"surface": f"孔壁 Ø{hole or '?'}", "ra": ra_hole, "symbol": f"Ra {ra_hole}", "process": "钻/镗"},
            {"surface": "其余面", "ra": ra_semi, "symbol": f"Ra {ra_semi}", "process": "粗铣"},
        ]
    else:
        items = [
            {"surface": "加工面", "ra": ra_finish, "symbol": f"Ra {ra_finish}", "process": "精铣"},
            {"surface": "非配合面", "ra": ra_semi, "symbol": f"Ra {ra_semi}", "process": "粗铣"},
        ]
    return items


def _ra_from_ops(op_text: str, *, finish: bool) -> str:
    if finish:
        if any(k in op_text for k in ("精滚", "精铣", "精车", "精加工")):
            return "1.6"
        if any(k in op_text for k in ("半精", "铰孔", "镗孔")):
            return "3.2"
        return "6.3"
    if any(k in op_text for k in ("粗铣", "粗车", "粗加工", "铣面")):
        return "6.3"
    return "12.5"


def _ra_hole_from_ops(op_text: str) -> str:
    if any(k in op_text for k in ("镗", "铰", "精镗", "数控镗")):
        return "1.6"
    if "钻" in op_text:
        return "6.3"
    return "12.5"


def _dim(features: dict[str, Any], axis: str) -> float:
    keys = {
        "x": ("size_x_mm", "length_x"),
        "y": ("size_y_mm", "length_y"),
        "z": ("size_z_mm", "length_z"),
    }
    k0, k1 = keys[axis]
    v = features.get(k0)
    if v is None and features.get("dimensions_mm"):
        v = features["dimensions_mm"].get(k1)
    if v is None:
        sorted_dims = sorted(
            [
                features.get("length_mm") or 0,
                features.get("width_mm") or 0,
                features.get("height_mm") or 0,
            ],
            reverse=True,
        )
        idx = {"x": 0, "y": 1, "z": 2}[axis]
        v = sorted_dims[idx] if sorted_dims[idx] else 50.0
    return max(float(v), 1.0)


def _plan_view_svg(
    features: dict[str, Any],
    part_type: str,
    datums: list[dict[str, str]],
    roughness: list[dict[str, str]],
) -> str:
    w, h = 480, 360
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="#fafafa"/>',
        f'<text x="{w/2}" y="22" text-anchor="middle" font-size="13" fill="#334155">俯视图 (Plan View)</text>',
    ]

    if part_type == "齿轮":
        parts.extend(_svg_gear_plan(features, datums, roughness))
    elif part_type == "轴类":
        parts.extend(_svg_shaft_plan(features, datums, roughness))
    else:
        parts.extend(_svg_block_plan(features, part_type, datums, roughness))

    parts.append("</svg>")
    return "".join(parts)


def _side_view_svg(
    features: dict[str, Any],
    part_type: str,
    datums: list[dict[str, str]],
    roughness: list[dict[str, str]],
) -> str:
    w, h = 480, 280
    lx, ly, lz = _dim(features, "x"), _dim(features, "y"), _dim(features, "z")
    scale = min(300 / max(lx, ly, 1), 180 / max(lz, 1))
    rw, rh = lx * scale, lz * scale
    ox, oy = (w - rw) / 2, 70

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="#fafafa"/>',
        f'<text x="{w/2}" y="22" text-anchor="middle" font-size="13" fill="#334155">侧视图 (Side View)</text>',
        f'<rect x="{ox}" y="{oy}" width="{rw}" height="{rh}" fill="#e2e8f0" stroke="#1e293b" stroke-width="2"/>',
        _dim_line_h(ox, oy + rh + 18, rw, f"{lx:.1f}"),
        _dim_line_v(ox - 18, oy, rh, f"{lz:.1f}"),
    ]
    if part_type == "块体（带圆柱孔）" and features.get("hole_diameter_mm"):
        hd = float(features["hole_diameter_mm"]) * scale
        cx, cy = ox + rw / 2, oy + rh / 2
        parts.append(
            f'<line x1="{cx-hd/2}" y1="{cy}" x2="{cx+hd/2}" y2="{cy}" '
            f'stroke="#dc2626" stroke-width="1.5" stroke-dasharray="4,2"/>'
        )
        parts.append(
            f'<text x="{cx}" y="{cy-8}" text-anchor="middle" font-size="10" fill="#dc2626">'
            f'Ø{features["hole_diameter_mm"]}</text>'
        )
    ra = roughness[0]["symbol"] if roughness else "Ra 6.3"
    parts.append(_roughness_mark(ox + 8, oy + 12, ra))
    parts.append(_datum_triangle(ox + rw - 28, oy + rh - 8, "B"))
    parts.append("</svg>")
    return "".join(parts)


def _svg_block_plan(
    features: dict[str, Any],
    part_type: str,
    datums: list[dict[str, str]],
    roughness: list[dict[str, str]],
) -> list[str]:
    lx, ly = _dim(features, "x"), _dim(features, "y")
    scale = min(320 / max(lx, 1), 220 / max(ly, 1))
    rw, rh = lx * scale, ly * scale
    ox, oy = (480 - rw) / 2, 80
    parts = [
        f'<rect x="{ox}" y="{oy}" width="{rw}" height="{rh}" fill="#e2e8f0" stroke="#1e293b" stroke-width="2"/>',
        _dim_line_h(ox, oy + rh + 20, rw, f"{lx:.1f}"),
        _dim_line_v(ox + rw + 16, oy, rh, f"{ly:.1f}"),
        _datum_triangle(ox + 12, oy + rh - 10, "A"),
        _datum_triangle(ox + rw - 10, oy + 18, "B"),
    ]
    hole = features.get("hole_diameter_mm")
    if hole and part_type == "块体（带圆柱孔）":
        hr = float(hole) / 2 * scale
        cx, cy = ox + rw / 2, oy + rh / 2
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{hr}" fill="#fff" stroke="#dc2626" stroke-width="2"/>')
        parts.append(
            f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="11" fill="#dc2626">Ø{hole}</text>'
        )
        parts.append(_datum_circle(cx + hr + 14, cy, "C"))
        ra_hole = next((r["symbol"] for r in roughness if "孔" in r.get("surface", "")), "Ra 6.3")
        parts.append(_roughness_mark(cx - hr - 36, cy - 6, ra_hole))
    ra_plane = roughness[0]["symbol"] if roughness else "Ra 6.3"
    parts.append(_roughness_mark(ox + 8, oy + 10, ra_plane))
    parts.append(
        f'<text x="{ox}" y="{oy-8}" font-size="10" fill="#64748b">基准 A: 底面装夹</text>'
    )
    return parts


def _svg_gear_plan(
    features: dict[str, Any],
    datums: list[dict[str, str]],
    roughness: list[dict[str, str]],
) -> list[str]:
    od = float(features.get("outer_diameter_mm") or _dim(features, "x"))
    scale = 200 / max(od, 1)
    r = od / 2 * scale
    cx, cy = 240, 190
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#e2e8f0" stroke="#1e293b" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r*0.75}" fill="none" stroke="#94a3b8" stroke-width="1" stroke-dasharray="3,2"/>',
    ]
    bore = r * 0.22
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{bore}" fill="#fff" stroke="#dc2626" stroke-width="1.5"/>')
    for i in range(12):
        ang = math.radians(i * 30)
        x1 = cx + r * 0.82 * math.cos(ang)
        y1 = cy + r * 0.82 * math.sin(ang)
        x2 = cx + r * math.cos(ang)
        y2 = cy + r * math.sin(ang)
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#64748b" stroke-width="1"/>')
    parts.append(_datum_triangle(cx - r - 20, cy, "A"))
    parts.append(_datum_circle(cx + bore + 16, cy, "B"))
    ra = roughness[0]["symbol"] if roughness else "Ra 1.6"
    parts.append(_roughness_mark(cx + r * 0.5, cy - r * 0.5, ra))
    parts.append(
        f'<text x="{cx}" y="{cy+r+28}" text-anchor="middle" font-size="11" fill="#334155">'
        f'外径 Ø{od:.1f}</text>'
    )
    return parts


def _svg_shaft_plan(
    features: dict[str, Any],
    datums: list[dict[str, str]],
    roughness: list[dict[str, str]],
) -> list[str]:
    d = float(features.get("diameter_mm") or _dim(features, "y"))
    scale = 180 / max(d, 1)
    r = d / 2 * scale
    cx, cy = 240, 190
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#e2e8f0" stroke="#1e293b" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="3" fill="#dc2626"/>',
        f'<line x1="{cx-r-30}" y1="{cy}" x2="{cx+r+30}" y2="{cy}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4,3"/>',
        f'<text x="{cx}" y="{cy+r+24}" text-anchor="middle" font-size="11">Ø{d:.1f}</text>',
        _datum_circle(cx + r + 18, cy, "A"),
        _roughness_mark(cx - r - 8, cy - r - 8, roughness[0]["symbol"] if roughness else "Ra 1.6"),
    ]
    return parts


def _datum_triangle(x: float, y: float, letter: str) -> str:
    return (
        f'<g transform="translate({x},{y})">'
        f'<polygon points="0,0 0,-14 10,-7" fill="#fff" stroke="#1e293b" stroke-width="1.2"/>'
        f'<text x="14" y="-4" font-size="12" font-weight="bold" fill="#1e40af">{letter}</text>'
        f"</g>"
    )


def _datum_circle(x: float, y: float, letter: str) -> str:
    return (
        f'<g transform="translate({x},{y})">'
        f'<circle cx="0" cy="0" r="9" fill="#fff" stroke="#1e293b" stroke-width="1.2"/>'
        f'<text x="0" y="4" text-anchor="middle" font-size="11" font-weight="bold" fill="#1e40af">{letter}</text>'
        f"</g>"
    )


def _roughness_mark(x: float, y: float, ra_text: str) -> str:
  # Ra symbol simplified
    return (
        f'<g transform="translate({x},{y})">'
        f'<text font-size="10" fill="#b45309" font-family="serif">√</text>'
        f'<text x="10" y="0" font-size="10" fill="#b45309">{escape(ra_text)}</text>'
        f"</g>"
    )


def _dim_line_h(x: float, y: float, length: float, label: str) -> str:
    x2 = x + length
    return (
        f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{x}" y1="{y-4}" x2="{x}" y2="{y+4}" stroke="#475569"/>'
        f'<line x1="{x2}" y1="{y-4}" x2="{x2}" y2="{y+4}" stroke="#475569"/>'
        f'<text x="{(x+x2)/2}" y="{y+14}" text-anchor="middle" font-size="10" fill="#475569">{label}</text>'
    )


def _dim_line_v(x: float, y: float, length: float, label: str) -> str:
    y2 = y + length
    return (
        f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y2}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{x-4}" y1="{y}" x2="{x+4}" y2="{y}" stroke="#475569"/>'
        f'<line x1="{x-4}" y1="{y2}" x2="{x+4}" y2="{y2}" stroke="#475569"/>'
        f'<text x="{x-6}" y="{(y+y2)/2}" text-anchor="middle" font-size="10" fill="#475569" '
        f'transform="rotate(-90 {x-6} {(y+y2)/2})">{label}</text>'
    )


def datums_table_html(datums: list[dict[str, str]]) -> str:
    rows = "".join(
        f"<tr><td>{escape(d['id'])}</td><td>{escape(d['face'])}</td>"
        f"<td>{escape(d['type'])}</td><td>{escape(d['note'])}</td></tr>"
        for d in datums
    )
    return (
        "<table class='draw-table'><thead><tr>"
        "<th>基准</th><th>表面</th><th>类型</th><th>说明</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def roughness_table_html(roughness: list[dict[str, str]]) -> str:
    rows = "".join(
        f"<tr><td>{escape(r['surface'])}</td><td>{escape(r['symbol'])}</td>"
        f"<td>{escape(r['process'])}</td></tr>"
        for r in roughness
    )
    return (
        "<table class='draw-table'><thead><tr>"
        "<th>表面</th><th>粗糙度</th><th>加工方法</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )
