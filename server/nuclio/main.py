"""
Nuclio Serverless Function Handler cho CVAT.
Xử lý các request gán nhãn tự động từ CVAT UI và chuyển tới ModelDispatcher.
"""

import base64
import io
import json
from PIL import Image

from locate_cvat.label_registry import LabelRegistry
from server.ai_engine.dispatcher import ModelDispatcher


def init_context(context):
    context.logger.info("Khởi tạo Universal AI Annotator Engine...")

    # Tải cấu hình nhãn nếu có
    try:
        registry = LabelRegistry.load_from_yaml("configs/labels_config.yaml")
    except Exception:
        registry = None

    dispatcher = ModelDispatcher(registry=registry)
    dispatcher.load_engines()

    setattr(context.user_data, "dispatcher", dispatcher)
    context.logger.info("✅ Universal AI Annotator Engine đã sẵn sàng!")


def handler(context, event):
    context.logger.info("Nhận request gán nhãn từ CVAT...")

    data = event.body
    if isinstance(data, (bytes, bytearray)):
        data = json.loads(data.decode("utf-8"))

    # Đọc ảnh từ base64
    image_b64 = data.get("image")
    if not image_b64:
        return context.Response(
            body=json.dumps({"error": "Thiếu trường 'image' trong request"}),
            headers={"Content-Type": "application/json"},
            status_code=400,
        )

    image_bytes = base64.b64decode(image_b64)
    image = Image.open(io.BytesIO(image_bytes))
    w, h = image.size
    image_shape = (h, w)

    # Đọc tham số tương tác
    pos_points = data.get("pos_points", [])
    neg_points = data.get("neg_points", [])
    obj_bbox = data.get("obj_bbox", None)
    label_name = data.get("label", "car")

    dispatcher: ModelDispatcher = context.user_data.dispatcher

    # Thực thi suy luận qua dispatcher
    annotations = dispatcher.dispatch(
        image_shape=image_shape,
        label_name=label_name,
        points=pos_points,
        bbox=obj_bbox,
    )

    return context.Response(
        body=json.dumps(annotations),
        headers={"Content-Type": "application/json"},
        status_code=200,
    )
