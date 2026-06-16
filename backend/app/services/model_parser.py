"""三维模型（STL/OBJ/STEP/IGES）解析 — 网格估算或 CAD 精确几何。"""

from __future__ import annotations

import math
import struct
import statistics
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from app.services.model_parser_cad import cad_formats_available, parse_cad_file

CAD_EXT = {".step", ".stp", ".iges", ".igs"}
MESH_EXT = {".stl", ".obj", ".ply", ".3mf"}


def supported_formats() -> dict[str, Any]:
    return {
        "mesh": sorted(MESH_EXT),
        "cad": sorted(CAD_EXT),
        "cad_available": cad_formats_available(),
        "recommended": "STEP (.step/.stp) — 尺寸与孔径最准确",
        "notes": [
            "STL/OBJ 仅为三角网格，无单位、孔径为估算",
            "STEP/IGES 为 CAD 实体，可精确读取包围盒与圆柱孔",
        ],
    }


def parse_model_file(content: bytes, filename: str, unit_scale: float | None = None) -> dict[str, Any]:
    ext = Path(filename).suffix.lower()
    if ext in CAD_EXT:
        return parse_cad_file(content, filename)
    if ext == ".3mf":
        return _parse_3mf(content, filename, unit_scale)
    if ext in (".stl", ".obj", ".ply"):
        return _parse_mesh(content, filename, ext, unit_scale)
    raise ValueError(
        f"暂不支持 {ext} 格式。可用: {', '.join(sorted(MESH_EXT | CAD_EXT))}"
    )


def _parse_mesh(content: bytes, filename: str, ext: str, unit_scale: float | None) -> dict[str, Any]:
    if ext == ".stl":
        vertices = _parse_stl(content)
    elif ext == ".obj":
        vertices = _parse_obj(content)
    elif ext == ".ply":
        vertices = _parse_ply(content)
    else:
        raise ValueError(f"不支持的网格格式 {ext}")

    if len(vertices) < 3:
        raise ValueError("模型顶点数过少，无法分析")

    bbox_raw = _bounding_box(vertices)
    dims_raw = {
        "length_x": bbox_raw["xmax"] - bbox_raw["xmin"],
        "length_y": bbox_raw["ymax"] - bbox_raw["ymin"],
        "length_z": bbox_raw["zmax"] - bbox_raw["zmin"],
    }

    if unit_scale is not None and unit_scale > 0:
        scale = float(unit_scale)
        unit_note = f"用户指定换算 ×{scale}"
    else:
        scale, unit_note = _infer_unit_scale(dims_raw)

    if abs(scale - 1.0) > 1e-9:
        vertices = [(v[0] * scale, v[1] * scale, v[2] * scale) for v in vertices]

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
        "format_family": "mesh",
        "vertex_count": len(vertices),
        "triangle_count": len(vertices) // 3,
        "bbox": bbox,
        "dimensions_mm": dims,
        "size_x_mm": dims["length_x"],
        "size_y_mm": dims["length_y"],
        "size_z_mm": dims["length_z"],
        "unit_scale_applied": scale,
        "unit_note": unit_note,
        "dimension_note": (
            "尺寸来自 STL/OBJ 三角网格包围盒（无精确特征）。"
            "建议导出 STEP 以获得准确长宽高与孔径；若与 CAD 不符请选择正确单位。"
        ),
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
        result["hole_is_estimated"] = geo.get("hole_is_estimated", True)
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


def _parse_3mf(content: bytes, filename: str, unit_scale: float | None) -> dict[str, Any]:
    """3MF 含 unit 元数据，比 STL 更可靠。"""
    scale = 1.0
    unit_note = "3MF 默认 mm"
    try:
        with zipfile.ZipFile(BytesIO(content)) as zf:
            xml_name = next((n for n in zf.namelist() if n.endswith(".model")), None)
            if xml_name:
                xml_text = zf.read(xml_name).decode("utf-8", errors="ignore")
                if 'unit="centimeter"' in xml_text or "unit='centimeter'" in xml_text:
                    scale = 10.0
                    unit_note = "3MF 单位为 cm，已×10 为 mm"
                elif 'unit="meter"' in xml_text:
                    scale = 1000.0
                    unit_note = "3MF 单位为 m，已×1000 为 mm"
    except Exception:
        pass
    if unit_scale and unit_scale > 0:
        scale = float(unit_scale)
        unit_note = f"用户指定换算 ×{scale}"

    vertices = _parse_3mf_mesh_vertices(content)
    if len(vertices) < 3:
        raise ValueError("3MF 文件中未找到有效网格顶点")

    if abs(scale - 1.0) > 1e-9:
        vertices = [(v[0] * scale, v[1] * scale, v[2] * scale) for v in vertices]

    return _build_mesh_result(vertices, filename, ".3mf", 1.0, unit_note)


def _parse_3mf_mesh_vertices(content: bytes) -> list[tuple[float, float, float]]:
    """从 3MF 提取 vertex 坐标（简化解析）。"""
    import re

    verts: list[tuple[float, float, float]] = []
    try:
        with zipfile.ZipFile(BytesIO(content)) as zf:
            for name in zf.namelist():
                if not name.endswith(".model"):
                    continue
                text = zf.read(name).decode("utf-8", errors="ignore")
                for m in re.finditer(r'<vertex\s+x="([^"]+)"\s+y="([^"]+)"\s+z="([^"]+)"', text):
                    verts.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
    except Exception:
        pass
    return verts


def _build_mesh_result(
    vertices: list[tuple[float, float, float]],
    filename: str,
    ext: str,
    scale: float,
    unit_note: str,
) -> dict[str, Any]:
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
        "format_family": "mesh",
        "vertex_count": len(vertices),
        "triangle_count": len(vertices) // 3,
        "bbox": bbox,
        "dimensions_mm": dims,
        "size_x_mm": dims["length_x"],
        "size_y_mm": dims["length_y"],
        "size_z_mm": dims["length_z"],
        "unit_scale_applied": scale,
        "unit_note": unit_note,
        "dimension_note": (
            "网格模型尺寸为估算。推荐从 CAD 另存 STEP (.step) 上传以获取精确数据。"
        ),
        "part_type": part_type,
        "shape_hint": geo["shape_hint"],
        "flat_face_ratio": geo["flat_face_ratio"],
        "recognition_confidence": geo.get("recognition_confidence", 0.75),
        "material_hint": _material_from_filename(filename),
    }
    _attach_type_dims(result, geo, part_type)
    return result


def _attach_type_dims(result: dict[str, Any], geo: dict[str, Any], part_type: str) -> None:
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
        result["hole_is_estimated"] = geo.get("hole_is_estimated", True)
    elif part_type in ("块体件", "箱体件", "曲面件"):
        result["length_mm"] = geo.get("length_mm")
        result["width_mm"] = geo.get("width_mm")
        result["height_mm"] = geo.get("height_mm")
    elif part_type == "轴类":
        result["length_mm"] = geo.get("length_mm")
        result["diameter_mm"] = geo.get("diameter_mm")


def _infer_unit_scale(dims: dict[str, float]) -> tuple[float, str]:
    """STL 无单位：按包围盒量级推断 m / cm / inch / mm。"""
    lx, ly, lz = dims["length_x"], dims["length_y"], dims["length_z"]
    mx = max(lx, ly, lz)
    if mx <= 0:
        return 1.0, "假定 mm"

    if mx < 0.2:
        return 1000.0, "检测到米(m)单位，已×1000 换算为 mm"
    if mx < 2.0:
        return 1000.0, "检测到米(m)或小尺度单位，已×1000 换算为 mm"

    scaled_mx = mx * 10
    if mx < 25 and 12 <= scaled_mx <= 800:
        return 10.0, "检测到厘米(cm)单位，已×10 换算为 mm"

    if mx < 15 and abs(mx * 25.4 - round(mx * 25.4)) < 2:
        inch_mm = mx * 25.4
        if 10 <= inch_mm <= 800:
            return 25.4, "检测到英寸(in)单位，已×25.4 换算为 mm"

    if mx > 8000:
        return 0.001, "检测到超大数值，已×0.001 换算为 mm"

    return 1.0, "按 mm 解读（若尺寸偏小，请选手动单位 cm）"


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

    hole_d, hole_plane, hole_est = _detect_cylindrical_hole(sample, bbox, lx, ly, lz)
    if hole_d and flat_ratio >= 0.15:
        conf = 0.82 if hole_est else 0.88
        hole_txt = f"约 Ø{hole_d} mm（估算）" if hole_est else f"Ø{hole_d} mm"
        return {
            "part_type": "块体（带圆柱孔）",
            "shape_hint": f"块体+圆柱孔特征，{hole_plane}，孔径{hole_txt}",
            "flat_face_ratio": round(flat_ratio, 3),
            "recognition_confidence": conf,
            "length_mm": length,
            "width_mm": width,
            "height_mm": height,
            "hole_diameter_mm": hole_d,
            "hole_is_estimated": hole_est,
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
) -> tuple[float | None, str, bool]:
    """检测块体上的圆柱孔，返回 (孔径mm, 轴线说明, 是否仅为估算)。"""
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

    if best_d is None:
        return None, "", True
    return best_d, best_label, True


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


def _parse_ply(content: bytes) -> list[tuple[float, float, float]]:
    text = content.decode("utf-8", errors="ignore")
    if "end_header" not in text.lower():
        return []
    body = text.split("end_header", 1)[-1]
    verts: list[tuple[float, float, float]] = []
    for line in body.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                verts.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError:
                continue
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
    unit_scale: float | None = None,
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
