# ⚡ Hướng Dẫn Cài Đặt & Sử Dụng "CVAT Performance Booster"

Tiện ích **CVAT Performance Booster** giúp annotator loại bỏ hoàn toàn hiện tượng giật lag khi gán nhãn trên máy tính cá nhân (kể cả máy văn phòng không GPU rời, RAM 4GB - 8GB) khi làm việc với các task có hàng trăm đối tượng phức tạp.

---

## 📥 1. Hướng Dẫn Cài Đặt (Dành cho Annotator)

Tiện ích được đóng gói dưới dạng **Userscript chuẩn** (`client/cvat-booster.user.js`), hỗ trợ tất cả các trình duyệt: **Google Chrome, Microsoft Edge, Mozilla Firefox, Brave, Cốc Cốc**.

### Bước 1: Cài đặt tiện ích mở rộng Tampermonkey
1. Truy cập cửa hàng tiện ích của trình duyệt:
   - [Tampermonkey trên Chrome Web Store](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)
   - Hoặc [Tampermonkey trên Microsoft Edge Addons](https://microsoftedge.microsoft.com/addons/detail/tampermonkey/iikmkjmpaadaobahmlepeloendndfphd)
2. Bấm **Thêm vào Chrome / Add to Browser**.

### Bước 2: Thêm Script vào Tampermonkey
1. Bấm vào biểu tượng **Tampermonkey** ở góc trên thanh công cụ của trình duyệt $\rightarrow$ Chọn **Tạo tập lệnh mới (Create a new script)**.
2. Xóa toàn bộ nội dung mẫu đang có trong trình soạn thảo.
3. Mở file [client/cvat-booster.user.js](file:///d:/QuanProject/locate-anything/client/cvat-booster.user.js), sao chép toàn bộ code và dán vào.
4. Bấm **File** $\rightarrow$ **Save** (hoặc nhấn `Ctrl + S`).
5. Xong! Kể từ bây giờ, mỗi khi bạn mở bất kỳ trang web CVAT nào (trên Colab, VPS hay cvat.ai), bảng điều khiển **CVAT Booster** sẽ tự động kích hoạt ở góc dưới màn hình.

---

## 🎯 2. Các Tính Năng Nổi Bật

### 1. Đồng hồ FPS & Bộ đếm Đối tượng thời gian thực
- Góc dưới màn hình hiển thị bảng kính mờ (Glassmorphism):
  - **Hiệu năng**: Hiển thị tốc độ khung hình thực tế (`FPS`). Nếu FPS giảm dưới 30, chữ sẽ chuyển sang màu vàng/đỏ.
  - **Đối tượng Canvas**: Thống kê chính xác số lượng hộp 2D, polygon, polyline, hộp 3D, hoặc khung xương đang được vẽ trên màn hình.

### 2. Cảnh báo Quá tải Tự Động (Threshold Alert)
- Khi số đối tượng trên màn hình vượt ngưỡng cấu hình (mặc định: `50 đối tượng`), banner cảnh báo sẽ nhấp nháy:
  > `⚠️ Cảnh báo quá tải! Canvas có 124 đối tượng (vượt ngưỡng 50). Trình duyệt có thể bị lag.`

### 3. Thanh kéo Tùy chỉnh Ngưỡng (Threshold Slider)
- Mỗi annotator có một cấu hình máy khác nhau:
  - Máy rất yếu (RAM 4GB, Core i3): Kéo thanh trượt về **30 đối tượng**.
  - Máy tầm trung (RAM 8GB - 16GB): Đặt ở mức **50 - 70 đối tượng**.
  - Máy cấu hình mạnh: Kéo lên **100 - 150 đối tượng**.
- Mức ngưỡng bạn chọn sẽ **tự động lưu vào trình duyệt** (`localStorage`), lần sau mở lại vẫn giữ nguyên.

### 4. Chế độ Solo Focus Mode (Cô lập 1 Nhãn đang làm)
- Đây là vũ khí mạnh nhất để chống lag:
  - Giả sử frame ảnh có 100 đối tượng hỗn hợp (50 người đi bộ, 30 ô tô, 20 vạch kẻ đường).
  - Bạn đang được phân công gán nhãn `car`: Bấm vào ô nhãn `car` trên bảng điều khiển (hoặc bấm `Alt + 1`).
  - **Lập tức toàn bộ 70 đối tượng khác (người, vạch kẻ đường, v.v.) sẽ bị ẩn hoàn toàn khỏi Canvas**.
  - Trình duyệt không phải render hàng ngàn điểm ảnh vector $\rightarrow$ **Chuột mượt mà 60 FPS tức thì**, không còn hiện tượng khựng trễ khi vẽ.
  - Sau khi vẽ xong nhãn đó, bấm **✕ Hủy Solo** (hoặc phím `Escape`) để hiện lại toàn cảnh.

---

## ⌨️ 3. Danh Sách Phím Tắt Nhanh

| Phím tắt | Tác vụ |
| :--- | :--- |
| **`Shift + F`** | Bật / Tắt nhanh chế độ Solo Focus Mode |
| **`Alt + 1` .. `Alt + 9`** | Chọn nhanh nhãn số 1 đến số 9 trong danh sách |
| **`Escape`** | Hủy Solo Mode, hiển thị lại toàn bộ các đối tượng |
| **`_` (nút thu gọn)** | Thu gọn bảng điều khiển thành một huy hiệu mini ở góc màn hình |
