---
title: "CVAT Universal Multi-Modal Labeling Booster & One-Click CI/CD Deployment"
description: "Hệ thống tối ưu hóa gán nhãn CVAT toàn diện: Tách riêng Label Management đa dạng (Box, Line, 3D, Polygon, Mask, Skeleton), Extension giảm tải Canvas (Solo Focus Mode & Cảnh báo lag), Serverless AI Engine, và CI/CD One-Click Colab/VPS."
status: completed
priority: P1
effort: 10h
tags: [feature, infra, frontend, cvat, ci-cd, ai, label-schema]
created: 2026-09-27
---

# Kế hoạch Triển khai: CVAT Universal Multi-Modal Labeling Booster & One-Click CI/CD

Tài liệu thiết kế kiến trúc chi tiết tham khảo tại:
[cvat_performance_plugin_brainstorm.md](file:///C:/Users/qu4nl/.gemini/antigravity-ide/brain/b84ed03f-7626-4d46-a075-c375cfa0f4cc/cvat_performance_plugin_brainstorm.md)

---

## 🎯 Mục tiêu Dự án
1. **Module hóa Nhãn Độc lập (Decoupled Universal Label System)**: Tách riêng 100% cấu hình nhãn ra khỏi code lõi. Cho phép sửa đổi, bổ sung nhãn nhanh chóng mà không ảnh hưởng tới tool. Hỗ trợ đầy đủ **6 dạng gán nhãn**:
   - 📦 **Box** (2D Bounding Box)
   - 📏 **Line** (Polyline, vạch kẻ đường, ranh giới)
   - 🧊 **3D** (3D Cuboid Bounding Box / LiDAR)
   - 📐 **Polygon** (Đa giác bám viền chi tiết)
   - 🎭 **Mask** (Bitmap / RLE segmentation mask)
   - 🦴 **Skeleton** (Pose estimation, khung xương khớp nối)
2. **Giải phóng máy cá nhân (Thin Client Booster)**: Loại bỏ hoàn toàn hiện tượng giật lag, đơ trình duyệt khi Canvas phải vẽ hàng trăm nhãn/polygon phức tạp qua Userscript thông minh có **Cảnh báo quá tải** và **Solo Focus Mode (cô lập 1 nhãn đang làm)** hỗ trợ mọi loại hình học.
3. **Tăng tốc độ gán nhãn gấp 3-5 lần**: Tận dụng GPU server thuê (Colab / Vultr / FPT) để chạy các mô hình AI tương ứng với từng dạng nhãn (SAM 2.1, YOLOv11, Pose, 3D).
4. **Quy trình Triển khai Tiện lợi (CI/CD One-Click)**: Triển khai lên Google Colab hoặc bất kỳ VPS nào chỉ bằng 1-Click hoặc 1 lệnh bash, tự động cấu hình tunnel HTTPS bảo mật.

---

## 🗺️ Lộ trình Triển khai theo Giai đoạn (Phases)

### Giai đoạn 1: Module Quản lý Nhãn Độc lập & Đa dạng (Decoupled Universal Label Schema)
> **Mục tiêu**: Tách hoàn toàn cấu hình nhãn ra file độc lập, hỗ trợ cả 6 dạng hình học (box, line, 3d, polygon, mask, skeleton) giúp người dùng chỉnh sửa nhãn dễ dàng mà không bao giờ làm lỗi code của tool.

- [x] **Task 1.1: Thiết kế Declarative Label Schema (`configs/labels_config.yaml`)**
  - Định nghĩa cấu trúc nhãn chuẩn cho cả 6 dạng:
    * `box`: Bounding box chuẩn VOC/COCO.
    * `polygon`: Danh sách tọa độ đa giác khép kín.
    * `mask`: Cấu hình RLE/Bitmap mask.
    * `line`: Polyline (dây cáp, làn đường, ranh giới).
    * `3d`: 3D Cuboid (tâm x,y,z, kích thước dx,dy,dz, góc quay yaw/pitch/roll).
    * `skeleton`: Danh sách nodes/keypoints (khớp) và edges/bones (đoạn nối khung xương).
  - Thuộc tính kèm theo: `color`, `hotkey`, `attributes` (select, checkbox, text), và `model_backend` (gắn mô hình AI nào xử lý nhãn đó).
- [x] **Task 1.2: Xây dựng Bộ xử lý Schema `locate_cvat/label_registry.py`**
  - Pydantic/Dataclass Model để tự động validate cú pháp file nhãn khi người dùng chỉnh sửa.
  - Tự động convert cấu hình sang định dạng **CVAT Project Labels Specification** (cho phép nạp 1-click vào CVAT qua API hoặc import JSON).
  - Tự động sinh template gán nhãn mẫu cho người dùng mới.
  - Tích hợp công cụ dòng lệnh `tools/cvat_labels_cli.py` (`validate`, `summary`, `export-cvat-spec`).
- [x] **Task 1.3: Bộ chuyển đổi Đa Định dạng (Universal Annotation Translators)**
  - Tích hợp exporter tương ứng cho từng dạng nhãn:
    * COCO 1.0 (`locate_cvat/translators/coco_translator.py` cho box, polygon)
    * COCO Keypoints (`locate_cvat/translators/skeleton_translator.py` cho skeleton)
    * CVAT XML 1.1 (`locate_cvat/translators/cuboid_3d_translator.py` cho line polyline và 3d cuboid)
  - Bộ Unit Test tự động [tests/test_label_registry.py](file:///d:/QuanProject/locate-anything/tests/test_label_registry.py) đạt 100% tỷ lệ pass.

---

### Giai đoạn 2: Client-Side "CVAT Performance Booster" (Userscript / Extension)
> **Mục tiêu**: Tối ưu hóa trải nghiệm gán nhãn trên máy cá nhân yếu, hỗ trợ cảnh báo và Solo Focus Mode cho TẤT CẢ các dạng nhãn (kể cả Skeleton & 3D).

- [x] **Task 2.1: Xây dựng Canvas & DOM Observer Đa Hình Học**
  - Nhận diện và theo dõi tất cả các loại SVG elements và Canvas shapes: rects, polygons, polylines, cuboid lines, và skeleton joints.
  - Tính toán số lượng annotations đang active theo thời gian thực kèm đồng hồ đo FPS mượt mà.
- [x] **Task 2.2: Triển khai Cơ chế Cảnh báo Quá tải & Thanh kéo Threshold Slider**
  - Tích hợp thanh kéo Slider cấu hình ngưỡng từ 20 đến 300 đối tượng trực tiếp trên UI widget, tự động lưu vào `localStorage`.
  - Hiển thị Toast/Badge cảnh báo màu vàng/đỏ khi số lượng đối tượng vượt ngưỡng.
- [x] **Task 2.3: Triển khai Chế độ Solo Focus Mode Toàn Diện**
  - Tạo thanh công cụ nổi Glassmorphism hiển thị danh sách nhãn kèm màu sắc và số lượng đối tượng.
  - Khi click chọn 1 nhãn: Tự động ẩn toàn bộ các đối tượng thuộc nhãn khác (kể cả skeleton joints và 3D cuboids) bằng CSS Injection triệt tiêu GPU rasterization.
  - Nút `✕ Hủy Solo` hoặc phím tắt để khôi phục xem toàn cảnh.
- [x] **Task 2.4: Tích hợp Hệ thống Phím tắt Tiện ích**
  - `Shift + F`: Bật / Tắt Solo Focus Mode nhanh.
  - `Alt + 1..9`: Chọn nhanh nhãn 1-9 theo danh mục.
  - `Escape`: Hủy Solo Mode tức thì.
- [x] **Task 2.5: Đóng gói Userscript `client/cvat-booster.user.js` & Hướng dẫn**
  - Đóng gói file userscript hoàn chỉnh tương thích Tampermonkey / Violentmonkey.
  - Soạn thảo tài liệu hướng dẫn chi tiết cho annotator tại [docs/client_guide.md](file:///d:/QuanProject/locate-anything/docs/client_guide.md).

---

### Giai đoạn 3: Serverless AI Engine Đa Model trên Server Thuê (Colab / VPS GPU)
> **Mục tiêu**: Định tuyến thông minh theo từng loại nhãn tới model AI chuyên trách trên GPU server thuê.

- [x] **Task 3.1: Bộ định tuyến AI theo loại nhãn (Model Dispatcher)**
  - Tích hợp `server/ai_engine/dispatcher.py` điều phối đa mô hình:
    * `polygon` / `mask`: Điều hướng tới **Ultralytics SAM 2.1** (`server/ai_engine/sam2_engine.py`) để bám viền khít chỉ qua click point hoặc box prompt.
    * `box`: Điều hướng tới **YOLO / Detector** (`server/ai_engine/detector_engine.py`) tự động phát hiện bounding box.
    * `skeleton`: Điều hướng tới **Pose Engine** (`server/ai_engine/pose_engine.py`) tự động nhận diện khớp xương theo cấu hình nodes/edges.
    * `line` & `3d`: Bộ trích xuất polyline và 3D cuboid.
  - Cơ chế dự phòng thông minh (Simulation Fallback) giúp kiểm thử độc lập mà không bắt buộc tải trước weights nặng hàng gigabyte.
- [x] **Task 3.2: Cấu hình Nuclio Serverless Function**
  - Tạo cấu hình `server/nuclio/function.yaml` tích hợp GPU limits và `eventTimeout: 180s` (loại bỏ lỗi 504 Gateway Timeout).
  - Viết handler `server/nuclio/main.py` nhận request từ CVAT, decode base64 và trả về JSON chuẩn format của CVAT Interactors / Detectors.
- [x] **Task 3.3: Xây dựng Fast API Fallback Service**
  - Viết dịch vụ `server/api_service.py` độc lập, hỗ trợ CORS, cung cấp các endpoint `/health`, `/api/labels`, `/api/annotate`.
  - Bộ Unit Test tự động [tests/test_ai_engine.py](file:///d:/QuanProject/locate-anything/tests/test_ai_engine.py) đạt 100% tỷ lệ pass (12/12 tests trên toàn repo).

---

### Giai đoạn 4: CI/CD Automation & One-Click Deployment Pipeline
> **Mục tiêu**: Đơn giản hóa tối đa việc đưa ứng dụng lên server thuê, ai cũng có thể bật được chỉ sau vài phút.

- [x] **Task 4.1: GitHub Actions CI Pipeline (`.github/workflows/deploy-images.yml`)**
  - Tự động build Docker Image đa tầng ([server/Dockerfile](file:///d:/QuanProject/locate-anything/server/Dockerfile)) có sẵn CUDA 12.1, PyTorch, Python, OpenCV, dependencies và model weights (YOLO, Pose, SAM 2.1).
  - Đẩy image tự động lên GitHub Container Registry (GHCR) với tag version / `latest`.
- [x] **Task 4.2: One-Click Colab Notebook (`colab/launch_colab.ipynb`)**
  - Tạo notebook chuẩn Google Colab ([colab/launch_colab.ipynb](file:///d:/QuanProject/locate-anything/colab/launch_colab.ipynb)): tự động kiểm tra T4 GPU (`nvidia-smi`), khởi chạy AI Service trong background.
  - Tự động mở **Cloudflare Tunnel** (`cloudflared`) miễn phí để sinh URL HTTPS bảo mật công khai kết nối trực tiếp với máy cá nhân mà không bị chặn port.
- [x] **Task 4.3: One-Command VPS Deployment Script (`scripts/deploy_vps.sh`)**
  - Viết script bash ([scripts/deploy_vps.sh](file:///d:/QuanProject/locate-anything/scripts/deploy_vps.sh)) tự động nhận diện Ubuntu, cài Docker, cài đặt NVIDIA Container Toolkit (nếu có GPU) và khởi chạy container.
  - Biên soạn tài liệu chi tiết tại [docs/deployment_guide.md](file:///d:/QuanProject/locate-anything/docs/deployment_guide.md).

---

### Giai đoạn 5: Kiểm thử, Benchmark & Hướng dẫn Sử dụng (Validation & Docs)
> **Mục tiêu**: Xác thực hiệu quả thực tế và cung cấp tài liệu chi tiết.

- [x] **Task 5.1: Benchmark Kiểm thử Đa Dạng Nhãn**
  - Kiểm thử toàn diện 6 loại hình học (`box`, `line`, `3d`, `polygon`, `mask`, `skeleton`) qua bộ unit test tự động [tests/test_label_registry.py](file:///d:/QuanProject/locate-anything/tests/test_label_registry.py) và [tests/test_ai_engine.py](file:///d:/QuanProject/locate-anything/tests/test_ai_engine.py).
  - Tỷ lệ pass: **100% (12/12 tests passed)**.
- [x] **Task 5.2: Hoàn thiện Toàn bộ Tài liệu Hướng dẫn**
  - [docs/label_configuration_guide.md](file:///d:/QuanProject/locate-anything/docs/label_configuration_guide.md): Sổ tay hướng dẫn cấu hình nhãn không cần chạm code & các lệnh CLI push/import/export.
  - [docs/client_guide.md](file:///d:/QuanProject/locate-anything/docs/client_guide.md): Hướng dẫn annotator cài đặt và dùng Userscript Booster.
  - [docs/deployment_guide.md](file:///d:/QuanProject/locate-anything/docs/deployment_guide.md): Hướng dẫn triển khai 1-click Colab và 1-lệnh VPS.
  - Hoàn thiện tổng quan hệ thống tại [README.md](file:///d:/QuanProject/locate-anything/README.md).

---

## 📁 Cấu trúc Thư mục Đề xuất

```
locate-anything/
├── configs/
│   └── labels_config.yaml          # ⭐ File cấu hình nhãn duy nhất (Box, Line, 3D, Poly, Mask, Skeleton)
├── locate_cvat/
│   ├── label_registry.py           # Parser, validator và converter sang CVAT Project Spec
│   ├── translators/                # Các bộ chuyển đổi COCO, CVAT XML, Keypoints
│   │   ├── coco_translator.py
│   │   ├── skeleton_translator.py
│   │   └── cuboid_3d_translator.py
│   └── pipeline.py
├── client/
│   └── cvat-booster.user.js        # Userscript Tampermonkey (Cảnh báo quá tải + Solo Focus Mode đa dạng shape)
├── server/
│   ├── nuclio/                     # Cấu hình Nuclio Serverless cho CVAT
│   │   ├── function.yaml
│   │   └── main.py
│   ├── ai_engine/                  # Dispatcher mô hình AI (SAM2, YOLO, Pose, 3D)
│   │   ├── dispatcher.py
│   │   ├── sam2_handler.py
│   │   └── pose_handler.py
│   └── api_service.py              # FastAPI fallback service
├── colab/
│   └── launch_colab.ipynb          # Notebook One-click chạy trên Google Colab
├── scripts/
│   └── deploy_vps.sh               # Script 1 dòng lệnh triển khai trên VPS
├── .github/
│   └── workflows/
│       └── deploy-images.yml       # GitHub Actions CI/CD
├── docs/
│   ├── label_configuration_guide.md# Sổ tay hướng dẫn cấu hình nhãn
│   ├── client_guide.md             # Hướng dẫn annotator
│   └── deployment_guide.md         # Hướng dẫn deploy server
├── plan.md                         # File kế hoạch triển khai
└── README.md
```

---

## ⚡ Hướng dẫn Bắt đầu Thực thi
Khi bạn đã sẵn sàng bắt đầu viết mã nguồn theo kế hoạch này, bạn có thể gọi lệnh:
```
/ck:cook plan.md
```
để tiến hành triển khai tuần tự từ **Giai đoạn 1 (Module Nhãn Độc Lập)**!
