# data — Dữ liệu (KHÔNG commit)

Thư mục này nằm trong `.gitignore`, trừ file README này. Dữ liệu được tải bằng script. Không ai copy tay rồi gửi cho nhau qua Zalo hay Drive.

```
data/
├── raw/          bộ dữ liệu gốc tải về (zalo2022/, rtfs10k/, mlaad_vi/, vimd/, ...)
├── interim/      đã cắt mặt, chuẩn hóa âm thanh, đã nén lại
├── synth/        dữ liệu tự tạo từ nguồn công khai (deepfake người Việt, giọng giả)
├── splits/       danh sách train / calibration / test (file .csv nhỏ, ĐƯỢC phép commit qua ml/configs nếu cần)
└── selftest/     video chạy thử ChromaPulse của thành viên nhóm (xóa sau dự án)
```

- **Danh sách bộ dữ liệu, giấy phép, cách tải:** `docs/data/data-plan.md`.
- **Lệnh tải:** `uv run python scripts/download_data.py --help` (task DATA-01).

## Quy tắc

1. Chỉ dùng dữ liệu công khai có giấy phép cho nghiên cứu. **Không** thu dữ liệu sinh trắc học của người ngoài nhóm.
2. Dữ liệu tự tạo chỉ dùng nội bộ, không phát tán.
3. Chia tập **theo người**: một người không được xuất hiện ở cả tập train lẫn tập test.
4. Tập test **không được dùng** để chọn ngưỡng hay chọn mô hình.
