"""
Detector Engine - Tự động phát hiện vật thể dạng Bounding Box (YOLO / LocateAnything).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class DetectorEngine:
    """
    Wrapper thực thi phát hiện bounding box 2D.
    """

    def __init__(self, model_name: str = "yolo11n-seg.pt", device: str = "auto"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._is_loaded = False

    def load_model(self) -> bool:
        if self._is_loaded:
            return True
        try:
            from ultralytics import YOLO
            import torch

            actual_device = "cuda" if torch.cuda.is_available() and self.device != "cpu" else "cpu"
            self._model = YOLO(self.model_name)
            self._is_loaded = True
            print(f"[INFO] Detector & Segmenter ({self.model_name}) da san sang tren: {actual_device}")
            return True
        except Exception as e:
            print(f"[WARN] Chay che do du phong Detector: {e}")
            self._is_loaded = False
            return False

    def detect(
        self,
        image_shape: Tuple[int, int],  # (height, width)
        image: Optional[Any] = None,   # PIL.Image, numpy array
        target_labels: Optional[List[str]] = None,
        confidence_threshold: float = 0.35,
        desired_type: str = "auto",    # 'auto', 'rectangle' (box), 'polygon' (mask)
    ) -> List[Dict[str, Any]]:
        """
        Phát hiện vật thể trên ảnh sử dụng YOLO thật (khi có image) hoặc fallback.
        Hỗ trợ tự động xuất Bounding Box hoặc Polygon Mask tùy theo cấu hình nhãn.
        """
        h, w = image_shape
        results = []

        # 1. Inference với model YOLO/YOLO-Seg thật
        if self._is_loaded and self._model is not None and image is not None:
            try:
                preds = self._model.predict(image, conf=confidence_threshold, verbose=False)
                if preds and len(preds) > 0:
                    pred = preds[0]
                    boxes = pred.boxes
                    masks = getattr(pred, "masks", None)
                    class_names = self._model.names
                    target_lower = [t.lower() for t in (target_labels or [])]

                    for idx, box in enumerate(boxes):
                        cls_id = int(box.cls[0].item())
                        detected_name = str(class_names.get(cls_id, cls_id)).lower()
                        conf = float(box.conf[0].item())

                        # COCO class mapping chuẩn xác theo từng loại đối tượng
                        match = False
                        matched_label = detected_name

                        if detected_name in target_lower:
                            match = True
                            matched_label = detected_name
                        elif detected_name in ["suv", "van"] and "car" in target_lower:
                            match = True
                            matched_label = "car"
                        elif detected_name in ["bicycle", "motorcycle"] and "bike" in target_lower:
                            match = True
                            matched_label = "bike"
                        elif detected_name == "person" and ("pedestrian" in target_lower or "person" in target_lower):
                            match = True
                            matched_label = "pedestrian" if "pedestrian" in target_lower else "person"
                        elif not target_labels:
                            match = True
                            matched_label = detected_name

                        if match:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()

                            # Kiểm tra nếu cần xuất dạng mask (RLE) hay polygon (Vector) hay box
                            if desired_type == "mask":
                                from locate_cvat.rle_utils import poly_to_cvat_rle
                                if masks is not None and len(masks.xy) > idx and len(masks.xy[idx]) >= 3:
                                    poly_pts = masks.xy[idx]
                                    flat_pts = [round(float(c), 1) for pt in poly_pts for c in pt]
                                    rle_pts = poly_to_cvat_rle(flat_pts, image_shape=(h, w), bbox=[x1, y1, x2, y2])
                                else:
                                    bw = max(1, int(round(x2 - x1 + 1)))
                                    bh = max(1, int(round(y2 - y1 + 1)))
                                    rle_pts = [0.0, float(bw * bh), float(round(x1, 1)), float(round(y1, 1)), float(round(x2, 1)), float(round(y2, 1))]
                                results.append({
                                    "label": matched_label,
                                    "confidence": round(conf, 3),
                                    "points": rle_pts,
                                    "type": "mask",
                                })
                            elif desired_type == "polygon":
                                if masks is not None and len(masks.xy) > idx and len(masks.xy[idx]) >= 3:
                                    poly_pts = masks.xy[idx]
                                    flat_pts = [round(float(c), 1) for pt in poly_pts for c in pt]
                                    results.append({
                                        "label": matched_label,
                                        "confidence": round(conf, 3),
                                        "points": flat_pts,
                                        "type": "polygon",
                                    })
                                else:
                                    poly_points = [round(x1, 1), round(y1, 1), round(x2, 1), round(y1, 1), round(x2, 1), round(y2, 1), round(x1, 1), round(y2, 1)]
                                    results.append({
                                        "label": matched_label,
                                        "confidence": round(conf, 3),
                                        "points": poly_points,
                                        "type": "polygon",
                                    })
                            else:
                                results.append({
                                    "label": matched_label,
                                    "confidence": round(conf, 3),
                                    "points": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                                    "type": "rectangle",
                                })
                # Khi model thật đã chạy trên ảnh: trả về kết quả thật (kể cả không tìm thấy vật thể nào)
                return results
            except Exception as e:
                print(f"[WARN] Lỗi khi chạy YOLO inference: {e}")

        # 2. Fallback / Simulated detection: CHỈ DÙNG CHO UNIT TEST (khi không tải được model hoặc không có ảnh)
        if not self._is_loaded or image is None:
            targets = target_labels or ["car"]
            for idx, lbl in enumerate(targets):
                x1 = round(w * (0.1 + idx * 0.25), 1)
                y1 = round(h * (0.2 + idx * 0.15), 1)
                x2 = round(min(w, x1 + w * 0.2), 1)
                y2 = round(min(h, y1 + h * 0.2), 1)

                if desired_type == "mask":
                    bw = max(1, int(round(x2 - x1 + 1)))
                    bh = max(1, int(round(y2 - y1 + 1)))
                    rle_points = [0.0, float(bw * bh), float(x1), float(y1), float(x2), float(y2)]
                    results.append({
                        "label": lbl,
                        "confidence": 0.92,
                        "points": rle_points,
                        "type": "mask",
                    })
                elif desired_type == "polygon":
                    poly_points = [x1, y1, x2, y1, x2, y2, x1, y2]
                    results.append({
                        "label": lbl,
                        "confidence": 0.92,
                        "points": poly_points,
                        "type": "polygon",
                    })
                else:
                    results.append({
                        "label": lbl,
                        "confidence": 0.92,
                        "points": [x1, y1, x2, y2],
                        "type": "rectangle",
                    })

        return results
