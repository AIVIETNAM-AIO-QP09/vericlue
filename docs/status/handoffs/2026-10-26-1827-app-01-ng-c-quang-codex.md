# Bàn giao · APP-01 · Ngọc Quang+Codex · 2026-10-26 18:27

**Nhánh:** `feat/APP-01-ui-polish`, tách từ `feat/APP-04-short-onboarding` tại `72c71a3` (PR #69 vẫn mở khi bắt đầu).
**Trạng thái task sau phiên này:** `doing` cho toàn APP-01; phần trau chuốt UI được giao đã xong, commit cục bộ. Không push, không mở PR theo yêu cầu Quang.

## Đã xong
- Giữ Be Vietnam Pro offline và toàn bộ câu chữ. Tiêu đề lớn 28/Bold, tiêu đề phụ 22/SemiBold, giãn chữ âm nhẹ; mọi kiểu chữ có dòng tối thiểu 1,4. Nền sáng tách khỏi thẻ, viền nhẹ hơn; theme tối tách nền/thẻ và sửa tương phản dấu tích, nhãn ngân hàng mẫu, nhãn ô sửa thông tin.
- Chuyển màn trượt nhẹ + mờ 250 ms, quay lại đảo chiều. Tắt cả enter/exit ở hai đầu mọi route camera, gồm CCCD, căn mặt, giữ yên/nháy màu, quay đầu và giọng nói.
- Nút chính/phụ/liên kết/bàn phím thu nhỏ 0,97 khi nhấn; nút chính đổi màu mượt khi bật/tắt. Màu chữ chọn theo nền đang chuyển để không mất tương phản ở giữa; nút ngân hàng khi nhấn dùng nền tối hơn, không làm nền trong suốt.
- Thanh ba bước chạy mượt, bỏ bộ nhớ toàn cục giữa các phiên. Chữ số OTP fade/scale, lệch nhau 35 ms khi nhiều số được điền cùng lúc. Viền/dấu tích chỉ xuất hiện sau khi CCCD đã chụp, không thêm hiệu ứng vào preview camera.
- Dấu tích thành công vẽ dần và nảy nhẹ một lần; thẻ đồng ý đổi màu mượt. Rung hệ thống nhẹ (`CONTEXT_CLICK`) khi chụp xong CCCD và thành công, không thêm quyền/thư viện.
- `Vc.motion` theo dõi trực tiếp `Settings.Global.ANIMATOR_DURATION_SCALE`. Giá trị 0 tắt chuyển động trang trí và các vòng lặp trang trí cũ. Lịch nháy màu/chấm sáng của server không đổi.
- Test tương phản các cặp màu chữ/nền ở hai theme, 101 điểm trung gian bật/tắt nút và trạng thái nhấn có state layer; test chiều cao dòng và loại trừ chuyển màn camera. Bổ sung ảnh tối còn thiếu và ảnh sửa thông tin tối.
- Đã rà soát độc lập bằng agent chỉ đọc; sửa các lỗi tương phản phát hiện. Không sửa `flow/`, `data/api/`, `capture/`, hợp đồng, ADR, ngưỡng hay `STATUS.md`.

## Đang dở
- APP-01 tổng thể còn nghiệm thu API trên điện thoại thật và các tiêu chí gốc chưa tích trong E9; không đánh dấu toàn task `done` chỉ vì xong phần UI.
- Chưa kiểm được cảm giác rung trên phần cứng thật; máy ảo chỉ kiểm được app chạy và điều hướng. Không chạy backend/API mock trong phiên này; smoke test dùng demo giao diện offline.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Quang xem bộ so ảnh cục bộ `D:/vericlue/tmp/android-ui-polish/comparison.html` (10 tấm ghép, đủ 20 cặp sáng/tối). Ảnh gốc ở `before/images`, ảnh sau ở `after`; các file này bị ignore, không nằm trong commit.
2. Cài `apps/android/app/build/outputs/apk/debug/app-arm64-v8a-debug.apk` lên điện thoại để duyệt cảm giác nhấn, OTP, rung chụp CCCD/thành công và giảm chuyển động. API mặc định vẫn `http://10.0.2.2:8000/` cho máy ảo; dùng hướng dẫn README khi build với API thật.
3. Chỉ push/mở PR khi Quang yêu cầu. Khi đó đính kèm ảnh trước/sau đã lưu; dùng nhánh APP-04 làm base nếu PR #69 chưa merge.

## Quyết định, lưu ý, bẫy
- Chạy Gradle với JDK có sẵn: `$env:JAVA_HOME='D:\tools\jdk17'`. Android SDK lấy từ `local.properties` (không commit).
- Không chạy đồng thời hai task Gradle có unit test: lượt ghi ảnh đầu bị khóa `test-results/.../output.bin` do trùng với lượt test; đã chạy lại tuần tự thành công.
- Paparazzi đặt `motionEnabled = false` để xem trạng thái tĩnh. Trước sửa lưu 61 ảnh; sau sửa 62 ảnh (thêm `17_edit_dark`), đủ 20 cặp theo đúng danh sách giao việc. Đã xem cả 10 tấm ghép; không thấy chữ/nút bị cắt mới.
- Smoke máy ảo: mở app → điều khoản → kéo hết → tích đồng ý và mục bắt buộc → điện thoại → gõ số → OTP → gõ sáu số → CCCD mặt trước. `AndroidRuntime` không ghi crash. Không coi đây là nghiệm thu API/điện thoại thật.
- Thử đổi animation scale ngay khi app đang mở ở Auth: hai ảnh khi scale=0 giống nhau hoàn toàn; scale=1 có khác biệt ở vùng các thẻ nổi. Đã khôi phục setting ban đầu (ban đầu `null`, dùng `settings delete`). Ảnh chứng cứ `motion-zero-*`, `motion-one-*` trong thư mục so ảnh.
- Android Lint báo 0 lỗi, 43 cảnh báo (phần lớn phiên bản dependency, resource và các đoạn code hiện có). Không nâng dependency ngoài phạm vi task. Compiler còn hai cảnh báo deprecation hiện có (`LocalLifecycleOwner`, `VolumeOff`).

## Câu hỏi cho nhóm
- Không có thay đổi thiết kế/hợp đồng cần duyệt trong phần UI này. Phần nghiệm thu thiết bị thật của APP-01 vẫn cần người có điện thoại thực hiện.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
cd apps/android
./gradlew testDebugUnitTest assembleDebug lintDebug
# BUILD SUCCESSFUL (lượt cuối 2m 1s); CitizenCopyTest và toàn bộ test đều qua.
# Lint: 0 errors, 43 warnings.

./gradlew recordPaparazziDebug --tests '*ScreensSnapshotTest*'
# BUILD SUCCESSFUL (34s); 62 ảnh sau sửa, không commit.

cd ../..
uv run python scripts/plan_check.py
# 0 lỗi, 10 cảnh báo tải công việc/đường găng của backlog hiện tại.

git diff --check
# Không lỗi khoảng trắng.
```

## Bổ sung · Phong cách A · Tối giản ấm (26/10/2026)

### Phạm vi và kết quả
- Làm tiếp trên `feat/APP-01-ui-polish`, sau `969d397`, theo `tmp/design/codex-APP-01-style-A.md` và hàng trên của `tmp/design/phong-cach-A-B.png`.
- Nền sáng `#FAF8F5`, chữ `#14202B`, nút navy `#0C2345` dạng pill cao 56 dp; nút phụ chỉ chữ. Điểm nhấn cam `#E8743B` cho số cuối/nhãn camera/góc khung; theme tối dùng màu nút navy sáng và chữ tối có tương phản.
- Giữ Be Vietnam Pro và đặt đủ mọi vai trò chữ Material về phông này. Tiêu đề 32 sp/Bold, dòng 1,2 theo chỉ dẫn A; thân chữ 15 sp, dòng 1,5. Test chiều cao dòng phân biệt tiêu đề với thân chữ, không còn áp quy tắc cũ 1,4 cho tiêu đề mới.
- Bỏ hộp thụ động ở thông báo, xem lại/xác nhận thông tin và danh sách kết quả; dùng khoảng trắng/đường kẻ. Giữ khung cho ô nhập, checkbox đồng ý và camera. Nút đáy nằm trong tấm có góc trên 24 dp.
- Màn chào dùng minh họa CCCD nghiêng/mặt tròn/vòng cam nét đứt bằng Canvas, danh sách đánh số và tiêu đề được duyệt `Mở tài khoản\ntrong 2 phút`. Không dùng thêm ảnh, phông hay thư viện.
- CCCD theo A2: nền camera `#0D1620`, nhãn bước cam viết hoa, góc khung cam bo tròn, gợi ý trên nền trắng trong suốt với chấm trạng thái, nút chụp vòng trắng. Dấu tích dùng Path; bỏ ký tự tick trong chữ.
- Thành công đăng ký dùng `Tài khoản\nđã sẵn sàng`, giữ dấu tích vẽ/nảy và rung cũ. Tấm đáy có số `0123 4567 8901` ở 26 sp/Bold và nhãn **Dữ liệu mẫu**. Danh sách xác minh lấy đúng từ `checked` hiện tại; `Ảnh giấy tờ` được trình bày thành nhãn `Giấy tờ` theo mục 4 của brief. Không tự coi mọi bước đều đã đạt.
- Giữ nguyên `Motion.kt`, `MotionPolicyTest`, chuyển màn trong `App.kt`, điều kiện giảm chuyển động và haptic. Không thay `flow/`, `data/api/`, `capture/`, hợp đồng, ADR, ngưỡng hoặc `STATUS.md`.

### Các điểm giữ riêng để không đổi màn camera
- `Palette.Primary` gốc vẫn giữ màu xanh cho chấm sáng; chỉ nút dùng token navy mới. Tất cả `Flash*` và lịch thử thách giữ nguyên.
- Căn mặt/nháy màu/quay đầu/đọc câu giữ cỡ chữ/bố cục cũ: `cameraTitle` 28 sp, `cameraButton` 15 sp, `bodySmall` 14 sp. Hai thông báo trong HoldStill/TimelineColour dùng `Banner(cameraLayout = true)` để giữ padding 12 dp, viền và caption 13 sp cũ.
- Agent review chỉ đọc đã tìm hai chỗ lan thay đổi qua component dùng chung (Banner và chữ nút Dừng); đã sửa. Không có vấn đề chặn còn lại sau rà soát.
- Xanh `#1E8A5A` dùng cho nét minh họa; chữ xanh dùng `#176940`. Chữ trên số nền cam dùng màu tối. Các biến thể này cần để đạt 4,5:1, không dùng chữ trắng trên cam hoặc xanh sáng trên nền nhạt.

### Kiểm tra và ảnh
- `testDebugUnitTest assembleDebug lintDebug`: qua; 84 test, 0 lỗi test, gồm `CitizenCopyTest`, `ThemeAccessibilityTest`, `MotionPolicyTest`. Android Lint: 0 lỗi, 44 cảnh báo (có thêm `logo_mark` hiện không dùng sau thay hero bằng Canvas).
- `recordPaparazziDebug --tests '*ScreensSnapshotTest*'`: qua. Snapshot mở rộng để mỗi trạng thái đang test có cả sáng/tối, tổng 92 biến thể duy nhất; ảnh trùng/ảnh cũ không nằm trong danh sách đang test bị loại khỏi báo cáo so ảnh.
- Bộ so ảnh: `D:/vericlue/tmp/android-ui-polish-A/comparison.html`, ảnh gốc `before/images/`, ảnh sau `after/`; `A1-A2-A3.png` ghép thiết kế với app, `overview*.png` để rà bố cục. Toàn bộ nằm trong thư mục ignore, không commit.
- Đã xem ảnh sáng/tối và đối chiếu A1/A2/A3; bố cục giữ các nội dung dài bằng cuộn ở các màn nhập/đồng ý. Khác chữ trong ảnh mẫu do giữ các câu chữ cũ theo brief; chỉ hai tiêu đề và các nhãn được cho phép mới thay.
- `uv run python scripts/plan_check.py`: 0 lỗi, 10 cảnh báo tải/đường găng hiện có. `git diff --check`: không lỗi khoảng trắng.
- Không chạy lại máy ảo trong phần phong cách A; haptic vật lý và nghiệm thu điện thoại/API thật vẫn thuộc phần còn lại của APP-01. Task tổng vẫn `doing`.

### Bước tiếp theo
1. Quang xem ảnh ghép A1/A2/A3 và bộ trước/sau trong thư mục trên; APK debug ở đường dẫn cũ.
2. Thử chữ lớn, thao tác và rung trên điện thoại thật. Giữ số tài khoản là mẫu cho tới khi có tích hợp ngân hàng trả số thật.
3. Không push, không mở PR cho tới khi Quang yêu cầu.
