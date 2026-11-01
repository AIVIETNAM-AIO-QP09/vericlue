# Bàn giao · SEC-09 · Ngoc Quang+Codex · 2026-11-01 20:30

**Nhánh:** codex/SEC-09-postgres-consent-review
**Trạng thái task sau phiên này:** doing

## Đã xong
- Regression PostgreSQL migration 0011: hai grant đồng thời cùng receipt/một hàng; UPDATE và DELETE bị P0001; FK receipt sai bị 23503; rollback giữ receipt/link hợp lệ.
- Review độc lập xác nhận phù hợp spec/chất lượng, không có Critical/Important. Không đổi production code/migration/API/Android.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- PostgreSQL local skip vì không có TEST_DATABASE_URL. CI dùng DB vericlue_test riêng; chỉ sau CI mới xác nhận hành vi trên engine này.
- Không có điện thoại để nghiệm thu CCCD/mặt/giọng và ba luồng. OTP vẫn mô phỏng, demo AI thật chưa nghiệm thu.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Xem CI PostgreSQL trên Draft PR, sửa nếu có lỗi thực tế. Không dùng DB sản phẩm để chạy test.
2. Khi có điện thoại, cài đè APK đã chuẩn bị và thử checklist ba luồng/consent; không reset dữ liệu.

## Quyết định, lưu ý, bẫy
- Test trên DB synthetic, không tác động tài khoản/media thật. Race bắt đầu qua barrier; engine kiểm một receipt bền vững và FK/trigger thật.
- Giữ SEC-09 doing; không đóng toàn task từ kết quả tự động.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Chưa có câu hỏi mới; điều kiện nghiệm thu thiết bị vẫn còn.

## Test đã chạy
<!-- lệnh + kết quả thật -->
- Nhóm regression API (dynamic_flows, manual_face_demo, session_calibration_guards, privacy_consent, accounts, account_auth, enrollment_pipeline, session_guards, session_ingress, media_proof, challenge_refresh): **333 passed**, 42.04s, một cảnh báo thư viện.
- test_security_postgres.py -k account_template -rs: **1 skipped**, 3 deselected; lý do thiếu TEST_DATABASE_URL, không báo đạt PostgreSQL.
- Ruff check/format file test: sạch. plan_check: 0 lỗi, 10 cảnh báo tải/đường găng hiện có.
