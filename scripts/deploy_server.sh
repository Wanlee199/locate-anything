#!/usr/bin/env bash
# ==============================================================================
# 🚀 Universal Server Deployment & Auto-Update Script (Linux / VPS / Cloud GPU)
# Tự động triển khai và cập nhật locate-anything trên bất kỳ máy chủ Linux nào:
#   - Hỗ trợ: Ubuntu, Debian, AWS EC2, RunPod, LambdaLabs, Hetzner, Vultr, Local
#   - Tự động kiểm tra GPU NVIDIA / CUDA
#   - Tự động cấu hình Virtualenv & Cài đặt 2D/3D Model Weights (nuScenes PointPillars)
#   - 1 Lệnh cập nhật code mới nhất từ GitHub không mất cấu hình/weights
# ==============================================================================

set -e

# Màu sắc hiển thị
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

BRANCH="locateV2"
REPO_URL="https://github.com/Wanlee199/locate-anything.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

print_header() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${BLUE}======================================================================${NC}"
}

check_python() {
    if command -v python3 &> /dev/null; then
        PY_CMD="python3"
    elif command -v python &> /dev/null; then
        PY_CMD="python"
    else
        echo -e "${RED}❌ Không tìm thấy Python 3 trên hệ thống! Vui lòng cài đặt: sudo apt install python3 python3-pip python3-venv${NC}"
        exit 1
    fi
}

check_gpu() {
    echo -e "${CYAN}🔍 Kiểm tra card đồ họa NVIDIA GPU...${NC}"
    if command -v nvidia-smi &> /dev/null; then
        echo -e "${GREEN}✅ Phát hiện GPU NVIDIA:${NC}"
        nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
        HAS_GPU=1
    else
        echo -e "${YELLOW}⚠️ Không phát hiện GPU NVIDIA rời. Hệ thống sẽ hoạt động ở chế độ CPU Mode.${NC}"
        HAS_GPU=0
    fi
}

setup_env() {
    print_header "📦 BẮT ĐẦU CÀI ĐẶT MÔI TRƯỜNG & DEPENDENCIES TRÊN SERVER"

    check_python
    check_gpu

    # Tạo virtual environment nếu chưa có
    if [ ! -d ".venv" ]; then
        echo -e "\n${CYAN}📦 Tạo môi trường Python độc lập (.venv)...${NC}"
        $PY_CMD -m venv .venv || true
    fi

    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        VENV_PY="python"
    else
        VENV_PY="$PY_CMD"
    fi

    echo -e "\n${CYAN}📦 Nâng cấp pip và cài đặt thư viện cơ bản từ requirements.txt...${NC}"
    $VENV_PY -m pip install -q --upgrade pip
    $VENV_PY -m pip install -q -r requirements.txt gdown

    echo -e "\n${CYAN}🧊 Thiết lập mô hình 3D LiDAR (spconv + OpenPCDet + nuScenes Weights)...${NC}"
    $VENV_PY tools/setup_3d_model.py --install

    echo -e "\n${CYAN}🧪 Chạy kiểm thử hệ thống...${NC}"
    $VENV_PY -m unittest discover tests

    print_header "🎉 TRIỂN KHAI HOÀN TẤT! SERVER ĐÃ SẴN SÀNG SỬ DỤNG!"
    echo -e "👉 Để đồng bộ gán nhãn CVAT:  bash scripts/deploy_server.sh --sync --host URL --token TOKEN --job-id ID"
    echo -e "👉 Để chạy daemon nền:        bash scripts/deploy_server.sh --daemon --host URL --token TOKEN --job-id ID"
    echo -e "👉 Để cập nhật code mới nhất: bash scripts/deploy_server.sh --update"
}

update_repo() {
    print_header "🔄 CẬP NHẬT MÃ NGUỒN VÀ TRỌNG SỐ TỪ GITHUB (NHÁNH $BRANCH)"

    check_python

    if [ -d ".git" ]; then
        echo -e "${CYAN}📥 Đang kéo commit mới nhất từ origin/$BRANCH...${NC}"
        git fetch origin "$BRANCH"
        git checkout "$BRANCH"
        git pull origin "$BRANCH"
        echo -e "${GREEN}✅ Mã nguồn đã được cập nhật lên phiên bản mới nhất!${NC}"
    else
        echo -e "${YELLOW}⚠️ Thư mục hiện tại không phải git repository. Bỏ qua git pull.${NC}"
    fi

    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        VENV_PY="python"
    else
        VENV_PY="$PY_CMD"
    fi

    echo -e "\n${CYAN}📦 Đồng bộ dependencies mới (nếu có thay đổi trong requirements.txt)...${NC}"
    $VENV_PY -m pip install -q -r requirements.txt

    echo -e "\n${CYAN}🧊 Kiểm tra và cập nhật mô hình 3D nuScenes...${NC}"
    $VENV_PY tools/setup_3d_model.py

    echo -e "\n${CYAN}🧪 Chạy kiểm thử tự động xác nhận tương thích...${NC}"
    $VENV_PY -m unittest discover tests

    echo -e "\n${GREEN}🎉 CẬP NHẬT THÀNH CÔNG! Server sẵn sàng phục vụ!${NC}"
}

check_status() {
    print_header "🩺 BÁO CÁO TRẠNG THÁI SERVER LOCATE-ANYTHING"

    check_python
    check_gpu

    if [ -d ".git" ]; then
        CURRENT_COMMIT=$(git log -1 --format="%h - %s (%cr)")
        CURRENT_BRANCH=$(git branch --show-current)
        echo -e "🌿 Nhánh Git:    ${GREEN}$CURRENT_BRANCH${NC}"
        echo -e "📌 Commit:       ${GREEN}$CURRENT_COMMIT${NC}"
    fi

    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        VENV_PY="python"
        echo -e "🐍 Python Env:   ${GREEN}Virtualenv (.venv)${NC}"
    else
        VENV_PY="$PY_CMD"
        echo -e "🐍 Python Env:   ${YELLOW}System Python ($VENV_PY)${NC}"
    fi

    echo -e "📦 Phiên bản Python: $($VENV_PY --version)"

    # Kiểm tra weights
    WEIGHT_FILE="weights/cbgs_pp_multihead_nds58.pth"
    if [ -f "$WEIGHT_FILE" ]; then
        FILE_SIZE=$(du -h "$WEIGHT_FILE" | cut -f1)
        echo -e "🧊 Weights 3D:   ${GREEN}Đã có sẵn ($FILE_SIZE) - $WEIGHT_FILE${NC}"
    else
        echo -e "🧊 Weights 3D:   ${RED}Chưa tải ($WEIGHT_FILE)${NC}"
    fi

    echo -e "\n🧪 Chạy nhanh kiểm thử đơn vị:"
    $VENV_PY -m unittest discover tests
}

run_sync() {
    check_python
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        VENV_PY="python"
    else
        VENV_PY="$PY_CMD"
    fi
    $VENV_PY colab/cvat_auto_sync.py "$@"
}

run_daemon() {
    check_python
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        VENV_PY="python"
    else
        VENV_PY="$PY_CMD"
    fi
    echo -e "${GREEN}🚀 Khởi chạy CVAT Sync Worker ở chế độ DAEMON nền...${NC}"
    $VENV_PY colab/cvat_auto_sync.py --daemon "$@"
}

# Xử lý tham số dòng lệnh
case "$1" in
    --install)
        setup_env
        ;;
    --update)
        update_repo
        ;;
    --status)
        check_status
        ;;
    --test)
        check_python
        if [ -f ".venv/bin/activate" ]; then source .venv/bin/activate; fi
        $PY_CMD -m unittest discover tests
        ;;
    --sync)
        shift
        run_sync "$@"
        ;;
    --daemon)
        shift
        run_daemon "$@"
        ;;
    *)
        echo -e "${CYAN}Cách sử dụng scripts/deploy_server.sh:${NC}"
        echo -e "  bash scripts/deploy_server.sh --install       Cài đặt môi trường toàn diện (GPU + 2D/3D Weights)"
        echo -e "  bash scripts/deploy_server.sh --update        Kéo code mới nhất từ GitHub & cập nhật dependencies"
        echo -e "  bash scripts/deploy_server.sh --status        Kiểm tra trạng thái server, GPU và weights"
        echo -e "  bash scripts/deploy_server.sh --test          Chạy bộ test suite"
        echo -e "  bash scripts/deploy_server.sh --sync [args]   Chạy đồng bộ gán nhãn tới CVAT"
        echo -e "  bash scripts/deploy_server.sh --daemon [args] Chạy dịch vụ nền lặp lại theo chu kỳ"
        exit 0
        ;;
esac
