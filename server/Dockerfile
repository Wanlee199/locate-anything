# ==============================================================================
# Dockerfile: CVAT Universal Multi-Modal AI Engine
# Hỗ trợ CUDA 12.1, PyTorch, Ultralytics SAM 2.1, YOLOv11 & Pose
# ==============================================================================

FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

LABEL maintainer="LocateAnything CVAT Team"
LABEL description="Universal Multi-Modal AI Engine for CVAT (Box, Polygon, Line, 3D, Skeleton)"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 1. Cài đặt các thư viện hệ thống cần thiết cho OpenCV và xử lý ảnh
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Cài đặt dependencies Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn[standard]==0.29.0 \
    pydantic==2.6.4 \
    pyyaml==6.0.1 \
    pillow==10.3.0 \
    opencv-python-headless==4.9.0.80 \
    ultralytics==8.2.0 \
    requests==2.31.0

# 3. Sao chép mã nguồn vào container
COPY configs/ /app/configs/
COPY locate_cvat/ /app/locate_cvat/
COPY server/ /app/server/
COPY tools/ /app/tools/

# 4. Tải trước các model weights gọn nhẹ để triệt tiêu thời gian cold-start
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n-seg.pt'); YOLO('yolo11n-pose.pt')" && \
    wget -q -O /app/sam2.1_t.pt https://github.com/facebookresearch/sam2/releases/download/v1.0/sam2_hiera_tiny.pt || true

EXPOSE 8000

# Khởi chạy FastAPI AI Engine
CMD ["python", "server/api_service.py", "--host", "0.0.0.0", "--port", "8000"]
