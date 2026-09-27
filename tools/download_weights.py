#!/usr/bin/env python3
"""
Script Tải và Quản lý Model Weights cho Server Thuê.
Tự động tải các model weights:
  1. Ultralytics SAM 2.1 (Segment Anything 2.1 Tiny/Base)
  2. YOLOv11 Object Detection (yolo11n / yolo11s)
  3. YOLOv11 Pose Estimation (yolo11n-pose)
Lưu vào thư mục weights/ để tái sử dụng mà không cần kết nối mạng nhiều lần.
"""

import argparse
import os
import sys
import urllib.request
from pathlib import Path

# Cấu hình danh sách models và link tải chính thức
MODEL_REGISTRY = {
    "sam2.1_t": {
        "filename": "sam2.1_t.pt",
        "url": "https://github.com/facebookresearch/sam2/releases/download/v1.0/sam2_hiera_tiny.pt",
        "size_mb": 156,
        "description": "SAM 2.1 Tiny - Siêu nhẹ, bám viền cực nhanh, tốn ít VRAM",
    },
    "sam2.1_b": {
        "filename": "sam2.1_b.pt",
        "url": "https://github.com/facebookresearch/sam2/releases/download/v1.0/sam2_hiera_base_plus.pt",
        "size_mb": 418,
        "description": "SAM 2.1 Base+ - Độ chính xác cao cho viền đa giác phức tạp",
    },
    "yolo11n": {
        "filename": "yolo11n.pt",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt",
        "size_mb": 6,
        "description": "YOLOv11 Nano - Phát hiện bounding box 2D tốc độ cực cao",
    },
    "yolo11s": {
        "filename": "yolo11s.pt",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt",
        "size_mb": 19,
        "description": "YOLOv11 Small - Cân bằng tốc độ và độ chính xác",
    },
    "yolo11n-pose": {
        "filename": "yolo11n-pose.pt",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt",
        "size_mb": 7,
        "description": "YOLOv11 Pose Nano - Trích xuất 17 khớp khung xương Skeleton",
    },
}


def download_file(url: str, dest_path: Path):
    """Tải file với thanh tiến trình phần trăm."""
    print(f"📥 Đang tải từ: {url}")
    print(f"📁 Lưu tại: {dest_path}")

    def progress_callback(block_num, block_size, total_size):
        if total_size > 0:
            downloaded = block_num * block_size
            percent = min(100, (downloaded / total_size) * 100)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  Progress: [{percent:5.1f}%] - {mb_downloaded:.1f}/{mb_total:.1f} MB")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, dest_path, reporthook=progress_callback)
        print("\n✅ Tải thành công!")
    except Exception as e:
        print(f"\n❌ Lỗi khi tải {url}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Tải Model Weights cho CVAT AI Engine trên Server")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["sam2.1_t", "yolo11n", "yolo11n-pose"],
        help=f"Danh sách model cần tải (Có sẵn: {list(MODEL_REGISTRY.keys())})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="weights",
        help="Thư mục lưu trữ weights (mặc định: weights/)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("🚀 BẮT ĐẦU CHUẨN BỊ MODEL WEIGHTS CHO SERVER THUÊ")
    print(f"📂 Thư mục đích: {out_dir.resolve()}")
    print("=" * 65)

    for model_key in args.models:
        if model_key not in MODEL_REGISTRY:
            print(f"⚠️ Bỏ qua model lạ: '{model_key}'. Chỉ hỗ trợ: {list(MODEL_REGISTRY.keys())}")
            continue

        info = MODEL_REGISTRY[model_key]
        dest_file = out_dir / info["filename"]

        print(f"\n🔹 Model: {model_key} (~{info['size_mb']} MB)")
        print(f"   Mô tả: {info['description']}")

        if dest_file.exists() and dest_file.stat().st_size > 1024 * 1024:
            print(f"   ⏩ Đã có sẵn file: {dest_file} (Bỏ qua tải)")
            continue

        download_file(info["url"], dest_file)

    print("\n" + "=" * 65)
    print("🎉 TOÀN BỘ MODEL WEIGHTS ĐÃ SẴN SÀNG!")
    print("=" * 65)


if __name__ == "__main__":
    main()
