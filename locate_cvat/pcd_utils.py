"""
PCD (Point Cloud Data) Utilities for CVAT 3D Tasks.
Hỗ trợ nạp và giải mã file đám mây điểm .pcd (ASCII / BINARY) và .bin (KITTI format)
tương thích với Open3D và tích hợp sẵn bộ giải mã thuần NumPy dự phòng.
"""

from __future__ import annotations

import io
import re
import struct
from pathlib import Path
from typing import Optional, Tuple, Union
import numpy as np

try:
    import open3d as o3d
except ImportError:
    o3d = None


def read_pcd_bytes(data: bytes) -> np.ndarray:
    """
    Đọc dữ liệu nhị phân PCD thành mảng numpy kích thước (N, 3) hoặc (N, 4).
    Hỗ trợ:
      1. Open3D (nếu có cài đặt)
      2. Bộ giải mã thuần NumPy cho PCD Header (ASCII & BINARY)
      3. Fallback mảng nhị phân KITTI float32 [x, y, z, i]
    """
    if not data or len(data) == 0:
        return np.zeros((0, 4), dtype=np.float32)

    # 1. Ưu tiên bộ giải mã thuần NumPy đọc trực tiếp PCD Header (Tốc độ cao, triệt tiêu warning in-memory của Open3D)
    try:
        points = _parse_pcd_numpy(data)
        if points is not None and len(points) > 0:
            return points
    except Exception:
        pass

    # 2. Dự phòng: Thử giải mã qua Open3D (cho định dạng khác như .ply)
    if o3d is not None:
        try:
            pcd = o3d.io.read_point_cloud_from_bytes(data)
            if len(pcd.points) > 0:
                pts = np.asarray(pcd.points, dtype=np.float32)
                # Ghép thêm trường intensity mặc định nếu chỉ có xyz
                if pts.shape[1] == 3:
                    intensity = np.zeros((pts.shape[0], 1), dtype=np.float32)
                    return np.hstack([pts, intensity])
                return pts
        except Exception:
            pass

    # 3. Fallback: Nếu là file nuScenes .bin (chuỗi float32 5 cột: x, y, z, intensity, ring_index)
    if len(data) % 20 == 0:
        try:
            pts5 = np.frombuffer(data, dtype=np.float32).reshape(-1, 5)
            return pts5[:, :4].astype(np.float32)  # Giữ lại [x, y, z, intensity]
        except Exception:
            pass

    # 4. Fallback: Nếu là file KITTI .bin (chuỗi float32 4 cột liên tục)
    if len(data) % 16 == 0:
        try:
            pts = np.frombuffer(data, dtype=np.float32).reshape(-1, 4)
            return pts
        except Exception:
            pass

    return np.zeros((0, 4), dtype=np.float32)


def _parse_pcd_numpy(data: bytes) -> Optional[np.ndarray]:
    """Phân tích cú pháp PCD header và trích xuất điểm dữ liệu thuần NumPy."""
    # Tìm ranh giới giữa Header và Data (kết thúc chính xác bằng dòng 'DATA ascii' hoặc 'DATA binary')
    header_end_match = re.search(rb"(DATA\s+(ascii|binary|binary_compressed)[^\S\r\n]*\r?\n)", data)
    if not header_end_match:
        return None

    header_bytes = data[: header_end_match.end()]
    payload_bytes = data[header_end_match.end() :]
    header_text = header_bytes.decode("ascii", errors="ignore")

    data_type = "ascii"
    fields = ["x", "y", "z"]
    sizes = [4, 4, 4]
    types = ["F", "F", "F"]
    counts = [1, 1, 1]
    num_points = 0

    for line in header_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        tag = parts[0].upper()

        if tag == "FIELDS":
            fields = [p.lower() for p in parts[1:]]
        elif tag == "SIZE":
            sizes = [int(p) for p in parts[1:]]
        elif tag == "TYPE":
            types = parts[1:]
        elif tag == "COUNT":
            counts = [int(p) for p in parts[1:]]
        elif tag == "POINTS":
            num_points = int(parts[1])
        elif tag == "DATA":
            data_type = parts[1].lower()

    if "x" not in fields or "y" not in fields or "z" not in fields:
        return None

    x_idx = fields.index("x")
    y_idx = fields.index("y")
    z_idx = fields.index("z")
    i_idx = fields.index("intensity") if "intensity" in fields else None

    # Xử lý DATA ascii
    if data_type == "ascii":
        lines = payload_bytes.decode("ascii", errors="ignore").splitlines()
        points = []
        for line in lines:
            vals = line.strip().split()
            if len(vals) >= len(fields):
                x = float(vals[x_idx])
                y = float(vals[y_idx])
                z = float(vals[z_idx])
                intensity = float(vals[i_idx]) if i_idx is not None else 0.0
                points.append([x, y, z, intensity])
        return np.array(points, dtype=np.float32)

    # Xử lý DATA binary (Float32 uncompressed)
    elif data_type == "binary":
        # Giả định các trường tiêu chuẩn Float32 (4 bytes / field)
        row_size = sum(sizes)
        if len(payload_bytes) >= num_points * row_size:
            arr = np.frombuffer(payload_bytes[: num_points * row_size], dtype=np.float32)
            cols = len(fields)
            if arr.size % cols == 0:
                grid = arr.reshape(-1, cols)
                x = grid[:, x_idx]
                y = grid[:, y_idx]
                z = grid[:, z_idx]
                intensity = grid[:, i_idx] if i_idx is not None else np.zeros_like(x)
                return np.column_stack([x, y, z, intensity]).astype(np.float32)

    return None


def create_sample_pcd_ascii(points: np.ndarray) -> bytes:
    """Tạo chuỗi byte PCD ASCII mẫu phục vụ unit test và mô phỏng dữ liệu."""
    header = (
        "# .PCD v0.7 - Point Cloud Data\n"
        "VERSION 0.7\n"
        "FIELDS x y z intensity\n"
        "SIZE 4 4 4 4\n"
        "TYPE F F F F\n"
        "COUNT 1 1 1 1\n"
        f"WIDTH {len(points)}\n"
        "HEIGHT 1\n"
        "VIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {len(points)}\n"
        "DATA ascii\n"
    )
    lines = [f"{pt[0]:.3f} {pt[1]:.3f} {pt[2]:.3f} {pt[3]:.1f}" for pt in points]
    return (header + "\n".join(lines) + "\n").encode("ascii")


def create_pcd_binary(points: np.ndarray) -> bytes:
    """Tạo chuỗi byte PCD BINARY (Float32 uncompressed) tối ưu dung lượng cho CVAT."""
    num_pts = len(points)
    if points.shape[1] == 3:
        intensity = np.zeros((num_pts, 1), dtype=np.float32)
        pts = np.hstack([points, intensity]).astype(np.float32)
    else:
        pts = points[:, :4].astype(np.float32)

    header = (
        f"# .PCD v0.7 - Point Cloud Data\n"
        f"VERSION 0.7\n"
        f"FIELDS x y z intensity\n"
        f"SIZE 4 4 4 4\n"
        f"TYPE F F F F\n"
        f"COUNT 1 1 1 1\n"
        f"WIDTH {num_pts}\n"
        f"HEIGHT 1\n"
        f"VIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {num_pts}\n"
        f"DATA binary\n"
    ).encode("ascii")

    return header + pts.tobytes()


def save_pcd(points: np.ndarray, filepath: Union[str, Path], binary: bool = True) -> Path:
    """Lưu mảng điểm NumPy thành file .pcd trên ổ đĩa để kéo thả vào CVAT Task."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = create_pcd_binary(points) if binary else create_sample_pcd_ascii(points)
    with open(path, "wb") as f:
        f.write(payload)
    return path
