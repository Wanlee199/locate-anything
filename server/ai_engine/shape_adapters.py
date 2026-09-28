"""
Shape Adapters & Extended Multi-Modal Converters for CVAT.
Cung cấp các bộ chuyển đổi hình thái:
  1. mask_to_polyline: Chuyển dải mask thành đường gấp khúc Polyline tim đường (RDP algorithm / NumPy fallback)
  2. mask_to_ellipse: Fit phương trình elip toán học từ mask contour (cv2 / Image Moments fallback)
  3. classify_tag: Phân loại nhãn toàn cảnh cấp độ ảnh (image-level tagging)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


class ShapeAdapters:
    @staticmethod
    def mask_to_polyline(
        binary_mask: np.ndarray,
        epsilon: float = 2.5,
    ) -> List[float]:
        """
        Chuyển đổi mặt nạ dải đường (lane / curb) thành danh sách tọa độ Polyline
        chuẩn CVAT [x1, y1, x2, y2, ...].
        """
        if binary_mask is None or np.sum(binary_mask) == 0:
            return []

        # 1. Nếu có OpenCV: Dùng Contour + Ramer-Douglas-Peucker (RDP)
        if cv2 is not None:
            mask_u8 = (binary_mask > 0).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_cnt = max(contours, key=cv2.contourArea)
                if len(largest_cnt) >= 2:
                    approx = cv2.approxPolyDP(largest_cnt, epsilon, closed=False)
                    pts = approx.reshape(-1, 2)
                    if len(pts) >= 4:
                        half_len = max(2, len(pts) // 2)
                        pts = pts[:half_len]
                    flat_coords: List[float] = []
                    for p in pts:
                        flat_coords.extend([float(round(p[0], 1)), float(round(p[1], 1))])
                    return flat_coords

        # 2. Bộ xử lý thuần NumPy dự phòng
        ys, xs = np.where(binary_mask > 0)
        if len(xs) < 4:
            return []

        # Trích xuất đường tim bằng cách chia các phân khúc đều nhau
        dy = np.max(ys) - np.min(ys)
        dx = np.max(xs) - np.min(xs)

        num_segments = 5
        poly_pts = []
        if dy >= dx:
            y_bins = np.linspace(np.min(ys), np.max(ys), num_segments + 1)
            for k in range(num_segments):
                in_bin = (ys >= y_bins[k]) & (ys <= y_bins[k + 1])
                if np.any(in_bin):
                    med_x = float(np.median(xs[in_bin]))
                    mean_y = float(np.mean(ys[in_bin]))
                    poly_pts.extend([round(med_x, 1), round(mean_y, 1)])
        else:
            x_bins = np.linspace(np.min(xs), np.max(xs), num_segments + 1)
            for k in range(num_segments):
                in_bin = (xs >= x_bins[k]) & (xs <= x_bins[k + 1])
                if np.any(in_bin):
                    mean_x = float(np.mean(xs[in_bin]))
                    med_y = float(np.median(ys[in_bin]))
                    poly_pts.extend([round(mean_x, 1), round(med_y, 1)])

        return poly_pts if len(poly_pts) >= 4 else []

    @staticmethod
    def mask_to_ellipse(binary_mask: np.ndarray) -> Optional[Dict[str, float]]:
        """
        Fit phương trình hình elip từ viền mask của đối tượng.
        Trả về tọa độ chuẩn CVAT:
          cx, cy: Tâm elip
          rx, ry: Bán kính trục lớn và trục nhỏ
          rotation: Góc xoay (độ)
        """
        if binary_mask is None or np.sum(binary_mask) == 0:
            return None

        # 1. Nếu có OpenCV: Dùng cv2.fitEllipse
        if cv2 is not None:
            mask_u8 = (binary_mask > 0).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_cnt = max(contours, key=cv2.contourArea)
                if len(largest_cnt) >= 5:
                    ellipse = cv2.fitEllipse(largest_cnt)
                    (cx, cy), (width, height), angle = ellipse
                    return {
                        "type": "ellipse",
                        "cx": float(round(cx, 1)),
                        "cy": float(round(cy, 1)),
                        "rx": float(round(width / 2.0, 1)),
                        "ry": float(round(height / 2.0, 1)),
                        "rotation": float(round(angle, 1)),
                    }

        # 2. Bộ xử lý thuần NumPy dự phòng dựa trên Ma trận Momen ảnh (Image Moments)
        ys, xs = np.where(binary_mask > 0)
        if len(xs) < 5:
            return None

        cx = float(np.mean(xs))
        cy = float(np.mean(ys))

        # Tính ma trận hiệp phương sai điểm ảnh
        pts = np.column_stack([xs - cx, ys - cy]).astype(np.float64)
        cov = np.cov(pts, rowvar=False)
        if cov.shape != (2, 2):
            return None

        eigenvals, eigenvecs = np.linalg.eig(cov)
        idx_order = np.argsort(eigenvals.real)[::-1]
        val_major = max(1.0, float(eigenvals[idx_order[0]].real))
        val_minor = max(1.0, float(eigenvals[idx_order[1]].real))

        # 2 * sigma xấp xỉ bán kính elip chứa 95% diện tích
        rx = float(2.0 * np.sqrt(val_major))
        ry = float(2.0 * np.sqrt(val_minor))

        vec_major = eigenvecs[:, idx_order[0]].real
        angle = float(np.degrees(np.arctan2(vec_major[1], vec_major[0])))

        return {
            "type": "ellipse",
            "cx": float(round(cx, 1)),
            "cy": float(round(cy, 1)),
            "rx": float(round(rx, 1)),
            "ry": float(round(ry, 1)),
            "rotation": float(round(angle, 1)),
        }

    @staticmethod
    def classify_image_tag(
        image: Optional[np.ndarray],
        candidate_tags: Optional[List[str]] = None,
    ) -> str:
        """
        Phân loại nhãn cấp độ toàn cảnh (Image-level Tagging).
        Mặc định phân tích độ sáng / bối cảnh thời tiết cơ bản.
        """
        candidates = candidate_tags or ["day", "night", "rainy", "foggy"]
        if image is None:
            return candidates[0]

        # Phân tích độ sáng trung bình kênh L (Lab) hoặc Gray
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image

        brightness = np.mean(gray)
        if brightness < 60:
            return "night" if "night" in candidates else candidates[0]
        elif brightness > 200 and "foggy" in candidates:
            return "foggy"
        return "day" if "day" in candidates else candidates[0]
