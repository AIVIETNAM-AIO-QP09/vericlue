# ADR-0007: ChromaPulse đo độ trễ tuyệt đối; CamProbe kiểm tra API bị can thiệp

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Bối cảnh

Khảo sát mã nguồn cho thấy hai điều:
- Deep-Live-Cam có chế độ hòa trộn Poisson, khiến mặt ghép **vẫn phản chiếu** ánh sáng màn hình, chỉ bị trễ. GOTCHA (EuroS&P 2024) ghi nhận mặt giả "làm theo" thử thách nháy sáng 52–83% số lần.
- Đã có tiện ích Chrome công khai thay hàm lấy camera trên trang KYC. Một số còn giả trọn bộ thông số camera thật.

## Quyết định

**ChromaPulse:**
- Phát màu bằng mã chép từ **AWS Amplify Liveness** (Apache-2.0): tô quanh khung oval, kéo mặt lại gần, giữ yên 1 giây.
- Giữ **bảng màu pastel an toàn** của nhóm: ≤ 2,5 lần đổi màu/giây, không dùng đỏ bão hòa.
- **Đo độ trễ tuyệt đối:** thời điểm vẽ màu (`requestAnimationFrame`) so với thời điểm chụp từng khung (`requestVideoFrameCallback.captureTime`), trên cùng đồng hồ `performance.now()`. **Không** dùng MediaRecorder để đo thời gian.
- Server khớp chuỗi màu trong miền log, có trừ nền, quét độ trễ τ từ 0–300 ms. Kết quả là R² và τ.

**CamProbe:**
1. Kiểm tra hàm camera bị can thiệp theo kỹ thuật **CreepJS** (MIT): `toString` có còn `[native code]`, so với bản gốc trong `<iframe>` sạch.
2. Thăm dò `applyConstraints` và đọc lại `getSettings()` để xem thông số có thật sự đổi.
3. Phát hiện khung hình lặp hoặc nhịp khung đều bất thường.

## Hệ quả

- Kiểm tra API chỉ là **một lớp**: kẻ tấn công có thể vá về sau. Tấn công ở tầng nhân Android chỉ ChromaPulse bắt được.
- Phân tích độ trễ phía server là phần nhóm tự xây (không có mã nguồn mở tương đương), cần chạy thử sớm ở Sprint 0 (task PRES-01).
