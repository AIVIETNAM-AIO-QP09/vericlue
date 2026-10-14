# ADR-0009: Hạ tầng tối giản cho demo; chính sách giấy phép

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Quyết định

**Hạ tầng:**
- FastAPI, PostgreSQL 16, và thư mục file tạm tự xóa theo hạn.
- **Không** dùng Redis, MinIO hay hàng đợi riêng. Việc nền chạy bằng `BackgroundTasks` hoặc thread pool của FastAPI.
- Chạy demo bằng Docker Compose trên **một máy có GPU** tại gian hàng, không phụ thuộc mạng. Có video dự phòng.
- Python 3.12 qua `uv`; Node.js ≥ 20 qua `npm`.

**Giấy phép:**
- **Được chép code:** MIT, Apache-2.0, BSD. Giữ dòng giấy phép, ghi vào `third_party/README.md`.
- **Được dùng trọng số chỉ cho phi thương mại** (SBI, SCRFD, AntiDeepfake, các bộ dữ liệu NC) cho bản thi. Ghi rõ trong bảng giấy phép, có phương án thay thế khi thương mại hóa.
- **Cấm** đưa vào sản phẩm: code GPL, AGPL, LGPL và repo không có giấy phép. Công cụ tấn công chỉ chạy trên máy red-team riêng.
