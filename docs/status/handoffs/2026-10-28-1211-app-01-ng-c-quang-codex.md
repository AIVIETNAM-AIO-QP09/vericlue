# Bàn giao · APP-01 · Ngọc Quang+Codex · 2026-10-28 12:11

**Nhánh:** `integration/APP-01-main-flow01`, worktree `D:\vericlue-wt\integration`.
**Trạng thái task sau phiên này:** doing; client đã nối tài khoản, chưa nghiệm thu sinh trắc tài khoản trên máy thật.

## Đã xong

- Rà PR Android: #69, #86, #87 đã ở main; #98 là phần tài khoản còn mở. Không đụng
  PR iOS #91–#95/#102. Yêu cầu 28/10 cho phép merge PR Android đủ điều kiện, bổ sung
  cho prompt nhánh thử cục bộ trước đó. Không mở PR mới.
- Bắt đầu từ UI local `ffeb683`, fast-forward main `a54d093`; #86 đã là tổ tiên.
  Gộp #98 (`f034fa9`) sạch, không xung đột. Không tự sửa server/ML, hợp đồng, ADR,
  ngưỡng hay STATUS. Giữ UI A, motion/haptic, QR hai mặt, xác nhận CCCD trước media,
  chờ MP4 Finalize. Commit nền: `0c6486e` (fixture), `4f07f28` (tích hợp #98).
- `data/AccountStore.kt`: receipt + alias trong một JSON riêng app, ghi `commit()`
  trên IO trước khi xóa khóa. Hết hạn/hỏng/thiếu alias coi như chưa có; không gán
  đoán receipt định dạng cũ sang một khóa.
- `security/AccountKeys.kt`, `AndroidMediaSigner.kt`: phân biệt mở khóa có sẵn và
  sinh khóa. Reauth thiếu khóa tới hướng dẫn khôi phục, không sinh khóa thay thế.
- `flow/AccountFlow.kt`: đăng nhập dùng receipt/alias cũ; thiếu hoặc tắt ký thì về
  đăng ký + lời nhắc. Khôi phục gửi account_id cũ và khóa mới, ghi binding mới rồi
  mới xóa alias cũ. Lỗi lấy/lưu chỉ log, vẫn thành công. Giữ CCCD sau OTP theo H32.
- `ui/App.kt`: mỗi lựa chọn Auth thay LiveFlow/ngữ cảnh lượt; lấy/lưu receipt ở
  Uploading trước Success, tránh bị chuyển trang sau 2,6 giây hủy coroutine.
  LiveFlow từ chối tái dùng phiên cho purpose/account khác.
- HTTP `409 recovery_required` tới đúng hướng dẫn khôi phục; `503 flow_unavailable`
  vẫn tới Dịch vụ chưa sẵn sàng. Manifest thêm reauth theo verifier server.
- Ba fixture unsigned truyền `mediaSigner=null`: main có 26 test hỏng khi bật ký
  do fixture gọi Android Keystore trên JVM. Test ký P-256 riêng vẫn giữ nguyên.
  `signedMedia` mặc định **false**.
- Review độc lập hai lượt: năm lỗi/thiếu sót #98 đã xử lý; không còn phát hiện chặn
  merge trong lượt cuối, với điều kiện kiểm tra và CI xanh.

## Kiểm server trước khi nối app

1. `SessionFlow.finalize` gọi enrollment khi onboarding pass và
   `account_enrollment=true`. FinalizeResponse không có account; dùng bearer phiên
   gọi `GET /v1/sessions/{id}/account`. Voice pass có thể có account.
   `accounts.py::_validate_biometrics` loại mock/mixed: **mock không ghi danh**.
   Bật ACCOUNT_ENROLLMENT trên mock không đủ. Mock không enrollment vẫn có thể
   thành công nhưng không có receipt.
2. `SessionFlow.ensure_flow_available` luôn trả `503 flow_unavailable` cho phiên có
   account_id sau kiểm L0/current account, kể cả mock. Chỉ thử được L0/OTP; sinh trắc
   reauth/recovery bị chặn FLOW-05/SEC-02. Không mở chốt để demo.
3. `services/.../media_proof.py::manifest` chỉ đòi purpose khác null, dùng purpose
   phiên trong JSON ký, không loại reauth. App thêm reauth vào allowlist; không
   bỏ qua chốt server ở câu 2.

## Đang dở

- HTTPS/release trên máy thật; kiểm quyền camera/mic, mất mạng, gián đoạn, chiều quay
  đầu và rung. Không cài đè bản đang thử tại root trong phiên này.
- Ghi danh thật → reauth → recovery cần backend mở chốt sau nghiệm thu; không thể
  tạo receipt mock để chứng minh đã đạt.

## Bước tiếp theo

1. Cập nhật #98 bằng nhánh đã kiểm/review; chỉ merge sau CI xanh.
2. Lấy main mới, build `-Pvericlue.signedMedia=true` cùng HTTPS máy demo; đăng ký từ
   Auth. Gallery nhảy thẳng từng màn dành cho thử giao diện.
3. Khi FLOW-05/SEC-02 đủ điều kiện: nghiệm thu receipt/alias, mất khóa, L0/OTP, 409,
   đổi khóa và xác nhận khóa cũ chỉ mất sau ghi bền trên điện thoại thật.

## Quyết định, lưu ý, bẫy

- Root vẫn UI `ffeb683`; local APP-04/FLOW-01 giữ `72c71a3`/`d642814`.
  Worktree account không bị thay file/HEAD.
- CI cũ #98 đỏ ở 5 test media/giọng không theo onboarding không giọng. Main đã có
  `9524fb9` sửa fixture; cập nhật main giải quyết, không sửa server mới.
- Ảnh/log ở `tmp/integration-APP01/`, không commit. JDK17/SDK ở D:\tools;
  `uv sync --frozen --all-packages --extra face` cài OpenCV đúng lock, không đổi lock.

## Câu hỏi cho nhóm

- Ai nghiệm thu/mở chốt FLOW-05/SEC-02; khi nào có cấu hình mô hình thật/ghi danh
  để thử đủ ba luồng trên điện thoại?
- HTTPS/thiết bị demo cuối cùng là gì? Có preset build ký sau nghiệm thu không?
  Hiện không tự bật mặc định.

## Test đã chạy

- Sau main: Android 109 test mặc định, assembleDebug/lintDebug đạt; bật ký đạt sau
  sửa fixture, Paparazzi đạt. Python 3.925 đạt/79 bỏ qua; Ruff đạt;
  plan_check 0 lỗi/10 cảnh báo.
- Sau #98: Android mặc định/bật ký, build/lint, Paparazzi đạt; Python/Ruff/plan_check
  đạt (4.004 ca, 79 bỏ qua).
- RED: HTTP409 sai màn, manifest reauth bị từ chối và tái dùng phiên khác purpose
  đều đỏ trước bản sửa. API test alias mới ban đầu chưa biên dịch vì thiếu kiểu;
  sau triển khai chạy đạt.
- Cuối: `testDebugUnitTest assembleDebug lintDebug`: 125 test/0 lỗi;
  lint 0 lỗi/43 cảnh báo. `testDebugUnitTest -Pvericlue.signedMedia=true`:
  125 test/0 lỗi, gồm CitizenCopyTest và ThemeAccessibilityTest ở cả hai lượt.
- `recordPaparazziDebug --tests '*ScreensSnapshotTest*'`: đạt, 100/100 PNG giống hệt
  byte trước/sau (SHA-256); không đổi UI A. Chạy lại AccountStoreTest sau chỉnh fixture
  JSON hỏng: đạt.
- `uv run pytest services ml -q`: 4.004 ca, 0 lỗi, 79 bỏ qua (3.925 đạt).
  `uv run ruff check .`: đạt. `uv run python scripts/plan_check.py`: 0 lỗi/10 cảnh báo.
  `git diff --check`: đạt. Không có ảnh/media/khóa hoặc cấu hình bí mật trong commit.
