# models — Trọng số mô hình (KHÔNG commit)

Trọng số được tải bằng `uv run python scripts/download_models.py` (task DATA-02), dựa theo `manifest.yaml`.

- Bản tinh chỉnh của nhóm lưu ở `models/finetuned/<tên>/<ngày>/`, kèm `card.md` ghi: dữ liệu, siêu tham số, kết quả, commit.
- Khi đổi mô hình dùng trong demo, cập nhật `ml/configs/models.yaml` và ghi vào `docs/status/STATUS.md`.
- Chú ý giấy phép từng mô hình (cột `license` trong `manifest.yaml`). Mô hình **chỉ dùng phi thương mại** phải được ghi rõ trong báo cáo.
