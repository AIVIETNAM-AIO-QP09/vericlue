# ADR-0003: Làm web trên điện thoại, không làm app native

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Quyết định

- Luồng xác minh chạy trên **trình duyệt điện thoại** (Next.js).
- Bàn duyệt và cổng giám định là **web trên máy tính**.
- Lõi phân tích cung cấp qua **API** để đơn vị khác tích hợp.

## Lý do

- Một bộ code cho cả Android và iPhone; nhóm mạnh web.
- Khách tham quan quét QR là trải nghiệm được, không phải cài app.
- Chống camera ảo trên web là điểm khác biệt, vì các hãng lớn chỉ làm trên SDK native.

## Hệ quả

- Web **không** kiểm tra được máy bị root hay hook ở cấp hệ điều hành. Ghi rõ là giới hạn; phần đó thuộc app của đơn vị tích hợp.
- iPhone không khóa được phơi sáng camera, nên ChromaPulse phải bù bằng cách trừ vùng nền.
