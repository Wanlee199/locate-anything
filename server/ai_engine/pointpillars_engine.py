"""
PointPillars 3D LiDAR Object Detection Engine.
Suy luận hộp bao 3D (Cuboid) từ đám mây điểm Point Cloud (.pcd / .bin)
hỗ trợ OpenPCDet và tích hợp bộ phân cụm hình học 3D Voxel Clustering dự phòng.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


NUSCENES_CLASSES = [
    "car", "truck", "construction_vehicle", "bus", "trailer",
    "barrier", "motorcycle", "bicycle", "pedestrian", "traffic_cone"
]

VEHICLE_CLASSES = {"car", "truck", "construction_vehicle", "bus", "trailer"}


class PointPillarsEngine:
    def __init__(
        self,
        weights_path: Optional[str] = None,
        cfg_path: Optional[str] = None,
        confidence_threshold: float = 0.25,
        spatial_range: Optional[Dict[str, float]] = None,
        auto_download: bool = True,
    ):
        self.weights_path = weights_path or "weights/cbgs_pp_multihead_nds58.pth"
        self.cfg_path = cfg_path or "configs/pcdet/cbgs_pp_multihead.yaml"
        self.conf_thresh = confidence_threshold
        self.auto_download = auto_download
        self.spatial_range = spatial_range or {
            "min_x": -51.2,
            "max_x": 51.2,
            "min_y": -51.2,
            "max_y": 51.2,
            "min_z": -5.0,
            "max_z": 3.0,
        }
        self.pcdet_model = None
        self.class_names = NUSCENES_CLASSES
        self.dataset_template = None
        self._load_model()

    def _ensure_weights(self) -> bool:
        """Kiểm tra và tự động tải weights nuScenes nếu thiếu."""
        p = Path(self.weights_path)
        if p.exists() and p.stat().st_size > 20 * 1024 * 1024:
            return True

        if not self.auto_download:
            return False

        print(f"📥 [PointPillars] Pretrained weights chưa có, bắt đầu tải về: {self.weights_path}...")
        try:
            import urllib.request
            url = "https://drive.google.com/uc?id=1p-501mTWsq0G9RzroTWSXreIMyTUUpBM&export=download"
            p.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(p, "wb") as f:
                block_size = 1024 * 1024
                while True:
                    buf = resp.read(block_size)
                    if not buf:
                        break
                    f.write(buf)
            print(f"✅ [PointPillars] Tải thành công weights: {p.resolve()} ({p.stat().st_size / (1024*1024):.1f} MB)")
            return True
        except Exception as e:
            print(f"⚠️ [PointPillars] Không thể tự động tải weights: {e}")
            return False

    def _load_model(self):
        """Khởi tạo mô hình OpenPCDet nuScenes PointPillars nếu có GPU và thư viện."""
        self._ensure_weights()
        p = Path(self.weights_path)
        cfg_p = Path(self.cfg_path)

        if p.exists() and cfg_p.exists():
            try:
                import torch
                from pcdet.config import cfg, cfg_from_yaml_file
                from pcdet.models import build_network
                from pcdet.datasets import DatasetTemplate

                cfg_from_yaml_file(str(cfg_p), cfg)
                self.class_names = cfg.CLASS_NAMES

                class CustomDatasetTemplate(DatasetTemplate):
                    pass

                self.dataset_template = CustomDatasetTemplate(
                    dataset_cfg=cfg.DATA_CONFIG,
                    class_names=self.class_names,
                    training=False,
                    root_path=Path("."),
                )

                model = build_network(model_cfg=cfg.MODEL, num_class=len(self.class_names), dataset=self.dataset_template)
                model.load_params_from_file(filename=str(p), logger=None, to_cpu=not torch.cuda.is_available())
                if torch.cuda.is_available():
                    model.cuda()
                model.eval()
                self.pcdet_model = model
                device_str = "CUDA GPU" if torch.cuda.is_available() else "CPU"
                print(f"🚀 [PointPillars] Nạp thành công mô hình Deep Learning OpenPCDet trên {device_str} ({len(self.class_names)} nhãn nuScenes)!")
            except Exception as e:
                print(f"⚠️ [PointPillars] Không thể nạp OpenPCDet ({e}), kích hoạt chế độ dự phòng Voxel Clustering.")
                self.pcdet_model = None
        else:
            self.pcdet_model = None

    def filter_points_in_range(self, points: np.ndarray) -> np.ndarray:
        """Lọc bỏ các điểm ngoài phạm vi quét hiệu dụng của LiDAR."""
        if len(points) == 0:
            return points

        r = self.spatial_range
        mask = (
            (points[:, 0] >= r["min_x"])
            & (points[:, 0] <= r["max_x"])
            & (points[:, 1] >= r["min_y"])
            & (points[:, 1] <= r["max_y"])
            & (points[:, 2] >= r["min_z"])
            & (points[:, 2] <= r["max_z"])
        )
        return points[mask]

    def _match_label(self, raw_class: str, available_labels: Optional[List[str]], target_label: str) -> str:
        """Ánh xạ nhãn dự đoán của model sang nhãn đang có trên CVAT Task."""
        if not available_labels:
            return raw_class

        raw_lower = raw_class.strip().lower()

        # 1. Khớp chính xác class
        for alb in available_labels:
            if alb.strip().lower() == raw_lower:
                return alb

        # 2. Nhóm phương tiện: nếu Task có nhãn "vehicles" và model phát hiện xe
        if raw_lower in VEHICLE_CLASSES:
            for alb in available_labels:
                if alb.strip().lower() in ["vehicles", "vehicle", "xe"]:
                    return alb

        # 3. Khớp tiền tố/hậu tố _3d (car_3d, 3d_car)
        for alb in available_labels:
            alb_clean = alb.strip().lower().replace("_3d", "").replace("3d_", "")
            if alb_clean == raw_lower or raw_lower in alb_clean:
                return alb

        # 4. Fallback về target_label hoặc nhãn đầu tiên của Task
        for alb in available_labels:
            if alb.strip().lower() == target_label.strip().lower():
                return alb
        return available_labels[0]

    def predict(
        self,
        points: np.ndarray,
        target_label: str = "car",
        available_labels: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Dự đoán các hộp bao 3D Cuboids từ mảng điểm LiDAR (N, 3) hoặc (N, 4/5).
        Nếu OpenPCDet sẵn sàng -> Chạy mô hình Deep Learning thật.
        Nếu chưa sẵn sàng -> Chạy phân cụm Voxel Cluster dự phòng.
        """
        filtered_points = self.filter_points_in_range(points)
        if len(filtered_points) < 10:
            return []

        # 1. Chạy mô hình Deep Learning OpenPCDet thật nếu có
        if self.pcdet_model is not None:
            try:
                return self._predict_openpcdet(filtered_points, available_labels=available_labels, target_label=target_label)
            except Exception as e:
                print(f"⚠️ [PointPillars] Lỗi suy luận Deep Learning: {e}, chuyển sang chế độ dự phòng.")

        # 2. Dự phòng hình học
        return self._predict_heuristic_clusters(
            filtered_points,
            target_label=target_label,
            available_labels=available_labels,
        )

    def _predict_openpcdet(
        self,
        points: np.ndarray,
        available_labels: Optional[List[str]] = None,
        target_label: str = "car",
    ) -> List[Dict[str, Any]]:
        """Suy luận bằng mô hình OpenPCDet PointPillars nuScenes."""
        import torch
        from pcdet.models import load_data_to_gpu

        # Đảm bảo mảng điểm có ít nhất 4 hoặc 5 chiều [x, y, z, intensity, timestamp]
        pts = points.astype(np.float32)
        if pts.shape[1] == 3:
            zeros = np.zeros((pts.shape[0], 2), dtype=np.float32)
            pts = np.hstack([pts, zeros])
        elif pts.shape[1] == 4:
            zeros = np.zeros((pts.shape[0], 1), dtype=np.float32)
            pts = np.hstack([pts, zeros])

        input_dict = {"points": pts, "frame_id": 0}
        data_dict = self.dataset_template.prepare_data(data_dict=input_dict)
        batch_dict = self.dataset_template.collate_batch([data_dict])
        if torch.cuda.is_available():
            load_data_to_gpu(batch_dict)

        with torch.no_grad():
            pred_dicts, _ = self.pcdet_model.forward(batch_dict)

        pred_boxes = pred_dicts[0]["pred_boxes"].cpu().numpy()
        pred_scores = pred_dicts[0]["pred_scores"].cpu().numpy()
        pred_labels = pred_dicts[0]["pred_labels"].cpu().numpy()

        results = []
        for i in range(len(pred_boxes)):
            score = float(pred_scores[i])
            if score < self.conf_thresh:
                continue

            box = pred_boxes[i]
            # OpenPCDet box: [x, y, z, dx, dy, dz, heading/yaw]
            cx, cy, cz = float(box[0]), float(box[1]), float(box[2])
            dx, dy, dz = float(box[3]), float(box[4]), float(box[5])
            yaw = float(box[6]) if len(box) > 6 else 0.0

            class_idx = int(pred_labels[i]) - 1
            raw_class = self.class_names[class_idx] if 0 <= class_idx < len(self.class_names) else "car"
            final_label = self._match_label(raw_class, available_labels, target_label)

            results.append({
                "type": "cuboid",
                "label": final_label,
                "position": [round(cx, 3), round(cy, 3), round(cz, 3)],
                "dimensions": [round(dx, 3), round(dy, 3), round(dz, 3)],
                "rotation": [0.0, 0.0, round(yaw, 4)],
                "confidence": round(score, 3),
            })

        return results

    def _predict_heuristic_clusters(
        self,
        points: np.ndarray,
        target_label: str = "car",
        available_labels: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Thuật toán gom cụm hình học 3D (Voxel Grid Clustering) tốc độ cao
        nhận diện và bao bọc các vật thể nổi trong không gian, ưu tiên nhãn Task CVAT.
        """
        # 1. Loại bỏ mặt đất (Ground Plane Removal) bằng ngưỡng cao độ Z
        ground_z_thresh = -1.6
        obj_points = points[points[:, 2] > ground_z_thresh]
        if len(obj_points) < 5:
            return []

        # 2. Voxelization thô 2D trên mặt phẳng (X, Y) với kích thước ô 1.0m
        voxel_size = 1.0
        x_coords = np.floor(obj_points[:, 0] / voxel_size).astype(int)
        y_coords = np.floor(obj_points[:, 1] / voxel_size).astype(int)

        # Gom nhóm điểm theo tọa độ ô
        cells: Dict[Tuple[int, int], List[int]] = {}
        for idx in range(len(obj_points)):
            key = (x_coords[idx], y_coords[idx])
            if key not in cells:
                cells[key] = []
            cells[key].append(idx)

        # 3. Gom các ô lân cận thành từng cụm vật thể (Connected Components)
        visited = set()
        clusters = []

        for key in list(cells.keys()):
            if key in visited:
                continue
            # BFS tìm các ô liền kề
            cluster_indices = []
            queue = [key]
            visited.add(key)

            while queue:
                curr = queue.pop(0)
                cluster_indices.extend(cells[curr])
                # Kiểm tra 8 ô xung quanh
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        neighbor = (curr[0] + dx, curr[1] + dy)
                        if neighbor in cells and neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

            # Lọc cụm có số điểm đủ lớn (tránh nhiễu tia lẻ)
            if len(cluster_indices) >= 8:
                clusters.append(obj_points[cluster_indices])

        # 4. Trích xuất Hộp bao 3D (Oriented 3D Bounding Box) cho từng cụm
        results = []
        for cl in clusters:
            min_xyz = np.min(cl[:, :3], axis=0)
            max_xyz = np.max(cl[:, :3], axis=0)

            dx = float(max_xyz[0] - min_xyz[0])
            dy = float(max_xyz[1] - min_xyz[1])
            dz = float(max_xyz[2] - min_xyz[2])

            # Lọc kích thước vật thể thực tế (xe hơi, người, xe tải)
            if 0.5 <= dx <= 12.0 and 0.5 <= dy <= 6.0 and 0.4 <= dz <= 4.5:
                cx = float((min_xyz[0] + max_xyz[0]) / 2.0)
                cy = float((min_xyz[1] + max_xyz[1]) / 2.0)
                cz = float((min_xyz[2] + max_xyz[2]) / 2.0)

                # Ước lượng góc xoay yaw theo trục chính (Principal Component)
                yaw = 0.0
                try:
                    xy_cov = np.cov(cl[:, 0].astype(np.float64), cl[:, 1].astype(np.float64))
                    if xy_cov.shape == (2, 2):
                        eigenvals, eigenvecs = np.linalg.eig(xy_cov)
                        idx_max = int(np.argmax(eigenvals.real))
                        vx = float(eigenvecs[0, idx_max].real)
                        vy = float(eigenvecs[1, idx_max].real)
                        yaw = float(np.arctan2(vy, vx))
                except Exception:
                    yaw = 0.0

                # Phân loại sơ bộ kích thước theo chuẩn nuScenes
                detected_class = "car"
                if dx > 6.0 or dz > 2.5:
                    detected_class = "truck"
                elif dx < 1.3 and dy < 1.3 and dz < 2.2:
                    detected_class = "pedestrian"
                elif (dx < 2.4 and dy < 1.3) and dz < 1.8:
                    detected_class = "motorcycle"
                elif dz < 0.9 and (dx < 1.3 or dy < 1.3):
                    detected_class = "barrier"

                # ƯU TIÊN 1: Khớp với nhãn đang có trong Task của CVAT (nếu có available_labels)
                final_label = target_label
                if available_labels:
                    matched = None
                    # 1.1 Khớp chính xác class
                    for alb in available_labels:
                        if alb.strip().lower() == detected_class.lower():
                            matched = alb
                            break
                    # 1.2 Khớp có đuôi _3d hoặc tiền tố 3d_ (ví dụ car_3d, truck_3d)
                    if not matched:
                        for alb in available_labels:
                            alb_clean = alb.strip().lower().replace("_3d", "").replace("3d_", "")
                            if alb_clean == detected_class.lower():
                                matched = alb
                                break
                    # 1.3 Nếu target_label có sẵn trong Task
                    if not matched and any(alb.strip().lower() == target_label.strip().lower() for alb in available_labels):
                        matched = target_label
                    # 1.4 Fallback về nhãn hợp lệ đầu tiên của Task
                    if not matched and available_labels:
                        matched = available_labels[0]

                    final_label = matched or target_label
                else:
                    final_label = target_label

                results.append(
                    {
                        "type": "cuboid",
                        "label": final_label,
                        "position": [round(cx, 3), round(cy, 3), round(cz, 3)],
                        "dimensions": [round(dx, 3), round(dy, 3), round(dz, 3)],
                        "rotation": [0.0, 0.0, round(yaw, 4)],
                        "confidence": 0.88,
                    }
                )

        # Giới hạn tối đa 50 vật thể nổi bật nhất
        return results[:50]
