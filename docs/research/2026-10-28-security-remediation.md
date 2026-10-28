# Khắc phục sau rà soát bảo mật — 28/10/2026

Cơ sở đối chiếu: main `caf4469`, bản rà soát cục bộ trong
`artifacts/security-review-2026-10-28/` và task SEC-03…08. Bằng chứng kiểm thử của
bản tích hợp nằm trong [bàn giao](../status/handoffs/2026-10-28-2126-sec-06-codex-integration.md).
Mọi kiểm tra mới dùng dữ liệu tổng hợp và kho disposable. Không thay cấu hình,
khóa, dữ liệu hoặc retention của kho đang dùng; không mở guard sinh trắc thật.

“Đã sửa trong code” dưới đây chỉ nói về đường chạy được nêu, không chứng nhận
toàn hệ thống an toàn hoặc đủ điều kiện nhận dữ liệu thật.

| Mã | Kết quả trong bản vá | Còn phải nghiệm thu/xử lý |
| --- | --- | --- |
| AUD-01 | Nhận diện ảnh theo nội dung; bounds trước OCR/ML; bỏ metadata; chữ ký kiểm trên byte gốc | Chất lượng OCR/model sau chuẩn hóa trên thiết bị và dữ liệu hợp lệ |
| AUD-02 | Counter/quota bền; tên file riêng; rollback giữ cặp cũ; dọn cặp thay thế sau commit | Orphan do kill/unlink lỗi giữ tới TTL; chưa có janitor an toàn đa worker |
| AUD-03 | Bearer hiện hành và consent được kiểm trước parser, kiểm lại sau upload | Proxy/TLS, timeout và giới hạn kết nối ngoài API |
| AUD-04 | Mode eKYC có retention hữu hạn, review không tạo ca nhân viên; chặn đọc/quyết định quá hạn | Operator rà kho cũ và backup trước khi đổi mode; chưa thực thi trên kho thật |
| AUD-05 | Profile protected fail-closed; khóa nền độc lập; preflight không in secrets; API bind loopback | Operator vẫn có thể chọn synthetic; preflight không chứng minh entropy/ACL/TLS hay cờ app |
| AUD-06 | OTP mô phỏng chỉ trong synthetic+mock; real/mixed/protected bị chặn | Chưa có SMS provider thật, chưa chứng minh quyền giữ số điện thoại |
| AUD-07 | Contract/API/SDK consent theo phiên bản và nhóm dữ liệu; withdrawal hủy khóa, tombstone chặn xử lý tiếp | Chưa nối lựa chọn UI/app, nội dung thông báo và kênh yêu cầu xóa; không xóa tài khoản/backup |
| AUD-08 | Tmpfs multipart riêng trong overlay; CLI rewrap DEK nguyên tử; kiểm kê temp chỉ đọc; runbook | Chưa thử crash/restore/ACL trên máy demo; không tự xóa lease chưa biết chủ sở hữu |
| AUD-09 | Giữ proof thiết bị, nonce và các guard; tài liệu không gọi đây là camera attestation hoặc passkey | Release signing, signedMedia, user presence và phần cứng trên thiết bị chưa nghiệm thu |
| AUD-10 | Giữ TTL ngắn, public pin, issuer-key registry và nonce hiện có; withdrawal không cấp BBS mới | Không thu hồi ngay từng credential đã cấp; tương quan metadata và nguồn sinh trắc vẫn có giới hạn |
| AUD-11 | Mode eKYC không đăng ký routes review/forensic, 404 trước auth/parser; tools giữ future work | Phải chọn đúng mode; UI/app không được hứa có nhân viên đang duyệt |
| AUD-12 | Giới hạn multipart thực, quota byte/lượt theo phiên và giao dịch serialize phù hợp DB | Rate limit tạo phiên vẫn RAM một process; chưa có quota tổng máy/chia sẻ nhiều worker/proxy load test |
| AUD-13 | Protected Compose không tự khởi động Next.js cũ | **Chưa vá dependency web**: npm network bị auto-review chặn, chưa có chấp thuận cho tải package; không tuyên bố đã khắc phục advisory |
| AUD-14 | Có test hồi quy, migration và runbook cho phần code mới | PostgreSQL/container/proxy/app/backup/load test thực tế còn cần môi trường CI và máy demo |

## Các ranh giới cần giữ khi trình diễn

- `SECURITY_PROFILE=synthetic` và mode `tools` giữ lab cũ; không dùng chúng làm
  chứng nhận có thể nhận dữ liệu thật. Protected profile không mở các guard
  real/mixed/account-bound đang chờ nghiệm thu.
- Bật `REQUIRE_PRIVACY_CONSENT` sau khi app gửi đúng lựa chọn chủ động. API nhận
  boolean không tự chứng minh người dùng đã đọc, hiểu hoặc đồng ý.
- Withdrawal là quyền trên **một phiên bằng bearer hiện hành**. Biên nhận không
  hứa xóa mẫu tài khoản, phiên khác, forensic độc lập, backup hoặc mọi plaintext
  lease đang xử lý; không thay cơ chế khôi phục khi đã mất/hết hạn bearer.
- Retention mới mặc định 24 giờ cho ca chưa đạt, tính từ quyết định hoặc
  `created_at + SESSION_MAX_SECONDS` nếu chưa có quyết định. Polling không gia hạn.
  File lỗi unlink sẽ được thử lại; hủy khóa mã hóa không chờ unlink thành công.
  DB commit lỗi không được ghi log rằng khóa đã hủy bền vững.
- Không thay ngưỡng ML, đo chất lượng AI hoặc suy ra tỷ lệ chống deepfake từ
  các test backend tổng hợp. Không đưa dữ liệu người thật vào commit.

## Việc chuyển giao ngoài PR

1. Nhóm app nối consent/rút lại và thông báo kết thúc chưa xác minh theo workflow
   đã chốt; không cần xây bàn duyệt trong sản phẩm hiện tại.
2. Kiểm chứng migration/locking PostgreSQL và container qua CI; nghiệm thu
   TLS/proxy, Keystore/release signing và capture thực trên thiết bị.
3. Operator chốt hạn mức từ capture, bảo vệ khóa/backup, thử restore bằng dữ liệu
   tổng hợp, rồi chọn profile. CLI rewrap không tự cập nhật `.env` hoặc khóa.
4. Nếu tiếp tục dùng web, cho phép npm registry khi nhóm đồng ý để đồng bộ
   Next.js/eslint-config-next/lockfile và kiểm lại bản vá. Nhánh hiện giữ manifest
   và lockfile cũ đồng bộ, không ép cài offline thiếu package.
