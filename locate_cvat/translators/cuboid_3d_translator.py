"""
Translator for 3D Cuboids and Polylines (Lines).
Hỗ trợ định dạng CVAT XML 1.1 và JSON cho bài toán xe tự hành và LiDAR / Polyline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import xml.etree.ElementTree as ET

from locate_cvat.label_registry import LabelRegistry, LabelType


class CuboidAndPolylineTranslator:
    """
    Quản lý và chuyển đổi dữ liệu gán nhãn 3D Cuboid và Line (Polyline)
    tương thích với định dạng CVAT XML 1.1 và cấu trúc JSON chuẩn.
    """

    def __init__(self, registry: LabelRegistry):
        self.registry = registry

    def create_polyline_item(
        self,
        label_name: str,
        points: List[List[float]],  # [[x1, y1], [x2, y2], ...]
        attributes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Tạo record polyline chuẩn."""
        label_item = self.registry.get(label_name)
        if not label_item or label_item.type != LabelType.LINE:
            raise ValueError(f"Nhãn '{label_name}' không phải loại 'line' trong Registry")

        return {
            "type": "polyline",
            "label": label_name,
            "points": [[round(pt[0], 2), round(pt[1], 2)] for pt in points],
            "attributes": attributes or {},
        }

    def create_cuboid_3d_item(
        self,
        label_name: str,
        center: List[float],      # [x, y, z]
        dimensions: List[float],  # [dx, dy, dz]
        rotation: List[float],    # [roll, pitch, yaw]
        projected_2d_points: Optional[List[List[float]]] = None,  # 8 đỉnh 2D (nếu có)
        attributes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Tạo record 3D Cuboid chuẩn."""
        label_item = self.registry.get(label_name)
        if not label_item or label_item.type != LabelType.CUBOID_3D:
            raise ValueError(f"Nhãn '{label_name}' không phải loại '3d' trong Registry")

        return {
            "type": "cuboid",
            "label": label_name,
            "center": [round(c, 3) for c in center],
            "dimensions": [round(d, 3) for d in dimensions],
            "rotation": [round(r, 3) for r in rotation],
            "projected_2d_points": projected_2d_points or [],
            "attributes": attributes or {},
        }

    def export_cvat_xml(
        self,
        image_name: str,
        image_width: int,
        image_height: int,
        shapes: List[Dict[str, Any]],
        output_filepath: Union[str, Path],
    ) -> str:
        """
        Xuất tài liệu sang định dạng CVAT XML 1.1 chính thống.
        CVAT có thể import file XML này trực tiếp vào task.
        """
        root = ET.Element("annotations")
        version_el = ET.SubElement(root, "version")
        version_el.text = "1.1"

        img_el = ET.SubElement(root, "image")
        img_el.set("id", "0")
        img_el.set("name", image_name)
        img_el.set("width", str(image_width))
        img_el.set("height", str(image_height))

        for shape in shapes:
            shape_type = shape.get("type", "polyline")
            label_name = shape.get("label", "")

            if shape_type == "polyline":
                poly_el = ET.SubElement(img_el, "polyline")
                poly_el.set("label", label_name)
                pts_str = ";".join(f"{pt[0]},{pt[1]}" for pt in shape["points"])
                poly_el.set("points", pts_str)

                for attr_k, attr_v in shape.get("attributes", {}).items():
                    attr_el = ET.SubElement(poly_el, "attribute")
                    attr_el.set("name", attr_k)
                    attr_el.text = str(attr_v)

            elif shape_type == "cuboid":
                cuboid_el = ET.SubElement(img_el, "cuboid")
                cuboid_el.set("label", label_name)
                # Lưu thông tin 3D vào attributes
                c = shape["center"]
                d = shape["dimensions"]
                r = shape["rotation"]
                cuboid_el.set("occluded", "0")

                for attr_name, attr_val in [
                    ("pos_x", c[0]), ("pos_y", c[1]), ("pos_z", c[2]),
                    ("dim_dx", d[0]), ("dim_dy", d[1]), ("dim_dz", d[2]),
                    ("rot_roll", r[0]), ("rot_pitch", r[1]), ("rot_yaw", r[2]),
                ]:
                    attr_el = ET.SubElement(cuboid_el, "attribute")
                    attr_el.set("name", attr_name)
                    attr_el.text = str(attr_val)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(output_filepath, encoding="utf-8", xml_declaration=True)
        return ET.tostring(root, encoding="unicode")
