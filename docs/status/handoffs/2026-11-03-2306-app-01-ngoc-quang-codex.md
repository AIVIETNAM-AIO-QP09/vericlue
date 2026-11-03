# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-03 23:06

**Nhánh:** `feat/APP-01-phone-registration`, nền PR #139.
**Trạng thái task sau phiên này:** doing, chờ nghiệm thu trên thiết bị.

## Đã xong
- Giữ nguyên UI Claude mới cài làm commit nền `5d2774b`; không sửa hướng thiết kế.
- Sau eKYC pass và liên kết thiết bị đã lưu: chuyển thẳng đến đặt mật khẩu,
  điền sẵn SĐT OTP và họ tên CCCD in hoa không dấu. Chỉ sau setup API thành công
  mới tới màn hoàn tất; không tự cấp phiên đăng nhập sau đăng ký.
- Setup username mới chỉ nhận SĐT 10 chữ số, đối chiếu HMAC với SĐT account.
  Onboarding/recovery cần OTP cùng phiên. Reauth legacy cần face/device proof
  và nhập đúng SĐT đã đăng ký. Password login username cũ vẫn được hỗ trợ.
- Contract schema/OpenAPI/types Web cập nhật cùng API và Android. Họ tên gốc
  vẫn có dấu trong hồ sơ; client không được gửi tên thay thế vào setup.
- Lời chào tối thiểu (tên, username/SĐT, account ID, expiry) mã hóa AES-GCM với
  khóa Android Keystore, AAD gắn storage key, không backup. Không lưu mật khẩu,
  token hay CCCD vào hint; hint không cấp quyền. Hết hạn bỏ khi đọc, mất khóa
  hoặc ciphertext hỏng chỉ mất lời chào. Chỉ hiển thị face khi account ID khớp
  liên kết thiết bị. Giữ guard generation sau IO, thu hồi token muộn.
- Test thêm SĐT khác/OTP thiếu, legacy username, tên client không được tin,
  encrypted store chống đổi ciphertext/khóa/storage key, hint hết hạn và
  snapshots setup/lời chào có tên ở sáng/tối, chữ thường/200%.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Android full suite và lượt kiểm tra cuối đã PASS; chờ ký/cài APK và nghiệm thu máy.
- Chưa nghiệm thu đăng ký mới hoặc recovery trên điện thoại; API tests dùng
  dữ liệu tổng hợp và chữ ký thật, không đo độ chính xác sinh trắc.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Nghiệm thu người dùng: OTP → quét CCCD/xác nhận tên → khuôn mặt → đặt mật
   khẩu (không nhập lại tên/SĐT) → thành công → Login có lời chào tên in hoa.
2. Thử mật khẩu sai, tài khoản khác, legacy username, legacy face setup,
   hủy/ra nền khi lưu, retry sau mất phản hồi setup, hết hạn và mất khóa hint.

## Quyết định, lưu ý, bẫy
- Không đổi model/ngưỡng/BBS hoặc thời hạn tài khoản/phiên. Hiển thị tên Latin
  không thay dữ liệu gốc có dấu. SĐT chỉ thay username ở setup mới, không thay
  account ID nội bộ và không tự chuyển chủ tài khoản cũ.
- Setup cần triển khai Android cùng API mới; API cũ chưa chặn chọn SĐT khác.
- Hint cũ chỉ có username được bỏ khi chuyển sang store mã hóa; tài khoản,
  khóa thiết bị và dữ liệu server không bị xóa.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Cần nghiệm thu thực tế trước khi đánh dấu APP-01 done; không có thay đổi
  protected schema nào ngoài account_access phục vụ yêu cầu đã xác nhận.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
API account-access/account-auth/accounts/identity-steps/contracts: 226 PASS.
gen_openapi.py --check: PASS; Web gen:api: PASS; Python Ruff: PASS.
compileDebugKotlin: PASS. plan_check.py: 0 lỗi, 10 cảnh báo.
Android full suite: 547 tests, 0 failures/errors, 1 skipped.
Sau chỉnh chữ/nhãn recovery: 29 tests liên quan PASS; record snapshots, lintDebug,
assembleDebug: BUILD SUCCESSFUL. Lint 0 errors, 44 warnings.
Đã xem ảnh setup và lời chào tên; nút hoàn tất nằm trong màn thường, chữ 200% có cuộn.
```
