# ADR-0001: Monorepo, hợp đồng cố định, mô-đun giả lập trước

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Bối cảnh

5 người và nhiều AI agent làm song song trong 3 tuần. Web, API và mô hình AI phụ thuộc lẫn nhau. Nếu chờ mô hình xong mới làm web, cả dự án sẽ bị tắc.

## Quyết định

- **Một repo duy nhất** (monorepo): `apps/web`, `services/api`, `ml`, `packages/contracts`, `docs`.
- **Hợp đồng dữ liệu** bằng JSON Schema trong `packages/contracts/` là nguồn sự thật.
- Mọi bộ phát hiện có **bản mock** trả kết quả đúng định dạng. Chuyển giữa mock và mô hình thật bằng `USE_MOCK_MODELS`.
- Python quản lý bằng **uv workspace** (`services/api` và `ml` là hai gói). Web dùng **npm**.

## Phương án đã cân nhắc

- **Nhiều repo:** khó đồng bộ hợp đồng, AI khó thấy toàn cảnh.
- **Không mock, làm tuần tự:** web và API phải chờ mô hình, rủi ro trễ hạn rất cao.

## Hệ quả

- Hệ thống chạy được đầu–cuối từ cuối Sprint 0 (mốc M0).
- Đổi hợp đồng phải sửa schema trước và sửa cả hai phía trong cùng PR.
