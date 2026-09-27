"""
Unit tests for Universal Multi-Modal Label Registry & Translators.
Kiểm thử toàn diện 6 dạng nhãn (box, line, 3d, polygon, mask, skeleton).
"""

import os
import tempfile
import unittest
from pathlib import Path

from locate_cvat import (
    LabelRegistry,
    LabelType,
    LabelItem,
    COCOTranslator,
    SkeletonCOCOTranslator,
    CuboidAndPolylineTranslator,
)


class TestLabelRegistry(unittest.TestCase):

    def setUp(self):
        self.config_path = Path("configs/labels_config.yaml")

    def test_load_yaml_config(self):
        """Kiểm tra đọc file cấu hình YAML chuẩn."""
        registry = LabelRegistry.load_from_yaml(self.config_path)
        self.assertTrue(len(registry.labels) >= 6)

        # Kiểm tra đầy đủ 6 loại nhãn
        types_in_registry = {lbl.type for lbl in registry.labels}
        self.assertIn(LabelType.BOX, types_in_registry)
        self.assertIn(LabelType.POLYGON, types_in_registry)
        self.assertIn(LabelType.MASK, types_in_registry)
        self.assertIn(LabelType.LINE, types_in_registry)
        self.assertIn(LabelType.CUBOID_3D, types_in_registry)
        self.assertIn(LabelType.SKELETON, types_in_registry)

    def test_cvat_spec_export(self):
        """Kiểm tra xuất cấu hình chuẩn CVAT Project Labels Specification."""
        registry = LabelRegistry.load_from_yaml(self.config_path)
        cvat_spec = registry.to_cvat_spec()

        self.assertEqual(len(cvat_spec), len(registry.labels))

        # Kiểm tra nhãn box 'car'
        car_spec = next(s for s in cvat_spec if s["name"] == "car")
        self.assertEqual(car_spec["type"], "rectangle")
        self.assertTrue(len(car_spec["attributes"]) >= 1)

        # Kiểm tra nhãn skeleton 'human_pose'
        pose_spec = next(s for s in cvat_spec if s["name"] == "human_pose")
        self.assertEqual(pose_spec["type"], "skeleton")
        self.assertIn("sublabels", pose_spec)
        self.assertEqual(len(pose_spec["sublabels"]), 17)
        self.assertIn("svg", pose_spec)
        self.assertTrue("<line " in pose_spec["svg"])

    def test_validation_errors(self):
        """Kiểm tra bắt lỗi duplicate name và skeleton không hợp lệ."""
        # 1. Trùng lặp tên nhãn
        with self.assertRaises(ValueError):
            LabelRegistry(
                labels=[
                    LabelItem(name="car", type=LabelType.BOX),
                    LabelItem(name="car", type=LabelType.BOX),
                ]
            )

        # 2. Skeleton thiếu nodes
        with self.assertRaises(ValueError):
            LabelRegistry(
                labels=[
                    LabelItem(name="broken_pose", type=LabelType.SKELETON),
                ]
            )

    def test_coco_box_and_polygon_translator(self):
        """Kiểm tra xuất COCO 1.0 cho box và polygon."""
        registry = LabelRegistry.load_from_yaml(self.config_path)
        translator = COCOTranslator(registry)

        images = [{"id": 1, "file_name": "street.jpg", "width": 1920, "height": 1080}]
        ann1 = translator.create_annotation(
            annotation_id=1,
            image_id=1,
            label_name="car",
            bbox=[100.0, 150.0, 200.0, 100.0],
            score=0.95,
        )
        ann2 = translator.create_annotation(
            annotation_id=2,
            image_id=1,
            label_name="road_damage",
            segmentation=[[50.0, 50.0, 150.0, 50.0, 150.0, 150.0, 50.0, 150.0]],
            score=0.88,
        )

        coco_data = translator.export_coco(images, [ann1, ann2])
        self.assertIn("info", coco_data)
        self.assertEqual(len(coco_data["annotations"]), 2)
        self.assertEqual(coco_data["annotations"][0]["area"], 20000.0)
        self.assertEqual(coco_data["annotations"][1]["area"], 10000.0)

    def test_coco_keypoints_translator(self):
        """Kiểm tra xuất COCO Keypoints cho skeleton."""
        registry = LabelRegistry.load_from_yaml(self.config_path)
        translator = SkeletonCOCOTranslator(registry)

        # 17 keypoints giả định
        coords = [(100.0 + i * 5, 200.0 + i * 10, 2) for i in range(17)]
        ann = translator.create_skeleton_annotation(
            annotation_id=1,
            image_id=1,
            label_name="human_pose",
            keypoints_coords=coords,
        )

        self.assertEqual(ann["num_keypoints"], 17)
        self.assertEqual(len(ann["keypoints"]), 17 * 3)
        self.assertTrue(ann["area"] > 0)
        self.assertEqual(len(ann["bbox"]), 4)

    def test_cuboid_and_polyline_translator(self):
        """Kiểm tra xuất CVAT XML cho 3D Cuboid và Line."""
        registry = LabelRegistry.load_from_yaml(self.config_path)
        translator = CuboidAndPolylineTranslator(registry)

        line_item = translator.create_polyline_item(
            label_name="lane_divider_white",
            points=[[100.0, 500.0], [200.0, 600.0], [300.0, 700.0]],
            attributes={"line_style": "dashed"},
        )
        cuboid_item = translator.create_cuboid_3d_item(
            label_name="truck_3d",
            center=[10.5, 2.0, -1.2],
            dimensions=[4.8, 2.1, 2.5],
            rotation=[0.0, 0.0, 1.57],
            attributes={"motion_state": "moving"},
        )

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            xml_str = translator.export_cvat_xml(
                image_name="test_road.jpg",
                image_width=1920,
                image_height=1080,
                shapes=[line_item, cuboid_item],
                output_filepath=tmp_path,
            )
            self.assertIn("<polyline", xml_str)
            self.assertIn("<cuboid", xml_str)
            self.assertIn("lane_divider_white", xml_str)
            self.assertIn("truck_3d", xml_str)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
