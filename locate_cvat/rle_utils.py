"""
CVAT RLE Utilities - Mã hóa và giải mã Bitmap Mask chuẩn Run-Length Encoding (RLE) của CVAT.
Tuân thủ đặc tả CVAT REST API:
  points = [rle_0, rle_1, rle_2, ..., xtl, ytl, xbr, ybr]
Trong đó:
  - rle_0: số lượng pixel 0 (background) đầu tiên. Nếu pixel đầu tiên là 1, rle_0 = 0.
  - rle_1: số lượng pixel 1 (foreground) tiếp theo.
  - Luân phiên giữa 0 và 1.
  - 4 số cuối cùng: tọa độ hộp bao [left, top, right, bottom].
"""

from __future__ import annotations

from typing import List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw


def mask_to_cvat_rle(binary_mask: np.ndarray, bbox: Optional[List[float]] = None) -> List[float]:
    """
    Chuyển ma trận boolean/nhị phân 2D thành mảng points chuẩn RLE của CVAT.
    """
    if binary_mask is None or binary_mask.size == 0:
        return []

    rows, cols = np.where(binary_mask)
    if len(rows) == 0:
        return []

    if bbox is None:
        y1, y2 = int(np.min(rows)), int(np.max(rows))
        x1, x2 = int(np.min(cols)), int(np.max(cols))
    else:
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        h, w = binary_mask.shape
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        if x2 < x1 or y2 < y1:
            return []

    # Cắt vùng bên trong bbox
    crop = binary_mask[y1:y2 + 1, x1:x2 + 1].astype(bool)
    flat = crop.flatten()

    if len(flat) == 0:
        return []

    # Thuật toán RLE luân phiên 0 và 1, bắt đầu bằng 0
    diffs = np.diff(flat)
    change_indices = np.where(diffs)[0] + 1
    split_indices = np.concatenate(([0], change_indices, [len(flat)]))
    run_lengths = np.diff(split_indices).tolist()

    # Nếu pixel đầu tiên là 1, chèn độ dài chuỗi 0 là 0 vào đầu
    if flat[0]:
        run_lengths.insert(0, 0)

    # Đảm bảo các giá trị là float/int hợp lệ và gắn bbox vào cuối
    result = [float(v) for v in run_lengths]
    result.extend([float(x1), float(y1), float(x2), float(y2)])
    return result


def poly_to_cvat_rle(
    poly_flat: List[float],
    image_shape: Tuple[int, int],
    bbox: Optional[List[float]] = None,
) -> List[float]:
    """
    Chuyển đổi chuỗi tọa độ đa giác phẳng [x1, y1, x2, y2, ...] thành chuỗi points RLE của CVAT.
    """
    if not poly_flat or len(poly_flat) < 6:
        return []

    h, w = image_shape
    poly_tuples = [(poly_flat[i], poly_flat[i + 1]) for i in range(0, len(poly_flat), 2)]

    img_mask = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(img_mask)
    draw.polygon(poly_tuples, outline=1, fill=1)
    binary_mask = np.array(img_mask, dtype=bool)

    return mask_to_cvat_rle(binary_mask, bbox=bbox)


def cvat_rle_to_mask(points: List[float]) -> Optional[Tuple[np.ndarray, List[float]]]:
    """
    Giải mã mảng points CVAT RLE thành ma trận boolean 2D và bounding box [x1, y1, x2, y2].
    """
    if len(points) < 5:
        return None

    rle_vals = [int(v) for v in points[:-4]]
    x1, y1, x2, y2 = [int(round(v)) for v in points[-4:]]
    bw = x2 - x1 + 1
    bh = y2 - y1 + 1

    if bw <= 0 or bh <= 0:
        return None

    total_pixels = bw * bh
    flat = np.zeros(total_pixels, dtype=bool)

    curr_idx = 0
    val = False  # Bắt đầu với 0 (background)
    for length in rle_vals:
        if length > 0:
            flat[curr_idx:curr_idx + length] = val
            curr_idx += length
        val = not val

    crop_mask = flat[:total_pixels].reshape((bh, bw))
    return crop_mask, [float(x1), float(y1), float(x2), float(y2)]
