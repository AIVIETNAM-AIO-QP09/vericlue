# Bàn giao · IOS-06 · Lý Anh Quân+Codex · 2026-10-27 23:55

**Nhánh:** `feat/IOS-06-interruption-retry`, nền `58c36fd` (IOS-05).
**Trạng thái task sau phiên này:** `doing` — sếp đã chấp nhận nghiệm thu mười ca với giới hạn bằng chứng bên dưới; đã sửa Gallery và test mới nhất 105/105 đạt. Còn review cuối/PR.
**Cập nhật cuối:** 2026-10-28.

## Đã xong
- Xử lý background, Back có xác nhận, lỗi camera/micro và hết hạn phiên ở cấp điều hướng. Gián đoạn khi thu hủy lượt cũ, trở về chuẩn bị mặt và bắt buộc lấy challenge/token mới.
- Giữ payload đã đóng khi lỗi mạng; retry media/signals/finalize/voice chỉ gửi phần chưa ack. Chỉ `step_already_received` cho media/signals được coi là ack; không suy diễn success từ lỗi hoặc status lạ.
- Gắn quyền sở hữu từng request: hủy lượt vô hiệu hóa phản hồi muộn, không cho phản hồi cũ đổi token/ack, mở camera, điều hướng hay dọn file của lượt mới.
- Dọn MP4 thuộc namespace `tmp/vericlue-capture` sau ack/hủy; dọn orphan có tên UUID hợp lệ khi mở app, bảo vệ file đang dùng và không xóa file xuất ra ngoài. WAV ở RAM. Gallery Debug có nút đếm file, không xóa.
- Thêm 13 phương thức test cho hủy request, retry/ack, hết hạn và phạm vi dọn file, dùng MockURLProtocol/barrier, không gọi mạng thật. Đã chạy toàn bộ scheme một lượt: Passed, 105 test (122 lượt khi tính tham số), 0 lỗi/0 bỏ qua.
- Thêm `apps/ios/docs/ios06-device-checklist.md`, cập nhật API notes, kế hoạch và dòng IOS-06 trong backlog. Không thay contracts/backend hay luồng/theme Android mới.
- Ghi nhận log API sếp cung cấp ngày 28/10: hai phiên `ses_f006d902cf8ee863` và `ses_d3d3cb80a44d4e2c` có media → signals → finalize → voice, mỗi endpoint một lần/HTTP 200 trong đoạn log, không thấy request lặp. Phiên thứ hai có hai challenge/200 trước media. Đây là log API mock (`mock@0.1`), không có mốc mất/bật mạng hay response/payload để chứng minh riêng từng ca retry hoặc token rotation. Bằng chứng chốt ca 4–7 là nghiệm thu thủ công + log nhận đủ endpoint + test retry/ack xanh; không tuyên bố đã đối chiếu mất mạng riêng từng endpoint máy thật. Chỉ ghi tóm tắt, không commit log gốc/media/token.

## Đang dở
- Review diff cuối ngày 28/10 chưa thấy lỗi chặn mới trong phạm vi đã đọc. Nhánh IOS-06 vẫn trên IOS-05 `58c36fd`; upstream/main chưa có chuỗi IOS-01…05, nên PR dự kiến base `feat/IOS-05-voice-capture`. Nội dung PR được cung cấp trong chat theo yêu cầu sếp, đã xóa file nháp PR chưa track, không lưu mô tả PR bằng file Markdown. GitHub connector chưa truy cập được repo, trình duyệt tích hợp chưa đăng nhập; sếp chọn **chỉ chuẩn bị nhánh và nội dung PR**, tự commit/push/tạo PR.
- Kiểm cuối trên 27 file dự kiến (kể cả file mới): chỉ `.swift/.md/.xcconfig`, không có media/DB/.env; quét mẫu private key/GitHub token/JWT không có kết quả. Đây là kiểm tra mẫu, không phải chứng minh tuyệt đối không có bí mật. Không thay contracts/backend/ADR/STATUS/thresholds. Hooks trên toàn bộ 27 file Passed hoặc Skipped đúng loại file; plan_check 0 lỗi/10 cảnh báo, diff --check sạch. Chưa có staged files; cần kiểm lại staged khi người dùng tự commit. Không chạy lại test trong lượt review tài liệu này.
- Lỗi Gallery ở lượt retest 104/105 đã được xử lý theo yêu cầu sếp; xem lịch sử hai bước sửa và lượt xanh cuối bên dưới. Chưa commit/push; không đồng nghĩa PR đã được duyệt/merge.
- Ngày 28/10, sếp chốt ca 1–3, 10, sau đó yêu cầu chốt ca 8 và ca 4–7. Mạng thật được xác nhận chung: mất Wi-Fi dừng ở gửi, có mạng gửi tiếp; retry/ack có test tự động xanh, nhưng chưa có log phân lập từng endpoint/payload trên iPhone. Không trình bày xác nhận này thành bằng chứng agent tự quan sát đủ từng request.
- Ca 8: bấm ngoài đóng confirmationDialog thay nút Tiếp tục riêng; hộp không pause lượt. Quay lại chuẩn bị thu từ đầu; Dừng về ngân hàng/file count 0. Ca 9: sếp xác nhận quyền tắt báo thiếu quyền/mở Settings; cấp lại quyền app về đầu, chọn lại API thật thu được. Chấp nhận phục hồi bằng phiên mới, không khôi phục face_ready; tự về giả lập là hạn chế UX chưa sửa. Chưa có log phân biệt crash/system termination lần app đóng khi đổi quyền.
- Chưa commit, push, mở hoặc merge PR. Tiêu chí task card vẫn chưa tick.

## Bước tiếp theo
1. Review diff cuối, chú ý binding path giữ chặn Back và vùng bấm các nút; không cần chạy lại test chỉ vì cập nhật tài liệu. Nếu code đổi hoặc sếp yêu cầu thì chạy lại.
2. Giữ kết quả/nghiệm thu và giới hạn bằng chứng trong `apps/ios/docs/ios06-device-checklist.md`; nếu reviewer cần bằng chứng endpoint máy thật, bổ sung log không chứa token thay vì ghi đã có sẵn.
3. Review diff và staged về dữ liệu/bí mật, hoàn tất nghiệm thu rồi mở PR IOS-06. Chỉ ghi done khi đủ Definition of Done và PR được duyệt/merge.

## Quyết định, lưu ý, bẫy
- Upload đã đóng khác với thu đang diễn ra: background trong lúc upload chỉ dừng preview, giữ payload để retry, không tự quay lại quay mới. Bỏ lượt có xác nhận mới xóa payload/đòi challenge mới.
- Nếu server xử lý finalize/voice nhưng phản hồi bị mất, contract hiện tại không có cơ chế đối soát kết quả ở client. Retry có thể nhận 409; báo lỗi, tuyệt đối không giả pass. Không sửa backend/contracts trong task này.
- Khi iOS kill app do thu hồi quyền, mở lại bắt đầu ở ngân hàng; không hứa khôi phục face_ready sau khi process đã chết. Không lưu token để tự resume.
- Dọn file chỉ áp dụng sandbox app iPhone, không đụng `tmp/media`/DB server Mac hay file đã xuất. Không dọn theo glob toàn bộ WAV/MP4.
- Theo Apple, theo dõi interruption/runtime error của đúng AVCaptureSession đang dùng: https://developer.apple.com/documentation/avfoundation/avcapturesession/wasinterruptednotification và https://developer.apple.com/documentation/avfoundation/avcapturesession/runtimeerrornotification .
- Đã dùng skill codebase-memory; graph chưa index project nên đọc source trực tiếp, không tuyên bố graph bao phủ đầy đủ.

## Câu hỏi cho nhóm
- Nếu cần tự khôi phục kết quả finalize/voice sau mất response, cần task backend/contract riêng; bản này ưu tiên không báo thành công thiếu bằng chứng.

## Kiểm tra đã chạy

Hai build dưới đây exit 0, không có warning trong output lượt cuối. `build-for-testing` chỉ biên dịch app/test bundle, **không chạy test**. Release không ký, không phải nghiệm thu iPhone.

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios06 build-for-testing

xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios06-device CODE_SIGNING_ALLOWED=NO build
```

`git diff --check`: sạch. Pre-commit trên đúng 23 file thay đổi/thêm: các hook áp dụng đều Passed; các hook không có loại file phù hợp Skipped. Đây không phải SwiftLint hay thực thi test Swift.

`uv run python scripts/plan_check.py`: exit 0, **0 lỗi, 10 cảnh báo** về tải công việc/đường găng; không sửa trạng thái task khác để che cảnh báo.

Review cuối sửa nút Dừng ở màn mặt: chỉ mở xác nhận, không hủy trước khi người dùng chọn; chọn Tiếp tục giữ lượt hiện tại. Đã build lại hai cấu hình sau sửa này.

### Lượt test được sếp yêu cầu — 28/10/2026

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=184BFA1A-7DB0-4CE7-A9BB-1DA25FB36F80' \
  -derivedDataPath /tmp/vericlue-ios06 \
  -resultBundlePath /tmp/vericlue-ios06-tests-20261028.xcresult \
  -parallel-testing-enabled NO test
```

Exit 0. `xcresulttool get test-results summary` xác nhận Passed, 105 test, 0 failed/0 skipped; theo thiết bị có 122 lượt pass gồm test tham số. Unit và UI bundle đều Passed, gồm CaptureRecoveryTests/CaptureFileStoreTests. Simulator iPhone 17 Pro, iOS 26.3.1. Chạy đúng một lượt, không nới assertion. Khởi động Simulator/test runner chậm, không phải một lượt test thất bại rồi chạy lại.

Thiết bị kết nối được công cụ đọc là iPhone 14 Pro, iOS **27.0.1**, Developer Mode enabled (không dùng lại bản iOS 18.7.8 từ bàn giao cũ làm bằng chứng hiện tại). API mock `/healthz` trả ok. Đã sửa Debug IP từ 192.168.1.11 sang **192.168.1.12** theo IP en0 hiện tại; healthz qua LAN này cũng ok. Thay đổi IP xảy ra trong lúc lượt Simulator chạy, sau bước build; test MockURLProtocol không dùng API LAN. Sếp cần Run lại bản trên iPhone để áp dụng IP mới.

### Lượt retest trước sửa — 28/10/2026, khoảng 01:28–01:34

Cùng lệnh test trên, đổi result bundle thành `/tmp/vericlue-ios06-retest-20261028.xcresult`. Chạy một lượt, exit 65. Summary: **Failed, 104 Passed / 1 Failed / 0 Skipped**, 105 test tổng; theo thiết bị 121 lượt pass/1 fail. Lỗi duy nhất `VeriClueUITests/testDebugGalleryOpens()` (`XCTAssertTrue failed`); kết quả cũ 105/105 vẫn là lịch sử, không phải trạng thái test mới nhất. Không sửa assertion, không tự retry để lấy xanh.

### Sửa Gallery theo yêu cầu sếp — 28/10/2026

Đọc activity/hierarchy của xcresult: tìm được nút Gallery, tap hoàn tất, nhưng app vẫn ở ngân hàng; chờ `debug-gallery-title` 15 giây thất bại. Dòng source summary trước đó không đủ xác định assertion; activity xác định được lỗi chờ tiêu đề sau tap.

1. Đưa frame/background/contentShape vào label của VcPrimaryButton/VcSecondaryButton, dùng plain style để toàn bộ khung nút nhận bấm. UI test thêm isHittable và tap phần padding (tọa độ tương đối 0.5/0.15), giữ assertion tiêu đề và nhóm Lỗi và gián đoạn, không tăng timeout. Lượt toàn bộ tại `/tmp/vericlue-ios06-buttonfix-20261028.xcresult` vẫn **104/105**, Gallery lỗi. Vì vậy không coi vùng bấm là nguyên nhân duy nhất.
2. Sửa custom binding NavigationStack đọc snapshot `navigation.path` ngay lúc dựng view, thay vì chỉ đọc muộn trong getter; setter vẫn giữ xử lý Back/exit. Đây là thay đổi bổ sung sau khi sửa nút chưa đủ. Toàn bộ test sau sửa binding đạt; chưa coi một lượt xanh là bằng chứng không bao giờ flaky.

Lượt **mới nhất**: lệnh test như trên, result bundle `/tmp/vericlue-ios06-navigationfix-20261028.xcresult`, khoảng 01:48–01:52, exit 0. `xcresulttool` xác nhận **Passed, 105/105, 0 failed, 0 skipped** (122 lượt tính tham số), gồm `testDebugGalleryOpens()` Passed. Không bỏ/nới assertion để lấy xanh. Đây là một lượt toàn bộ trên bản binding mới, không phải chạy lặp cùng bản code đến khi xanh.

Hooks áp dụng trên ba file sửa đều Passed; `git diff --check` sạch; `plan_check.py` 0 lỗi/10 cảnh báo. Lượt Release thành công ghi trước đó có trước bản sửa Gallery, không phải build Release lại sau sửa này. Không đổi contracts/backend, không stage/commit/push.
