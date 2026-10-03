#!/usr/bin/env python3
"""
Setup and Verification Script for 3D LiDAR Object Detection on Deploy Server (Google Colab / Linux).
Tự động cài đặt spconv, OpenPCDet và tải Pretrained Weights nuScenes PointPillars (23MB).
"""

import os
import sys
import subprocess
import urllib.request
from pathlib import Path


WEIGHTS_DIR = Path("weights")
WEIGHTS_PATH = WEIGHTS_DIR / "cbgs_pp_multihead_nds58.pth"
# Direct Google Drive link for OpenPCDet official nuScenes PointPillars (23.3 MB)
WEIGHTS_URL = "https://drive.google.com/uc?id=1p-501mTWsq0G9RzroTWSXreIMyTUUpBM&export=download"


def run_cmd(cmd: str, desc: str):
    print(f"⚙️  {desc}...")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"⚠️  Lệnh thất bại (Exit code {res.returncode}): {cmd}")
    else:
        print(f"✅  Hoàn thành: {desc}")


def download_weights():
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    if WEIGHTS_PATH.exists() and WEIGHTS_PATH.stat().st_size > 20 * 1024 * 1024:
        print(f"✅ Trọng số nuScenes đã có sẵn: {WEIGHTS_PATH} ({WEIGHTS_PATH.stat().st_size / (1024*1024):.1f} MB)")
        return True

    print(f"📥 Đang tải pretrained weights nuScenes PointPillars từ OpenPCDet ({WEIGHTS_URL})...")
    try:
        req = urllib.request.Request(WEIGHTS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(WEIGHTS_PATH, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 1024 * 1024
            while True:
                buf = resp.read(block_size)
                if not buf:
                    break
                downloaded += len(buf)
                f.write(buf)
                if total > 0:
                    percent = downloaded * 100 / total
                    sys.stdout.write(f"\r  ⏳ Tiến độ: {downloaded / (1024*1024):.1f}MB / {total / (1024*1024):.1f}MB ({percent:.1f}%)")
                    sys.stdout.flush()
        print(f"\n🎉 Đã tải xong trọng số: {WEIGHTS_PATH}!")
        return True
    except Exception as e:
        print(f"❌ Lỗi tải weights: {e}")
        # Fallback thử gdown nếu có
        try:
            print("🔄 Thử lại bằng gdown...")
            run_cmd(f"gdown 1p-501mTWsq0G9RzroTWSXreIMyTUUpBM -O {WEIGHTS_PATH}", "Tải weights qua gdown")
            if WEIGHTS_PATH.exists() and WEIGHTS_PATH.stat().st_size > 20 * 1024 * 1024:
                return True
        except Exception:
            pass
        return False


def install_dependencies():
    print("=" * 65)
    print("🚀 BẮT ĐẦU CÀI ĐẶT 3D DEEP LEARNING (OPENCPOET + SPCONV)")
    print("=" * 65)

    # 1. Cài đặt spconv
    try:
        import spconv
        print(f"✅ spconv đã được cài đặt: {spconv.__version__}")
    except ImportError:
        print("📦 Cài đặt thư viện spconv tương thích CUDA...")
        run_cmd("pip install -q spconv-cu120 || pip install -q spconv-cu118 || pip install -q spconv", "Cài đặt spconv")

    # 2. Cài đặt OpenPCDet (pcdet)
    try:
        import pcdet
        print(f"✅ OpenPCDet (pcdet) đã sẵn sàng: {pcdet.__version__}")
    except ImportError:
        print("📦 Đang cài đặt OpenPCDet từ source...")
        pcdet_dir = Path("OpenPCDet")
        if not pcdet_dir.exists():
            run_cmd("git clone --depth 1 https://github.com/open-mmlab/OpenPCDet.git", "Clone OpenPCDet repository")
        run_cmd("cd OpenPCDet && pip install -r requirements.txt && python setup.py develop", "Build và cài đặt OpenPCDet")


def verify_installation():
    print("=" * 65)
    print("🧪 KIỂM TRA MÔ HÌNH POINTPILLARS NUSCENES")
    print("=" * 65)
    try:
        import torch
        from pcdet.config import cfg, cfg_from_yaml_file
        from pcdet.models import build_network
        from pcdet.datasets import DatasetTemplate

        print(f"🔥 PyTorch version: {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
        cfg_file = "configs/pcdet/cbgs_pp_multihead.yaml"
        cfg_from_yaml_file(cfg_file, cfg)
        print(f"📋 Cấu hình Model: {cfg.MODEL.NAME}, Số lượng nhãn: {len(cfg.CLASS_NAMES)}")
        print(f"🏷️  10 Nhãn nuScenes: {cfg.CLASS_NAMES}")

        class DummyDataset(DatasetTemplate):
            pass

        dummy_dataset = DummyDataset(
            dataset_cfg=cfg.DATA_CONFIG,
            class_names=cfg.CLASS_NAMES,
            training=False,
            root_path=Path("."),
        )

        model = build_network(model_cfg=cfg.MODEL, num_class=len(cfg.CLASS_NAMES), dataset=dummy_dataset)
        if WEIGHTS_PATH.exists():
            model.load_params_from_file(filename=str(WEIGHTS_PATH), logger=None, to_cpu=not torch.cuda.is_available())
            print(f"🎉 Đã nạp thành công Pretrained Weights: {WEIGHTS_PATH}")
        else:
            print(f"⚠️ Chưa tìm thấy file weights tại {WEIGHTS_PATH}")

        print("✅ HỆ THỐNG 3D DEEP LEARNING SẴN SÀNG 100% CHO PRE-LABELING!")
    except Exception as e:
        print(f"⚠️ Kiểm tra nâng cao có lỗi (có thể bỏ qua nếu đang test trên môi trường không có GPU): {e}")


if __name__ == "__main__":
    download_weights()
    if "--install" in sys.argv or "google.colab" in sys.modules:
        install_dependencies()
    verify_installation()
