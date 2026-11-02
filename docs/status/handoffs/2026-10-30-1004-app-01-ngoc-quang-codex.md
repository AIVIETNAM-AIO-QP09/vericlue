# Bàn giao · APP-01 · Ngoc Quang+Codex · 30/10/2026

**Nhánh:** codex/APP-01-demo-integration, từ main 7fc2ce9.
**Trạng thái:** doing; chưa nghiệm thu toàn bộ demo thật. Không push/mở PR.

## Đã xong
- Android ghi consent xử lý phiên trước OTP/CCCD/camera/micro, theo thông báo demo-v1 thực sự hiển thị. Giữ đủ phạm vi/receipt; policy đổi, response sai/thiếu, request lỗi không cho tiến tới bước thu dữ liệu.
- Reauth có binding: đồng ý phiên -> L0 -> mặt, bỏ Phone/OTP. Recovery có binding: đồng ý -> OTP demo -> mặt, bỏ CCCD mới theo API account-authentication. Giữ nguyên chốt sinh trắc 503 của server.
- Dừng có thao tác rút consent; chặn bước upload mới giữa media/signals/finalize. Tuần tự hóa refresh/withdraw bằng mutex; refresh được nhận bearer mới kể cả khi rời màn, sau đó khôi phục cancellation của caller. Lỗi giữ ngữ cảnh để retry; có về màn chính với trạng thái chưa xác nhận xóa. Thành công bỏ back stack cũ.
- Phân biệt pass phiên với binding tài khoản đã lưu: thiếu receipt/lỗi lưu không dẫn tới màn mở tài khoản. Không xóa khóa cũ khi chưa lưu bền binding mới.
- API chỉ bổ sung lựa chọn Quality SCRFD/CamProbe rules thật khi SESSION_FACE_MODELS bật; không sửa capture/, schema, ADR hoặc thresholds; không dùng ngưỡng tay để ép đạt. iOS chưa xử lý.

## Kiểm tra
- Đã quan sát test đỏ cho lớp privacy chưa có, accountSaved chưa có, withdraw giữa media/signals và cancellation của refresh; sau sửa full Android testDebugUnitTest + assembleDebug + lintDebug đạt.
- 158 test, 0 failure/error/skipped; CitizenCopyTest và ThemeAccessibilityTest đạt. Lint 0 lỗi, 42 cảnh báo hiện có.
- recordPaparazziDebug --tests '*OnboardingJourneySnapshotTest*': đạt, có trạng thái consent reauth, withdrawal/lỗi, pass chưa có tài khoản; sáng/tối, compact, chữ 200%, ngang. Đã xem ảnh đại diện (nội dung dài cuộn, nút vẫn nhìn thấy).
- Kiểm API local với REQUIRE_PRIVACY_CONSENT=true: OTP trước consent 409; GET/grant 200; OTP demo sau consent 200; withdraw 200/files_deleted, processing_cleanup=not_verified, account_data_erased=false; OTP sau withdraw 410.
- Full services/api/tests: exit 0 (các ca opt-in thiếu môi trường được skip); thêm 4 test factory Quality/CamProbe, không tải model trong test. Ruff check/format của Python thay đổi đạt. Runtime bổ sung jsonschema theo dev dependencies để chạy contract tests.
- plan_check.py: 0 lỗi, 10 cảnh báo tải/phụ thuộc của kế hoạch. git diff --check sạch.
- Review độc lập bắt và đã sửa các lỗi bearer/cancellation, back stack sau withdrawal và không có lối thoát khi bearer hết hạn. Không dùng review source thay nghiệm thu máy thật.

## Chạy trên máy này
- Cấu hình/model/runtime và báo cáo: D:/vericlue/tmp/full-demo-setup/README.md.
- Server: D:/vericlue/tmp/full-demo-setup/VeriClue.cmd start|stop|status. Chỉ một server localhost:8421; DB/khóa cũ được giữ. Không chia sẻ server/.env.
- APK cục bộ ở D:/vericlue/tmp/full-demo-setup/apk/VeriClue-demo-debug.apk đã ký/kiểm chữ ký v2, fingerprint debug khớp bản thử laptop trước. Checksum ở cùng thư mục. Đây là khóa debug laptop, không phải khóa phát hành demo của nhóm; không tự gỡ app/xóa Keystore nếu điện thoại có bản ký khác.
- Nối USB/adb reverse tcp:8421 tcp:8421, mở app debug -> Xem tất cả màn -> API thật -> Đăng ký. OTP hiển thị SMS mô phỏng. Điện thoại để test sau theo yêu cầu người dùng.

## Đang dở / câu hỏi cho nhóm
- Không tìm thấy dữ liệu/đầu ra hiệu chỉnh đúng protocol video trong D:/vericlue, D:/vericlue-wt, Downloads/Desktop, ZIP vericlue-e-local và artifact GitHub. data/ chỉ có README. Các calibrator repo là provisional identity, n_pos=n_neg=0 của pipeline cũ; tài liệu ngưỡng 0.40 là AdaFace cũ, không dùng cho LVFace/video.
- Cần dữ liệu chia theo người cho calib_fit/calib_ltt và đánh giá độc lập; sau đó thực thi đường đọc artifact/quyết định cho PAD/GenD/giọng đang diagnostic. Không chỉ trỏ env vào file rồi coi hardcoded unclear đã biến mất.
- SEC-09 còn thiếu contract/receipt đồng ý lưu mẫu tài khoản riêng và kiểm ghi danh. Consent theo phiên không thay quyền lưu tài khoản; ACCOUNT_ENROLLMENT vẫn false.
- USE_MOCK_MODELS=true giữ OTP synthetic; các cờ session_* chạy các lõi phiên thật, Quality SCRFD/CamProbe rules cũng được chọn thật bởi SESSION_FACE_MODELS; không fallback mock khi lỗi. Toàn bộ model nạp/suy luận tổng hợp đã chạy ở phiên setup, không phải số liệu accuracy. Chưa mở real/mixed hoặc account-bound guards.
- Nghiệm thu điện thoại: quyền camera/micro, mất mạng/đưa xuống nền, QR/ảnh CCCD, video liên tục, yaw/offset, rút đồng ý khi đang refresh/upload, TTL và binding thật. Chưa thể khẳng định demo đăng ký/đăng nhập/khôi phục đạt đầu-cuối.
