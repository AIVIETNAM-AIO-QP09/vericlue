# Bàn giao · IOS-03 · Lý Anh Quân+Codex · 2026-10-28 09:30

**Nhánh:** `feat/IOS-02-android-alignment`
**Trạng thái task sau phiên này:** doing · checkpoint chặng 2–3, chờ iPhone

## Đã xong
- Chặng 2: Terms/consent một màn, không chọn sẵn, điều kiện đọc/đồng ý/mục bắt buộc tách logic. Xóa route Consent/Intro/Permission khỏi enum/caller/Gallery; tới điện thoại thẳng. Recovery bỏ CCCD sau OTP; reauth giữ passive face.
- Sếp xác nhận trong chat dùng phân loại Android ref `f034fa9` và giữ nhãn nội dung demo, không đánh dấu đã duyệt. Bắt buộc mục 0 xử lý mặt/giọng, hai mục còn lại tùy chọn. Bỏ lời hứa qua màn Settings quyền riêng tư chưa tồn tại; không thêm lời hứa lưu/xóa mới.
- OTP parse đúng một mã sáu số ASCII từ simulated_sms, không auto verify; vẫn sửa tay, giữ cooldown tuyệt đối, attempts server, chặn gửi trùng và đổi số/reset. Demo có mã mẫu gắn nhãn riêng, không giả làm mã server; dùng deadline thay timer đếm lùi.
- Quyền camera tại camera sau/front, micro lúc bắt đầu đọc. Mở Settings không chuyển route; thử lại chỉ quay về chuẩn bị khi quyền cần thiết đã cho phép. Giữ policy IOS-06 làm lại mặt sau gián đoạn giọng, không âm thầm dùng bản thu dở.
- Chặng 3: camera sau thêm video output phân tích serial, bỏ frame trễ, throttle 500ms; crop cùng tỷ lệ 1.586, quality/QR và chữ thẻ Vision. Nền phòng nét không đủ để auto; OCR lỗi auto fail-closed, nút tay còn hoạt động. Ảnh cuối đo lại quality/QR.
- IDAutoCapture pure state: delay 1,5s, hai mẫu đạt liên tiếp, reset lỗi/gap, một claim chung auto/manual và cancel. Pause 1,5s sau chụp, retake, Background/Back hủy pending và loại callback trễ; resume ảnh giữ không tự chuyển màn.
- Một route id_review cho cả hai ảnh; retake giữ mặt kia. Capture ID riêng mỗi mặt khởi tạo lại SwiftUI camera, tránh dùng heldPhoto cũ khi pop NavigationStack. QR lỗi về mặt sau giữ mặt trước. Gửi lại review không đổi ảnh không lặp /id-card.
- /id-card thành công giữ fields/draft, tới face_ready nhưng hiện **checkpoint dừng**, không gọi confirm/media/finalize trước khi chặng 4 được nối. Không đổi pipeline camera trước/timeline/voice trong chặng này.
- Thêm 9 hàm unit test và 1 UI test, cập nhật assertion route/retake/fields theo hành vi mới; compile nhưng không thực thi. Không sửa assertion để bỏ qua lỗi; test đầy đủ route mới, consent, SMS parser, timing/reset/claim/cancel/card content, retake và không re-upload.

## Đang dở
- Chưa nghiệm thu camera sau trên iPhone; chưa chạy test mới. Không dùng test/thiết bị nền cũ làm bằng chứng mới.
- Chặng 4 (giữ MP4/evidence chờ confirm, expiry/retry/cleanup) và chặng 5 theme chưa triển khai. Bản trung gian cố ý không hoàn tất onboarding live; demo còn confirm trước mặt tới khi chặng 4 cập nhật.
- Receipt thật/backend ghi danh vẫn có giới hạn ghi trong bàn giao chặng 1; không gộp ký media/device proof hoặc sửa backend/contracts vào chặng này.

## Bước tiếp theo
1. Sếp Run Debug trên iPhone 14 Pro, API cổng 8001 genuine; làm [checklist màn đầu/camera](../../../apps/ios/docs/compact-flow-device-checklist.md). Không dùng Gallery mở riêng ảnh demo thay cho chụp thật.
2. Xác nhận auto/manual, pause, ảnh/preview/crop, retake từng mặt, QR, Home/Back và gửi hai ảnh. Nếu lỗi: gửi bước tái hiện, không gửi ảnh định danh thật vào Git.
3. Sau checkpoint được sếp xác nhận mới nối chặng 4 và gỡ màn dừng tạm. Không nối đường upload cũ trước confirm để làm demo chạy tiếp.
4. Chỉ chạy test khi sếp yêu cầu. Chặng 5 sau chặng 4. Review/tách commit và PR khi sếp chỉ định; không tự commit/push.

## Quyết định, lưu ý, bẫy
- HEAD baseline `6aef3ac`, nguồn Android `f034fa9`; receipt và chặng 2–3 còn chung dirty worktree vì receipt chưa commit. Không tự stash/commit hoặc tạo nhánh giả lập PR độc lập. Debug.xcconfig cổng 8001 sếp đã đổi được giữ nguyên.
- Thời gian/threshold auto là tham số tham chiếu, chưa đo iPhone. OCR chữ in song ngữ dùng en-US, QR hợp định dạng là cue nội dung, không chứng minh thẻ thật; server vẫn là nguồn fields. Không log ảnh/QR/nội dung OCR.
- Mục consent chưa có audit persistence/backend và chưa có câu chữ pháp lý được duyệt. Không coi lựa chọn UI là hoàn thành quản lý đồng ý thật.
- Không sửa project.pbxproj, contracts, backend, thresholds, ADR hoặc STATUS. Không thêm ảnh/audio/video/token thật. README riêng apps/ios chưa có, hướng dẫn ở docs/.

## Câu hỏi cho nhóm
- Chờ nhóm chốt nội dung consent/phân loại chính thức; hiện giữ bản demo theo quyết định sếp.
- Cần sếp thử checkpoint camera sau trước khi tiếp tục chặng 4. Không coi khó khăn receipt/backend thật là lý do mở rộng ký thiết bị ngầm.

## Test đã chạy
**Không chạy test** theo yêu cầu sếp; build-for-testing chỉ compile app/unit/UI test.
Chặng 2 đã build exit 0 trước thay camera. Build bản checkpoint cuối sau khi sửa
compile/macro/concurrency đều exit 0, không còn warning trong output cuối.

```
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios-alignment-stages build-for-testing
# exit 0, không thực thi test

xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios-alignment-stages-release CODE_SIGNING_ALLOWED=NO build
# exit 0, không ký/cài iPhone

uv run python scripts/plan_check.py
# exit 0, 0 lỗi, 10 cảnh báo tải công việc/đường găng
```

Pre-commit trên 25 file chặng 2–3: exit 0, hook áp dụng đều Passed; không có
SwiftLint trong bộ hook. `git diff --check` sạch; protected paths/project không
có diff. Chưa stage, commit, push hoặc chạy test. Các kết quả test chặng receipt
và baseline chỉ là lịch sử, không chứng minh bản camera/OTP mới đã xanh.

## Sửa theo phản hồi iPhone: OTP và crash Home — 28/10

- Sếp báo lỗi sau checkpoint, vì vậy chưa đánh dấu nghiệm thu camera đạt. Đã
  xem Xcode đang paused trên iPhone: exception NSInvalidArgumentException tại
  RearCameraPreview.updateUIView, `setVideoMirrored` không cho phép khi auto
  mirroring còn YES. Đã tắt automaticallyAdjustsVideoMirroring trước khi đặt
  isVideoMirrored tại cả preview, photo và sample output. Không sửa pipeline
  camera trước; chưa nghiệm thu lại Home sau bản sửa.
- OTP đã pass là session state dùng một lần: server trả otp_already_verified,
  không còn kiểm mã nhập lại. UI mới ẩn nhập/resend, hiện đã xác nhận và Tiếp tục.
  verifyOTP/append/erase bị chặn sau verified; Tiếp tục là API local riêng. SMS
  autofill giữ theo yêu cầu chặng 2, không tự verify. Demo chỉ nhận mã mẫu đúng.
- Sếp trả lời rõ “Tổng chỉ sai 5 lần dù gửi lại mã”. Đây là ngoại lệ được duyệt
  cho phạm vi backend: sửa IdentitySteps ở repo chính và worktree backend riêng,
  không chỉ kẹp số UI. Khởi tạo attempts ở lần gửi đầu; resend không tăng lại;
  đã hết budget thì gửi/verify đều otp_locked. Không đổi contract, field, schema
  hay migration. Policy ảnh hưởng Android/web, cần nhóm đối chiếu khi tích hợp.
- Cổng 8001 đã được khởi động lại với source f034fa9 + patch OTP local. Token mock
  cũ có thể không còn hợp lệ; sếp cần bắt đầu phiên mới. Giữ DB/media, không sửa
  dữ liệu lịch sử và không đụng tiến trình 8000; cổng 8000 cũ chưa tự nạp source mới.
- Đã thêm 2 test backend cho ngân sách qua resend/lock và pass sau resend; thêm
  test iOS không giả verify mã khác sau verified, cập nhật expired/locked/too-many
  đúng state mới. Chưa chạy test theo quy ước. Syntax Python, ruff check/format
  hai file backend đều qua; build kết quả bản sửa ghi sau khi hoàn tất.

Kết quả bản sửa: build-for-testing Simulator và Release iPhone không ký đều exit
0, không có output warning/error; chưa thực thi unit/UI/Python test. Pre-commit
14 file sửa lỗi exit 0 (gồm ruff check/format); diff --check sạch. Backend 8001
sau restart health 200, mock_models=true. Chưa chứng minh hết crash trên iPhone
hoặc budget qua request thật; cần sếp cài bản mới và mở phiên mới để nghiệm thu.
Worktree backend tham chiếu hiện có đúng một file source modified do patch OTP,
không còn là bản nguyên trạng f034fa9. Repo chính giữ patch backend có thể review.

## Sửa QR hai mặt theo phản hồi sếp — 28/10

Đối chiếu Android `f034fa9` FlowRules.cardQr: đọc hai mặt, ưu tiên back rồi front;
auto capture chỉ xét quality và nội dung thẻ, không bắt QR riêng ở mặt sau. Bản
iOS trước đã giữ giả định sai “QR bắt buộc mặt sau”, gây chặn thẻ có QR mặt trước.

- Bỏ QR riêng khỏi gate mỗi ảnh/auto; vẫn chặn thiếu ảnh, mờ, lóa và nền phòng
  không có dấu hiệu nội dung thẻ khi auto. Kiểm lại quality ảnh cuối không đổi.
- CCCDQR.select chọn back hợp định dạng rồi front hợp định dạng, bỏ candidate
  hỏng/blank. Review đủ hai ảnh và có QR hợp định dạng mới cho gửi; multipart
  gửi đúng QR đã chọn, không cố định back.qr. Fields server vẫn là nguồn sự thật.
- Local không đọc QR hoặc server retry/QR_INVALID → ở id_review, giữ cả hai ảnh,
  chọn retake mặt chứa QR. Server reject khóa gửi lại cùng bộ ảnh đến khi retake;
  retake giữ mặt kia, xóa QR của ảnh bỏ đi và invalidate fields/draft cũ.
- Khác Android ở xử lý retry: không tự chỉ định về mặt sau. Nếu cả hai mặt có
  candidate hợp định dạng vẫn ưu tiên back theo nguồn Android; client không xác
  thực danh tính bằng QR local và không thay kiểm server.
- Cập nhật test không đòi QR ở mặt sau, gửi front-only/back-only, fallback/priority,
  no-QR, giữ cả ảnh sau reject và không reuse QR ảnh đã retake. Chỉ compile, chưa
  chạy test; cần sếp thử trên iPhone với thẻ thử có QR mặt trước.

Build bản QR mới: Simulator build-for-testing và Release iPhone không ký đều
exit 0, không có warning/error trong output. Pre-commit 12 file Passed,
git diff --check sạch. Không sửa backend thêm trong lượt QR này, không đổi
contracts/project; chưa test runtime, commit hoặc push.
