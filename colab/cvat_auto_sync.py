#!/usr/bin/env python3
"""
CVAT Colab Auto-Sync Worker - Cầu nối tự động giữa Google Colab GPU và CVAT Server.
Cách hoạt động:
  1. Kết nối tới CVAT (cvat.ai Cloud hoặc VPS riêng) bằng API Token.
  2. Hỗ trợ gán nhãn cho TOÀN BỘ TASK hoặc ĐỘC LẬP CHO 1 JOB CỤ THỂ (--job-id).
  3. Tự động rẽ nhánh: Task 3D Point Cloud (.pcd) hoặc Task 2D Image (.jpg/.png).
  4. Đẩy thẳng annotations ngược lại lên Task hoặc Job trên CVAT.
"""

import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from PIL import Image

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from locate_cvat.label_registry import LabelRegistry
from locate_cvat.pcd_utils import read_pcd_bytes
from server.ai_engine.dispatcher import ModelDispatcher


class CVATSyncWorker:
    def __init__(
        self,
        host: str,
        token: str,
        task_id: Optional[int] = None,
        job_id: Optional[int] = None,
        registry_path: str = "configs/labels_config.yaml",
    ):
        self.host = host.rstrip("/")
        self.token = token
        self.task_id = task_id
        self.job_id = job_id

        # Load danh mục nhãn và AI Engine
        print(f"📦 Đang tải cấu hình nhãn từ: {registry_path}")
        self.registry = LabelRegistry.load_from_yaml(registry_path)

        print("🧠 Đang khởi tạo Model Dispatcher (SAM 2.1 + YOLO + Pose + 3D)...")
        self.dispatcher = ModelDispatcher(registry=self.registry)
        self.dispatcher.load_engines()

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.cvat+json, application/json;q=0.9",
        }

    def get_job_info(self, job_id: int) -> dict:
        """Lấy thông tin chi tiết của 1 Job cụ thể (start_frame, stop_frame, task_id)."""
        url = f"{self.host}/api/jobs/{job_id}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Không thể kết nối Job {job_id} trên {self.host}: {e}")

    def get_task_info(self) -> dict:
        """Lấy thông tin task và số lượng frame ảnh từ CVAT."""
        url = f"{self.host}/api/tasks/{self.task_id}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Không thể kết nối Task {self.task_id} trên {self.host}: {e}")

    def download_frame(self, frame_idx: int) -> Image.Image:
        """Tải 1 frame ảnh từ CVAT về Colab theo số thứ tự frame tuyệt đối."""
        url = f"{self.host}/api/tasks/{self.task_id}/data?type=frame&number={frame_idx}&quality=compressed"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req) as resp:
            img_bytes = resp.read()
            return Image.open(io.BytesIO(img_bytes))

    def download_pcd_frame(self, frame_idx: int):
        """Tải 1 frame dữ liệu đám mây điểm 3D (.pcd/.bin) từ CVAT về Colab."""
        url = f"{self.host}/api/tasks/{self.task_id}/data?type=frame&number={frame_idx}"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req) as resp:
            raw_bytes = resp.read()
            return read_pcd_bytes(raw_bytes)

    def upload_annotations(self, shapes: list, tags: list = None):
        """
        Đẩy toàn bộ annotations đã gán nhãn lên CVAT.
        Tự động chọn endpoint cấp Job (/api/jobs/{id}/annotations) hoặc Task (/api/tasks/{id}/annotations).
        """
        if self.job_id:
            url = f"{self.host}/api/jobs/{self.job_id}/annotations?action=create"
            target_str = f"Job #{self.job_id}"
        else:
            url = f"{self.host}/api/tasks/{self.task_id}/annotations?action=create"
            target_str = f"Task #{self.task_id}"

        headers = self._headers()
        headers["Content-Type"] = "application/json"

        payload = json.dumps({
            "shapes": shapes,
            "tracks": [],
            "tags": tags or [],
            "version": 0,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"CVAT từ chối annotations cho {target_str} (HTTP {e.code}): {err_msg}")

    def get_task_labels(self) -> list:
        """Lấy danh sách các nhãn thực sự được định nghĩa trong Task."""
        url = f"{self.host}/api/labels?task_id={self.task_id}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", [])
        except Exception as e:
            print(f"[WARN] Không lấy được danh sách labels: {e}")
            return []

    def _resolve_label_id(self, label_name: str) -> int:
        """
        Tìm ID của nhãn trong Task CVAT.
        ƯU TIÊN TUYỆT ĐỐI nhãn của Task hiện tại trước, sau đó mới tới registry.
        """
        # 1. Khớp chính xác tên nhãn có sẵn trong Task CVAT
        for lbl in self.task_labels:
            if lbl.get("name", "").strip().lower() == label_name.strip().lower():
                return lbl.get("id", 0)

        # 2. Khớp thông minh bỏ qua hậu tố _3d (ví dụ: model báo 'car' nhưng Task đặt 'car_3d')
        clean_name = label_name.strip().lower().replace("_3d", "").replace("3d_", "")
        for lbl in self.task_labels:
            lbl_clean = lbl.get("name", "").strip().lower().replace("_3d", "").replace("3d_", "")
            if clean_name and (lbl_clean == clean_name or clean_name in lbl_clean):
                return lbl.get("id", 0)

        # 3. Fallback an toàn: lấy nhãn đầu tiên của Task để tránh lỗi CVAT 400 Bad Request
        if self.task_labels:
            return self.task_labels[0].get("id", 0)
        return 1

    def clear_annotations(self):
        """Xóa annotations cũ trên task hoặc job trước khi đồng bộ mới."""
        if self.job_id:
            url = f"{self.host}/api/jobs/{self.job_id}/annotations"
        else:
            url = f"{self.host}/api/tasks/{self.task_id}/annotations"

        req = urllib.request.Request(url, headers=self._headers(), method="DELETE")
        try:
            with urllib.request.urlopen(req) as resp:
                pass
        except Exception:
            pass

    def run(self):
        # 1. Xác định phạm vi frames cần chạy (Toàn bộ Task hay Riêng 1 Job)
        if self.job_id:
            job_info = self.get_job_info(self.job_id)
            if not self.task_id:
                self.task_id = job_info.get("task_id")
            start_frame = int(job_info.get("start_frame", 0))
            stop_frame = int(job_info.get("stop_frame", 0))
            frame_indices = list(range(start_frame, stop_frame + 1))
            mode_desc = f"🎯 JOB #{self.job_id} thuộc Task #{self.task_id} (từ frame {start_frame} đến {stop_frame}, tổng {len(frame_indices)} frames)"
        else:
            task_info_temp = self.get_task_info()
            size = task_info_temp.get("size", 0)
            frame_indices = list(range(size))
            mode_desc = f"📋 TOÀN BỘ TASK #{self.task_id} ({size} frames từ 0 đến {size - 1})"

        print("=" * 65)
        print(f"🚀 BẮT ĐẦU ĐỒNG BỘ TỰ ĐỘNG COLAB GPU <---> CVAT {mode_desc}")
        print("=" * 65)

        task_info = self.get_task_info()
        task_name = task_info.get("name", f"Task {self.task_id}")
        self.task_labels = self.get_task_labels()
        label_names = [l.get("name") for l in self.task_labels]
        print(f"📋 Tên Task: {task_name}")
        print(f"🏷️ Danh sách nhãn trong Task: {label_names}")
        print(f"🎯 Phạm vi xử lý: {mode_desc}")

        # Tự động đồng bộ và tôn trọng 100% loại nhãn cấu hình trên CVAT
        from locate_cvat.label_registry import LabelItem, LabelType

        target_labels = []
        for l in self.task_labels:
            l_name = l.get("name")
            l_type_raw = str(l.get("type", "any")).strip().lower()

            if l_type_raw in ["mask", "segmentation"]:
                target_type = LabelType.MASK
            elif l_type_raw in ["polygon", "poly"]:
                target_type = LabelType.POLYGON
            elif l_type_raw in ["rectangle", "box"]:
                target_type = LabelType.BOX
            elif l_type_raw in ["line", "polyline"]:
                target_type = LabelType.LINE
            elif l_type_raw in ["skeleton", "pose"]:
                target_type = LabelType.SKELETON
            elif l_type_raw in ["3d", "cuboid"]:
                target_type = LabelType.CUBOID_3D
            elif l_type_raw in ["ellipse", "circle"]:
                target_type = LabelType.ELLIPSE
            elif l_type_raw in ["tag", "classification"]:
                target_type = LabelType.TAG
            else:
                # Nếu là Task 3D, ưu tiên gán CUBOID_3D; nếu 2D mới tra cứu fallback sang registry
                if str(task_info.get("dimension", "2d")).lower() == "3d":
                    target_type = LabelType.CUBOID_3D
                else:
                    reg_item = self.registry.get(l_name)
                    target_type = reg_item.type if reg_item else LabelType.BOX

            target_labels.append(LabelItem(name=l_name, type=target_type))

        if not target_labels and self.registry.labels:
            target_labels = [self.registry.labels[0]]

        dimension = str(task_info.get("dimension", "2d")).lower()
        is_3d_task = (dimension == "3d") or all(t.type == LabelType.CUBOID_3D for t in target_labels)

        print(f"🎯 Mô hình AI sẽ gán nhãn cho {len(target_labels)} đối tượng chuẩn xác theo Task:")
        for t in target_labels:
            if t.type == LabelType.MASK:
                type_desc = "Native Bitmap MASK (Brush RLE chuẩn CVAT)"
            elif t.type == LabelType.POLYGON:
                type_desc = "Vector Polygon (Đa giác viền kéo thả)"
            elif t.type == LabelType.CUBOID_3D:
                type_desc = "3D Point Cloud Cuboid (Hộp lập phương LiDAR)"
            elif t.type == LabelType.ELLIPSE:
                type_desc = "Ellipse (Hình elip toán học)"
            elif t.type == LabelType.TAG:
                type_desc = "Tag (Phân loại toàn ảnh)"
            else:
                type_desc = "2D Bounding Box (rectangle)"
            print(f"   • {t.name:<12} -> Chuẩn type: {t.type.value.upper():<8} ({type_desc})")

        all_shapes = []
        all_tags = []
        start_time = time.time()
        total_frames = len(frame_indices)

        if is_3d_task:
            print("🧊 [3D LiDAR Pipeline] Kích hoạt suy luận Point Cloud (PointPillars Engine)...")
            task_label_names = [t.name for t in target_labels]
            print(f"🎯 Ưu tiên các nhãn có sẵn trên CVAT Task: {task_label_names}")
            for idx, frame_idx in enumerate(frame_indices):
                sys.stdout.write(f"\r  ⏳ Đang quét LiDAR frame {frame_idx} ({idx + 1}/{total_frames})...")
                sys.stdout.flush()

                # 1. Kéo dữ liệu đám mây điểm .pcd về GPU Colab
                pcd_points = self.download_pcd_frame(frame_idx)

                # 2. Suy luận 3D một lượt cho frame, ưu tiên phân loại theo nhãn Task
                results = self.dispatcher.dispatch(
                    image_shape=(0, 0),
                    label_name=target_labels[0].name if target_labels else "car",
                    target_type=LabelType.CUBOID_3D,
                    point_cloud=pcd_points,
                    available_labels=task_label_names,
                )
                for res in results:
                    detected_label = res.get("label", target_labels[0].name if target_labels else "car")
                    pos = res.get("position", res.get("center", [0.0, 0.0, 0.0]))
                    dim = res.get("dimensions", [1.0, 1.0, 1.0])
                    rot = res.get("rotation", [0.0, 0.0, 0.0])
                    shape_record = {
                        "frame": frame_idx,
                        "label_id": self._resolve_label_id(detected_label),
                        "type": "cuboid",
                        "rotation": 0.0,
                        "points": [
                            float(pos[0]), float(pos[1]), float(pos[2]),
                            float(dim[0]), float(dim[1]), float(dim[2]),
                            float(rot[0]), float(rot[1]), float(rot[2]),
                        ],
                        "occluded": False,
                        "z_order": 0,
                        "attributes": [],
                    }
                    all_shapes.append(shape_record)

        else:
            print("🖼️ [2D Vision Pipeline] Kích hoạt suy luận Ảnh RGB (YOLO / SAM2 / Pose)...")
            for idx, frame_idx in enumerate(frame_indices):
                sys.stdout.write(f"\r  ⏳ Đang xử lý frame {frame_idx} ({idx + 1}/{total_frames})...")
                sys.stdout.flush()

                # 1. Kéo ảnh về GPU Colab
                img = self.download_frame(frame_idx)
                w, h = img.size

                # 2. Chạy AI Model Dispatcher cho các nhãn mục tiêu
                for label_item in target_labels:
                    results = self.dispatcher.dispatch(
                        image_shape=(h, w),
                        image=img,
                        label_name=label_item.name,
                        target_type=label_item.type,
                    )
                    for res in results:
                        detected_label = res.get("label", label_item.name)
                        shape_type = res.get("type", label_item.type.to_cvat_type())

                        if shape_type == "tag":
                            all_tags.append({
                                "frame": frame_idx,
                                "label_id": self._resolve_label_id(detected_label),
                                "attributes": [{"name": "tag", "value": res.get("tag_value", "day")}],
                            })
                        elif shape_type == "ellipse":
                            all_shapes.append({
                                "frame": frame_idx,
                                "label_id": self._resolve_label_id(detected_label),
                                "type": "ellipse",
                                "cx": res.get("cx", 0.0),
                                "cy": res.get("cy", 0.0),
                                "rx": res.get("rx", 0.0),
                                "ry": res.get("ry", 0.0),
                                "rotation": res.get("rotation", 0.0),
                                "occluded": False,
                                "z_order": 0,
                                "attributes": [],
                            })
                        else:
                            all_shapes.append({
                                "frame": frame_idx,
                                "label_id": self._resolve_label_id(detected_label),
                                "type": shape_type,
                                "points": res.get("points", []),
                                "occluded": False,
                                "z_order": 0,
                                "attributes": [],
                            })

        print(f"\n✅ Đã hoàn thành suy luận AI cho {total_frames} frame! Tổng số shapes sinh ra: {len(all_shapes)}")

        # 3. Đẩy kết quả ngược lên CVAT (làm sạch nhãn rác cũ trước khi ghi)
        target_name = f"Job #{self.job_id}" if self.job_id else f"Task #{self.task_id}"
        print(f"📤 Đang dọn dẹp nhãn cũ và cập nhật nhãn mới lên CVAT Server ({target_name})...")
        self.clear_annotations()
        self.upload_annotations(all_shapes, tags=all_tags)

        elapsed = time.time() - start_time
        print("=" * 65)
        print(f"🎉 THÀNH CÔNG! Đã gán nhãn xong {mode_desc} trong {elapsed:.1f} giây!")
        print(f"👉 Bây giờ bạn chỉ cần mở CVAT trên trình duyệt: toàn bộ đối tượng đã được vẽ sẵn!")
        print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Tự động đồng bộ gán nhãn AI giữa Colab GPU và CVAT")
    parser.add_argument("--host", type=str, required=True, help="Địa chỉ CVAT (VD: https://app.cvat.ai hoặc http://ip-vps:8080)")
    parser.add_argument("--token", type=str, required=True, help="API Token của tài khoản CVAT")
    parser.add_argument("--task-id", type=int, default=None, help="ID của Task cần gán nhãn")
    parser.add_argument("--job-id", type=int, default=None, help="ID của Job cụ thể trong Task (nếu chỉ muốn gán nhãn cho 1 Job)")
    parser.add_argument("--config", type=str, default="configs/labels_config.yaml", help="File cấu hình nhãn")
    args = parser.parse_args()

    if args.task_id is None and args.job_id is None:
        parser.error("Cần cung cấp ít nhất --task-id hoặc --job-id")

    worker = CVATSyncWorker(
        host=args.host,
        token=args.token,
        task_id=args.task_id,
        job_id=args.job_id,
        registry_path=args.config,
    )
    worker.run()


if __name__ == "__main__":
    main()
