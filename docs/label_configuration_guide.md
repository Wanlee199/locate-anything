# 📖 Hướng Dẫn Cấu Hình Danh Mục Nhãn Đa Hình Thái (Universal Label Guide)

Hệ thống cho phép cấu hình và thay đổi nhãn hoàn toàn độc lập với code lõi của tool. Bạn chỉ cần chỉnh sửa một file duy nhất:
👉 **`configs/labels_config.yaml`**

Mọi thay đổi trong file này sẽ:
1. **Không làm ảnh hưởng hoặc làm lỗi tool**.
2. **Tự động cập nhật vào CVAT** qua lệnh xuất Project Specification.
3. **Tương thích với bộ lọc Solo Focus Mode** trên giao diện gán nhãn của annotator.

---

## 1. Các Dạng Hình Thái Gán Nhãn Được Hỗ Trợ

Hệ thống hỗ trợ đầy đủ 6 loại hình học chuẩn quốc tế:

| Loại (`type`) | Tên gọi | Ứng dụng tiêu biểu | Quy cách dữ liệu |
| :--- | :--- | :--- | :--- |
| `box` | 2D Bounding Box | Phát hiện xe cộ, người, đồ vật | `[xtl, ytl, xbr, ybr]` |
| `polygon` | Đa giác khép kín | Vết nứt đường, khối nhà, diện tích hỏng | `[[x1,y1], [x2,y2], ...]` |
| `mask` | Segmentation Mask | Mặt đường di chuyển, cây cối, bầu trời | Bitmap / RLE mask |
| `line` | Polyline / Đường nét | Vạch kẻ làn đường, ranh giới, dây điện | `[[x1,y1], [x2,y2], ...]` |
| `3d` | 3D Cuboid | Xe tự hành, định vị không gian 3 chiều | Tâm `(x,y,z)`, Kích thước, Góc quay |
| `skeleton` | Khung xương Pose | Nhận diện tư thế người, dáng đi, thể thao | Danh sách khớp `nodes` + đoạn xương `edges` |

---

## 2. Cú pháp Mẫu trong `configs/labels_config.yaml`

### A. Nhãn Bounding Box (`box`)
```yaml
- name: "car"
  type: "box"
  color: "#ff3b30"
  hotkey: "1"
  description: "Xe ô tô con"
  model_backend: "yolo"
  attributes:
    - name: "occluded"
      input_type: "checkbox"
      default_value: "false"
```

### B. Nhãn Polygon (`polygon`)
```yaml
- name: "road_damage"
  type: "polygon"
  color: "#ff9500"
  hotkey: "2"
  description: "Ổ gà, vết nứt"
  model_backend: "sam2"
  attributes:
    - name: "severity"
      input_type: "select"
      values: ["minor", "moderate", "severe"]
      default_value: "minor"
```

### C. Nhãn Đường nét (`line`)
```yaml
- name: "lane_divider"
  type: "line"
  color: "#ffffff"
  hotkey: "3"
  model_backend: "contour"
```

### D. Nhãn 3D Cuboid (`3d`)
```yaml
- name: "truck_3d"
  type: "3d"
  color: "#af52de"
  hotkey: "4"
  model_backend: "cuboid_3d"
  attributes:
    - name: "motion_state"
      input_type: "select"
      values: ["parked", "moving"]
      default_value: "moving"
```

### E. Nhãn Khung Xương (`skeleton`)
```yaml
- name: "human_pose"
  type: "skeleton"
  color: "#00c7be"
  hotkey: "5"
  model_backend: "yolo_pose"
  skeleton_config:
    nodes:
      - { id: 0, name: "head", color: "#ff0000" }
      - { id: 1, name: "neck", color: "#00ff00" }
      - { id: 2, name: "left_hand", color: "#0000ff" }
      - { id: 3, name: "right_hand", color: "#ffff00" }
    edges:
      - [0, 1]  # Nối đầu xuống cổ
      - [1, 2]  # Cổ sang tay trái
      - [1, 3]  # Cổ sang tay phải
```

---

## 3. Các Lệnh CLI Hữu Ích

### 1. Kiểm tra tính hợp lệ của file cấu hình:
```bash
python tools/cvat_labels_cli.py validate configs/labels_config.yaml
```

### 2. Xem thống kê phân bố nhãn:
```bash
python tools/cvat_labels_cli.py summary configs/labels_config.yaml
```

### 3. Xuất file raw JSON để import vào CVAT Project qua giao diện:
```bash
python tools/cvat_labels_cli.py export-cvat-spec configs/labels_config.yaml -o cvat_labels_spec.json
```

### 4. Đẩy (PUSH) trực tiếp danh mục nhãn lên Server CVAT qua REST API:
Không cần mở giao diện web hay upload file thủ công, bạn có thể đẩy thẳng danh mục nhãn lên Project trên server thuê (Colab / VPS / Cloud):
```bash
# Đẩy với API Token:
python tools/cvat_labels_cli.py push configs/labels_config.yaml \
  --host http://<vps-ip>:8080 \
  --project-id 1 \
  --token <your_cvat_api_token>

# Hoặc đẩy với Username/Password (Basic Auth):
python tools/cvat_labels_cli.py push configs/labels_config.yaml \
  --host http://<vps-ip>:8080 \
  --project-id 1 \
  --username admin \
  --password secret
```

### 5. Nhập (IMPORT) file raw JSON có sẵn của CVAT thành file cấu hình YAML:
Nếu bạn đã có sẵn file nhãn raw JSON từ một dự án CVAT cũ hoặc từ CVAT Docs:
```bash
python tools/cvat_labels_cli.py import-cvat-spec cvat_raw_labels.json -o configs/labels_config.yaml
```
Tool sẽ tự động nhận diện cả 6 dạng nhãn (kể cả cấu trúc khớp xương của Skeleton) và chuyển đổi thành file YAML cấu hình sạch đẹp!
