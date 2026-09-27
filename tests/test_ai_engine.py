"""
Unit tests for Server AI Engine, Model Dispatcher and FastAPI Service.
Kiểm thử toàn diện định tuyến AI cho cả 6 dạng nhãn (box, polygon, mask, line, 3d, skeleton).
"""

import base64
import io
import unittest
from pathlib import Path
from PIL import Image

from locate_cvat import LabelRegistry
from server.ai_engine.dispatcher import ModelDispatcher
from fastapi.testclient import TestClient
from server.api_service import app


class TestAIEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config_path = Path("configs/labels_config.yaml")
        cls.registry = LabelRegistry.load_from_yaml(cls.config_path)
        cls.dispatcher = ModelDispatcher(registry=cls.registry)
        cls.client = TestClient(app)

    def test_dispatch_box(self):
        """Kiểm tra định tuyến nhãn Box."""
        res = self.dispatcher.dispatch(
            image_shape=(1080, 1920),
            label_name="car",
        )
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["type"], "rectangle")
        self.assertEqual(res[0]["label"], "car")
        self.assertEqual(len(res[0]["points"]), 4)

    def test_dispatch_polygon_sam2(self):
        """Kiểm tra định tuyến nhãn Polygon tới SAM 2.1."""
        res = self.dispatcher.dispatch(
            image_shape=(1080, 1920),
            label_name="road_damage",
            points=[[500.0, 400.0]],
        )
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["type"], "polygon")
        self.assertEqual(res[0]["label"], "road_damage")
        self.assertTrue(len(res[0]["points"]) >= 6)

    def test_dispatch_skeleton(self):
        """Kiểm tra định tuyến nhãn Skeleton."""
        res = self.dispatcher.dispatch(
            image_shape=(1080, 1920),
            label_name="human_pose",
        )
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["type"], "skeleton")
        self.assertEqual(res[0]["label"], "human_pose")
        self.assertTrue(len(res[0]["elements"]) > 0)

    def test_dispatch_line(self):
        """Kiểm tra định tuyến nhãn Line (Polyline)."""
        res = self.dispatcher.dispatch(
            image_shape=(1080, 1920),
            label_name="lane_divider_white",
        )
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["type"], "polyline")

    def test_dispatch_3d_cuboid(self):
        """Kiểm tra định tuyến nhãn 3D Cuboid."""
        res = self.dispatcher.dispatch(
            image_shape=(1080, 1920),
            label_name="truck_3d",
        )
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["type"], "cuboid")
        self.assertIn("center", res[0])
        self.assertIn("dimensions", res[0])

    def test_fastapi_endpoints(self):
        """Kiểm tra các endpoints của FastAPI Service."""
        # 1. Health check
        r_health = self.client.get("/health")
        self.assertEqual(r_health.status_code, 200)
        self.assertEqual(r_health.json()["status"], "healthy")

        # 2. Labels list
        r_labels = self.client.get("/api/labels")
        self.assertEqual(r_labels.status_code, 200)
        self.assertTrue(len(r_labels.json()["labels"]) >= 6)

        # 3. Annotate endpoint
        img = Image.new("RGB", (200, 200), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        r_ann = self.client.post(
            "/api/annotate",
            json={
                "image_base64": img_b64,
                "label_name": "car",
            },
        )
        self.assertEqual(r_ann.status_code, 200)
        data = r_ann.json()
        self.assertEqual(data["label_name"], "car")
        self.assertTrue(len(data["annotations"]) > 0)


if __name__ == "__main__":
    unittest.main()
