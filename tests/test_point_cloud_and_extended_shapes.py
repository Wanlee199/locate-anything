"""
Unit tests for 3D Point Cloud LiDAR Engine & Extended Multi-Modal Shapes.
Kiểm thử toàn diện:
  1. Giải mã dữ liệu PCD Header & Data thuần NumPy (pcd_utils)
  2. PointPillars 3D Cuboids Detection & Voxel Clustering (pointpillars_engine)
  3. Shape Adapters: Mask to Polyline và Mask to Ellipse (shape_adapters)
  4. Model Dispatcher tích hợp Point Cloud và Extended Types (3D, Ellipse, Tag)
"""

import unittest
import numpy as np

from locate_cvat.label_registry import LabelRegistry, LabelType
from locate_cvat.pcd_utils import read_pcd_bytes, create_sample_pcd_ascii
from server.ai_engine.pointpillars_engine import PointPillarsEngine
from server.ai_engine.shape_adapters import ShapeAdapters
from server.ai_engine.dispatcher import ModelDispatcher


class TestPointCloudAndExtendedShapes(unittest.TestCase):

    def setUp(self):
        self.engine = PointPillarsEngine()
        self.dispatcher = ModelDispatcher()

    def test_pcd_utils_read_ascii(self):
        """Kiểm tra tạo và giải mã file PCD ASCII."""
        # Tạo 20 điểm mẫu
        sample_pts = np.array([
            [float(i) * 0.5, float(i) * 0.2, 0.5, 10.0] for i in range(20)
        ], dtype=np.float32)

        pcd_bytes = create_sample_pcd_ascii(sample_pts)
        self.assertTrue(len(pcd_bytes) > 0)

        parsed_pts = read_pcd_bytes(pcd_bytes)
        self.assertEqual(len(parsed_pts), 20)
        self.assertEqual(parsed_pts.shape[1], 4)
        np.testing.assert_almost_equal(parsed_pts[0, :3], sample_pts[0, :3], decimal=2)

    def test_pointpillars_predict_cluster(self):
        """Kiểm tra PointPillars phát hiện vật thể 3D từ cụm điểm LiDAR."""
        # Tạo cụm điểm mô phỏng 1 chiếc xe tải (kích thước x: 3m, y: 2m, z: 1.5m)
        xs = np.linspace(5.0, 8.0, 10)
        ys = np.linspace(1.0, 3.0, 10)
        zs = np.linspace(-0.5, 1.0, 10)
        grid_x, grid_y, grid_z = np.meshgrid(xs, ys, zs)
        pts = np.column_stack([
            grid_x.flatten(),
            grid_y.flatten(),
            grid_z.flatten(),
            np.ones(grid_x.size) * 50.0,
        ]).astype(np.float32)

        predictions = self.engine.predict(pts, target_label="truck_3d")
        self.assertTrue(len(predictions) > 0)

        box = predictions[0]
        self.assertEqual(box["type"], "cuboid")
        self.assertEqual(box["label"], "truck_3d")
        self.assertEqual(len(box["position"]), 3)
        self.assertEqual(len(box["dimensions"]), 3)
        self.assertTrue(box["dimensions"][0] > 0)
        self.assertTrue(box["dimensions"][1] > 0)
        self.assertTrue(box["dimensions"][2] > 0)

    def test_dispatcher_point_cloud_cuboid(self):
        """Kiểm tra Dispatcher xử lý dữ liệu đám mây điểm 3D."""
        xs = np.linspace(10.0, 14.0, 10)
        ys = np.linspace(0.0, 2.5, 10)
        zs = np.linspace(0.0, 1.5, 10)
        grid_x, grid_y, grid_z = np.meshgrid(xs, ys, zs)
        pts = np.column_stack([
            grid_x.flatten(), grid_y.flatten(), grid_z.flatten(), np.ones(grid_x.size) * 20.0
        ]).astype(np.float32)

        results = self.dispatcher.dispatch(
            image_shape=(0, 0),
            label_name="truck_3d",
            target_type=LabelType.CUBOID_3D,
            point_cloud=pts,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["type"], "cuboid")
        self.assertIn("position", results[0])
        self.assertIn("dimensions", results[0])
        self.assertIn("rotation", results[0])

    def test_shape_adapter_ellipse(self):
        """Kiểm tra ShapeAdapters fit phương trình elip từ mask."""
        mask = np.zeros((200, 200), dtype=np.uint8)
        # Vẽ hình bầu dục trên mask
        y, x = np.ogrid[:200, :200]
        ellipse_region = ((x - 100) / 40) ** 2 + ((y - 100) / 20) ** 2 <= 1
        mask[ellipse_region] = 1

        res = ShapeAdapters.mask_to_ellipse(mask)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "ellipse")
        self.assertAlmostEqual(res["cx"], 100, delta=5)
        self.assertAlmostEqual(res["cy"], 100, delta=5)
        self.assertTrue(res["rx"] > 0)
        self.assertTrue(res["ry"] > 0)

    def test_shape_adapter_polyline(self):
        """Kiểm tra ShapeAdapters trích xuất Polyline tim đường."""
        mask = np.zeros((200, 200), dtype=np.uint8)
        # Vẽ một dải vạch kẻ thẳng dài
        mask[50:150, 95:105] = 1

        poly_coords = ShapeAdapters.mask_to_polyline(mask)
        self.assertTrue(len(poly_coords) >= 4)

    def test_dispatch_ellipse_and_tag(self):
        """Kiểm tra Dispatcher hỗ trợ nhãn Ellipse và Tag."""
        # 1. Ellipse
        res_ellipse = self.dispatcher.dispatch(
            image_shape=(1080, 1920),
            label_name="traffic_sign_circle",
            target_type=LabelType.ELLIPSE,
        )
        self.assertEqual(res_ellipse[0]["type"], "ellipse")
        self.assertIn("cx", res_ellipse[0])
        self.assertIn("rx", res_ellipse[0])

        # 2. Tag
        dummy_img = np.ones((100, 100, 3), dtype=np.uint8) * 150
        res_tag = self.dispatcher.dispatch(
            image_shape=(100, 100),
            label_name="scene_weather",
            image=dummy_img,
            target_type=LabelType.TAG,
        )
        self.assertEqual(res_tag[0]["type"], "tag")
        self.assertIn("tag_value", res_tag[0])


if __name__ == "__main__":
    unittest.main()
