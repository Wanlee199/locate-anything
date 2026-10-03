#!/usr/bin/env python3
"""
Công cụ Tải và Chuẩn bị Dữ liệu nuScenes LiDAR cho CVAT 3D Auto-Annotation.
Hỗ trợ:
  1. mode 'sample': Tải / sinh sequence LiDAR chuẩn nuScenes dạng .pcd sẵn sàng nạp vào CVAT Task.
  2. mode 'full-mini': Tải trực tiếp v1.0-mini.tgz trên Colab/Server và giải nén chọn lọc (chỉ lấy LiDAR).
  3. mode 'convert': Chuyển đổi hàng loạt file nuScenes .bin (5 cột float32) sang chuẩn .pcd của CVAT.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional
import numpy as np

# Thêm thư mục gốc dự án vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from locate_cvat.pcd_utils import (
    create_pcd_binary,
    read_pcd_bytes,
    save_pcd,
)

NUSCENES_MINI_URL = "https://www.nuscenes.org/data/v1.0-mini.tgz"


def download_with_progress(url: str, dest_path: Path):
    """Tải file từ URL với thanh tiến trình phần trăm rõ ràng."""
    print(f"📥 Đang tải: {url}")
    print(f"📁 Lưu tại: {dest_path}")

    def progress(block_num, block_size, total_size):
        if total_size > 0:
            downloaded = block_num * block_size
            percent = min(100.0, (downloaded / total_size) * 100)
            mb_down = downloaded / (1024 * 1024)
            mb_tot = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  Tiến độ: [{percent:5.1f}%] - {mb_down:.1f}/{mb_tot:.1f} MB")
            sys.stdout.flush()

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out_f:
            total_size = int(resp.headers.get("Content-Length", 0))
            block_size = 1024 * 1024  # 1MB chunks
            downloaded = 0
            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = min(100.0, (downloaded / total_size) * 100)
                    sys.stdout.write(
                        f"\r  Tiến độ: [{pct:5.1f}%] - {downloaded / 1048576:.1f}/{total_size / 1048576:.1f} MB"
                    )
                    sys.stdout.flush()
        print("\n✅ Tải thành công!")
    except Exception as e:
        print(f"\n❌ Lỗi khi tải: {e}")
        if dest_path.exists():
            dest_path.unlink()
        raise


def extract_lidar_from_tar(tar_path: Path, output_dir: Path):
    """Giải nén chọn lọc: chỉ trích xuất thư mục samples/LIDAR_TOP và v1.0-mini metadata."""
    print(f"📦 Đang giải nén chọn lọc LiDAR từ: {tar_path}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        members = []
        for m in tar.getmembers():
            if m.name.startswith("samples/LIDAR_TOP") or m.name.startswith("v1.0-mini"):
                members.append(m)
        print(f"   Tìm thấy {len(members)} files LiDAR & Metadata. Đang giải nén...")
        tar.extractall(path=output_dir, members=members)
    print(f"✅ Hoàn tất giải nén vào: {output_dir}")


def convert_bin_dir_to_pcd(bin_dir: Path, pcd_dir: Path, max_frames: int = 40) -> list[Path]:
    """Chuyển đổi các file nuScenes .bin thành file .pcd chuẩn CVAT."""
    pcd_dir.mkdir(parents=True, exist_ok=True)
    bin_files = sorted(list(bin_dir.glob("*.bin")))[:max_frames]
    if not bin_files:
        print(f"⚠️ Không tìm thấy file .bin nào trong: {bin_dir}")
        return []

    print(f"🔄 Đang chuyển đổi {len(bin_files)} file nuScenes .bin sang .pcd...")
    pcd_paths = []
    for idx, bf in enumerate(bin_files):
        with open(bf, "rb") as f:
            raw_bytes = f.read()
        pts = read_pcd_bytes(raw_bytes)
        out_name = f"frame_{idx:04d}.pcd"
        out_path = pcd_dir / out_name
        save_pcd(pts, out_path, binary=True)
        pcd_paths.append(out_path)
        sys.stdout.write(f"\r  Chuyển đổi: [{idx+1}/{len(bin_files)}] -> {out_name} ({len(pts)} điểm)")
        sys.stdout.flush()

    print(f"\n✅ Đã lưu {len(pcd_paths)} file .pcd tại: {pcd_dir}")
    return pcd_paths


def generate_synthetic_nuscenes_sequence(output_dir: Path, num_frames: int = 20) -> Path:
    """
    Sinh sequence LiDAR thực tế chuẩn tọa độ nuScenes (gồm mặt đường + xe hơi + xe tải + người đi bộ)
    đóng gói chuẩn bị cho CVAT 3D Task.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pcd_folder = output_dir / "pcd_frames"
    pcd_folder.mkdir(parents=True, exist_ok=True)

    print(f"✨ Đang sinh {num_frames} frame LiDAR thực nghiệm chuẩn nuScenes...")
    np.random.seed(42)

    for f_idx in range(num_frames):
        # Mô phỏng xe di chuyển dọc trục Y (khoảng cách tăng dần theo thời gian)
        speed = 0.5 * f_idx

        # 1. Mặt đường: Z quanh -1.7m
        gx = np.random.uniform(-35, 35, 2500)
        gy = np.random.uniform(-35, 35, 2500)
        gz = np.random.uniform(-1.75, -1.65, 2500)
        gi = np.random.uniform(5, 25, 2500)
        ground = np.column_stack([gx, gy, gz, gi])

        # 2. Xe ô tô con (Car): di chuyển phía trước
        car_x = np.random.uniform(2.5, 6.5, 200)
        car_y = np.random.uniform(8.0 + speed, 12.0 + speed, 200)
        car_z = np.random.uniform(-1.6, -0.2, 200)
        car_i = np.random.uniform(40, 90, 200)
        car = np.column_stack([car_x, car_y, car_z, car_i])

        # 3. Xe tải (Truck): đi làn bên cạnh
        truck_x = np.random.uniform(-8.5, -4.5, 300)
        truck_y = np.random.uniform(15.0 + speed * 0.8, 22.0 + speed * 0.8, 300)
        truck_z = np.random.uniform(-1.6, 1.2, 300)
        truck_i = np.random.uniform(50, 100, 300)
        truck = np.column_stack([truck_x, truck_y, truck_z, truck_i])

        # 4. Người đi bộ (Pedestrian): trên vỉa hè bên phải
        ped_x = np.random.uniform(8.0, 9.0, 50)
        ped_y = np.random.uniform(5.0, 6.0, 50)
        ped_z = np.random.uniform(-1.6, 0.1, 50)
        ped_i = np.random.uniform(30, 60, 50)
        ped = np.column_stack([ped_x, ped_y, ped_z, ped_i])

        frame_pts = np.vstack([ground, car, truck, ped]).astype(np.float32)
        frame_file = pcd_folder / f"frame_{f_idx:04d}.pcd"
        save_pcd(frame_pts, frame_file, binary=True)

    # Đóng gói zip để người dùng tải 1 click về ném vào CVAT
    zip_path = output_dir / "nuscenes_sample_cvat.zip"
    print(f"📦 Đang đóng gói file ZIP sẵn sàng import CVAT: {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pcd_file in sorted(pcd_folder.glob("*.pcd")):
            zf.write(pcd_file, arcname=pcd_file.name)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"🎉 Hoàn tất! File sẵn sàng: {zip_path.resolve()} ({size_mb:.2f} MB)")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Tải và xử lý dữ liệu nuScenes LiDAR cho CVAT 3D")
    parser.add_argument(
        "--mode",
        choices=["sample", "full-mini", "convert"],
        default="sample",
        help="Chế độ: 'sample' (tạo bộ mẫu 20 frame .pcd), 'full-mini' (tải v1.0-mini.tgz trên Colab), 'convert' (convert .bin sang .pcd)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/nuscenes_sample",
        help="Thư mục xuất dữ liệu (mặc định: data/nuscenes_sample)",
    )
    parser.add_argument(
        "--bin-dir",
        type=str,
        default="data/nuscenes/samples/LIDAR_TOP",
        help="Thư mục chứa file .bin nuScenes (cho mode convert)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=40,
        help="Số lượng frame LiDAR tối đa cần xử lý (mặc định: 40)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)

    print("=" * 65)
    print("🚀 BẮT ĐẦU CHUẨN BỊ DỮ LIỆU NUSCENES LIDAR CHO CVAT 3D")
    print(f"🎯 Chế độ: {args.mode.upper()}")
    print(f"📂 Thư mục: {out_dir.resolve()}")
    print("=" * 65)

    if args.mode == "sample":
        zip_file = generate_synthetic_nuscenes_sequence(out_dir, num_frames=args.max_frames)
        print("\n📋 HƯỚNG DẪN TẠO TASK TRÊN CVAT CÁ NHÂN:")
        print(" 1. Mở CVAT (http://localhost:8080) -> Bấm '+' -> Create a new task.")
        print(" 2. Đặt tên: 'nuScenes 3D LiDAR Evaluation' -> Chọn Dimension: '3D'.")
        print(" 3. Nhập các nhãn: car, truck, bus, pedestrian, motorcycle, barrier.")
        print(f" 4. Kéo thả các file .pcd trong thư mục '{out_dir}/pcd_frames' hoặc giải nén file zip vào Task.")
        print(" 5. Bấm 'Submit & Open' -> Sẵn sàng chạy AI Auto-Sync từ Colab!")

    elif args.mode == "full-mini":
        tar_dest = out_dir / "v1.0-mini.tgz"
        out_dir.mkdir(parents=True, exist_ok=True)
        if not tar_dest.exists():
            download_with_progress(NUSCENES_MINI_URL, tar_dest)
        else:
            print(f"⏩ Đã có sẵn file nén: {tar_dest}")

        extract_lidar_from_tar(tar_dest, out_dir)
        lidar_dir = out_dir / "samples" / "LIDAR_TOP"
        pcd_dir = out_dir / "pcd_frames"
        convert_bin_dir_to_pcd(lidar_dir, pcd_dir, max_frames=args.max_frames)

    elif args.mode == "convert":
        bin_dir = Path(args.bin_dir)
        pcd_dir = out_dir / "pcd_frames"
        convert_bin_dir_to_pcd(bin_dir, pcd_dir, max_frames=args.max_frames)


if __name__ == "__main__":
    main()
