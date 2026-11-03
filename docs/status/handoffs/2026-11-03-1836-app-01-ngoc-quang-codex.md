# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-03 18:36

**Nhánh:** `feat/APP-01-account-access`, nền PR #136 (`c7faca1`).
**Trạng thái task sau phiên này:** doing — cần nghiệm thu camera/đăng ký/khôi phục trên điện thoại.

## Đã xong
- Mở app: logo → đăng nhập; Mở tài khoản → giới thiệu xác minh hiện có.
- Sau pass và lưu receipt: thiết lập tên đăng nhập/mật khẩu với đồng ý lưu hồ sơ;
  Vào ứng dụng trở lại đăng nhập. Tài khoản bản cũ dùng camera để thiết lập lần đầu.
- Đăng nhập mật khẩu hoặc camera VeriClue thụ động; không dùng Android biometric.
  Chỉ đổi phiên camera lấy access token sau pass có đủ bằng chứng và binding.
- Hồ sơ hiển thị dữ liệu API có thật, che CCCD; không bịa số dư hoặc số tài khoản ngân hàng.
- Contract viết trước code; API có migration 0012, mã hóa hồ sơ, băm mật khẩu,
  giới hạn thử sai bằng DB, token thu hồi được. Giữ nguyên ngưỡng/model eKYC.
- Chặn kết quả muộn sau Back/ra nền, xóa mật khẩu trong RAM, bảo vệ back stack,
  xử lý thiết lập đã được server ghi nhưng client mất phản hồi; khóa mất phải khôi phục.
- UI Compose theo hệ thống VeriClue, Three.js có sẵn; camera giữ oval và lịch ghi.
  Chỉ báo tiến độ đoạn quay thụ động theo thời gian thật, không giả lập kết quả.

## Đang dở
- Chưa có lượt người dùng nghiệm thu luồng đăng ký → thiết lập → đăng nhập mật khẩu
  và camera → hồ sơ → đăng xuất bằng mô hình thật cho phiên bản này.
- Task APP-01 còn các mục HTTPS/nghiệm thu ba luồng từ trước, không đổi sang done.

## Bước tiếp theo
1. Nâng DB bằng migration và bật `ACCOUNT_ACCESS_ENABLED=true` cùng enrollment/privacy.
2. Cài APK cùng chữ ký, giữ dữ liệu. Thử mở app → Mở tài khoản → đăng ký,
   thiết lập username/password, Vào ứng dụng → login → hồ sơ → logout/Back.
3. Thử camera ngắn trên thiết bị đã ghi danh; nếu API yêu cầu giọng phải hoàn tất
   bước đó. Không dùng timeout, thanh tiến độ hoặc kết quả dựng sẵn để mở hồ sơ.
4. Thử sai mật khẩu, mất mạng, Back khi đang bắt đầu quét và đưa app xuống nền.

## Quyết định, lưu ý, bẫy
- User đã xác nhận luồng splash → login và chọn camera VeriClue, không biometric hệ điều hành.
- `ACCOUNT_ACCESS_ENABLED` mặc định false; account TTL giữ 24 giờ, bearer hồ sơ
  tối đa 15 phút. Hồ sơ/token không được lưu xuống Android; đi nền yêu cầu đăng nhập lại.
- Thiết lập mới cần username 3–32 ký tự, mật khẩu 12–128 ký tự, consent riêng.
  Recovery đổi mật khẩu, giữ hồ sơ/TTL và làm phiên cũ không còn hợp lệ.
- Tài khoản cũ không có dữ liệu tên/CCCD trả null, UI bỏ trường đó; số điện thoại
  server chỉ giữ HMAC nên không tự suy ra hoặc hiển thị số bịa.
- Test API dùng dữ liệu tổng hợp/chữ ký thật trong fixture, không phải số đo chất lượng AI.
- Không đưa vào commit file research JSON người dùng đã có sẵn, dữ liệu, trọng số,
  `.env`, APK, ảnh snapshot hay khóa ký.

## Câu hỏi cho nhóm
- Không cần quyết định thêm cho luồng đã xác nhận; chờ người dùng nghiệm thu cảm giác
  chuyển động và camera trên S24 FE. PR #136 vẫn mở; PR mới cần ghi rõ quan hệ nền.

## Test đã chạy
```
Android compileDebugKotlin + compileDebugUnitTestKotlin: PASS.
Lượt Android ban đầu: 533 tests, 0 failure/error, 1 existing export skip.
Lượt cuối sau sửa Back/bố cục: 535 tests, 0 failure/error, 1 existing export skip.
lintDebug: 0 errors, 44 warnings. assembleDebug: BUILD SUCCESSFUL,
LIVE_API_DEFAULT=true, SIGNED_MEDIA=true, PRESENCE_TRACE_ENABLED=false.
recordPaparazziDebug: đã xem ảnh login/face/profile sáng-tối và font lớn;
test kiểm nút Mở tài khoản không khuất ở 375×812, font lớn có thể cuộn.
API: 304 regression tests PASS; 20 account-access tests PASS sau sửa thứ tự lock.
uv run --no-sync pytest services/api/tests/test_account_access.py services/api/tests/test_accounts.py services/api/tests/test_account_auth.py services/api/tests/test_contract_examples.py services/api/tests/test_contract_schema.py services/api/tests/test_request_limits.py services/api/tests/test_privacy_consent.py services/api/tests/test_security_profile.py -q --tb=short --show-capture=no
Ruff API/migration/tests: PASS. OpenAPI --check: PASS.
plan_check.py: 0 lỗi, 10 cảnh báo tải công việc/phụ thuộc có sẵn.
```

## Triển khai local và PR

- PR #137 (ready for review), base PR #136; không tự merge.
- APK từ commit `18904b8da941f6ef616ef3c8678074725171246e` đã ký bằng khóa demo
  hiện có và cài đè S24 FE thành công; giữ dữ liệu/Keystore. SHA-256 trên thiết bị
  khớp `fee1bae140d479517a73b9d58af8b3d702718135e4fb696abf97fe1607560a66`.
- Đã thấy màn đăng nhập khuôn mặt/Three.js mới trên điện thoại. Người dùng
  đang thử; chưa có bằng chứng hoàn tất cả hai cách đăng nhập trên thiết bị.
- Server 8421 đã nạp model xong, migrate 0012 và bật account access. Smoke
  giai đoạn A đạt, giữ đúng `phone-demo-fixed-v1`; phiên tổng hợp được rút đồng ý.
  API password sai và `/me` thiếu bearer đều trả 401, không mở hồ sơ.
- CI đầu tiên phát hiện Web thiếu type sinh lại. Đã chạy `npm.cmd run gen:api`,
  cập nhật `apps/web/src/lib/api/schema.d.ts`; `typecheck` và `lint` đạt.
  Bản sửa này chỉ thay type Web và bàn giao, không thay code APK đã cài.
