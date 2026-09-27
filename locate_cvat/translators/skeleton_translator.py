"""
COCO Keypoints Translator for Skeleton and Pose Estimation.
Hỗ trợ định dạng COCO Keypoints chuẩn mực cho CVAT và các thư viện Pose Estimation (YOLO-Pose, OpenPose, MMPose).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from locate_cvat.label_registry import LabelRegistry, LabelType


class SkeletonCOCOTranslator:
    """
    Chuyển đổi dữ liệu nhãn khung xương (Skeleton / Pose) sang định dạng chuẩn COCO Keypoints.
    """

    def __init__(self, registry: LabelRegistry):
        self.registry = registry
        self._categories: List[Dict[str, Any]] = []
        self._cat_name_to_id: Dict[str, int] = {}
        self._build_keypoints_categories()

    def _build_keypoints_categories(self) -> None:
        cat_id = 1
        skeleton_labels = self.registry.filter_by_type(LabelType.SKELETON)
        for lbl in skeleton_labels:
            if not lbl.skeleton_config:
                continue

            node_names = [n.name for n in lbl.skeleton_config.nodes]
            id_to_coco_index = {node.id: idx + 1 for idx, node in enumerate(lbl.skeleton_config.nodes)}

            # COCO Keypoints quy định edges theo 1-based index
            coco_skeleton_edges = [
                [id_to_coco_index[u], id_to_coco_index[v]]
                for u, v in lbl.skeleton_config.edges
                if u in id_to_coco_index and v in id_to_coco_index
            ]

            self._cat_name_to_id[lbl.name] = cat_id
            self._categories.append({
                "id": cat_id,
                "name": lbl.name,
                "supercategory": "skeleton",
                "keypoints": node_names,
                "skeleton": coco_skeleton_edges,
                "color": lbl.color,
            })
            cat_id += 1

    def create_skeleton_annotation(
        self,
        annotation_id: int,
        image_id: int,
        label_name: str,
        keypoints_coords: List[Tuple[float, float, int]],  # (x, y, visibility)
        bbox: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Tạo một record annotation COCO Keypoints.
        - keypoints_coords: danh sách (x, y, v) với v:
            0: Chưa gán nhãn
            1: Bị che khuất (occluded)
            2: Nhìn thấy rõ (visible)
        - bbox: Tự động tính từ keypoints nếu không truyền vào.
        """
        if label_name not in self._cat_name_to_id:
            raise ValueError(f"Nhãn skeleton '{label_name}' không có trong danh mục")

        flat_keypoints: List[Union[float, int]] = []
        valid_x = []
        valid_y = []
        num_valid = 0

        for x, y, v in keypoints_coords:
            flat_keypoints.extend([round(float(x), 2), round(float(y), 2), int(v)])
            if v > 0:
                valid_x.append(x)
                valid_y.append(y)
                num_valid += 1

        # Tự động tính bounding box bao quanh các khớp nếu chưa có
        if bbox is None and valid_x and valid_y:
            min_x = min(valid_x)
            min_y = min(valid_y)
            max_x = max(valid_x)
            max_y = max(valid_y)
            width = max_x - min_x
            height = max_y - min_y
            bbox = [round(min_x, 2), round(min_y, 2), round(width, 2), round(height, 2)]
            area = round(width * height, 2)
        elif bbox is not None:
            area = round(bbox[2] * bbox[3], 2)
        else:
            bbox = [0.0, 0.0, 0.0, 0.0]
            area = 0.0

        return {
            "id": annotation_id,
            "image_id": image_id,
            "category_id": self._cat_name_to_id[label_name],
            "keypoints": flat_keypoints,
            "num_keypoints": num_valid,
            "bbox": bbox,
            "area": area,
            "iscrowd": 0,
            "segmentation": [],
        }

    def export_coco_keypoints(
        self,
        images_info: List[Dict[str, Any]],
        annotations_list: List[Dict[str, Any]],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Xuất tài liệu COCO Keypoints đầy đủ."""
        return {
            "info": {
                "description": description or f"{self.registry.project_name} - Skeleton Annotations",
                "version": self.registry.version,
                "year": datetime.now().year,
                "contributor": "CVAT Universal Skeleton Translator",
                "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "licenses": [{"id": 1, "name": "Proprietary", "url": ""}],
            "images": images_info,
            "annotations": annotations_list,
            "categories": self._categories,
        }

    def save_to_file(self, data: Dict[str, Any], filepath: Union[str, Path]) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
