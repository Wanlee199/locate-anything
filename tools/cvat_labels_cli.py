#!/usr/bin/env python3
"""
CLI Công cụ Quản lý Danh mục Nhãn CVAT Đa Hình Thái.
Cho phép kiểm tra tính hợp lệ và xuất cấu hình nhãn sang CVAT Project Specification.
"""

import argparse
import json
import sys
from pathlib import Path

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from locate_cvat import LabelRegistry


def main():
    parser = argparse.ArgumentParser(
        description="CVAT Universal Multi-Modal Label CLI - Quản lý cấu hình nhãn độc lập",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Lệnh validate
    val_parser = subparsers.add_parser("validate", help="Kiểm tra tính hợp lệ của file cấu hình nhãn")
    val_parser.add_argument("config_file", type=str, help="Đường dẫn file cấu hình YAML/JSON")

    # 2. Lệnh summary
    sum_parser = subparsers.add_parser("summary", help="Hiển thị thống kê tổng quan danh mục nhãn")
    sum_parser.add_argument("config_file", type=str, help="Đường dẫn file cấu hình YAML/JSON")

    # 3. Lệnh export-cvat-spec
    exp_parser = subparsers.add_parser("export-cvat-spec", help="Xuất file JSON nạp vào CVAT Project / Task")
    exp_parser.add_argument("config_file", type=str, help="Đường dẫn file cấu hình YAML/JSON")
    exp_parser.add_argument("-o", "--output", type=str, default="cvat_labels_spec.json", help="File JSON đầu ra")

    # 4. Lệnh import-cvat-spec (đọc raw CVAT JSON -> YAML)
    imp_parser = subparsers.add_parser("import-cvat-spec", help="Nhập từ raw CVAT JSON sang YAML cấu hình sạch")
    imp_parser.add_argument("cvat_json", type=str, help="Đường dẫn file raw JSON từ CVAT")
    imp_parser.add_argument("-o", "--output", type=str, default="configs/imported_labels.yaml", help="File YAML đầu ra")

    # 5. Lệnh push (đẩy trực tiếp lên Server CVAT qua REST API)
    push_parser = subparsers.add_parser("push", help="Đẩy trực tiếp danh mục nhãn lên CVAT Project qua REST API")
    push_parser.add_argument("config_file", type=str, help="Đường dẫn file cấu hình YAML/JSON")
    push_parser.add_argument("--host", type=str, required=True, help="Địa chỉ server CVAT (VD: http://192.168.1.10:8080 hoặc https://app.cvat.ai)")
    push_parser.add_argument("--project-id", type=int, required=True, help="ID của Project trên CVAT")
    push_parser.add_argument("--token", type=str, default=None, help="API Token của tài khoản CVAT")
    push_parser.add_argument("--username", type=str, default=None, help="Tên đăng nhập (nếu dùng Basic Auth)")
    push_parser.add_argument("--password", type=str, default=None, help="Mật khẩu (nếu dùng Basic Auth)")

    args = parser.parse_args()

    # Xử lý lệnh import-cvat-spec trước (vì không yêu cầu đọc config_file chuẩn)
    if args.command == "import-cvat-spec":
        try:
            reg = LabelRegistry.load_from_json(args.cvat_json)
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            reg.save_to_yaml(out_p)
            print(f"✅ Đã chuyển đổi thành công {len(reg.labels)} nhãn từ raw CVAT JSON sang: {out_p.resolve()}")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Lỗi import file raw CVAT JSON: {e}")
            sys.exit(1)

    try:
        path = Path(args.config_file)
        if path.suffix in (".yaml", ".yml"):
            registry = LabelRegistry.load_from_yaml(path)
        else:
            registry = LabelRegistry.load_from_json(path)
    except Exception as e:
        print(f"❌ Lỗi đọc file cấu hình: {e}")
        sys.exit(1)

    if args.command == "validate":
        print(f"✅ File cấu hình hợp lệ! Tổng cộng {len(registry.labels)} nhãn.")
        for lbl in registry.labels:
            print(f"  - [{lbl.type.value.upper()}] {lbl.name} (màu: {lbl.color}, hotkey: {lbl.hotkey or 'none'})")

    elif args.command == "summary":
        s = registry.summary()
        print(f"\n📊 TỔNG QUAN DANH MỤC NHÃN: {s['project_name']}")
        print(f"Tổng số nhãn: {s['total_labels']}")
        print("Phân bố theo loại:")
        for t, count in s["by_type"].items():
            print(f"  • {t.capitalize():<10}: {count} nhãn")
        print("\nDanh sách nhãn:")
        print(", ".join(s["labels"]))

    elif args.command == "export-cvat-spec":
        cvat_spec = registry.to_cvat_spec()
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cvat_spec, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã xuất {len(cvat_spec)} nhãn sang định dạng CVAT Project Spec: {out_path.resolve()}")
        print("💡 Bạn có thể import file này trực tiếp khi tạo Project trên CVAT!")

    elif args.command == "push":
        auth_basic = (args.username, args.password) if (args.username and args.password) else None
        print(f"🚀 Đang đẩy {len(registry.labels)} nhãn lên CVAT Project {args.project_id} tại {args.host}...")
        try:
            res = registry.push_to_cvat_api(
                server_url=args.host,
                project_id=args.project_id,
                token=args.token,
                basic_auth=auth_basic,
            )
            print(f"🎉 Thành công! Project '{res.get('name', args.project_id)}' đã được cập nhật toàn bộ nhãn.")
        except Exception as e:
            print(f"❌ Lỗi đẩy nhãn lên CVAT: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
