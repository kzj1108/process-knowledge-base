"""三维模型（STL/OBJ）轻量解析 — 提取包围盒与齿轮几何特征，纯 Python 无外部 CAD 依赖。"""

from __future__ import annotations

import math
import struct
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
    outer_diameter = round(max(dims["length_x"], dims["length_y"]), 3)
    face_width = round(min(dims["length_x"], dims["length_y"], dims["length_z"]), 3)
    if face_width == outer_diameter:
        face_width = round(min(dims.values()), 3)

    part_type = _guess_part_type(filename, outer_diameter, face_width)
    teeth_z = _estimate_teeth(vertices, outer_diameter, part_type)
    module_m = round(outer_diameter / (teeth_z + 2), 2) if teeth_z else None

    return {
        "filename": filename,
        "format": ext.lstrip("."),
        "vertex_count": len(vertices),
        "triangle_count": len(vertices) // 3,
        "bbox": bbox,
        "dimensions_mm": dims,
        "outer_diameter_mm": outer_diameter,
        "face_width_mm": face_width,
        "part_type": part_type,
        "teeth_z": teeth_z,
        "module_m": module_m,
        "material_hint": _material_from_filename(filename),
    }


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


def _guess_part_type(filename: str, outer_d: float, face_w: float) -> str:
    name = filename.lower()
    if any(k in name for k in ("gear", "chi", "齿轮", "gearwheel")):
        return "齿轮"
    if any(k in name for k in ("shaft", "轴")):
        return "轴类"
    ratio = face_w / outer_d if outer_d else 1
    if 0.15 <= ratio <= 0.8 and outer_d > 20:
        return "齿轮"
    return "回转体"


def _estimate_teeth(vertices: list[tuple[float, float, float]], outer_d: float, part_type: str) -> int | None:
    if part_type != "齿轮" or outer_d < 10:
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
    r_max = max(radii)
    r_min = min(radii)
    if r_max - r_min < r_max * 0.02:
        return 32
    peaks = 0
    threshold = r_min + (r_max - r_min) * 0.6
    window = max(3, len(radii) // 80)
    for i in range(window, len(radii) - window):
        local = radii[i - window : i + window]
        if radii[i] == max(local) and radii[i] >= threshold:
            if i == 0 or radii[i] > radii[i - 1]:
                peaks += 1
    teeth = max(12, min(120, peaks // 2 if peaks > 4 else 32))
    return teeth


def _material_from_filename(filename: str) -> str | None:
    name = filename.upper()
    for mat in ("42CRMO", "20CRMNTI", "40CR", "45"):
        if mat.replace("CR", "Cr") in name or mat in name:
            return mat.replace("CR", "Cr").replace("CRMNTI", "CrMnTi")
    return None


def merge_features(
    parsed: dict[str, Any],
    *,
    material: str | None = None,
    teeth_z: int | None = None,
    module_m: float | None = None,
    heat_treatment: str | None = None,
) -> dict[str, Any]:
    """用户表单参数覆盖自动识别结果。"""
    out = dict(parsed)
    if material:
        out["material"] = material
    elif parsed.get("material_hint"):
        out["material"] = parsed["material_hint"]
    else:
        out["material"] = "42CrMo"

    z = teeth_z or parsed.get("teeth_z")
    if z:
        out["teeth_z"] = int(z)
        od = parsed.get("outer_diameter_mm") or 0
        if od and not module_m:
            out["module_m"] = round(od / (int(z) + 2), 2)
    if module_m:
        out["module_m"] = float(module_m)

    if heat_treatment:
        out["heat_treatment"] = heat_treatment

    out["part_type"] = parsed.get("part_type") or "齿轮"
    return out
