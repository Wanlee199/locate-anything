#!/usr/bin/env python3
"""
FastAPI Serverless Fallback Service - Dịch vụ AI gán nhãn độc lập chạy trên Colab / VPS.
Không phụ thuộc vào cụm microservices phức tạp của Nuclio, cực kỳ tiện lợi cho Colab.
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from locate_cvat.label_registry import LabelRegistry
from server.ai_engine.dispatcher import ModelDispatcher

app = FastAPI(
    title="CVAT Universal AI Engine API",
    description="Dịch vụ AI gán nhãn tự động đa hình thái (Box, Polygon, Line, 3D, Skeleton)",
    version="1.0.0",
)

# Kích hoạt CORS để frontend hoặc extension có thể gọi trực tiếp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo registry và dispatcher toàn cục
REGISTRY: Optional[LabelRegistry] = None
DISPATCHER: Optional[ModelDispatcher] = None


def get_registry() -> Optional[LabelRegistry]:
    global REGISTRY
    if REGISTRY is None:
        config_file = Path("configs/labels_config.yaml")
        if config_file.exists():
            try:
                REGISTRY = LabelRegistry.load_from_yaml(config_file)
            except Exception as e:
                print(f"⚠️ Cảnh báo tải file config: {e}")
                REGISTRY = None
    return REGISTRY


def get_dispatcher() -> ModelDispatcher:
    global DISPATCHER
    if DISPATCHER is None:
        reg = get_registry()
        DISPATCHER = ModelDispatcher(registry=reg)
        DISPATCHER.load_engines()
    return DISPATCHER


class AnnotateRequest(BaseModel):
    image_base64: str
    label_name: str
    points: Optional[List[List[float]]] = None  # [[x, y]]
    bbox: Optional[List[float]] = None          # [xtl, ytl, xbr, ybr]


class AnnotateResponse(BaseModel):
    label_name: str
    annotations: List[Dict[str, Any]]
    image_size: List[int]  # [width, height]


@app.get("/health")
def health_check():
    has_cuda = False
    gpu_name = "None (CPU / Emulation Mode)"
    try:
        import torch
        has_cuda = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if has_cuda else "None (CPU Mode)"
    except ImportError:
        pass

    reg = get_registry()
    return {
        "status": "healthy",
        "service": "CVAT Universal AI Engine",
        "cuda_available": has_cuda,
        "gpu_device": gpu_name,
        "total_labels": len(reg.labels) if reg else 0,
    }


@app.get("/api/labels")
def get_labels():
    reg = get_registry()
    if not reg:
        raise HTTPException(status_code=404, detail="Chưa cấu hình danh mục nhãn")
    return reg.to_dict()


@app.post("/api/annotate", response_model=AnnotateResponse)
def annotate_image(req: AnnotateRequest):
    dispatcher = get_dispatcher()

    try:
        image_bytes = base64.b64decode(req.image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        w, h = image.size
        image_shape = (h, w)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dữ liệu ảnh không hợp lệ: {e}")

    annotations = dispatcher.dispatch(
        image_shape=image_shape,
        label_name=req.label_name,
        points=req.points,
        bbox=req.bbox,
    )

    return AnnotateResponse(
        label_name=req.label_name,
        annotations=annotations,
        image_size=[w, h],
    )


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Khởi chạy CVAT Universal AI API Service")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Địa chỉ host lắng nghe")
    parser.add_argument("--port", type=int, default=8000, help="Cổng port mạng")
    args = parser.parse_args()

    print(f"🔥 Khởi chạy FastAPI AI Service trên http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
