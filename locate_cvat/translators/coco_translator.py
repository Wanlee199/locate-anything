"""
COCO 1.0 Format Translator for Bounding Boxes and Polygons.
Tương thích hoàn toàn với chuẩn nhập/xuất COCO của CVAT.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from locate_cvat.label_registry import LabelRegistry, LabelType


def calculate_polygon_area(polygon: List[float]) -> float:
    """Tính diện tích đa giác theo công thức Shoelace (Gauss Area)."""
    if len(polygon) < 6:
        return 0.0
    x = polygon[0::2]
    y = polygon[1::2]
    n = len(x)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += x[i] * y[j]
        area -= x[j] * y[i]
    return abs(area) / 2.0


class COCOTranslator:
    """
    Chuyển đổi dữ liệu gán nhãn dạng Box và Polygon sang định dạng chuẩn CVAT COCO 1.0.
    """

    def __init__(self, registry: LabelRegistry):
        self.registry = registry
        self._cat_name_to_id: Dict[str, int] = {}
        self._categories: List[Dict[str, Any]] = []
        self._build_categories()

    def _build_categories(self) -> None:
        """Xây dựng bảng categories chuẩn COCO từ LabelRegistry."""
        cat_id = 1
        for lbl in self.registry.labels:
            if lbl.type in (LabelType.BOX, LabelType.POLYGON, LabelType.MASK):
                self._cat_name_to_id[lbl.name] = cat_id
                self._categories.append({
                    "id": cat_id,
                    "name": lbl.name,
                    "supercategory": lbl.type.value,
                    "color": lbl.color,
                })
                cat_id += 1

    def export_coco(
        self,
        images_info: List[Dict[str, Any]],
        annotations_list: List[Dict[str, Any]],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tạo dict cấu trúc COCO 1.0 đầy đủ các trường:
        info, licenses, images, annotations, categories.
        """
        coco_doc = {
            "info": {
                "description": description or self.registry.description or self.registry.project_name,
                "version": self.registry.version,
                "year": datetime.now().year,
                "contributor": "CVAT Universal Label Pipeline",
                "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "licenses": [
                {
                    "id": 1,
                    "name": "Proprietary",
                    "url": "",
                }
            ],
            "images": images_info,
            "annotations": annotations_list,
            "categories": self._categories,
        }
        return coco_doc

    def create_annotation(
        self,
        annotation_id: int,
        image_id: int,
        label_name: str,
        bbox: Optional[List[float]] = None,
        segmentation: Optional[List[List[float]]] = None,
        score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Tạo một record annotation COCO chuẩn.
        - bbox: [x, y, width, height]
        - segmentation: [[x1, y1, x2, y2, ...]]
        """
        if label_name not in self._cat_name_to_id:
            raise ValueError(f"Nhãn '{label_name}' không tồn tại trong danh mục COCO của Registry")

        category_id = self._cat_name_to_id[label_name]

        # Tính toán diện tích
        if segmentation and len(segmentation) > 0 and len(segmentation[0]) >= 6:
            area = calculate_polygon_area(segmentation[0])
        elif bbox and len(bbox) == 4:
            area = float(bbox[2] * bbox[3])
        else:
            area = 0.0

        ann: Dict[str, Any] = {
            "id": annotation_id,
            "image_id": image_id,
            "category_id": category_id,
            "segmentation": segmentation or ([] if bbox is None else []),
            "area": round(area, 2),
            "bbox": bbox or [],
            "iscrowd": 0,
        }

        if score is not None:
            ann["score"] = round(float(score), 4)

        return ann

    def save_to_file(self, data: Dict[str, Any], filepath: Union[str, Path]) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
