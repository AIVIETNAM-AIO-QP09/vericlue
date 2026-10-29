# Bàn giao · IOS-03 · Lý Anh Quân+Codex · 2026-10-28 11:06

**Nhánh:** `feat/IOS-02-android-alignment`, HEAD nền `6aef3ac`; chưa commit.
**Trạng thái hiện hành:** review — chặng 4 xanh 148/148 sau sửa ba lỗi; chưa commit/push/merge.

## Đã xong

- Điều kiện bắt đầu: sếp xác nhận 4 ca chặng 3 (auto/manual không chuyển trùng,
  QR mặt trước, review/retake giữ ảnh kia, Home khi chụp không crash/task cũ) đạt.
  Không coi đây là nghiệm thu bản chặng 4.
- Tách `finishCapture` khỏi `submit`. Writer finish + inspection + evidence checks
  hoàn tất rồi mới giữ PendingFaceCapture: URL MP4, JPEG, signals/probe/events,
  binding đúng session/token/challenge/deadline. Camera dừng khi chờ sửa thông tin.
- Onboarding chưa confirm → confirm/edit. CaptureFlows kiểm binding trước/sau
  confirm; confirm ack mới chuyển upload. Draft/ID khóa/ISO date giữ logic cũ.
- `idCardConfirmed` trong LiveFlow tồn tại qua face retry, reset khi phiên/thẻ
  đổi; không confirm lại chỉ vì tap trễ hoặc quay lại do chất lượng. Recovery/
  reauth không đòi fields giả; mọi kết quả vẫn theo server status.
- MP4 nằm trên đĩa lúc chờ, đọc mapped-if-safe khi gửi. Media ack xóa file;
  retry signals/finalize không đọc lại MP4 đã xóa hoặc gửi lại media.
- Hết challenge/đổi binding/file thiếu → face_expired, hết session → error_session.
  Dynamic challenge thiếu/sai deadline bị từ chối, không lấy session TTL thay thế.
- Home ở confirm/edit giữ draft/file đến deadline, không tự gửi. Back confirm
  hỏi dừng; Back edit về confirm. Retake CCCD bỏ evidence mặt cũ, yêu cầu quay mới.
- Bỏ checkpoint dừng chặng 3 khỏi source; demo chuyển confirm sau mặt. Gallery
  có face_expired. Theme không đổi.
- Thêm PendingFaceCaptureTests: 11 hàm test, có 2 nhóm tham số. Bao phủ thứ tự,
  mạng/ack, expiry, rotation, late reply, double tap/rejection, thiếu file/deadline,
  retry chất lượng, purpose không CCCD và demo/navigation. Chưa thực thi.

## Đang dở

- Chưa chạy test theo yêu cầu sếp; compile test bundle không chứng minh test pass.
- Chưa nghiệm thu writer/navigation/expiry/network/cleanup chặng 4 trên iPhone.
- Theme ấm thuộc chặng 5, chưa triển khai. Chưa chốt task hoặc chuyển cổng 8.
- Receipt GET 200 thật và account-bound auth vẫn bị giới hạn backend như bàn giao
  chặng 1. Không mở chốt sinh trắc/giả receipt để làm demo đạt.

## Bước tiếp theo

1. Xcode Run Debug mới nhất trên iPhone với backend tương thích, API/scenario genuine.
2. Theo `apps/ios/docs/post-face-confirm-device-checklist.md`: log cùng session
   phải confirm trước media/signals/finalize; thử sửa, offline, expiry, Home/Back,
   retry/cleanup và nhánh voice. Ghi bằng chứng mới, không dùng số IOS-06 cũ.
3. Chỉ chạy bộ test khi sếp yêu cầu; xử lý kết quả trước khi chốt chặng.
4. Review/chia PR và tiếp tục theme sau khi luồng này ổn định.

## Quyết định, lưu ý, bẫy

- Nền Android đối chiếu hiện hành upstream/main a54d093 (PR #104). Không merge
  main; runtime BBS mới ngoài scope. Không sửa backend trong lượt này.
- Giữ các thay đổi người dùng và code trước lượt này, IP Debug 192.168.1.12:8001,
  project.pbxproj blob 3757f703fa286597f132a254105c3ace82decb68.
- Không sửa contracts/thresholds/ADR/STATUS, không thêm thư viện hoặc media thật.
- File chỉ cleanup theo URL capture sở hữu, không quét thư mục rộng. File chưa
  có media ack được giữ qua lỗi mạng nhưng bị bỏ khi rời lượt/expiry.
- File thu không lưu bền qua force-quit; orphan cleanup ở lần mở app sau. Không
  tuyên bố tiếp tục phiên qua process death. Home confirm chỉ giữ trong tiến trình
  khi còn deadline, camera đã dừng. Receipt riêng không thay device proof.
- Confirm terminal error không upload. Response confirm bị mất có thể gửi lại
  confirm trước media; không bổ sung suy luận pass/idempotency finalize hoặc voice.

## Câu hỏi cho nhóm

- Các khác biệt Android đã chốt vẫn giữ: recovery bỏ CCCD, OTP tổng 5 lần sai,
  receipt Keychain riêng. Backend tích hợp phải có OTP policy local tương ứng.
- Consent vẫn là mẫu chờ nhóm/pháp chế, không tuyên bố đã duyệt hoặc đã có audit.

## Kiểm chứng (không thực thi test)

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios-stage4 build-for-testing
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios-stage4-release CODE_SIGNING_ALLOWED=NO build
.venv/bin/python scripts/plan_check.py
git diff --check
```

- Simulator app/test bundle và Release iPhone không ký trên bản guard deadline
  cuối đều exit 0, không có output lỗi/cảnh báo. Không thực thi test.
- Trong lúc phát triển, build test bundle từng lỗi recursive nested #require;
  đã tách macro thành biến cục bộ và build lại thành công, không nới assertion.
- plan_check: exit 0, 0 lỗi/10 cảnh báo tải công việc/chuỗi găng. Diff whitespace sạch.
- Không có kết quả unit/UI test mới, snapshot hoặc phép đo iPhone chặng 4.

## Cập nhật nghiệm thu và một lượt test — 28/10/2026

Sếp xác nhận nhóm A/B/C/D đạt theo thao tác iPhone. Access log phiên
`ses_525f99d660051cc5` cho thấy confirm → media → signals → finalize đều 200,
mỗi endpoint một lần trong đoạn log; GET account 409 không phải receipt 200.
Kiểm DB readonly: status pass, id_confirmed true, id_edited gồm full_name và
date_of_birth; cả hai khác bản đọc ban đầu, ngày confirm là ISO/ngày hợp lệ,
HMAC ID confirm khớp HMAC ID gốc. Không in dữ liệu định danh hoặc token.
Log này không chứng minh riêng retry từng endpoint hoặc byte HTTP JSON nguyên bản.

Theo yêu cầu mới, đã thực thi **một lượt** toàn bộ test iOS, không sửa source
trong khi chạy hoặc tự chạy lại test lỗi:

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=184BFA1A-7DB0-4CE7-A9BB-1DA25FB36F80' \
  -derivedDataPath /tmp/vericlue-ios-stage4 \
  -resultBundlePath /tmp/vericlue-ios-stage4-tests.IpfhJ2/FullRun.xcresult \
  -parallel-testing-enabled NO test
```

- iPhone 17 Pro Simulator iOS 26.3.1, arm64; exit 65, Failed.
- xcresult summary: **145/148 test đạt, 3 lỗi, 0 skipped**. Tính cả tham số:
  171/174 lần thực thi đạt, 3 lỗi. Xcode báo testing elapsed 322.666 giây.
- Result: `/tmp/vericlue-ios-stage4-tests.IpfhJ2/FullRun.xcresult`.
- Log: `/tmp/vericlue-ios-stage4-tests.IpfhJ2/FullRun.log`.
- Hai lệnh chuẩn bị trước đó bị từ chối tham số, chưa thực thi test: cờ retry
  là unary, và test-iterations không chấp nhận 1. Lệnh FullRun dùng mặc định
  một lượt, không bật retry/repetition; không có lượt thực thi thứ hai.

Ba lỗi còn mở:

1. `PendingFaceCaptureTests.missingFileAndServerExpiredChallengeNeverUpload`:
   sau xóa file, số request là 5 thay vì giữ 4. Guard trước confirm chưa đạt
   invariant; không nới assertion. Cần kiểm cache URL resource values và kiểm
   tồn tại file thực tế; nguyên nhân này mới là hướng chẩn đoán, chưa xác minh.
2. `FlowRulesTests.qualityAndOTPTextsMatchAndroid`: assertion vẫn mong câu yêu
   cầu resend khi hết lượt; code dùng câu bắt đầu lại phù hợp luật tổng 5 lần
   sai/phiên sếp chốt. Cần cập nhật assertion theo policy, không đổi code về luật cũ.
3. `VeriClueUITests.testTermsRequiresExplicitConsentAndContinuesDirectlyToPhone`:
   XCTAssertTrue lỗi ở bước sau chọn consent bắt buộc. Chưa đủ căn cứ kết luận
   là tap/scroll, accessibility hay state; không đánh dấu UI đã xanh.

Chưa sửa ba lỗi, chưa chạy lại; task giữ doing. Các mục phía trên ghi “chưa chạy
test” là lịch sử trước yêu cầu mới này. **Chưa đủ điều kiện chốt chặng 4/test xanh.**

## Chốt chặng 4 sau sửa ba lỗi — 28/10/2026

Theo yêu cầu sếp sửa và chạy lại:

1. Guard file: dùng FileManager.attributesOfItem mỗi lần thay cho URL resource
   values có cache. Giữ chặn file không regular/symlink/rỗng; assertion không
   phát thêm request khi file mất giữ nguyên và đã xanh.
2. OTP: sửa đúng expected text theo luật tổng 5 lần sai/phiên đã chốt; đổi tên
   test để không còn tuyên bố toàn bộ câu OTP khớp Android. Không đổi policy code
   về reset theo resend, không bỏ assertion.
3. UI consent: log thao tác cũ tap gần đáy màn hình; isHittable không đảm bảo
   toàn bộ control không bị footer che. Test cuộn control hoàn toàn vào viewport
   và kiểm riêng trạng thái đồng ý/chọn bắt buộc. Lượt sửa đầu vẫn phát hiện
   switch không đổi 0 → 1. Sau đó thay hàng switch nhãn dài bằng checkbox button
   44pt tối thiểu với contentShape đầy hàng, cùng Agreement.toggle và guard đọc
   cuối; không chọn sẵn/không tự đồng ý. Thêm contentShape cho hàng đọc cuối và
   consent. Assertion nút tiếp tục khóa trước đủ đồng ý và đi thẳng điện thoại
   vẫn giữ; thêm assertion giá trị checkbox trước/sau tap.

Lịch sử kiểm lại (đều full unit + UI, không bật tự retry):

- Lượt sửa đầu: 147/148 đạt, còn lỗi UI switch value 0, 0 skipped. Bundle
  `/tmp/vericlue-ios-stage4-fix-tests.vefkOx/FullRun.xcresult`.
- **Lượt cuối: Passed, 148/148 đạt, 0 lỗi, 0 skipped**; tính tham số là
  **174/174**. iPhone 17 Pro Simulator iOS 26.3.1, arm64, xcodebuild exit 0.
  Testing elapsed theo Xcode: 131.852 giây. Bộ test giữ 148 bài, không bỏ test.
- Bundle cuối: `/tmp/vericlue-ios-stage4-final-tests.GT5ZbJ/FullRun.xcresult`.
- Log cuối: `/tmp/vericlue-ios-stage4-final-tests.GT5ZbJ/FullRun.log`.
- Lệnh giống lượt trước, chỉ đổi resultBundlePath sang bundle cuối. Code không
  đổi giữa lúc chạy. Không dùng kết quả cũ để chốt bản mới.
- Build Release iPhone không ký trên bản cuối exit 0. Diff whitespace sạch;
  plan_check sau chuyển IOS-03 review: 0 lỗi/10 cảnh báo kế hoạch cũ.

**Kết luận:** chặng 4 xanh về code/test, cùng nghiệm thu A/B/C/D do sếp báo và
DB confirm đã kiểm. IOS-03 chuyển review, không done; chờ diff/PR theo quy trình.
Chưa commit/push, không thay project/IP/contracts/backend trong lượt sửa này.
Theme thuộc chặng 5, receipt GET 200/account auth thật vẫn ngoài bằng chứng hiện có.
Các mục “chưa chốt” phía trên là lịch sử trước bản sửa cuối.
