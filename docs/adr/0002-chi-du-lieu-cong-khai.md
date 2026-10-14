# ADR-0002: Chỉ dùng dữ liệu công khai, không tổ chức thu dữ liệu

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Bối cảnh

Mục tiêu của bản thi là demo chạy được. Thu dữ liệu sinh trắc học cần đồng ý theo Nghị định 356/2025, tốn thời gian và có rủi ro pháp lý.

## Quyết định

- Chỉ dùng bộ dữ liệu công khai liệt kê trong `docs/data/data-plan.md`, chủ yếu: Zalo AI 2022, Face_anti_spoofing, RTFS-10k, WildDeepfake, MLAAD-vi, ViSpoofDB, VSASV, ViMD, ViCocktail.
- Khoảng trống (deepfake người Việt, video nén mạng xã hội) được **tự tạo từ nguồn công khai**.
- ChromaPulse và CamProbe chỉnh ngưỡng bằng **chạy thử của chính thành viên nhóm**. Đây là kiểm thử phần mềm, không phải thu dữ liệu.
- Tấn công trình diễn trực tiếp chỉ dùng mặt và giọng của thành viên nhóm, có đồng ý.

## Hệ quả

- Kết quả không đại diện cho môi trường eKYC thật; báo cáo phải nói rõ điều này.
- Bảo đảm thống kê tính riêng cho từng bước (mặt, giọng), vì dữ liệu công khai không có phiên ghép cả hai.
