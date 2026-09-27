#!/usr/bin/env python3
"""
CVAT Colab Auto-Sync Worker - Cầu nối tự động giữa Google Colab GPU và CVAT Server.
Cách hoạt động:
  1. Kết nối tới CVAT (cvat.ai Cloud hoặc VPS riêng) bằng API Token.
  2. Tự động kéo ảnh của Task về GPU Colab.
  3. Dùng SAM 2.1 và YOLOv11 gán nhãn tự động cực nhanh.
  4. Đẩy thẳng annotations ngược lại lên Task trên CVAT.
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
from PIL import Image

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from locate_cvat.label_registry import LabelRegistry
from server.ai_engine.dispatcher import ModelDispatcher


class CVATSyncWorker:
    def __init__(self, host: str, token: str, task_id: int, registry_path: str = "configs/labels_config.yaml"):
        self.host = host.rstrip("/")
        self.token = token
        self.task_id = task_id
        
        # Load danh mục nhãn và AI Engine
        print(f"📦 Đang tải cấu hình nhãn từ: {registry_path}")
        self.registry = LabelRegistry.load_from_yaml(registry_path)
        
        print("🧠 Đang khởi tạo Model Dispatcher (SAM 2.1 + YOLO + Pose)...")
        self.dispatcher = ModelDispatcher(registry=self.registry)
        self.dispatcher.load_engines()

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.cvat+json, application/json;q=0.9",
        }

    def get_task_info(self):
        """Lấy thông tin task và số lượng frame ảnh từ CVAT."""
        url = f"{self.host}/api/tasks/{self.task_id}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Không thể kết nối Task {self.task_id} trên {self.host}: {e}")

    def download_frame(self, frame_idx: int) -> Image.Image:
        """Tải 1 frame ảnh từ CVAT về Colab."""
        url = f"{self.host}/api/tasks/{self.task_id}/data?type=frame&number={frame_idx}&quality=compressed"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req) as resp:
            img_bytes = resp.read()
            return Image.open(io.BytesIO(img_bytes))

    def upload_annotations(self, shapes: list):
        """Đẩy toàn bộ annotations đã gán nhãn lên CVAT Task (PUT /api/tasks/{id}/annotations)."""
        url = f"{self.host}/api/tasks/{self.task_id}/annotations?action=create"
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        
        payload = json.dumps({
            "shapes": shapes,
            "tracks": [],
            "tags": [],
            "version": 0,
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"CVAT từ chối annotations (HTTP {e.code}): {err_msg}")

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
        """Tìm ID của nhãn trong Task CVAT."""
        for lbl in self.task_labels:
            if lbl.get("name", "").lower() == label_name.lower():
                return lbl.get("id", 0)
        if self.task_labels:
            return self.task_labels[0].get("id", 0)
        return 1

    def clear_annotations(self):
        """Xóa annotations cũ trên task trước khi đồng bộ mới."""
        url = f"{self.host}/api/tasks/{self.task_id}/annotations"
        req = urllib.request.Request(url, headers=self._headers(), method="DELETE")
        try:
            with urllib.request.urlopen(req) as resp:
                pass
        except Exception:
            pass

    def run(self):
        print("=" * 65)
        print(f"🚀 BẮT ĐẦU ĐỒNG BỘ TỰ ĐỘNG COLAB GPU <---> CVAT TASK #{self.task_id}")
        print("=" * 65)
        
        task_info = self.get_task_info()
        task_name = task_info.get("name", f"Task {self.task_id}")
        size = task_info.get("size", 0)
        self.task_labels = self.get_task_labels()
        label_names = [l.get("name") for l in self.task_labels]
        print(f"📋 Tên Task: {task_name}")
        print(f"🏷️ Danh sách nhãn trong Task: {label_names}")
        print(f"🖼️ Tổng số ảnh cần gán nhãn: {size}")

        # Tự động hỗ trợ toàn bộ các nhãn có trong Task của CVAT
        target_labels = []
        for l_name in label_names:
            item = self.registry.get(l_name)
            if item:
                target_labels.append(item)
            else:
                from locate_cvat.label_registry import LabelItem, LabelType
                target_labels.append(LabelItem(name=l_name, type=LabelType.BOX))

        if not target_labels and self.registry.labels:
            target_labels = [self.registry.labels[0]]

        print(f"🎯 Mô hình AI sẽ gán nhãn cho: {[l.name for l in target_labels]}")

        all_shapes = []
        start_time = time.time()

        for frame_idx in range(size):
            sys.stdout.write(f"\r  ⏳ Đang xử lý frame {frame_idx + 1}/{size}...")
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
                )
                for res in results:
                    detected_label = res.get("label", label_item.name)
                    shape_record = {
                        "frame": frame_idx,
                        "label_id": self._resolve_label_id(detected_label),
                        "type": res.get("type", "rectangle"),
                        "points": res.get("points", []),
                        "occluded": False,
                        "z_order": 0,
                        "attributes": [],
                    }
                    all_shapes.append(shape_record)

        print(f"\n✅ Đã hoàn thành suy luận AI cho {size} ảnh! Tổng số shapes sinh ra: {len(all_shapes)}")
        
        # 3. Đẩy kết quả ngược lên CVAT (làm sạch nhãn rác cũ trước khi ghi)
        print("📤 Đang dọn dẹp nhãn cũ và cập nhật nhãn mới lên CVAT Server...")
        self.clear_annotations()
        self.upload_annotations(all_shapes)
        
        elapsed = time.time() - start_time
        print("=" * 65)
        print(f"🎉 THÀNH CÔNG! Đã gán nhãn xong Task #{self.task_id} trong {elapsed:.1f} giây!")
        print(f"👉 Bây giờ bạn chỉ cần mở CVAT trên trình duyệt: toàn bộ đối tượng đã được vẽ sẵn!")
        print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Tự động đồng bộ gán nhãn AI giữa Colab GPU và CVAT")
    parser.add_argument("--host", type=str, required=True, help="Địa chỉ CVAT (VD: https://app.cvat.ai hoặc http://ip-vps:8080)")
    parser.add_argument("--token", type=str, required=True, help="API Token của tài khoản CVAT")
    parser.add_argument("--task-id", type=int, required=True, help="ID của Task cần gán nhãn")
    parser.add_argument("--config", type=str, default="configs/labels_config.yaml", help="File cấu hình nhãn")
    args = parser.parse_args()

    worker = CVATSyncWorker(
        host=args.host,
        token=args.token,
        task_id=args.task_id,
        registry_path=args.config,
    )
    worker.run()


if __name__ == "__main__":
    main()
