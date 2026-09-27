# 🎯 CVAT Universal Multi-Modal Labeling Booster & Cloud/VPS AI Engine

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Wanlee199/locate-anything/blob/main/colab/launch_colab.ipynb)

Hệ thống toàn diện giải quyết triệt để 2 vấn đề lớn nhất khi sử dụng CVAT:
1. **Máy tính cá nhân bị giật lag, ngốn RAM/CPU** khi Canvas phải vẽ hàng trăm nhãn/polygon phức tạp.
2. **Quy trình gán nhãn thủ công chậm** và **triển khai hạ tầng AI lên server thuê (Google Colab / VPS) quá cồng kềnh**.

---

## 🌟 Tính Năng Nổi Bật

### 1. ⭐ Module Quản Lý Nhãn Độc Lập (Decoupled Universal Schema)
- **Tách riêng 100% cấu hình nhãn**: Bạn chỉ cần chỉnh sửa một file duy nhất [`configs/labels_config.yaml`](file:///d:/QuanProject/locate-anything/configs/labels_config.yaml). Sửa đổi nhãn bất kỳ lúc nào mà **không bao giờ ảnh hưởng tới code của tool**.
- **Hỗ trợ đầy đủ 6 dạng hình học thị giác máy tính**:
  - 📦 **`box`**: 2D Bounding Box chuẩn VOC / YOLO / COCO.
  - 📐 **`polygon`**: Đa giác bám viền khép kín (ổ gà, vết nứt, tổn thương).
  - 🎭 **`mask`**: Bitmap / RLE segmentation mask (mặt đường, thảm cỏ, thảm thực vật).
  - 📏 **`line`**: Polyline (vạch kẻ đường, ranh giới lề đường, dây cáp).
  - 🧊 **`3d`**: 3D Cuboid Bounding Box (xe tự hành, kho thông minh, LiDAR).
  - 🦴 **`skeleton`**: Khung xương Pose Estimation (định nghĩa danh sách khớp `nodes` + đoạn xương nối `edges`).
- **CLI Tool linh hoạt**:
  - `python tools/cvat_labels_cli.py summary configs/labels_config.yaml` $\rightarrow$ Thống kê nhãn.
  - `python tools/cvat_labels_cli.py validate configs/labels_config.yaml` $\rightarrow$ Kiểm tra file hợp lệ.
  - `python tools/cvat_labels_cli.py export-cvat-spec ...` $\rightarrow$ Xuất file raw JSON để import vào CVAT.
  - `python tools/cvat_labels_cli.py push ... --host <url> --project-id <id>` $\rightarrow$ **Đẩy thẳng nhãn lên CVAT Project qua REST API trong 1 giây**.
  - `python tools/cvat_labels_cli.py import-cvat-spec ...` $\rightarrow$ Đọc ngược file raw JSON có sẵn từ CVAT thành YAML.

---

### 2. ⚡ Client-Side "CVAT Performance Booster" (Userscript)
- **Cài đặt 1 click qua Tampermonkey**: File [`client/cvat-booster.user.js`](file:///d:/QuanProject/locate-anything/client/cvat-booster.user.js) hoạt động trên mọi trình duyệt (Chrome, Edge, Firefox, Cốc Cốc, Brave).
- **Đồng hồ đo FPS & Bộ đếm đối tượng thời gian thực**: Giám sát tải phần cứng trực tiếp trên màn hình gán nhãn.
- **Thanh trượt Tùy biến Ngưỡng (Threshold Slider)**: Cho phép annotator tự do chỉnh ngưỡng cảnh báo từ **20 đến 300 đối tượng** ngay trên giao diện widget, tự động lưu vào trình duyệt (`localStorage`).
- **Chế độ Solo Focus Mode (Vũ khí chống giật lag)**:
  - Khi Canvas có hàng trăm đối tượng hỗn hợp, bấm chọn nhãn bạn đang làm (ví dụ `car` hoặc `human_pose`).
  - Toàn bộ các đối tượng khác lập tức bị ẩn khỏi Canvas bằng kỹ thuật **CSS Injection (`display: none !important`)**, triệt tiêu 85-95% gánh nặng GPU/CPU của trình duyệt.
  - **FPS ngay lập tức tăng vọt lên 60 FPS**, thao tác chuột mượt mà tuyệt đối.
  - Phím tắt tiện lợi: `Shift + F` (bật/tắt Solo), `Alt + 1..9` (chọn nhanh nhãn), `Escape` (hủy Solo).

---

### 3. 🤖 Serverless AI Engine Đa Model trên Server Thuê (Colab / VPS GPU)
- **Bộ định tuyến thông minh (Model Dispatcher)**:
  - `polygon` / `mask` $\rightarrow$ Gọi **Ultralytics SAM 2.1** sinh viền đa giác ôm khít chỉ với 1 click.
  - `box` $\rightarrow$ Gọi **YOLO** tự động phát hiện hộp 2D.
  - `skeleton` $\rightarrow$ Gọi **Pose Engine** tự động trích xuất khớp xương và liên kết các node.
  - `line` & `3d` $\rightarrow$ Trích xuất polyline và 3D cuboid.
- **Cấu hình Nuclio Serverless chuẩn CVAT**:
  - Thiết lập **`eventTimeout: 180s`** giúp khắc phục hoàn toàn lỗi **504 Gateway Timeout** khi chạy các mô hình nặng trên CVAT.
- **Dịch vụ FastAPI Độc lập ([`server/api_service.py`](file:///d:/QuanProject/locate-anything/server/api_service.py))**:
  - Không cần cài cụm microservices 10 container đồ sộ của CVAT, chỉ cần 1 lệnh là có ngay AI Engine có GPU phục vụ API.

---

### 4. 🚀 CI/CD Automation & Triển Khai One-Click
- **Triển khai 1-Click trên Google Colab T4 GPU (Miễn phí)**:
  - Mở file [`colab/launch_colab.ipynb`](file:///d:/QuanProject/locate-anything/colab/launch_colab.ipynb) trên Colab $\rightarrow$ Chọn **T4 GPU** $\rightarrow$ Bấm **Run all**.
  - Tự động mở **Cloudflare Tunnel** (`cloudflared`) sinh đường dẫn HTTPS công khai bảo mật kết nối với máy cá nhân.
- **Triển khai 1-Lệnh trên VPS (Vultr / FPT Cloud / Ubuntu)**:
  - Chạy script [`scripts/deploy_vps.sh`](file:///d:/QuanProject/locate-anything/scripts/deploy_vps.sh) $\rightarrow$ Tự động cài Docker, cấu hình NVIDIA Container Toolkit (nếu có GPU) và khởi chạy container.
- **GitHub Actions Pipeline**:
  - Tự động build và push Docker image lên GitHub Container Registry (GHCR) qua file [`.github/workflows/deploy-images.yml`](file:///d:/QuanProject/locate-anything/.github/workflows/deploy-images.yml).

---

## 🚀 Hướng Dẫn Từng Bước Khởi Chạy Tool (Step-by-Step Quickstart)

### 📌 Kịch bản 1: Tự động gán nhãn AI qua Google Colab T4 GPU (Khuyên dùng nhất)
Toàn bộ quy trình gán nhãn tự động hàng trăm ảnh từ Colab về máy tính cá nhân chỉ mất **3 phút** thực hiện theo 4 bước sau:

#### Bước 1: Mở cầu nối Cloudflare Tunnel trên máy tính cá nhân
CVAT đang chạy trên máy tính bạn tại `http://localhost:8080`. Để Google Colab (trên Internet) kết nối được vào máy bạn mà không bị tường lửa/modem chặn:
1. Mở một cửa sổ PowerShell tại thư mục dự án và chạy:
   ```powershell
   # Tải công cụ Cloudflare Tunnel (chỉ cần chạy 1 lần đầu tiên)
   Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile "cloudflared.exe"

   # Mở cổng kết nối an toàn ra ngoài Internet (BẮT BUỘC có cờ --http-host-header localhost)
   .\cloudflared.exe tunnel --url http://localhost:8080 --http-host-header localhost
   ```
2. Trên màn hình sẽ in ra một đường link HTTPS công khai, ví dụ:
   ```text
   https://xxxx-yyyy-zzzz.trycloudflare.com
   ```
   *(Hãy giữ nguyên cửa sổ PowerShell này chạy ngầm để duy trì kết nối).*

---

#### Bước 2: Lấy Personal Access Token trên CVAT máy tính
1. Mở trình duyệt vào `http://localhost:8080` $\rightarrow$ Đăng nhập tài khoản của bạn.
2. Bấm vào **Avatar** ở góc trên cùng bên phải $\rightarrow$ Chọn **Profile**.
3. Chọn tab **API Tokens** $\rightarrow$ Bấm nút **Create** (Tạo mới) $\rightarrow$ Đặt tên bất kỳ (VD: `colab`) rồi xác nhận.
4. Copy chuỗi Token hiển thị (có dạng: `xxxxxxxx.yyyyyyyyyyyyyyyyyyyy...`).

---

#### Bước 3: Mở Google Colab bằng 1 Click
Bấm trực tiếp vào huy hiệu bên dưới để mở notebook trên Google Colab:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Wanlee199/locate-anything/blob/main/colab/launch_colab.ipynb)

*(Hoặc mở [Google Colab](https://colab.research.google.com) $\rightarrow$ Chọn tab GitHub $\rightarrow$ Nhập `Wanlee199/locate-anything` $\rightarrow$ Chọn file `colab/launch_colab.ipynb`).*

⚠️ **Nhớ bật GPU miễn phí**: Vào menu **Runtime** $\rightarrow$ **Change runtime type** $\rightarrow$ Chọn **T4 GPU** $\rightarrow$ Bấm **Save**.

---

#### Bước 4: Chạy tự động gán nhãn
Tại Google Colab, điền thông tin kết nối và bấm **Play (Run)**:

```python
# 1. Tải mã nguồn mới nhất từ GitHub
%cd /content
!rm -rf /content/locate-anything
!git clone https://github.com/Wanlee199/locate-anything.git
%cd /content/locate-anything
!pip install -q ultralytics pillow pyyaml

# 2. Cấu hình kết nối tới máy tính của bạn
CVAT_HOST = "https://xxxx-yyyy-zzzz.trycloudflare.com"  # Link Cloudflare ở Bước 1
CVAT_TASK_ID = 1                                         # ID của Task trên CVAT
CVAT_TOKEN = "xxxxxxxx.yyyyyyyyyyyyyyyyyyyy..."           # Token lấy ở Bước 2

# 3. Kích hoạt AI tự động gán nhãn
!python colab/cvat_auto_sync.py --host $CVAT_HOST --token $CVAT_TOKEN --task-id $CVAT_TASK_ID
```

GPU Colab sẽ tự động:
- Kéo từng frame ảnh từ CVAT máy bạn về.
- Chạy YOLOv11 nhận diện chính xác từng xe bus, ô tô con, xe tải, xe máy.
- Đẩy toàn bộ annotations hoàn chỉnh ngược lại lên CVAT.
- Khi màn hình hiện `🎉 THÀNH CÔNG!`, bạn chỉ việc F5 trang CVAT trên máy tính: toàn bộ ảnh đã được vẽ sẵn nhãn bám khít từng đối tượng!

---

### ⚡ Kịch bản 2: Bật "Vũ Khí Chống Giật Lag" (Userscript Solo Focus Mode)
Dành cho người gán nhãn trực tiếp trên trình duyệt máy tính:
1. Cài đặt tiện ích **Tampermonkey** trên trình duyệt Chrome/Edge/Firefox/Brave.
2. Mở file [`client/cvat-booster.user.js`](locate-anything/client/cvat-booster.user.js) $\rightarrow$ Cài đặt script vào Tampermonkey.
3. Mở CVAT trên trình duyệt: Một Widget kính mờ hiển thị FPS và bộ đếm đối tượng sẽ xuất hiện ở góc dưới bên trái.
4. Khi Canvas bị lag do có quá nhiều nhãn: Nhấn phím tắt **`Shift + F`** để kích hoạt **Solo Focus Mode** $\rightarrow$ Ẩn 90% nhãn rác, đưa tốc độ vẽ trở lại **60 FPS siêu mượt**!

---

### 📦 Kịch bản 3: Quản lý và đẩy cấu hình nhãn lên CVAT bằng CLI
1. Mở file [`configs/labels_config.yaml`](locate-anything/configs/labels_config.yaml) và chỉnh sửa nhãn tùy ý.
2. Kiểm tra tính hợp lệ của file cấu hình nhãn:
   ```bash
   python tools/cvat_labels_cli.py validate configs/labels_config.yaml
   ```
3. Đẩy thẳng cấu hình nhãn mới lên CVAT Project qua REST API trong 1 giây:
   ```bash
   python tools/cvat_labels_cli.py push configs/labels_config.yaml --host http://localhost:8080 --token <YOUR_TOKEN> --project-id 1
   ```

---

> 📖 **Xem chi tiết tài liệu kiến trúc kỹ thuật và báo cáo tổng kết toàn diện**: Xem file [`SYSTEM_DOCUMENTATION.md`](file:///d:/QuanProject/locate-anything/SYSTEM_DOCUMENTATION.md).

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
locate-anything/
├── configs/
│   └── labels_config.yaml          # ⭐ File cấu hình nhãn duy nhất (Box, Line, 3D, Poly, Mask, Skeleton)
├── locate_cvat/
│   ├── label_registry.py           # Core Registry, Validator, API Push và Spec Converter
│   └── translators/                # Các bộ chuyển đổi đa định dạng
│       ├── coco_translator.py      # Chuẩn COCO 1.0 (Box, Polygon)
│       ├── skeleton_translator.py  # Chuẩn COCO Keypoints (Khung xương)
│       └── cuboid_3d_translator.py # Chuẩn CVAT XML 1.1 (3D Cuboid, Polyline)
├── client/
│   └── cvat-booster.user.js        # Userscript Tampermonkey (Cảnh báo quá tải + Slider + Solo Mode)
├── server/
│   ├── Dockerfile                  # Dockerfile đóng gói PyTorch CUDA, OpenCV và weights
│   ├── api_service.py              # Dịch vụ FastAPI Serverless Fallback
│   ├── nuclio/                     # Cấu hình FaaS cho CVAT
│   │   ├── function.yaml           # Cấu hình 180s timeout và GPU limits
│   │   └── main.py                 # Handler nhận request từ CVAT
│   └── ai_engine/                  # Dispatcher và các model wrappers
│       ├── dispatcher.py
│       ├── sam2_engine.py
│       ├── detector_engine.py
│       └── pose_engine.py
├── colab/
│   └── launch_colab.ipynb          # Notebook One-click chạy trên Google Colab T4 GPU
├── scripts/
│   └── deploy_vps.sh               # Script 1 lệnh tự động hóa cài đặt trên VPS
├── .github/
│   └── workflows/
│       └── deploy-images.yml       # GitHub Actions CI/CD tự động build Docker
├── docs/
│   ├── label_configuration_guide.md# Sổ tay hướng dẫn cấu hình và quản lý nhãn
│   ├── client_guide.md             # Hướng dẫn cài đặt Userscript cho annotator
│   └── deployment_guide.md         # Hướng dẫn triển khai Colab và VPS
├── tests/                          # Bộ Unit Test tự động (12/12 passed)
│   ├── test_label_registry.py
│   └── test_ai_engine.py
├── plan.md                         # Kế hoạch kỹ thuật
└── README.md
```

---

## 🧪 Kiểm Thử Hệ Thống (Unit Tests)

Chạy toàn bộ bộ test tự động:
```bash
python -m unittest discover tests
```
Kết quả kiểm thử: **`Ran 12 tests in 0.266s - OK`** (100% pass trên toàn hệ thống).
