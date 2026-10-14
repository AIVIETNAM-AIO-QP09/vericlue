# ADR-0008: Báo cáo giám định theo ENFSI, có chữ ký; quét nguồn gốc là bằng chứng một chiều

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Quyết định

- **Chia đoạn:** 2–3 giây, chồng lấn 50%. Đoạn không có mặt hoặc im lặng ghi "không áp dụng" thay vì cho điểm thấp.
- **Đoạn nghi giả:** ghi thành **khoảng thời gian ±1 giây**, không ghi mốc chính xác tới từng khung.
- **Mức độ bằng chứng:** dùng thang lời **ENFSI 2015**, suy ra từ **tỷ số khả năng đã hiệu chỉnh**, không suy ra từ xác suất thô. Lý do: InVID và TrueMedia đổi xác suất thô thành chữ, cách này không đúng chuẩn giám định.
- **Hash SHA-256** tính trên byte gốc, **trước** mọi bước chuyển mã.
- **Quét nguồn gốc:**
  - AudioSeal và Perth (thủy vân âm thanh), c2pa-python (chứng nhận nguồn gốc);
  - **một chiều**: có thủy vân → "do AI tạo, công cụ X"; không có → "không có tín hiệu nguồn gốc", **không** có nghĩa là thật.
- **Ký báo cáo** bằng Ed25519 (thư viện `cryptography`), in kèm dấu vân tay khóa công khai.
- **Báo cáo có mục giới hạn bắt buộc;** là công cụ hỗ trợ, không thay thế giám định tư pháp.

## Hệ quả

- Cần tập hiệu chỉnh riêng cho chế độ giám định, gồm cả video đã nén.
- Bàn duyệt 3 giai đoạn (duyệt mù trước khi xem AI) để sau. Bản thi dùng nguyên tắc "nhân viên quyết trước, AI hiện sau" ở dạng đơn giản.
