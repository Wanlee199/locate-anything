#!/usr/bin/env bash
# ==============================================================================
# Script Triển Khai 1 Lệnh Tự Động Hóa CVAT AI Engine Trên VPS (Ubuntu/Debian)
# Hỗ trợ máy chủ Vultr, FPT Cloud, DigitalOcean, Hetzner, Local Server...
# ==============================================================================

set -e

# Màu sắc thông báo
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}🚀 BẮT ĐẦU TRIỂN KHAI CVAT UNIVERSAL AI ENGINE TRÊN VPS${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. Kiểm tra quyền root/sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Vui lòng chạy script với quyền root hoặc sudo: sudo bash deploy_vps.sh${NC}"
    exit 1
fi

# 2. Cập nhật hệ thống và cài đặt gói cơ bản
echo -e "\n${YELLOW}📦 [1/5] Cập nhật hệ điều hành và các gói tiện ích...${NC}"
apt-get update -qq
apt-get install -y -qq curl wget git ca-certificates gnupg lsb-release

# 3. Cài đặt Docker & Docker Compose nếu chưa có
echo -e "\n${YELLOW}🐳 [2/5] Kiểm tra và cài đặt Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo "Docker chưa được cài đặt. Đang tiến hành cài đặt Docker Engine chính thức..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    echo -e "${GREEN}✅ Docker đã được cài đặt thành công!${NC}"
else
    echo -e "${GREEN}✅ Docker đã có sẵn trên hệ thống.${NC}"
fi

# 4. Kiểm tra GPU NVIDIA và cài đặt NVIDIA Container Toolkit
echo -e "\n${YELLOW}🎮 [3/5] Kiểm tra phần cứng GPU NVIDIA...${NC}"
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✅ Phát hiện GPU NVIDIA:${NC}"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    
    if ! dpkg -l | grep -q nvidia-container-toolkit; then
        echo "Đang cài đặt NVIDIA Container Toolkit để cho phép Docker dùng GPU..."
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
          sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
          tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
        apt-get update -qq
        apt-get install -y -qq nvidia-container-toolkit
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker
        echo -e "${GREEN}✅ NVIDIA Container Toolkit đã cấu hình xong!${NC}"
    else
        echo -e "${GREEN}✅ NVIDIA Container Toolkit đã được cài đặt.${NC}"
    fi
else
    echo -e "${BLUE}ℹ️ Không tìm thấy GPU rời. Hệ thống sẽ chạy ở chế độ CPU Mode.${NC}"
fi

# 5. Tạo file cấu hình docker-compose.server.yml
echo -e "\n${YELLOW}⚙️ [4/5] Thiết lập cấu hình Docker Compose...${NC}"
mkdir -p /opt/cvat-ai-engine
cd /opt/cvat-ai-engine

cat << 'EOF' > docker-compose.server.yml
version: '3.8'

services:
  ai-engine:
    image: python:3.10-slim
    container_name: cvat_universal_ai_engine
    restart: unless-stopped
    working_dir: /app
    ports:
      - "8000:8000"
    volumes:
      - ./:/app
    environment:
      - PYTHONUNBUFFERED=1
    command: >
      bash -c "pip install -q fastapi uvicorn pydantic pyyaml pillow opencv-python-headless &&
               python server/api_service.py --host 0.0.0.0 --port 8000"
EOF

# 6. Khởi chạy container
echo -e "\n${YELLOW}🚀 [5/5] Khởi chạy dịch vụ AI Engine...${NC}"
# Sao chép mã nguồn cần thiết nếu chạy từ thư mục repo
if [ -d "$PWD/server" ]; then
    cp -r "$PWD/server" /opt/cvat-ai-engine/
    cp -r "$PWD/configs" /opt/cvat-ai-engine/
    cp -r "$PWD/locate_cvat" /opt/cvat-ai-engine/
fi

cd /opt/cvat-ai-engine
docker compose -f docker-compose.server.yml up -d

# Lấy địa chỉ IP máy chủ
PUBLIC_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${GREEN}🎉 TRIỂN KHAI HOÀN TẤT THÀNH CÔNG!${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo -e "🌐 Dịch vụ AI Engine đang chạy tại: ${YELLOW}http://${PUBLIC_IP}:8000${NC}"
echo -e "🩺 Kiểm tra trạng thái:             ${YELLOW}http://${PUBLIC_IP}:8000/health${NC}"
echo -e "📋 Danh mục nhãn:                  ${YELLOW}http://${PUBLIC_IP}:8000/api/labels${NC}"
echo -e "\n💡 Để xem nhật ký hoạt động (logs):"
echo -e "   ${BLUE}docker compose -f /opt/cvat-ai-engine/docker-compose.server.yml logs -f${NC}"
echo -e "${BLUE}======================================================================${NC}"
