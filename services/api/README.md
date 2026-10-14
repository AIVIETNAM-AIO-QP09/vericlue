# services/api — Máy chủ API (FastAPI)

**Phụ trách:** M5
**Trạng thái:** chưa khởi tạo — làm ở task **PLAT-03** (`docs/plan/epics/E0-platform.md`).

## Trách nhiệm

- Phiên eKYC: tạo phiên, cấp seed thử thách, nhận media và tín hiệu, gọi bộ não, trả kết quả.
- Bàn duyệt: danh sách ca, hồ sơ bằng chứng, ghi quyết định vào nhật ký chuỗi băm.
- Giám định: nhận file, chạy phân tích theo đoạn, sinh và ký báo cáo.

## Quy ước

- Code trong `src/vericlue_api/`, chia `routers/` (HTTP), `services/` (nghiệp vụ), `db/` (SQLAlchemy + Alembic), `core/` (cấu hình, bảo mật, ký số).
- Router chỉ nhận/trả dữ liệu; nghiệp vụ nằm trong `services/`.
- Model request/response khớp `packages/contracts/`.
- Cấu hình chỉ đọc từ biến môi trường (`.env`), không hard-code.
- Mọi lỗi trả về theo một định dạng `{error_code, message}`.

## Lệnh (sau khi khởi tạo)

```bash
uv sync
uv run uvicorn vericlue_api.main:app --reload --app-dir services/api/src
uv run pytest services/api
```
