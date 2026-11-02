# Bàn giao · SEC-09 · Ngoc Quang+Codex · 30/10/2026

**Nhánh:** codex/APP-01-demo-integration, từ main 7fc2ce9.
**Trạng thái:** doing, hoàn thiện phần client xử lý theo phiên; chưa hoàn thành contract lưu mẫu.

## Đã xong
- SessionApi có GET privacy, POST consent và POST withdraw khớp schema hiện hành; boolean true luôn gửi rõ, không bị serializer bỏ qua default.
- SessionPrivacyFlow giữ receipt đầy đủ, kiểm đúng phiên/version/scope/category/status; không tự grant từ cấu hình. Terms hiển thị thông báo demo-v1, checkbox không tích sẵn, nhận lỗi trước khi chuyển màn.
- Production UI bật enforcePrivacy trong cả hai nơi tạo LiveFlow. Gửi OTP/thẻ/mặt/giọng thiếu receipt bị chặn tại client; server demo cũng bật REQUIRE_PRIVACY_CONSENT=true để kiểm độc lập.
- Withdrawal dừng capture và bước upload mới, dùng bearer mới sau refresh, giữ trạng thái chưa xác nhận khi lỗi. Receipt không bị rút gọn thành deleted=true, không hứa xóa account/backup/chứng nhận.
- Tài liệu mobile-privacy-integration và README Android bổ sung hiện trạng; backlog từ todo -> doing. Không sửa STATUS.md, contract hoặc guard sinh trắc.

## Test đã chạy
- Full Android: 158 test, 0 failure/error/skipped; assembleDebug/lintDebug đạt, lint 0 lỗi/42 cảnh báo.
- 8 test privacy gồm policy đổi, thiếu scope/category, chặn gửi dữ liệu chưa consent, withdraw lỗi/retry, chặn signals/finalize sau withdraw, refresh bị cancel vẫn giữ token mới và không tiếp tục điều hướng.
- Snapshot các màn consent/withdrawal/pass chưa có binding: recordPaparazziDebug đạt; đã xem ảnh đại diện.
- API local: OTP trước consent 409, grant 200, OTP sau consent 200, withdraw 200, bước tiếp theo 410. Chỉ số điện thoại tổng hợp và OTP synthetic, không gửi SMS thật.
- Full services/api/tests exit 0 (có skip các ca opt-in theo môi trường); Ruff check/format phần Python thay đổi đạt.
- plan_check.py: 0 lỗi/10 cảnh báo kế hoạch; diff --check sạch. Chi tiết và báo cáo tại D:/vericlue/tmp/full-demo-setup/.

## Đang dở
- Quyền lưu mẫu tài khoản theo D1: cần contract riêng, receipt và gate server trước EnrollmentService. Không suy diễn face_biometrics thành quyền lưu mẫu. Tiêu chí này giữ chưa xong, ACCOUNT_ENROLLMENT=false.
- iOS chưa tích hợp. Không đánh dấu toàn bộ SEC-09 done chỉ từ phần Android này.
- Thử rút đồng ý và gián đoạn trên điện thoại thật còn chờ; test JVM/HTTP không chứng minh driver/camera hoặc xóa RAM/backup.

## Bước tiếp theo / câu hỏi cho nhóm
1. Cung cấp tập hiệu chỉnh đúng protocol video và kết quả đánh giá; giữ mọi degraded/error không đạt.
2. Thực hiện phần contract quyền lưu mẫu trước khi mở ghi danh; đồng bộ API/SDK/client cùng thay đổi, sau đó nghiệm thu account lifecycle.
3. Dùng APK mới khi nối máy, vì APK cũ chưa ghi consent sẽ bị server chặn đúng thiết kế. Không chia sẻ .env/token/CCCD hoặc tạo ngưỡng giả để đi tiếp.
