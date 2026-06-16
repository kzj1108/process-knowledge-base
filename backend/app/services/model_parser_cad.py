"""STEP / IGES 精确几何解析（需 Open CASCADE，通过 cadquery-ocp）。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

_CAD_AVAILABLE: bool | None = None


def cad_formats_available() -> bool:
    global _CAD_AVAILABLE
    if _CAD_AVAILABLE is None:
        try:
            import cadquery  # noqa: F401
            from OCP.GeomAbs import GeomAbs_Cylinder  # noqa: F401

            _CAD_AVAILABLE = True
        except ImportError:
            _CAD_AVAILABLE = False
    return _CAD_AVAILABLE


def parse_cad_file(content: bytes, filename: str) -> dict[str, Any]:
    if not cad_formats_available():
        raise ValueError(
            "当前运行环境未安装 CAD 解析库，无法读取 STEP/IGES。"
            "请在 backend 目录执行: .venv\\Scripts\\pip install -r requirements-cad.txt"
            " 然后重启 启动.bat"
        )

    import cadquery as cq
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    ext = Path(filename).suffix.lower()
    fd, path = tempfile.mkstemp(suffix=ext or ".step")
    try:
        os.write(fd, content)
        os.close(fd)
        if ext in (".step", ".stp"):
            shape = cq.importers.importStep(path)
        elif ext in (".iges", ".igs"):
            if not hasattr(cq.importers, "importIges"):
                raise ValueError("当前 cadquery 版本不支持 IGES，请改用 STEP 格式")
            shape = cq.importers.importIges(path)
        else:
            raise ValueError(f"不支持的 CAD 格式 {ext}")

        solid = shape.val()
        bb = solid.BoundingBox()
        lx = round(bb.xlen, 3)
        ly = round(bb.ylen, 3)
        lz = round(bb.zlen, 3)

        bbox = {
            "xmin": round(bb.xmin, 3),
            "xmax": round(bb.xmax, 3),
            "ymin": round(bb.ymin, 3),
            "ymax": round(bb.ymax, 3),
            "zmin": round(bb.zmin, 3),
            "zmax": round(bb.zmax, 3),
        }
        dims = {"length_x": lx, "length_y": ly, "length_z": lz}

        holes = _extract_cylindrical_faces(solid.wrapped, BRepAdaptor_Surface, GeomAbs_Cylinder, TopAbs_FACE, TopExp_Explorer)
        sorted_dims = sorted([lx, ly, lz], reverse=True)

        if holes:
            main_hole = max(holes, key=lambda h: h["diameter_mm"])
            part_type = "块体（带圆柱孔）"
            shape_hint = (
                f"CAD 精确模型：检测到 {len(holes)} 个圆柱面，"
                f"主孔 Ø{main_hole['diameter_mm']} mm（STEP/IGES 实体解析）"
            )
            conf = 0.94
        else:
            part_type = "块体件"
            shape_hint = "CAD 精确模型：包围盒尺寸来自 STEP/IGES 实体（单位 mm）"
            conf = 0.92
            main_hole = None

        result: dict[str, Any] = {
            "filename": filename,
            "format": ext.lstrip("."),
            "format_family": "cad_brep",
            "vertex_count": None,
            "triangle_count": None,
            "bbox": bbox,
            "dimensions_mm": dims,
            "size_x_mm": lx,
            "size_y_mm": ly,
            "size_z_mm": lz,
            "length_mm": sorted_dims[0],
            "width_mm": sorted_dims[1],
            "height_mm": sorted_dims[2],
            "unit_scale_applied": 1.0,
            "unit_note": "STEP/IGES 实体模型，尺寸为 CAD 精确值（mm）",
            "dimension_note": "尺寸来自 B-Rep 实体包围盒与圆柱面解析，精度高于 STL 网格估算。",
            "part_type": part_type,
            "shape_hint": shape_hint,
            "flat_face_ratio": None,
            "recognition_confidence": conf,
            "material_hint": None,
            "cad_holes": holes,
        }
        if main_hole:
            result["hole_diameter_mm"] = main_hole["diameter_mm"]
            result["hole_is_estimated"] = False
        return result
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _extract_cylindrical_faces(
    shape: Any,
    BRepAdaptor_Surface: Any,
    GeomAbs_Cylinder: Any,
    TopAbs_FACE: Any,
    TopExp_Explorer: Any,
) -> list[dict[str, float]]:
    holes: list[dict[str, float]] = []
    seen: set[float] = set()
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        try:
            surf = BRepAdaptor_Surface(face)
            if surf.GetType() == GeomAbs_Cylinder:
                cyl = surf.Cylinder()
                diameter = round(2 * cyl.Radius(), 3)
                if diameter > 0.1 and diameter not in seen:
                    seen.add(diameter)
                    holes.append({"diameter_mm": diameter})
        except Exception:
            pass
        exp.Next()
    return sorted(holes, key=lambda h: h["diameter_mm"], reverse=True)
