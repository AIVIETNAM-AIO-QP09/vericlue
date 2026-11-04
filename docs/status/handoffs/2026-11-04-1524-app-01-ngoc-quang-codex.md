# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-04 15:24

**Nhánh:** `codex/APP-01-consent-ui-polish`; nền `8f3e67b`.
**PR:** #141 vào main, gồm chuỗi PR137–140 chưa có trên main cùng UI polish.
**Trạng thái task:** doing, còn nghiệm thu thiết bị/HTTPS/ba luồng.

## Đã xong
- Hai subagent review độc lập phát hiện ba lỗi có bằng chứng trước merge;
  root kiểm lại mã, sửa trong phạm vi account-access và kiểm tra local.
- Không xóa username khi mở quét mặt; hủy/lỗi/đăng nhập mặt rồi đăng xuất
  không để form mật khẩu ẩn username bị khóa. Mật khẩu vẫn được xóa. Sau
  trao đổi đăng nhập thành công, đồng bộ username từ hồ sơ server đã kiểm:
  tránh trường hợp máy có binding A nhưng chưa có hint, nhập B rồi đăng nhập
  mặt thành A, logout lại hiển thị lời chào A nhưng gửi mật khẩu tới B.
- Popup quét mặt khi dispose chỉ dừng/unlock/unbind camera. Xóa MP4 thuộc
  quyền App khi server ACK, người dùng hủy hoặc bỏ lượt; giữ bản chưa ACK
  để nhánh retry/timeout hiện có gửi lại được.
- Công cụ xoay master key xử lý thêm DEK AccountAccessCredentialRow bằng
  đúng AAD/master; thêm khóa bảng PostgreSQL, đếm live/erased và fail-closed
  nếu xóa dở. Payload không đổi, lỗi một envelope rollback tất cả.
- Test rotation bổ sung dry-run, giữ nguyên payload, dùng master mới và từ
  chối master cũ, corruption/partial-erasure/rollback; cập nhật runbook CLI.

## Kiểm chứng
- Subagent tái hiện RED: 8 lỗi mong đợi ở rotation trước sửa.
- Root chạy lại test_key_rotation.py + test_account_access.py cô lập:
  44 PASS, 1 SKIP (host thiếu quyền tạo symlink), 1 deprecation warning có sẵn.
- Ruff check và format --check hai file Python: PASS. git diff --check: PASS.
- Android testDebugUnitTest các nhóm AccountAccess, LoginHint, LiveFlowRetry,
  ResponseGuards, VideoCompletion, PresenceTraceCache, QuickFaceLogin:
  BUILD SUCCESSFUL, 74 tests, 0 failure/error/skip.
- Sau bổ sung đồng bộ username từ hồ sơ đã xác thực: compileDebugKotlin PASS.
- CI 10/10 xanh ở nền 8f3e67b; sẽ chờ CI lại trên commit sửa trước merge.

## Giới hạn và bước tiếp theo
- Chưa có test dựng toàn bộ VeriClueApp/CameraX/Keystore cho chuỗi nhớ tài
  khoản → mặt → hủy/lỗi hoặc thành công → logout → mật khẩu. Các test hiện
  có kiểm logic/form, retry và ACK; chưa mô phỏng trực tiếp dispose popup thật.
- Cần thử trên điện thoại các ca trên và lỗi mạng/finalize timeout rồi gửi lại.
- PostgreSQL lock được review trong code, chưa chạy với PostgreSQL thật trong
  phiên này. Không thay khóa/cấu hình, DB, tài khoản, server hay thiết bị thật.
- User đã cho phép mở PR và merge; chỉ merge sau CI đạt đúng commit sửa.

## Câu hỏi cho nhóm
- Không có quyết định mới cần hỏi cho các lỗi đã xác nhận. Giữ task doing
  cho tới nghiệm thu thiết bị, không suy khả năng AI từ unit test.
