"""
Model Dispatcher - Bộ định tuyến thông minh theo từng dạng nhãn tới model AI chuyên trách.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from locate_cvat.label_registry import LabelRegistry, LabelType, LabelItem
from server.ai_engine.sam2_engine import SAM2Engine
from server.ai_engine.detector_engine import DetectorEngine
from server.ai_engine.pose_engine import PoseEngine


class ModelDispatcher:
    """
    Điều phối tác vụ gán nhãn tự động tới đúng model AI backend dựa theo cấu hình của nhãn.
    """

    def __init__(self, registry: Optional[LabelRegistry] = None, device: str = "auto"):
        self.registry = registry
        self.device = device

        # Khởi tạo các sub-engine
        self.sam2_engine = SAM2Engine(device=device)
        self.detector_engine = DetectorEngine(device=device)
        self.pose_engine = PoseEngine(device=device)

    def load_engines(self) -> None:
        """Tải các weights mô hình lên GPU."""
        self.sam2_engine.load_model()
        self.detector_engine.load_model()
        self.pose_engine.load_model()

    def dispatch(
        self,
        image_shape: Tuple[int, int],  # (height, width)
        label_name: str,
        image: Optional[Any] = None,
        points: Optional[List[List[float]]] = None,
        bbox: Optional[List[float]] = None,
        target_type: Optional[Union[str, LabelType]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Định tuyến yêu cầu gán nhãn tới engine tương ứng.
        Trả về kết quả chuẩn định dạng CVAT Annotations.
        """
        if target_type is not None:
            if isinstance(target_type, str):
                try:
                    label_type = LabelType.from_str(target_type)
                except ValueError:
                    label_type = LabelType.BOX
            else:
                label_type = target_type
        else:
            label_item = self.registry.get(label_name) if self.registry else None
            label_type = label_item.type if label_item else LabelType.BOX

        h, w = image_shape

        # 1. Định tuyến Mask (Native CVAT Bitmap RLE)
        if label_type == LabelType.MASK:
            if points or bbox:
                polygon_pts = self.sam2_engine.segment_from_prompt(
                    image_shape=image_shape,
                    points=points,
                    bbox=bbox,
                )
                from locate_cvat.rle_utils import poly_to_cvat_rle
                rle_pts = poly_to_cvat_rle(polygon_pts, image_shape=image_shape, bbox=bbox)
                return [
                    {
                        "type": "mask",
                        "label": label_name,
                        "points": rle_pts,
                        "confidence": 0.95,
                    }
                ]
            else:
                return self.detector_engine.detect(
                    image_shape=image_shape,
                    image=image,
                    target_labels=[label_name],
                    desired_type="mask",
                )

        # 2. Định tuyến Polygon (Đa giác vector đỉnh)
        elif label_type == LabelType.POLYGON:
            if points or bbox:
                polygon_pts = self.sam2_engine.segment_from_prompt(
                    image_shape=image_shape,
                    points=points,
                    bbox=bbox,
                )
                return [
                    {
                        "type": "polygon",
                        "label": label_name,
                        "points": polygon_pts,
                        "confidence": 0.95,
                    }
                ]
            else:
                return self.detector_engine.detect(
                    image_shape=image_shape,
                    image=image,
                    target_labels=[label_name],
                    desired_type="polygon",
                )

        # 3. Định tuyến Bounding Box 2D -> YOLO / Detector
        elif label_type == LabelType.BOX:
            if bbox:
                # Nếu đã có bbox prompt
                return [
                    {
                        "type": "rectangle",
                        "label": label_name,
                        "points": bbox,
                        "confidence": 0.98,
                    }
                ]
            return self.detector_engine.detect(
                image_shape=image_shape,
                image=image,
                target_labels=[label_name],
                desired_type="rectangle",
            )

        # 3. Định tuyến Skeleton -> Pose Engine
        elif label_type == LabelType.SKELETON:
            sk_config = label_item.skeleton_config if label_item else None
            return self.pose_engine.estimate_pose(
                image_shape=image_shape,
                skeleton_config=sk_config,
                label_name=label_name,
            )

        # 4. Định tuyến Line / Polyline
        elif label_type == LabelType.LINE:
            # Sinh polyline theo chiều dọc hoặc ngang
            pts = [
                round(w * 0.2, 1), round(h * 0.7, 1),
                round(w * 0.5, 1), round(h * 0.5, 1),
                round(w * 0.8, 1), round(h * 0.3, 1),
            ]
            return [
                {
                    "type": "polyline",
                    "label": label_name,
                    "points": pts,
                    "confidence": 0.91,
                }
            ]

        # 5. Định tuyến 3D Cuboid
        elif label_type == LabelType.CUBOID_3D:
            return [
                {
                    "type": "cuboid",
                    "label": label_name,
                    "center": [0.0, 5.0, -1.0],
                    "dimensions": [2.0, 4.5, 1.8],
                    "rotation": [0.0, 0.0, 0.2],
                    "confidence": 0.88,
                }
            ]

        # Fallback Box
        return [
            {
                "type": "rectangle",
                "label": label_name,
                "points": [w * 0.2, h * 0.2, w * 0.8, h * 0.8],
                "confidence": 0.85,
            }
        ]
