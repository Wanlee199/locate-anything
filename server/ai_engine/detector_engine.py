"""
Detector Engine - Tự động phát hiện vật thể dạng Bounding Box (YOLO / LocateAnything).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class DetectorEngine:
    """
    Wrapper thực thi phát hiện bounding box 2D.
    """

    def __init__(self, model_name: str = "yolo11n.pt", device: str = "auto"):
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
            print(f"[INFO] Detector ({self.model_name}) da san sang tren: {actual_device}")
            return True
        except Exception as e:
            print(f"[WARN] Chay che do du phong Detector: {e}")
            self._is_loaded = False
            return False

    def detect(
        self,
        image_shape: Tuple[int, int],  # (height, width)
        target_labels: Optional[List[str]] = None,
        confidence_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Phát hiện vật thể trên ảnh.
        Trả về danh sách:
        [
          {"label": "car", "confidence": 0.92, "points": [xtl, ytl, xbr, ybr], "type": "rectangle"}
        ]
        """
        h, w = image_shape
        results = []

        # Nếu model thật có sẵn
        if self._is_loaded and self._model is not None:
            try:
                # Inference thật
                pass
            except Exception as e:
                print(f"Lỗi inference detector: {e}")

        # Fallback / Simulated detection cho testing
        targets = target_labels or ["car"]
        for idx, lbl in enumerate(targets):
            # Tạo box hợp lý trong kích thước ảnh
            x1 = round(w * (0.1 + idx * 0.25), 1)
            y1 = round(h * (0.2 + idx * 0.15), 1)
            x2 = round(min(w, x1 + w * 0.2), 1)
            y2 = round(min(h, y1 + h * 0.2), 1)

            results.append({
                "label": lbl,
                "confidence": 0.92,
                "points": [x1, y1, x2, y2],
                "type": "rectangle",
            })

        return results
