"""
CVAT Universal Multi-Modal Label Registry & Schema Validator.
Hỗ trợ đầy đủ 6 dạng hình thái gán nhãn:
  1. Box (2D Bounding Box: rectangle)
  2. Polygon (Đa giác khép kín)
  3. Mask (Bitmap / RLE segmentation)
  4. Line (Polyline: vạch kẻ đường, ranh giới)
  5. 3D (Cuboid: 3D bounding box)
  6. Skeleton (Pose estimation: nodes khớp + edges xương)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None


class LabelType(str, Enum):
    BOX = "box"
    POLYGON = "polygon"
    MASK = "mask"
    LINE = "line"
    CUBOID_3D = "3d"
    SKELETON = "skeleton"
    ELLIPSE = "ellipse"
    TAG = "tag"

    @classmethod
    def from_str(cls, val: str) -> "LabelType":
        val_clean = val.strip().lower()
        mapping = {
            "box": cls.BOX,
            "rectangle": cls.BOX,
            "bbox": cls.BOX,
            "polygon": cls.POLYGON,
            "poly": cls.POLYGON,
            "mask": cls.MASK,
            "segmentation": cls.MASK,
            "line": cls.LINE,
            "polyline": cls.LINE,
            "3d": cls.CUBOID_3D,
            "cuboid": cls.CUBOID_3D,
            "cuboid_3d": cls.CUBOID_3D,
            "skeleton": cls.SKELETON,
            "pose": cls.SKELETON,
            "keypoints": cls.SKELETON,
            "ellipse": cls.ELLIPSE,
            "circle": cls.ELLIPSE,
            "tag": cls.TAG,
            "classification": cls.TAG,
        }
        if val_clean in mapping:
            return mapping[val_clean]
        raise ValueError(
            f"Không hỗ trợ loại nhãn '{val}'. Các loại hỗ trợ: box, polygon, mask, line, 3d, skeleton, ellipse, tag"
        )

    def to_cvat_type(self) -> str:
        """Chuyển đổi sang type tương ứng của CVAT specification."""
        mapping = {
            LabelType.BOX: "rectangle",
            LabelType.POLYGON: "polygon",
            LabelType.MASK: "mask",
            LabelType.LINE: "polyline",
            LabelType.CUBOID_3D: "cuboid",
            LabelType.SKELETON: "skeleton",
            LabelType.ELLIPSE: "ellipse",
            LabelType.TAG: "tag",
        }
        return mapping[self]


@dataclass
class LabelAttribute:
    name: str
    input_type: str = "select"  # select | checkbox | radio | number | text
    values: List[str] = field(default_factory=list)
    default_value: str = ""
    mutable: bool = True

    def to_cvat_spec(self) -> Dict[str, Any]:
        spec: Dict[str, Any] = {
            "name": self.name,
            "input_type": self.input_type,
            "mutable": self.mutable,
            "values": self.values if self.values else ([self.default_value] if self.default_value else []),
        }
        if self.default_value:
            spec["default_value"] = self.default_value
        return spec


@dataclass
class SkeletonNode:
    id: int
    name: str
    color: str = "#00ff00"


@dataclass
class SkeletonConfig:
    nodes: List[SkeletonNode] = field(default_factory=list)
    edges: List[Tuple[int, int]] = field(default_factory=list)

    def validate(self) -> None:
        """Kiểm tra tính toàn vẹn của đồ thị khung xương."""
        node_ids = {n.id for n in self.nodes}
        node_names = [n.name for n in self.nodes]

        if len(node_names) != len(set(node_names)):
            raise ValueError(f"Tên các khớp (nodes) trong skeleton không được trùng lặp: {node_names}")

        for u, v in self.edges:
            if u not in node_ids:
                raise ValueError(f"Khớp ID {u} trong edge [{u}, {v}] không tồn tại trong danh sách nodes")
            if v not in node_ids:
                raise ValueError(f"Khớp ID {v} trong edge [{u}, {v}] không tồn tại trong danh sách nodes")

    def to_cvat_sublabels(self) -> List[Dict[str, Any]]:
        """Chuyển các nodes thành danh sách sublabels dạng points trong CVAT."""
        sublabels = []
        for node in self.nodes:
            sublabels.append({
                "name": node.name,
                "color": node.color,
                "type": "points",
                "attributes": [],
            })
        return sublabels

    def to_cvat_svg(self) -> str:
        """Tạo chuỗi SVG skeleton graph kết nối các sublabels cho CVAT."""
        lines = []
        node_map = {n.id: n.name for n in self.nodes}
        for u, v in self.edges:
            lines.append(f'<line data-node-from="{node_map[u]}" data-node-to="{node_map[v]}"></line>')
        return "".join(lines)


@dataclass
class LabelItem:
    name: str
    type: LabelType
    color: str = "#ff0000"
    hotkey: Optional[str] = None
    description: str = ""
    model_backend: str = "auto"
    attributes: List[LabelAttribute] = field(default_factory=list)
    skeleton_config: Optional[SkeletonConfig] = None

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Tên nhãn không được để trống")
        if self.type == LabelType.SKELETON:
            if not self.skeleton_config or not self.skeleton_config.nodes:
                raise ValueError(f"Nhãn skeleton '{self.name}' phải có cấu hình nodes khớp xương")
            self.skeleton_config.validate()

    def to_cvat_spec(self) -> Dict[str, Any]:
        """Tạo payload cấu hình nhãn chuẩn CVAT API."""
        spec: Dict[str, Any] = {
            "name": self.name,
            "color": self.color,
            "type": self.type.to_cvat_type(),
            "attributes": [attr.to_cvat_spec() for attr in self.attributes],
        }
        if self.type == LabelType.SKELETON and self.skeleton_config:
            spec["sublabels"] = self.skeleton_config.to_cvat_sublabels()
            spec["svg"] = self.skeleton_config.to_cvat_svg()

        return spec


class LabelRegistry:
    """
    Registry quản lý danh mục nhãn tập trung, độc lập với tool lõi.
    Cung cấp các hàm load, validate, filter và export sang CVAT / COCO specs.
    """

    def __init__(
        self,
        project_name: str = "CVAT Project",
        version: str = "1.0",
        description: str = "",
        labels: Optional[List[LabelItem]] = None,
    ):
        self.project_name = project_name
        self.version = version
        self.description = description
        self.labels: List[LabelItem] = labels or []
        self._validate_all()

    def _validate_all(self) -> None:
        seen_names = set()
        for label in self.labels:
            if label.name in seen_names:
                raise ValueError(f"Trùng lặp tên nhãn trong danh mục: '{label.name}'")
            seen_names.add(label.name)
            label.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LabelRegistry":
        project_name = data.get("project_name", "CVAT Project")
        version = str(data.get("version", "1.0"))
        description = data.get("description", "")
        raw_labels = data.get("labels", [])

        labels: List[LabelItem] = []
        for raw in raw_labels:
            label_type = LabelType.from_str(raw.get("type", "box"))

            # Attributes
            raw_attrs = raw.get("attributes", [])
            attributes = [
                LabelAttribute(
                    name=attr["name"],
                    input_type=attr.get("input_type", "select"),
                    values=attr.get("values", []),
                    default_value=str(attr.get("default_value", "")),
                    mutable=attr.get("mutable", True),
                )
                for attr in raw_attrs
            ]

            # Skeleton
            skeleton_config = None
            if label_type == LabelType.SKELETON and "skeleton_config" in raw:
                sk_data = raw["skeleton_config"]
                nodes = [
                    SkeletonNode(
                        id=int(n["id"]),
                        name=n["name"],
                        color=n.get("color", "#00ff00"),
                    )
                    for n in sk_data.get("nodes", [])
                ]
                edges = [
                    (int(edge[0]), int(edge[1]))
                    for edge in sk_data.get("edges", [])
                ]
                skeleton_config = SkeletonConfig(nodes=nodes, edges=edges)

            item = LabelItem(
                name=raw["name"],
                type=label_type,
                color=raw.get("color", "#ff0000"),
                hotkey=str(raw.get("hotkey", "")) if raw.get("hotkey") is not None else None,
                description=raw.get("description", ""),
                model_backend=raw.get("model_backend", "auto"),
                attributes=attributes,
                skeleton_config=skeleton_config,
            )
            labels.append(item)

        return cls(
            project_name=project_name,
            version=version,
            description=description,
            labels=labels,
        )

    @classmethod
    def load_from_yaml(cls, filepath: Union[str, Path]) -> "LabelRegistry":
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file cấu hình nhãn tại: {filepath}")

        if yaml is None:
            raise ImportError("PyYAML chưa được cài đặt. Vui lòng cài qua `pip install pyyaml`.")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def load_from_json(cls, filepath: Union[str, Path]) -> "LabelRegistry":
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file cấu hình nhãn tại: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Hỗ trợ tự động nhận diện nếu file là raw CVAT JSON (dạng list các nhãn)
        if isinstance(data, list):
            return cls.from_cvat_raw_spec(data, project_name=path.stem)

        return cls.from_dict(data)

    @classmethod
    def from_cvat_raw_spec(
        cls,
        raw_spec: List[Dict[str, Any]],
        project_name: str = "Imported CVAT Project",
    ) -> "LabelRegistry":
        """
        Nhập trực tiếp từ danh sách nhãn raw JSON chuẩn của CVAT:
        [{"name": "car", "type": "rectangle", ...}, {"name": "pose", "type": "skeleton", ...}]
        """
        import re

        cvat_to_internal = {
            "rectangle": LabelType.BOX,
            "polygon": LabelType.POLYGON,
            "mask": LabelType.MASK,
            "polyline": LabelType.LINE,
            "cuboid": LabelType.CUBOID_3D,
            "skeleton": LabelType.SKELETON,
            "points": LabelType.BOX,
            "any": LabelType.BOX,
        }

        labels: List[LabelItem] = []
        for raw in raw_spec:
            name = raw.get("name", "")
            cvat_type_str = raw.get("type", "rectangle").lower()
            label_type = cvat_to_internal.get(cvat_type_str, LabelType.BOX)
            color = raw.get("color", "#ff0000")

            # Attributes
            attributes = [
                LabelAttribute(
                    name=attr["name"],
                    input_type=attr.get("input_type", "select"),
                    values=attr.get("values", []),
                    default_value=str(attr.get("default_value", "")),
                    mutable=attr.get("mutable", True),
                )
                for attr in raw.get("attributes", [])
            ]

            # Skeleton
            skeleton_config = None
            if label_type == LabelType.SKELETON:
                sublabels = raw.get("sublabels", [])
                node_name_to_id = {}
                nodes = []
                for idx, sl in enumerate(sublabels):
                    n_name = sl.get("name", f"joint_{idx}")
                    node_name_to_id[n_name] = idx
                    nodes.append(
                        SkeletonNode(
                            id=idx,
                            name=n_name,
                            color=sl.get("color", "#00ff00"),
                        )
                    )

                edges: List[Tuple[int, int]] = []
                svg_str = raw.get("svg", "")
                if svg_str:
                    # Trích xuất các cặp line: <line data-node-from="A" data-node-to="B"></line>
                    pattern = r'data-node-from="([^"]+)"\s+data-node-to="([^"]+)"'
                    for match in re.finditer(pattern, svg_str):
                        from_node, to_node = match.group(1), match.group(2)
                        if from_node in node_name_to_id and to_node in node_name_to_id:
                            edges.append((node_name_to_id[from_node], node_name_to_id[to_node]))

                skeleton_config = SkeletonConfig(nodes=nodes, edges=edges)

            labels.append(
                LabelItem(
                    name=name,
                    type=label_type,
                    color=color,
                    attributes=attributes,
                    skeleton_config=skeleton_config,
                )
            )

        return cls(
            project_name=project_name,
            version="1.0",
            description="Imported from raw CVAT specification",
            labels=labels,
        )

    def push_to_cvat_api(
        self,
        server_url: str,
        project_id: int,
        token: Optional[str] = None,
        basic_auth: Optional[Tuple[str, str]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Đẩy trực tiếp danh mục nhãn lên Project trên Server CVAT thông qua REST API (PATCH /api/projects/{id}).
        """
        import base64
        import urllib.request
        import urllib.error

        clean_url = server_url.rstrip("/")
        endpoint = f"{clean_url}/api/projects/{project_id}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Token {token}"
        elif basic_auth:
            creds = f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")
            headers["Authorization"] = f"Basic {base64.b64encode(creds).decode('utf-8')}"

        payload = json.dumps({"labels": self.to_cvat_spec()}).encode("utf-8")
        req = urllib.request.Request(endpoint, data=payload, headers=headers, method="PATCH")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                resp_data = response.read().decode("utf-8")
                return json.loads(resp_data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"CVAT API Error {e.code} ({e.reason}): {err_body}")
        except Exception as e:
            raise RuntimeError(f"Không thể kết nối tới server CVAT ({server_url}): {e}")

    def save_to_yaml(self, filepath: Union[str, Path]) -> None:
        """Lưu lại danh mục nhãn vào file YAML."""
        if yaml is None:
            raise ImportError("PyYAML chưa được cài đặt.")

        data = self.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    def save_to_json(self, filepath: Union[str, Path], indent: int = 2) -> None:
        """Lưu lại danh mục nhãn vào file JSON."""
        data = self.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)

    def to_dict(self) -> Dict[str, Any]:
        raw_labels = []
        for lbl in self.labels:
            item_dict: Dict[str, Any] = {
                "name": lbl.name,
                "type": lbl.type.value,
                "color": lbl.color,
                "hotkey": lbl.hotkey,
                "description": lbl.description,
                "model_backend": lbl.model_backend,
                "attributes": [asdict(a) for a in lbl.attributes],
            }
            if lbl.skeleton_config:
                item_dict["skeleton_config"] = {
                    "nodes": [asdict(n) for n in lbl.skeleton_config.nodes],
                    "edges": [list(e) for e in lbl.skeleton_config.edges],
                }
            raw_labels.append(item_dict)

        return {
            "version": self.version,
            "project_name": self.project_name,
            "description": self.description,
            "labels": raw_labels,
        }

    def to_cvat_spec(self) -> List[Dict[str, Any]]:
        """
        Sinh ra danh sách nhãn chuẩn định dạng CVAT Project Labels Specification (JSON).
        Sẵn sàng dùng cho CVAT REST API /api/projects hoặc /api/tasks.
        """
        return [lbl.to_cvat_spec() for lbl in self.labels]

    def get(self, name: str) -> Optional[LabelItem]:
        for lbl in self.labels:
            if lbl.name == name:
                return lbl
        return None

    def filter_by_type(self, label_type: Union[LabelType, str]) -> List[LabelItem]:
        target = LabelType.from_str(label_type) if isinstance(label_type, str) else label_type
        return [lbl for lbl in self.labels if lbl.type == target]

    def summary(self) -> Dict[str, Any]:
        """Thống kê tổng quan danh mục nhãn."""
        counts: Dict[str, int] = {}
        for t in LabelType:
            counts[t.value] = len(self.filter_by_type(t))

        return {
            "project_name": self.project_name,
            "total_labels": len(self.labels),
            "by_type": counts,
            "labels": [lbl.name for lbl in self.labels],
        }
