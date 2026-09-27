# 🚀 Hướng Dẫn Triển Khai Tiện Lợi (One-Click Deployment Guide)

Tài liệu hướng dẫn triển khai **CVAT Universal AI Engine** lên các môi trường server thuê: **Google Colab (Miễn phí có GPU T4)** và **VPS máy chủ riêng (Vultr, FPT Cloud, Ubuntu Server)**.

---

## 🟢 Cách 1: Triển Khai 1-Click Trên Google Colab (Khuyên Dùng)

Google Colab cung cấp GPU NVIDIA T4 (15GB VRAM) hoàn toàn miễn phí, rất phù hợp cho cá nhân hoặc nhóm nhỏ làm gán nhãn AI.

### Các bước thực hiện:
1. Mở trình duyệt và truy cập [Google Colab](https://colab.research.google.com/).
2. Chọn **Upload** $\rightarrow$ Tải file [colab/launch_colab.ipynb](file:///d:/QuanProject/locate-anything/colab/launch_colab.ipynb) lên.
3. Trên thanh menu Colab:
   - Chọn **Runtime** $\rightarrow$ **Change runtime type** $\rightarrow$ Chọn phần cứng **T4 GPU** $\rightarrow$ Bấm **Save**.
4. Chọn **Runtime** $\rightarrow$ **Run all** (hoặc nhấn tổ hợp phím `Ctrl + F9`).
5. Sau khoảng 1-2 phút, Colab sẽ hiển thị một đường dẫn HTTPS công khai dạng:
   ```
   =================================================================
   🎉 CVAT UNIVERSAL AI ENGINE ĐANG CHẠY THÀNH CÔNG TRÊN COLAB GPU!
   🌐 URL HTTPS CÔNG KHAI: https://xxxx-xxxx-xxxx.trycloudflare.com
   🩺 Health Check: https://xxxx-xxxx-xxxx.trycloudflare.com/health
   =================================================================
   ```
6. **Xong!** Bạn đã có một Server AI có GPU chạy trực tuyến kết nối với máy cá nhân qua đường truyền mã hóa của Cloudflare Tunnel (hoàn toàn miễn phí, không giới hạn 2h như Ngrok).

---

## 🔵 Cách 2: Triển Khai 1 Lệnh Duy Nhất Trên VPS (Vultr / FPT Cloud / Ubuntu)

Nếu bạn thuê máy chủ VPS hoặc Cloud Server chạy Ubuntu 20.04 / 22.04 / 24.04:

### Các bước thực hiện:
1. Đăng nhập vào VPS qua SSH:
   ```bash
   ssh root@<ip_vps>
   ```
2. Chạy lệnh cài đặt và khởi chạy tự động:
   ```bash
   curl -sSL https://raw.githubusercontent.com/.../scripts/deploy_vps.sh | bash
   ```
   *(Hoặc tải file [scripts/deploy_vps.sh](file:///d:/QuanProject/locate-anything/scripts/deploy_vps.sh) lên máy chủ và chạy `sudo bash deploy_vps.sh`)*.

3. Script sẽ tự động:
   - Cài đặt Docker & Docker Compose plugin chính thức.
   - Kiểm tra nếu máy có GPU NVIDIA $\rightarrow$ Tự động cài **NVIDIA Container Toolkit**.
   - Tạo cấu hình Docker Compose và khởi chạy dịch vụ AI Engine trên cổng `8000`.
   - Hiển thị địa chỉ IP và endpoint kiểm tra `http://<ip_vps>:8000/health`.

---

## 🟣 Cách 3: CI/CD Tự Động Hóa Với GitHub Actions & Docker (GHCR)

Dự án đã tích hợp sẵn GitHub Actions workflow tại [.github/workflows/deploy-images.yml](file:///d:/QuanProject/locate-anything/.github/workflows/deploy-images.yml):

- **Tự động build**: Mỗi khi bạn push code vào nhánh `main`, GitHub Actions sẽ tự động kích hoạt máy chủ Ubuntu build Docker image đa tầng có sẵn PyTorch CUDA, OpenCV, Ultralytics và nén tối ưu.
- **Tự động push lên GHCR**: Image được đẩy lên GitHub Container Registry (`ghcr.io/your-org/cvat-ai-engine:latest`).
- **Kéo về máy chủ**: Trên bất kỳ server nào, bạn chỉ cần gõ:
  ```bash
  docker pull ghcr.io/your-org/cvat-ai-engine:latest
  docker run -d --gpus all -p 8000:8000 ghcr.io/your-org/cvat-ai-engine:latest
  ```
  Tốc độ khởi động chỉ mất **vài chục giây** vì toàn bộ weights và dependencies đã được đóng gói sẵn!
