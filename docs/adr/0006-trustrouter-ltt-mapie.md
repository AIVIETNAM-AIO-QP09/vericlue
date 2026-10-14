# ADR-0006: TrustRouter chọn ngưỡng bằng Learn-then-Test qua thư viện MAPIE

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Quyết định

- Mỗi bộ phát hiện được **hiệu chỉnh** thành xác suất (Platt hoặc isotonic) trên tập hiệu chỉnh tách theo người.
- **Bước khuôn mặt:**
  - hợp nhất bằng hồi quy logistic có đặc trưng chất lượng;
  - so với hai ngưỡng B < A: dưới B → cho qua, trên A → chuyển nhân viên, ở giữa → bước giọng nói.
- **Bước giọng nói** có ngưỡng riêng.
- **Chọn ngưỡng bằng Learn-then-Test**, dùng `mapie.risk_control.BinaryClassificationController`:
  - mỗi loại tấn công đã biết là một rủi ro;
  - hiệu chỉnh đa kiểm định bằng Holm;
  - trong các bộ ngưỡng hợp lệ, chọn bộ ít chuyển nhân viên nhất.
- **Bảo đảm:** tỷ lệ lọt của cả quy trình ≤ α_mặt + α_giọng (bất đẳng thức hợp).
- **Ngưỡng đã chọn** được khóa trong `ml/configs/thresholds.yaml`, kèm số mẫu, α, δ và commit.
- **ChromaPulse và CamProbe là cổng luật** (đạt / không đạt / chưa rõ), không thuộc phần bảo đảm thống kê.

## Lý do

- Không tự viết phần toán khó: MAPIE (BSD-3) đã có sẵn kiểu hai ngưỡng với vùng chuyển người duyệt.
- Theo khảo sát, chưa có công trình nào áp dụng Learn-then-Test cho quyết định chống giả mạo sinh trắc học; đây là điểm mới chính của đề tài.

## Hệ quả

- Bảo đảm chỉ đúng với loại tấn công đã biết và dữ liệu tương tự dữ liệu hiệu chỉnh. Phải nói rõ trong báo cáo.
- Cần ≥ 59 mẫu cho mỗi loại tấn công để chứng nhận α = 5% với δ = 0,05 (khi không có lỗi).
