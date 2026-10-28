# Bàn giao · IOS-01 · Lý Anh Quân+Codex · 2026-10-28 16:08

**Nhánh:** feat/IOS-02-android-alignment
**Trạng thái task sau phiên này:** review — Simulator xanh, sếp xác nhận iPhone A–D đạt

## Cập nhật nghiệm thu iPhone · 28/10/2026

## Chuẩn bị commit/PR · 28/10/2026

- Sếp cho phép review, commit/push và chọn PR nối tầng vào
  `feat/IOS-06-interruption-retry`; không gộp chuỗi IOS-01–06 vào main trong PR này.
- Đối chiếu SHA256 toàn bộ Swift hiện tại trùng manifest bản test cuối;
  đọc lại xcresult xác nhận 159/159 bài, 186 lần thực thi, 0 lỗi/0 bỏ qua.
  Không chạy lại test trong lượt Git này.
- Review tập trung ownership evidence, confirm trước upload, retry theo ack,
  receipt độc lập, Back và sửa camera/QR. Chưa thấy lỗi chặn mới trong phần đã rà;
  không coi đây là peer review hoặc kết luận không còn lỗi ở toàn app.
- Luật OTP backend tổng số lần sai/phiên được tách commit; hai test Python mới
  chưa có bằng chứng thực thi. Cần chạy trước khi duyệt merge phần backend.
- Giữ thay đổi Debug API cổng 8001 ở local, loại khỏi commit.
- Đã commit/push upstream: `e7cfa6d` (backend OTP), `737e020` (đồng bộ iOS),
  nhánh `feat/IOS-02-android-alignment`. Hook commit đạt, Swift sau commit vẫn
  khớp manifest bản test cuối. Chỉ Debug.xcconfig còn modified local.
- Lượt Git read ban đầu lỗi xác thực nhưng push sau đó thành công. GitHub
  connector vẫn trả 404 khi tạo PR; trình duyệt tích hợp chưa đăng nhập nên
  không truy cập được repo. Chưa mở PR/đăng review trên GitHub; không tự merge.
- Link tạo PR đúng base:
  https://github.com/AIVIETNAM-AIO-QP09/vericlue/compare/feat/IOS-06-interruption-retry...feat/IOS-02-android-alignment?expand=1
- `plan_check.py`: 0 lỗi/10 cảnh báo kế hoạch; chưa cấu hình SwiftLint riêng.

## Xác nhận thiết bị

Sếp xác nhận “tất cả đều thoả” cho bản mới nhất:

- A: light/dark, Back, chữ lớn.
- B: CCCD auto/manual, retake, Home.
- C: quay → sửa/confirm, mất mạng rồi thử lại, đúng thứ tự API.
- D: Home/Back/Dừng, file tạm về `0` sau dừng hẳn.

Đã tick bốn nhóm trong checklist theo báo cáo của sếp; agent không tự thao tác
iPhone. Chốt nghiệm thu chặng 5/đồng bộ UI trong phạm vi này. Không chạy lại test
hoặc sửa code trong lượt ghi nhận, không tự bổ sung log/số đo/model/iOS của lượt
này. Kết quả tự động vẫn là bundle cuối 159/159 bên dưới.

Còn tạo PR và peer review/merge theo quy trình; commit/push đã thực hiện như
cập nhật trên. Không đánh dấu task done/đã merge. Receipt thật/device proof
không thuộc xác nhận A–D.
Các dòng “chưa có kết quả iPhone” bên dưới là lịch sử trước xác nhận mới này.

## Kết luận mới nhất · 28/10/2026 17:23

- **159/159 bài, 186/186 lần thực thi đạt**, 0 lỗi, 0 bỏ qua, trên source cuối
  không đổi trong lượt chạy (đã đối chiếu SHA256 toàn bộ Swift).
- Cả 4 cấu hình UI qua 3 vòng Back Terms → Gallery (12 vòng, mỗi vòng một tap),
  gồm dark/light và default/AX3. Hai ca AX3 nhập sai rồi đúng, không tự xác nhận,
  xác nhận đúng mới vào chụp; cuộn đủ 5 fields và kiểm vùng nút confirm.
- Đã review phần sửa: demo dùng projected Binding, live giữ adapter exit;
  keypad/confirm hỗ trợ chữ lớn. Không thấy vấn đề chặn mới trong phạm vi này.
  Đây là review của agent, không thay review PR/duyệt nhóm trưởng.
- Release không ký build exit 0; marker trace/override UI không xuất hiện khi
  quét strings binary Release. Không sửa capture/flow/data, contract, project
  hoặc cấu hình IP. Chưa commit/push, không tự merge/main hay đổi nhánh.
- Tại mốc 17:23, iPhone chưa có kết quả; sau đó sếp đã xác nhận A–D đạt như
  cập nhật đầu file. Task chuyển review, chưa done/đã merge.

Bundle cuối: `/tmp/vericlue-ios-theme-final-20261028.xcresult`.
Log: `/tmp/vericlue-ios-theme-final-20261028.log`.
28 ảnh theme export: `/tmp/vericlue-ios-theme-final-qa/manifest.json`.
Đã xem trực tiếp các ảnh cuối OTP nhập tay light/dark AX3, cuối confirm light/dark
AX3, welcome/success dark. Không tuyên bố golden-image diff hoặc đã xem mọi pixel
của toàn bộ 28 ảnh. 24 ảnh giai đoạn đầu đã xem riêng được ghi ở lịch sử dưới.

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=F4629DA5-E113-4A6A-82EC-B2F27454F6AF' \
  -derivedDataPath /tmp/vericlue-ios-stage5 \
  -resultBundlePath /tmp/vericlue-ios-theme-final-20261028.xcresult \
  -parallel-testing-enabled NO test
```

`git diff --check`: sạch. `plan_check.py`: 0 lỗi, 10 cảnh báo kế hoạch.
Giới hạn còn lại sau xác nhận A–D: review/merge PR; receipt thật/device proof vẫn ngoài
phạm vi chặng giao diện. Các phần dưới giữ lịch sử, không thay kết luận mới nhất.

## Đã xong
- Port token Android: nền FAF8F5, navy 0C2345, accent E8743B; dark mode riêng,
  màu chữ trên nút sáng được tách đúng. Primary pill tối thiểu 56 pt ngoài camera.
- Dùng Be Vietnam Pro, tiêu đề lớn, bố cục cuộn được khi tăng chữ; list/banner
  bớt viền. Dấu VC là SwiftUI Path từ drawable của Android trong cùng repo.
- Welcome/splash/success dùng VC; tài khoản demo luôn ghi “Dữ liệu mẫu”.
- Reduce Motion chỉ ảnh hưởng chuyển động trang trí. Không sửa capture/flow/API,
  màu flash, clock hay tọa độ thử thách. Giữ cấu hình project và API của sếp.
- Thêm unit test palette/contrast/font/motion/flash và ma trận UI 4 cấu hình,
  6 màn mỗi cấu hình. Override trình bày chỉ tồn tại trong Debug.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- iPhone A–D đã được sếp xác nhận đạt; thiếu metadata model/iOS/thời điểm Run
  cụ thể của lượt này, không tự lấy thông tin lịch sử điền thay.
- Lỗi Simulator trong các lượt trước đã được kiểm lại xanh ở bundle cuối;
  không xóa lịch sử thất bại và không khẳng định đã truy vết mọi nguyên nhân cũ.
- Receipt/device proof mới của Android trên upstream/main caf4469 nằm ngoài
  phạm vi theme; không tự port, merge hoặc coi đăng nhập lại thật đã hoàn tất.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Sếp duyệt diff/PR; có thể bổ sung model/iOS/thời điểm Run cho hồ sơ nghiệm thu.
2. Giữ kết quả A–D và bundle cuối trong bàn giao; chỉ kiểm lại phần bị ảnh hưởng
   nếu có sửa code sau nghiệm thu.
3. Chỉ commit/push/mở PR sau sếp duyệt. Phiên này không thực hiện các thao tác đó.

## Quyết định, lưu ý, bẫy
- Redesign audit tập trung typography, tương phản, vùng bấm và chữ lớn; không
  thay hành vi thu để phục vụ trang trí. Dùng token Android thay vì tự chọn màu.
- Nguồn theme Android không đổi trong delta a54d093..caf4469 vừa fetch.
- Consent vẫn nội dung demo/chờ duyệt. Tài khoản mẫu không phải receipt thật.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Chưa có yêu cầu mở rộng ký media/device proof trong chặng giao diện này.

## Test đã chạy
Một lượt toàn bộ iOS test: **159/159 bài đạt**, **186/186 lần thực thi tính
tham số**, 0 lỗi, 0 bỏ qua. Simulator iPhone 17 Pro, iOS 26.3.1 (23D8133).
Nền git 6aef3ac + worktree chưa commit; kết quả không phải của commit 6aef3ac sạch.

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=184BFA1A-7DB0-4CE7-A9BB-1DA25FB36F80' \
  -derivedDataPath /tmp/vericlue-ios-stage5 \
  -resultBundlePath /tmp/vericlue-ios-stage5-tests.FxlgpS/FullRun.xcresult \
  -parallel-testing-enabled NO test
```

- Bundle: `/tmp/vericlue-ios-stage5-tests.FxlgpS/FullRun.xcresult`.
- 24 ảnh theme được export tại `/tmp/vericlue-ios-stage5-qa/`, mapping trong
  manifest.json. Đã xem trực tiếp cả 24; đây không phải golden-image comparison.
- Phát hiện ảnh dark/default thiếu VC và vài số thứ tự dù element tồn tại.
  Thêm 1 giây chờ trước chụp trong UI runner, không thay code app. Kiểm riêng
  `WarmThemeUITests/testDarkThemeScreensAndTargets`: **0/1 đạt**, lỗi assertion
  chờ Gallery sau Back từ Terms (`WarmThemeUITests.swift`, dòng 58). Không nới
  assertion, không tự bấm Back lần hai để che kết quả.
- Bundle kiểm lại: `/tmp/vericlue-ios-stage5-dark-check.xcresult`; ảnh tại
  `/tmp/vericlue-ios-stage5-dark-qa`. Welcome dark trong lượt này hiện đủ VC và
  số 1/2/3, đã xem trực tiếp. Chưa xác định nguyên nhân ảnh đầu thiếu thành phần;
  chưa xác nhận lại success dark trong lượt riêng vì test dừng ở Terms.
- **Kết luận:** 159/159 là kết quả lượt toàn bộ trước thay đổi thời gian chụp
  trong test; không gọi lượt kiểm lại mới nhất là xanh. App source không đổi
  giữa hai lượt. Nghiệm thu Simulator chưa hoàn tất, IOS-01 vẫn doing.
- AX3 cần kiểm thao tác cuộn để tới OTP/fields và cuối màn, chưa đủ bằng chứng
  thao tác chỉ từ 24 ảnh đầu. Không ghi “mọi chữ lớn đều đã nghiệm thu”.
- Build-for-testing Simulator và Release iPhone không ký: exit 0.
- `git diff --check`: sạch. `plan_check.py`: 0 lỗi, 10 cảnh báo tải/đường găng.
- SHA256 toàn bộ Capture/Flow/Data giống mốc trước theme; project.pbxproj vẫn
  blob `3757f703fa286597f132a254105c3ace82decb68`. Không sửa contract.

Không coi build hoặc test logic là nghiệm thu camera/iPhone.

## Lượt tiếp theo — sửa Back và kiểm thao tác AX3

- Binding NavigationStack vẫn đọc path trong body nhưng getter đọc giá trị hiện
  hành, không giữ snapshot cũ qua một native pop. Giữ nguyên setter chốt exit,
  cancel/cleanup, không thay bằng Back tùy biến hoặc bỏ hỗ trợ Back hệ thống.
  Snapshot cũ là cơ chế nghi ngờ từ source; kết quả UI mới mới là bằng chứng
  kiểm thao tác, không khẳng định đã truy vết chính xác mọi nguyên nhân cũ.
- Màn confirm demo dùng VcChecklistCard như màn thật, label/value xếp dọc khi
  cỡ accessibility thay vì cố định nhãn rộng 100 pt. Keypad bỏ chữ ABC phụ ở
  cỡ accessibility, giữ số lớn; thêm nhãn/ID cho nút và full-cell hit area.
- OTP có accessibility value cho giá trị đang hiện; không thêm log OTP/token.
- UI test mở rộng: AX3 nhập sai rồi đúng, attempts demo 4, không tự xác nhận,
  chỉ xác nhận đúng mới mở chụp CCCD; cuộn đọc đủ 5 trường confirm và vùng bấm.
- Assert Back theo navigation bar Gallery hiện hành, không theo heading có
  thể nằm ngoài viewport cuộn đã khôi phục. Không bấm Back lần hai để qua test.
- Đang chạy toàn bộ test tại `/tmp/vericlue-ios-theme-close-tests-20261028.xcresult`.
  Chưa lấy kết quả lượt trước làm kết quả của source sửa mới.

Kết quả lượt trên: **156/159**, 183/186 lần thực thi, 3 lỗi UI (dark AX3 không
đọc được ScrollView Gallery, dark mặc định Back Terms không về Gallery, light
AX3 mở Gallery không thấy heading). Không lỗi unit được báo, nhưng tổng chưa
xanh. Việc đổi getter chưa giải quyết được ca dark, không coi giả thuyết ban đầu
là nguyên nhân đã xác nhận.

UI helper được chỉnh gesture nằm trong phần ScrollView thật sự nhìn thấy,
không kéo trên fixed keypad/footer; chờ ScrollView tồn tại trước đọc frame.
Sau Back camera về OTP kiểm code trong viewport đã khôi phục, không đòi heading
ở đầu nội dung phải đang hiện. Assertion nhập code/route vẫn giữ.

Tạo Simulator riêng `VeriClue Theme QA`, ID
`F4629DA5-E113-4A6A-82EC-B2F27454F6AF`, không reset/xóa Simulator có sẵn. Đang
kiểm riêng dark tại `/tmp/vericlue-ios-theme-fresh-dark-20261028.xcresult`.

Kiểm riêng trên Simulator mới vẫn **0/1**, lỗi mở Gallery (dòng 22), không
chứng minh dữ liệu Simulator cũ là nguyên nhân. Đã bỏ thử nghiệm getter live
cho adapter cũ: nhánh API thật giữ cách đọc snapshot và setter chốt exit như
baseline. **Source hiện tại**: demo/Gallery dùng `$navigation.path` trực tiếp;
chỉ luồng API thật dùng adapter Back có chốt hủy/cleanup. Không thay bằng nút
Back tự chế hoặc bấm hai lần. Đang kiểm 4 ca WarmThemeUITests tại
`/tmp/vericlue-ios-theme-native-binding-20261028.xcresult`.

Kết quả 4 UI ca: **3/4 đạt** (dark/default, dark/AX3, light/default). Dark AX3
đã nhập OTP sai → 4 lượt demo còn lại → sửa đúng, không tự xác nhận, xác nhận
mới mở chụp, Back về OTP; cuộn đủ 5 fields confirm. Đã xem ảnh
`/tmp/vericlue-ios-theme-native-binding-qa/3C5D6816-9DC5-46C3-BE2C-4E7911DDF814.png`
và `0D79F68E-44FE-461F-8CBF-18251AEA9D62.png`; nội dung số/địa chỉ đọc được,
nút nằm riêng dưới vùng cuộn. Ảnh dark success hiện VC đầy đủ.

Còn light AX3 lỗi Back Terms → Gallery. Thêm trace opt-in
`--vc-navigation-trace` chỉ trong Debug: ghi tên route, không ghi token, OTP,
receipt, ID hoặc trường CCCD. Test Terms được tăng thành 3 vòng Back/push,
mỗi vòng đúng một lần Back, không fallback. Đang kiểm riêng light AX3 tại
`/tmp/vericlue-ios-theme-trace-light-20261028.xcresult`.

Ca trace light AX3 **1/1 đạt**, 0 bỏ qua. Trace ghi đủ 3 vòng
gallery/terms → gallery, rồi gallery/otp → id_front → otp → gallery và confirm.
Đã xem ảnh OTP nhập tay, cuối confirm và success tại
`/tmp/vericlue-ios-theme-trace-light-qa/`; không thấy tràn ngang ở các ảnh này.
Các ảnh đầu cắt nội dung phía trên khi đã cuộn là viewport, không phải mất dữ liệu.

Build Release không ký source cuối: exit 0, log
`/tmp/vericlue-ios-theme-close-release.log`. Trace chỉ Debug/opt-in, Release không
biên dịch logger này. Lượt toàn bộ source cuối đang chạy tại
`/tmp/vericlue-ios-theme-final-20261028.xcresult`; không đổi code trong lượt này.
Chưa nhận kết quả iPhone A/B/C/D trên bản cuối.
