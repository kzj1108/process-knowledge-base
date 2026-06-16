"""三维模型（STL/OBJ）轻量解析 — 识别块体/带孔件/齿轮等形状特征。"""

from __future__ import annotations

import math
import struct
import statistics
from pathlib import Path
from typing import Any


def parse_model_file(content: bytes, filename: str) -> dict[str, Any]:
    ext = Path(filename).suffix.lower()
    if ext == ".stl":
        vertices = _parse_stl(content)
    elif ext == ".obj":
        vertices = _parse_obj(content)
    else:
        raise ValueError(f"暂不支持 {ext} 格式，请上传 STL 或 OBJ 文件")

    if len(vertices) < 3:
        raise ValueError("模型顶点数过少，无法分析")

    bbox = _bounding_box(vertices)
    dims = {
        "length_x": round(bbox["xmax"] - bbox["xmin"], 3),
        "length_y": round(bbox["ymax"] - bbox["ymin"], 3),
        "length_z": round(bbox["zmax"] - bbox["zmin"], 3),
    }

    geo = _analyze_geometry(vertices, bbox, dims, filename)
    part_type = geo["part_type"]

    result: dict[str, Any] = {
        "filename": filename,
        "format": ext.lstrip("."),
        "vertex_count": len(vertices),
        "triangle_count": len(vertices) // 3,
        "bbox": bbox,
        "dimensions_mm": dims,
        "part_type": part_type,
        "shape_hint": geo["shape_hint"],
        "flat_face_ratio": geo["flat_face_ratio"],
        "recognition_confidence": geo.get("recognition_confidence", 0.75),
        "material_hint": _material_from_filename(filename),
    }

    if part_type == "齿轮":
        result["outer_diameter_mm"] = geo.get("outer_diameter_mm")
        result["face_width_mm"] = geo.get("face_width_mm")
        result["teeth_z"] = geo.get("teeth_z")
        result["module_m"] = geo.get("module_m")
    elif part_type == "块体（带圆柱孔）":
        result["length_mm"] = geo.get("length_mm")
        result["width_mm"] = geo.get("width_mm")
        result["height_mm"] = geo.get("height_mm")
        result["hole_diameter_mm"] = geo.get("hole_diameter_mm")
    elif part_type in ("块体件", "箱体件"):
        result["length_mm"] = geo.get("length_mm")
        result["width_mm"] = geo.get("width_mm")
        result["height_mm"] = geo.get("height_mm")
    elif part_type == "轴类":
        result["length_mm"] = geo.get("length_mm")
        result["diameter_mm"] = geo.get("diameter_mm")
    elif part_type == "曲面件":
        result["length_mm"] = geo.get("length_mm")
        result["width_mm"] = geo.get("width_mm")
        result["height_mm"] = geo.get("height_mm")

    return result


def _analyze_geometry(
    vertices: list[tuple[float, float, float]],
    bbox: dict[str, float],
    dims: dict[str, float],
    filename: str,
) -> dict[str, Any]:
    lx, ly, lz = dims["length_x"], dims["length_y"], dims["length_z"]
    sorted_dims = sorted([lx, ly, lz], reverse=True)
    length, width, height = sorted_dims[0], sorted_dims[1], sorted_dims[2]

    step = max(1, len(vertices) // 3000)
    sample = vertices[::step]
    flat_ratio = _flat_face_ratio(sample, bbox, max(lx, ly, lz))

    name = filename.lower()
    if any(k in name for k in ("gear", "chi", "齿轮", "gearwheel")):
        return _as_gear(vertices, dims, flat_ratio, "文件名含齿轮关键字")

    hole_d, hole_plane = _detect_cylindrical_hole(sample, bbox, lx, ly, lz)
    if hole_d and flat_ratio >= 0.15:
        return {
            "part_type": "块体（带圆柱孔）",
            "shape_hint": f"检测到平面占比 {flat_ratio:.0%}，{hole_plane} 向圆柱孔约 Ø{hole_d} mm",
            "flat_face_ratio": round(flat_ratio, 3),
            "recognition_confidence": 0.88,
            "length_mm": length,
            "width_mm": width,
            "height_mm": height,
            "hole_diameter_mm": hole_d,
        }

    if any(k in name for k in ("box", "block", "plate", "块", "板", "零件")):
        return {
            "part_type": "块体件",
            "shape_hint": "文件名提示为块体/板类零件",
            "flat_face_ratio": round(flat_ratio, 3),
            "length_mm": length,
            "width_mm": width,
            "height_mm": height,
        }

    if any(k in name for k in ("shaft", "轴")):
        return {
            "part_type": "轴类",
            "shape_hint": "文件名提示为轴类",
            "flat_face_ratio": round(flat_ratio, 3),
            "length_mm": max(lx, ly, lz),
            "diameter_mm": round(min(lx, ly, lz), 3),
        }

    if any(k in name for k in ("housing", "箱", "盖")):
        return {
            "part_type": "箱体件",
            "shape_hint": "文件名提示为箱体类",
            "flat_face_ratio": round(flat_ratio, 3),
            "length_mm": length,
            "width_mm": width,
            "height_mm": height,
        }

    # 块体：大量顶点落在包围盒平面上
    if flat_ratio >= 0.20:
        return {
            "part_type": "块体件",
            "shape_hint": f"平面特征明显（{flat_ratio:.0%}），判定为块体/板类",
            "flat_face_ratio": round(flat_ratio, 3),
            "length_mm": length,
            "width_mm": width,
            "height_mm": height,
        }

    # 轴类：细长回转体
    if length / max(height, 0.001) >= 2.5 and flat_ratio < 0.15:
        return {
            "part_type": "轴类",
            "shape_hint": "细长回转外形",
            "flat_face_ratio": round(flat_ratio, 3),
            "length_mm": length,
            "diameter_mm": round(min(lx, ly, lz), 3),
        }

    # 齿轮：圆形截面 + 齿形半径波动 + 非块体
    if _is_gear_like(sample, bbox, lx, ly, flat_ratio):
        g = _as_gear(vertices, dims, flat_ratio, "圆形齿形特征")
        g["recognition_confidence"] = 0.84
        return g

    # 曲面件：自由曲面、低平面占比
    if flat_ratio < 0.12 and length / max(height, 0.001) < 2.2:
        return {
            "part_type": "曲面件",
            "shape_hint": f"自由曲面特征（平面占比 {flat_ratio:.0%}），建议五轴加工",
            "flat_face_ratio": round(flat_ratio, 3),
            "recognition_confidence": 0.80,
            "length_mm": length,
            "width_mm": width,
            "height_mm": height,
        }

    # 默认块体，避免误推滚齿
    return {
        "part_type": "块体件",
        "shape_hint": f"未识别齿形，按块体件处理（平面占比 {flat_ratio:.0%}）",
        "flat_face_ratio": round(flat_ratio, 3),
        "recognition_confidence": 0.68,
        "length_mm": length,
        "width_mm": width,
        "height_mm": height,
    }


def _flat_face_ratio(
    sample: list[tuple[float, float, float]], bbox: dict[str, float], span: float
) -> float:
    tol = max(span * 0.025, 1e-6)
    on_face = 0
    for x, y, z in sample:
        if (
            abs(x - bbox["xmin"]) < tol
            or abs(x - bbox["xmax"]) < tol
            or abs(y - bbox["ymin"]) < tol
            or abs(y - bbox["ymax"]) < tol
            or abs(z - bbox["zmin"]) < tol
            or abs(z - bbox["zmax"]) < tol
        ):
            on_face += 1
    return on_face / max(len(sample), 1)


def _detect_cylindrical_hole(
    sample: list[tuple[float, float, float]],
    bbox: dict[str, float],
    lx: float,
    ly: float,
    lz: float,
) -> tuple[float | None, str]:
    """检测块体上的圆柱孔，返回 (孔径, 孔轴线方向说明)。"""
    cx = (bbox["xmin"] + bbox["xmax"]) / 2
    cy = (bbox["ymin"] + bbox["ymax"]) / 2
    cz = (bbox["zmin"] + bbox["zmax"]) / 2

    configs = [
        ("Z 向通孔", lx, ly, lambda v: math.hypot(v[0] - cx, v[1] - cy), min(lx, ly) / 2),
        ("Y 向通孔", lx, lz, lambda v: math.hypot(v[0] - cx, v[2] - cz), min(lx, lz) / 2),
        ("X 向通孔", ly, lz, lambda v: math.hypot(v[1] - cy, v[2] - cz), min(ly, lz) / 2),
    ]

    best_d: float | None = None
    best_label = ""
    best_score = 0.0

    for label, _a, _b, radius_fn, half_extent in configs:
        if half_extent <= 0:
            continue
        radii = [radius_fn(v) for v in sample]
        if not radii:
            continue

        inner = [r for r in radii if 0.10 * half_extent < r < 0.62 * half_extent]
        center_empty = sum(1 for r in radii if r < 0.07 * half_extent) <= max(2, len(radii) * 0.04)
        outer = [r for r in radii if r > 0.72 * half_extent]

        if not center_empty or len(inner) < max(6, len(sample) * 0.025):
            continue

        inner_median = statistics.median(inner)
        score = len(inner) + (0.15 if outer else 0)
        if score > best_score and inner_median > 0:
            best_score = score
            best_d = round(2 * inner_median, 3)
            best_label = label

    return best_d, best_label


def _is_gear_like(
    sample: list[tuple[float, float, float]],
    bbox: dict[str, float],
    lx: float,
    ly: float,
    flat_ratio: float,
) -> bool:
    if flat_ratio >= 0.18:
        return False
    if max(lx, ly) < 12:
        return False
    if abs(lx - ly) / max(lx, ly, 1e-9) > 0.18:
        return False

    cx = (bbox["xmin"] + bbox["xmax"]) / 2
    cy = (bbox["ymin"] + bbox["ymax"]) / 2
    radii = [math.hypot(v[0] - cx, v[1] - cy) for v in sample]
    if len(radii) < 10:
        return False
    r_mean = statistics.mean(radii)
    if r_mean <= 0:
        return False
    variation = statistics.pstdev(radii) / r_mean
    return variation >= 0.06


def _as_gear(
    vertices: list[tuple[float, float, float]],
    dims: dict[str, float],
    flat_ratio: float,
    hint: str,
) -> dict[str, Any]:
    outer_d = round(max(dims["length_x"], dims["length_y"]), 3)
    face_w = round(min(dims["length_x"], dims["length_y"], dims["length_z"]), 3)
    teeth = _estimate_teeth(vertices, outer_d)
    module_m = round(outer_d / (teeth + 2), 2) if teeth else None
    return {
        "part_type": "齿轮",
        "shape_hint": hint,
        "flat_face_ratio": round(flat_ratio, 3),
        "outer_diameter_mm": outer_d,
        "face_width_mm": face_w,
        "teeth_z": teeth,
        "module_m": module_m,
    }


def _estimate_teeth(vertices: list[tuple[float, float, float]], outer_d: float) -> int | None:
    if outer_d < 12:
        return None
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    radii: list[float] = []
    step = max(1, len(vertices) // 2000)
    for v in vertices[::step]:
        radii.append(math.hypot(v[0] - cx, v[1] - cy))
    if not radii:
        return None
    r_max, r_min = max(radii), min(radii)
    if r_max - r_min < r_max * 0.04:
        return None
    return 32


def _parse_stl(content: bytes) -> list[tuple[float, float, float]]:
    if content[:5].lower().startswith(b"solid") and b"facet" in content[:800].lower():
        return _parse_stl_ascii(content.decode("utf-8", errors="ignore"))
    return _parse_stl_binary(content)


def _parse_stl_ascii(text: str) -> list[tuple[float, float, float]]:
    verts: list[tuple[float, float, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("vertex"):
            parts = line.split()
            if len(parts) >= 4:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return verts


def _parse_stl_binary(content: bytes) -> list[tuple[float, float, float]]:
    if len(content) < 84:
        return _parse_stl_ascii(content.decode("utf-8", errors="ignore"))
    count = struct.unpack("<I", content[80:84])[0]
    verts: list[tuple[float, float, float]] = []
    offset = 84
    for _ in range(count):
        if offset + 50 > len(content):
            break
        tri = struct.unpack("<12fH", content[offset : offset + 50])
        for i in range(3):
            verts.append((tri[i * 3], tri[i * 3 + 1], tri[i * 3 + 2]))
        offset += 50
    return verts


def _parse_obj(content: bytes) -> list[tuple[float, float, float]]:
    verts: list[tuple[float, float, float]] = []
    for line in content.decode("utf-8", errors="ignore").splitlines():
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return verts


def _bounding_box(vertices: list[tuple[float, float, float]]) -> dict[str, float]:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    return {
        "xmin": round(min(xs), 3),
        "xmax": round(max(xs), 3),
        "ymin": round(min(ys), 3),
        "ymax": round(max(ys), 3),
        "zmin": round(min(zs), 3),
        "zmax": round(max(zs), 3),
    }


def _material_from_filename(filename: str) -> str | None:
    name = filename.upper()
    for mat in ("42CRMO", "20CRMNTI", "40CR", "45"):
        if mat in name:
            return mat.replace("CR", "Cr").replace("CRMNTI", "CrMnTi")
    return None


def merge_features(
    parsed: dict[str, Any],
    *,
    material: str | None = None,
    teeth_z: int | None = None,
    module_m: float | None = None,
    heat_treatment: str | None = None,
    part_type: str | None = None,
) -> dict[str, Any]:
    out = dict(parsed)
    out["material"] = material or parsed.get("material_hint") or "45钢"

    if part_type:
        out["part_type"] = part_type
        out["shape_hint"] = (parsed.get("shape_hint") or "") + "（用户指定类型覆盖）"

    if teeth_z and out.get("part_type") == "齿轮":
        out["teeth_z"] = int(teeth_z)
        od = parsed.get("outer_diameter_mm") or 0
        if od and not module_m:
            out["module_m"] = round(od / (int(teeth_z) + 2), 2)
    if module_m:
        out["module_m"] = float(module_m)
    if heat_treatment:
        out["heat_treatment"] = heat_treatment

    return out
