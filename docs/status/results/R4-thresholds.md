# R4 — chưa có ngưỡng được chứng nhận

Ngày 01/11/2026, công cụ offline ROUT-03 đã được kiểm thử; **chưa có kết quả R4
trên dữ liệu thật** và chưa thay `ml/configs/thresholds.yaml`.

- Core mặt/giọng dùng MAPIE 1.4.1, HB nhị phân, max-p qua các rủi ro rồi Holm
  trên toàn lưới đã khai báo trước; kết quả vẫn không đủ điều kiện runtime.
- Consumer NES2Net toàn câu kiểm model/runtime/parity/calibrator, người/nguồn
  xuyên tập và artifact LTT đã khóa trước tính xác suất test. Không refit trên test.
- [Smoke tổng hợp](ROUT-03-offline-smoke-2026-11-01.json) chạy subprocess thật
  tại source `87a740fcc09c8a42ec71fca421768c6356f8bb16`: bốn lệnh fixture
  thành công, hai từ chối đúng dự kiến; mọi ModuleResult vẫn degraded. Đây là
  fixture synthetic, không chạy trọng số và không phải accuracy sinh trắc.
- Report DNU calib_fit thật được kiểm lại qua CLI fit: từ chối do thiếu lớp
  tấn công, không tạo artifact; byte report giữ nguyên. Không có inference mới.

Chưa thể ghi p-value, ngưỡng thật hoặc alpha thực tế đạt được cho lớp tấn công
khi chưa có quan sát tấn công hợp lệ. Bộ VIVOS32 parity không vào hiệu chỉnh.
Còn cần dữ liệu có quyền sử dụng/crosswalk người–nguồn, protocol quan sát độc
lập và quần thể áp dụng đã review, calibrator thật đúng version, rồi LTT và test.

Mặt có core (B,A) và consumer ghép max PAD/GenD trên calib_fit. [Smoke mặt](ROUT-03-face-candidate-smoke-2026-11-01.json)
chỉ dùng fixture synthetic, giữ 2 hàng thiếu max, không chạy trọng số. Report đo
hiện thiếu stratum/crosswalk/runtime/gate để chọn ngưỡng mặt trung thực. Không
nối các CSV khác tập bằng số dòng.
Bảo đảm cuối luồng mặt–giọng vẫn cần sự kiện/quần thể tương thích và phân bổ
delta chung; chưa được nghiệm thu trên Android.

Xem [runbook](../../runbooks/offline-ltt.md) và
[bàn giao](../handoffs/2026-11-01-2037-rout-03-ngoc-quang-codex.md).
