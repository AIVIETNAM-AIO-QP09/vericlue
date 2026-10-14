# AGENTS.md — services/api/ (FastAPI)

Bổ sung cho `AGENTS.md` ở gốc repo. Đọc thêm `services/api/README.md` và `docs/architecture/architecture.md` §4–§6.

- **Router chỉ nhận và trả dữ liệu; nghiệp vụ nằm trong `services/`.**
- **Request/response khớp `packages/contracts/`.** Đổi hợp đồng thì sửa schema trước, PR có `[contract]`.
- **Phản hồi cho `/verify` không bao giờ chứa điểm số** hay chữ "giả mạo" — có test bảo vệ, đừng xóa test đó.
- **`error`/`degraded` ở bước bắt buộc → `review`**, không bao giờ `pass`.
- **Cấu hình chỉ đọc từ biến môi trường** (`core/config.py`); không hard-code bí mật.
- **`review_events` chỉ ghi thêm** (chuỗi băm). Không viết code UPDATE hay DELETE bảng này.
- **Hash file giám định** tính trên byte gốc, trước mọi bước chuyển mã.
- **Lỗi trả về theo một định dạng:** `{error_code, message}`.
- Test bằng `TestClient` với `USE_MOCK_MODELS=true`; kịch bản đầu–cuối ở `tests/e2e/`.
