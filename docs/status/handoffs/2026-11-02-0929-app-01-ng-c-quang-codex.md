# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-02 09:29

**Nhánh:** `codex/APP-01-s24fe-enrollment-binding`, base `f095d27`.
**Trạng thái task sau phiên này:** doing; chưa nghiệm thu ba luồng.

## Đã xong
- Cài APK0.3.0 trên Galaxy S24 FE, kết nối ADB Wi-Fi/reverse8421. Chỉ gỡ bản cũ sau khi người dùng cho phép mất dữ liệu app do khác signer; không gỡ/reset thêm.
- API health `ok`, failed_modules rỗng. Lượt đăng ký đầu review do gaze trajectory mismatch; giữ nguyên ngưỡng/chốt.
- Phát hiện lỗi chắc chắn trong EnrollmentService: thiếu top-level challenge_id khi detector gọi lại expected_dynamic trong enrollment_template. Lỗi này gây enrollment_unavailable503 và rollback sau preflight đủ điều kiện. Lượt thứ hai đã chạy bảy module nhưng chưa có kết quả/account commit; chưa thu response để khẳng định mã lỗi thực tế của lượt đó.
- Bổ sung challenge_id từ challenge phía server, giữ nguyên binding/integrity, lease, deadline và transaction. Review độc lập không có finding.
- Regression coordinator dùng validator production: RED E_CHALLENGE_MISMATCH trước sửa, GREEN sau sửa. Native replay read-only trên media có sẵn trích template512 chiều thành công, binding đúng, 21.641s gồm predict và extraction; không ghi tài khoản/DB, không hiệu chỉnh.

## Đang dở
- Full pytest đã chạy tới100%, exit0; các test thiếu dependency/artifact được skip đúng điều kiện. Log đầy đủ giữ private.
- Đã triển khai frozen source6f3171e, giữ source cũ và backup SQLite đã quick_check. Profile/khóa/DB/media/APK/signer giữ nguyên. Lần khởi động đầu của snapshot thiếu models/manifest.yaml nên dừng đúng chốt; đã đóng gói thêm manifest/third_party từ cùng commit, lập lại hash và khởi động thành công. Health/ownership/HMAC/mode/policy/ADB đều qua; lượt thử mới đang chạy.
- Đăng ký, đăng nhập lại, khôi phục trên điện thoại chưa nghiệm thu; cần lượt thử sau triển khai.

## Bước tiếp theo
1. Theo dõi lượt thử đăng ký mới sau triển khai; chỉ kết luận nghiệm thu từ kết quả thực tế.
2. Hoàn tất review/Draft PR; không merge main hoặc đổi ngưỡng.
3. Người dùng thử lại; theo dõi log và kết quả kỹ thuật, không công khai PII/media/ID/token.

## Quyết định, lưu ý, bẫy
- Server chạy source đóng gói riêng, không tự đọc code worktree. Không sửa ngưỡng để cho phiên qua.
- OTP mô phỏng, model thật/ngưỡng tạm; không dùng số paper làm chất lượng của demo.
- Cleanup từng gặp SQLite busy khi finalize giữ transaction; lượt cleanup sau chạy được. Không đổi BEGIN IMMEDIATE hoặc xóa dữ liệu.
- Runtime đang dùng budget90s; không đổi deadline trong patch này.

## Câu hỏi cho nhóm
- Không có quyết định thiết kế mới. Cần người dùng thao tác điện thoại để nghiệm thu sau cập nhật.

## Test đã chạy
- `python -m pytest services/api/tests/test_enrollment_pipeline.py services/api/tests/test_accounts.py -q --tb=short`: 73 test đạt, exit0.
- Ruff check/format hai file code/test sạch; git diff --check sạch.
- Native LVFace/SCRFD/Face Landmarker replay: template_extracted,512 chiều, binding_matches=true, database_read_only=true, account_created=false. Artifact kỹ thuật nằm trong gói private, không commit media/vector.

- Toàn bộ python -m pytest -q --tb=short: exit0,100% (log private); warning Starlette/Pydantic đã có.
- plan_check.py:0 lỗi,10 cảnh báo đã có. Delivery helper7 test đạt sau cập nhật source path.
