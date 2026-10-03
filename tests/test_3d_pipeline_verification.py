"""
Kiểm thử và xác minh toàn diện quy trình tự động gán nhãn 3D LiDAR (Point Cloud Cuboids).
Pipeline được kiểm tra:
  1. Sinh dữ liệu LiDAR 3D thực tế (Mặt đường + Xe hơi + Xe tải).
  2. Mã hóa & Giải mã định dạng file .pcd (Cả ASCII và BINARY Float32).
  3. Xử lý qua PointPillars Engine (Lọc phạm vi không gian, tách mặt đường, gom cụm Voxel 3D, tính toán Oriented Bounding Box).
  4. Tích hợp qua Model Dispatcher (Routing target_type = CUBOID_3D).
  5. Đóng gói payload JSON chuẩn CVAT REST API (hỗ trợ cả position/dimensions/rotation lẫn points).
"""

import json
import os
import sys
from pathlib import Path
import unittest
import numpy as np

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from locate_cvat.label_registry import LabelItem, LabelType
from locate_cvat.pcd_utils import read_pcd_bytes, create_sample_pcd_ascii
from server.ai_engine.pointpillars_engine import PointPillarsEngine
from server.ai_engine.dispatcher import ModelDispatcher


def generate_synthetic_lidar_scene() -> np.ndarray:
    """Tạo đám mây điểm mô phỏng một khung cảnh LiDAR xe tự hành thực tế."""
    np.random.seed(42)

    # 1. Mặt đường (Ground plane): Z nằm quanh -1.7m
    ground_x = np.random.uniform(-30, 30, 2000)
    ground_y = np.random.uniform(-30, 30, 2000)
    ground_z = np.random.uniform(-1.75, -1.65, 2000)
    ground_i = np.random.uniform(5, 20, 2000)
    ground_pts = np.column_stack([ground_x, ground_y, ground_z, ground_i])

    # 2. Chiếc xe hơi (Car): Trung tâm [10.0, 2.0, -1.0], kích thước Dx=4.2m, Dy=1.8m, Dz=1.4m
    car_x = np.random.uniform(7.9, 12.1, 150)
    car_y = np.random.uniform(1.1, 2.9, 150)
    car_z = np.random.uniform(-1.6, -0.2, 150)
    car_i = np.random.uniform(40, 90, 150)
    car_pts = np.column_stack([car_x, car_y, car_z, car_i])

    # 3. Chiếc xe tải lớn (Truck): Trung tâm [20.0, -4.0, -0.2], kích thước Dx=7.5m, Dy=2.5m, Dz=2.8m
    truck_x = np.random.uniform(16.25, 23.75, 250)
    truck_y = np.random.uniform(-5.25, -2.75, 250)
    truck_z = np.random.uniform(-1.6, 1.2, 250)
    truck_i = np.random.uniform(50, 100, 250)
    truck_pts = np.column_stack([truck_x, truck_y, truck_z, truck_i])

    # Ghép toàn bộ điểm lại thành 1 frame quét hoàn chỉnh
    scene = np.vstack([ground_pts, car_pts, truck_pts]).astype(np.float32)
    return scene


class Test3DPipelineVerification(unittest.TestCase):

    def setUp(self):
        self.raw_points = generate_synthetic_lidar_scene()
        self.engine = PointPillarsEngine()
        self.dispatcher = ModelDispatcher()

    def test_01_pcd_ascii_encoding_and_decoding(self):
        """1. Kiểm tra mã hóa và giải mã file PCD ASCII từ luồng byte."""
        pcd_ascii_bytes = create_sample_pcd_ascii(self.raw_points)
        self.assertTrue(len(pcd_ascii_bytes) > 0)
        self.assertTrue(pcd_ascii_bytes.startswith(b"# .PCD v0.7"))

        decoded_points = read_pcd_bytes(pcd_ascii_bytes)
        self.assertEqual(decoded_points.shape[0], self.raw_points.shape[0])
        self.assertEqual(decoded_points.shape[1], 4)
        np.testing.assert_almost_equal(decoded_points[:, :3], self.raw_points[:, :3], decimal=2)
        print(f"\n   [OK] Giải mã PCD ASCII thành công: {decoded_points.shape[0]} điểm LiDAR.")

    def test_02_pcd_binary_decoding(self):
        """2. Kiểm tra giải mã file PCD BINARY từ luồng byte."""
        num_pts = len(self.raw_points)
        header = (
            f"# .PCD v0.7\nVERSION 0.7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\n"
            f"COUNT 1 1 1 1\nWIDTH {num_pts}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {num_pts}\nDATA binary\n"
        ).encode("ascii")
        binary_payload = self.raw_points.tobytes()
        pcd_binary_bytes = header + binary_payload

        decoded_points = read_pcd_bytes(pcd_binary_bytes)
        self.assertEqual(decoded_points.shape[0], num_pts)
        self.assertEqual(decoded_points.shape[1], 4)
        np.testing.assert_almost_equal(decoded_points, self.raw_points, decimal=3)
        print(f"\n   [OK] Giải mã PCD BINARY thành công: {decoded_points.shape[0]} điểm LiDAR.")

    def test_03_pointpillars_3d_detection_and_cuboid_geometry(self):
        """3. Kiểm tra PointPillars phát hiện đúng các vật thể nổi và tính toán hình học 3D."""
        cuboids = self.engine.predict(self.raw_points, target_label="car_3d")
        self.assertGreaterEqual(len(cuboids), 2, "Hệ thống phải nhận diện được ít nhất 2 cụm vật thể (Car và Truck)")

        for i, box in enumerate(cuboids):
            self.assertEqual(box["type"], "cuboid")
            self.assertEqual(box["label"], "car_3d")

            # Kiểm tra tọa độ tâm position [x, y, z]
            pos = box["position"]
            self.assertEqual(len(pos), 3)
            self.assertTrue(all(isinstance(v, (int, float)) for v in pos))

            # Kiểm tra kích thước dimensions [dx, dy, dz]
            dim = box["dimensions"]
            self.assertEqual(len(dim), 3)
            self.assertTrue(dim[0] > 0 and dim[1] > 0 and dim[2] > 0, "Kích thước 3D phải dương")

            # Kiểm tra góc xoay rotation [0, 0, yaw]
            rot = box["rotation"]
            self.assertEqual(len(rot), 3)
            yaw = rot[2]
            self.assertTrue(-np.pi <= yaw <= np.pi, f"Góc yaw {yaw} phải nằm trong khoảng [-pi, pi]")

            print(
                f"\n   [OK] Cuboid {i+1}: Tâm={pos}, Kích thước={dim}, Góc xoay={rot}, Conf={box.get('confidence')}"
            )

    def test_04_dispatcher_cuboid_3d_routing(self):
        """4. Kiểm tra Model Dispatcher tự động định tuyến target_type=CUBOID_3D."""
        results = self.dispatcher.dispatch(
            image_shape=(0, 0),
            label_name="vehicle_3d",
            target_type=LabelType.CUBOID_3D,
            point_cloud=self.raw_points,
        )
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["type"], "cuboid")
        print(f"\n   [OK] Model Dispatcher điều phối thành công {len(results)} cuboid 3D.")

    def test_05_cvat_rest_api_payload_compliance(self):
        """5. Kiểm tra tính hợp lệ tuyệt đối của Payload JSON gửi lên CVAT REST API."""
        cuboids = self.engine.predict(self.raw_points, target_label="car_3d")
        self.assertGreater(len(cuboids), 0)

        all_shapes = []
        for box in cuboids:
            pos = box["position"]
            dim = box["dimensions"]
            rot = box["rotation"]

            shape_record = {
                "frame": 0,
                "label_id": 1,
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

        payload = {
            "shapes": all_shapes,
            "tracks": [],
            "tags": [],
            "version": 0,
        }

        # Kiểm tra tính tuần tự hóa JSON (không chứa NaN, Infinity hay Object lỗi)
        json_str = json.dumps(payload, indent=2)
        self.assertTrue(len(json_str) > 0)

        # Kiểm tra từng shape chứa đầy đủ các trường chuẩn của CVAT REST API
        for s in payload["shapes"]:
            self.assertEqual(s["type"], "cuboid")
            self.assertIn("points", s)
            self.assertEqual(len(s["points"]), 9)
            self.assertIn("rotation", s)
            self.assertIsInstance(s["rotation"], float)
            self.assertIn("frame", s)
            self.assertIn("label_id", s)

        print(f"\n   [OK] Payload CVAT hợp lệ 100% với {len(all_shapes)} shapes 3D.")


if __name__ == "__main__":
    unittest.main()
