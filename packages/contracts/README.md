# Contracts — hợp đồng giữa các phần

Đây là **nguồn sự thật** cho dữ liệu đi qua lại giữa web, API và bộ não AI. Nhờ có hợp đồng cố định, 5 người (và nhiều AI) làm song song mà không lệch nhau.

| File | Dùng cho |
|---|---|
| `schemas/module_result.schema.json` | Kết quả của MỌI bộ phát hiện |
| `schemas/session.schema.json` | API phiên eKYC: tạo phiên, tín hiệu, kết quả |
| `examples/` | Ví dụ JSON hợp lệ (dùng làm dữ liệu test và mock) — thêm ở task PLAT-04 |

## Quy tắc

1. **Đổi schema trước, code sau**, cả hai phía trong **cùng một PR**. Tiêu đề PR có `[contract]`.
2. Chỉ **thêm** trường tùy chọn thì không phá tương thích. **Đổi tên / xóa / đổi kiểu** thì phải tăng phiên bản API (`/v2`) hoặc báo cả nhóm.
3. Phía Python sinh model Pydantic từ schema; phía TypeScript sinh type từ OpenAPI của FastAPI (task PLAT-04).
4. Không ai tự thêm trường "tạm" ngoài schema.
