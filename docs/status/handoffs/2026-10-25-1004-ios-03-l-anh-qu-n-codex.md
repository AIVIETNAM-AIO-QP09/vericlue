# Bàn giao · IOS-03 · Lý Anh Quân+Codex · 2026-10-25 10:04

**Nhánh:** `feat/IOS-03-otp-id-card` từ IOS-02 commit `2e043e2`.
**Trạng thái task sau phiên này:** `review` — nghiệm thu thủ công được sếp xác nhận; review cuối hoàn tất, bản cuối đạt **54/54 test**, Release SDK iPhone build thành công. Chưa stage/commit/push/mở hoặc merge PR.

## Đã xong

- `Flow/IdentityFlow.swift`: coordinator giai đoạn A, giữ phone/OTP/SMS/attempts, deadline resend 45s, hai ảnh, fields server và bản nháp chỉnh sửa. Chặn request đồng thời, giữ trạng thái khi lỗi mạng.
- Số điện thoại chỉ nhận `0` + 9 số ASCII. Tạo session trước OTP. Back về điện thoại rồi gửi cùng số trong cooldown không phát thêm mã; đổi số bắt đầu phiên mới.
- OTP sáu ô, SMS từ server, attempts đúng response; xử lý retry/expired/locked/too_many/already_verified. Countdown tính lại từ deadline thay vì trừ một biến theo tick khi app ở nền.
- `Capture/CameraSession.swift`: camera sau với queue riêng, preview 1.586:1, portrait, không lật ảnh, permission/settings, stop khi background/rời màn, photo continuation có ID và timeout, chặn callback trễ.
- `Capture/IdCard.swift`: không nhận ảnh rỗng, chuẩn hóa EXIF, crop cùng tỉ lệ khung; luma/Laplacian variance bằng vImage; đo lóa; đọc QR bằng Vision và kiểm định dạng cơ bản. Đây chỉ là quality gate, không kết luận danh tính.
- `UI/Screens/LiveIdentityScreens.swift`: phone/OTP/capture/review/confirm/edit dùng dữ liệu thật. Giữ ảnh mặt trước khi QR mặt sau lỗi; retry về route mặt sau đang có, không tạo stack lặp.
- Số CCCD khóa cả UI và model; giữ bản nháp qua Back/lỗi mạng; ngày hiển thị dd/MM/yyyy và gửi ISO; confirm gửi chính fields đã sửa, giữ các fields gốc không sửa.
- Debug Gallery preview vẫn độc lập. Chế độ API thật dừng sau giai đoạn A, không chuyển sang demo mặt/giọng và báo success giả. `IdentityFlow.liveFlow` cung cấp phiên hiện tại để IOS-04 tiếp tục.
- Thêm `IdentityFlowTests` và `IDCardTests`: deadline, phone/resend, OTP errors, QR retry, JSON confirm edited, ảnh/variance/glare, Vision QR sinh bằng CoreImage và route Back. Không có CCCD/ảnh cá nhân thật trong fixture.
- Thêm hướng dẫn `apps/ios/docs/ios03-device-checklist.md` để sếp chạy iPhone và kiểm tra server.

## Đang dở

- Lượt đầu 52/53 qua, sau sửa QR đạt 53/53. Review cuối thêm test đổi số rồi lỗi mạng; lượt cuối theo yêu cầu sếp đạt **54/54**, không lỗi/skip. Chi tiết và artifact bên dưới.
- Sếp xác nhận checklist thao tác trên **iPhone 14 Pro, iOS 18.7.8** đạt, gồm mất mạng rồi thử lại. Codex không trực tiếp quan sát thao tác. Kiểm tra DB/file xác nhận phiên `ses_10429dfead210e88` có hai JPEG 1200×758 và `id_edited` gồm `date_of_birth`, `full_name`.
- Ngưỡng sharpness 60, glare fraction 0.02, luma >=250 lấy từ Android làm mốc ban đầu, chưa đo/hiệu chỉnh trên iPhone.
- Chưa commit/push/PR. Thay đổi IP trong `Config/Debug.xcconfig` là của sếp từ trước, được giữ nguyên.

## Bước tiếp theo

1. Sếp tự stage theo danh sách trong bản nháp PR, kiểm `git diff --cached` rồi commit/push khi duyệt. Codex không stage/commit/push.
2. Mở PR theo `apps/ios/docs/ios03-pr.md`; sau khi PR được duyệt/merge mới đổi backlog từ `review` sang `done`.
3. IOS-04 tiếp tục bằng `identity.liveFlow`, không tạo phiên khác sau OTP/CCCD. Ngưỡng quality vẫn cần đo nếu thay thiết bị/điều kiện.

## Quyết định, lưu ý, bẫy

- Ảnh chỉ ở RAM của app trong phiên; server lưu theo MEDIA_DIR hiện hành. Không thêm ảnh/video/audio vào repo.
- API thật phải không đi qua checking/outcome mô phỏng của IOS-01. Màn dừng ghi rõ chưa hoàn tất xác minh; capture mặt/voice thật thuộc IOS-04/05.
- iPhone chuyển nền lúc chụp: dừng camera, bỏ callback của lượt cũ; quay lại khởi động lại. Không tự chuyển route bằng ảnh cũ.
- Backend `IdentitySteps.confirm_id_card` hiện giữ danh sách `id_edited` nhưng không ghi đè `id_fields` bằng giá trị sửa. App gửi đúng payload và giữ bản nháp trong phiên. Không sửa backend ngoài scope IOS-03.
- Build Release cho thiết bị dùng CODE_SIGNING_ALLOWED=NO chỉ kiểm tra biên dịch/link; không chứng minh signing hoặc cài iPhone đã thành công.
- Không sửa packages/contracts, thresholds, ADR hay docs/status/STATUS.md.

## Câu hỏi cho nhóm

- Nếu yêu cầu giá trị sửa mới được lưu bền ở backend, cần task backend riêng: hiện chỉ `id_edited` ghi tên trường thay đổi, còn snapshot QR giữ giá trị gốc.

## Chẩn đoán bổ sung — bị chặn trước OTP

- API local `192.168.1.11:8000/healthz` báo `ok`, `mock_models=true`, nhưng một request tạo phiên onboarding bằng nonce tổng hợp trả HTTP 503, `error_code=security_unavailable`. Không gửi phone/OTP/CCCD trong kiểm tra này; token không được ghi ra.
- `Settings.session_token_signer` trả mã này khi khóa được chọn dưới 32 byte. Khóa cấu hình quá ngắn nhưng không rỗng không được thay bằng khóa mock tự sinh.
- Bổ sung runbook export khóa ngẫu nhiên 32 byte dạng hex trong shell, restart server và bắt đầu phiên mới. Không thay backend, không bỏ kiểm tra xác thực, không thực thi test. Chưa xác nhận lại sau restart vì server hiện do sếp chạy.

## Test đã chạy

Ở phiên triển khai ban đầu chỉ kiểm tra build; sau đó sếp cho phép chạy test một lượt (25/10/2026):

```
xcodebuild -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=184BFA1A-7DB0-4CE7-A9BB-1DA25FB36F80' \
  -derivedDataPath /tmp/vericlue-ios03 \
  -resultBundlePath /tmp/vericlue-ios03-20261025-1120.xcresult \
  -parallel-testing-enabled NO test
```

- Exit 65, TEST FAILED. iPhone 17 Pro Simulator, iOS 26.3.1 (23D8133).
- `xcresulttool get test-results summary`: 53 test cases, 52 passed, 1 failed, 0 skipped. Báo cáo thiết bị đếm 65 lượt passed do có test tham số hóa; không cộng lẫn lượt chạy và test cases.
- Duy nhất `IDCardTests.visionDecodesSyntheticQRAndCropMatchesCardRatio`: `com.apple.Vision Code=9: Could not create inference context`.
- Toàn bộ `IdentityFlowTests` qua, gồm giữ chỉnh sửa khi lỗi mạng và xác nhận JSON ISO/ID khóa. Bốn lượt UI/launch qua.
- Chưa xác định nguyên nhân gốc Vision; không kết luận đây chỉ là lỗi môi trường, không sửa assertion, không chạy lại.
- Artifact chỉ ở `/tmp`, không đưa vào Git.

### Sửa sau lượt test (theo yêu cầu của sếp)

- Tách `IDCardAnalyzer.decodeQR`: vẫn gọi Vision trước. Chỉ trên Simulator và khi nhận `VNErrorDomain`/`VNErrorCode.internalError` (Code 9), đọc QR thật từ ảnh bằng Core Image `CIDetectorTypeQRCode`, context software renderer. Lỗi khác vẫn được ném ra; không áp dụng fallback cho iPhone thật.
- Không trả mã fixture cố định, không coi lỗi là QR hợp lệ, không bỏ test. Đổi tên test thành `qrDecoderReadsSyntheticPayloadAndCropMatchesCardRatio` để phản ánh có hai backend đọc QR theo môi trường; giữ nguyên mọi assertion về payload, QR hợp lệ và tỉ lệ crop.
- Build-for-testing Simulator: exit 0. Không thực thi lại test, vì sếp chỉ yêu cầu sửa sau lượt chạy duy nhất. Chưa khẳng định test QR đã xanh hoặc giải thích được toàn bộ nguyên nhân nội bộ Vision.
- Release build cho SDK iPhone, `CODE_SIGNING_ALLOWED=NO`: exit 0; không ký/cài/chạy trên thiết bị.
- API fallback tham khảo: https://developer.apple.com/documentation/coreimage/cidetectortypeqrcode

### Kết quả chạy lại sau bản sửa QR

Theo yêu cầu mới của sếp, chạy toàn bộ scheme đúng một lượt với cùng destination/derivedDataPath, result bundle `/tmp/vericlue-ios03-qr-fix-20261025.xcresult`.

- `xcodebuild test`: exit 0, **TEST SUCCEEDED**, iPhone 17 Pro Simulator iOS 26.3.1.
- `xcresulttool get test-results summary`: **53/53 test cases passed, 0 failed, 0 skipped** (66 lượt passed khi tính các tham số).
- Log Swift Testing: 50 tests/8 suites passed; XCTest UI/launch: 4 lượt passed (launch chạy Light và Dark).
- `qrDecoderReadsSyntheticPayloadAndCropMatchesCardRatio` passed; assertions payload chính xác và tỉ lệ crop giữ nguyên.
- Không sửa code trong lượt chạy lại; chưa commit/push.

Build trước đó:

```
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj \
  -scheme VeriClue -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios03 build-for-testing

Kết quả cuối: exit 0; app và test bundle biên dịch thành công.

xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj \
  -scheme VeriClue -configuration Release \
  -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios03-device CODE_SIGNING_ALLOWED=NO build

Kết quả cuối: exit 0; Release build với SDK thiết bị thật thành công.

git diff --check: sạch.
```

`uv run python scripts/plan_check.py` sau review cuối: exit 0, **0 lỗi, 10 cảnh báo** về tải công việc/đánh dấu đường găng toàn dự án. Backlog IOS-03 đặt `review`, không đánh dấu tích hợp hoàn tất.

## Review diff cuối — 25/10/2026

- Phạm vi: toàn bộ file mới/sửa IOS-03, bao gồm capture, coordinator, route/UI, test, config và tài liệu. Không review toàn repository hoặc lịch sử Git cũ.
- Phát hiện và sửa: đổi phone trong cooldown rồi lỗi mạng vẫn giữ deadline cũ, khiến lần thử sau có thể mở OTP mà chưa gửi mã cho phone mới. Đã reset clock/locked/error khi tạo flow cho phone mới; thêm `changedPhoneCannotReuseOldCooldownAfterNetworkFailure`, giữ kiểm tra retry thực sự gửi `/otp` cho số mới.
- Build-for-testing bản sửa cuối exit 0. Lượt test cuối theo phép của sếp dùng `/tmp/vericlue-ios03-final-review-20261025.xcresult`: **exit 0; xcresult summary Passed, 54/54 test cases, 0 failed, 0 skipped** (67 lượt passed có tính tham số). Chỉ chạy một lượt trên bản sửa cuối. Test hồi quy mới và QR đều qua.
- Release SDK iPhone bản cuối, `CODE_SIGNING_ALLOWED=NO`: exit 0. Đây là kiểm chứng biên dịch/link, không phải cài đặt hoặc một lần nghiệm thu thiết bị bổ sung.
- Hook pre-commit trên file IOS-03: passed/skip theo loại file; không có cấu hình SwiftLint riêng. `git diff --check` sạch. Không dùng lint Python để khẳng định đã lint toàn bộ Swift.
- Không thấy vấn đề chặn khác trong phạm vi review; không đồng nghĩa code không có bug. Simulator fallback chỉ khi Vision Code 9; payload QR/quality/fail-closed không bị nới.
- Kiểm nhạy cảm: file thay đổi đều là text; không thấy token/private key/dữ liệu media nhúng theo mẫu quét. QR/phone/ID trong fixture là dữ liệu tổng hợp. `tmp/dev.db` và hai JPEG được ignore, không tracked. Chưa có staged diff; sếp cần kiểm staged sau khi chọn file.
- Thay đổi IP Debug là của sếp (`192.168.1.11`), giữ nguyên. Không sửa backend/contracts/thresholds/ADR/STATUS.
- Khác biệt tài liệu luma >245 được chỉnh thành ≥250 cho đúng mốc Android/code; không nới ngưỡng để test xanh.
