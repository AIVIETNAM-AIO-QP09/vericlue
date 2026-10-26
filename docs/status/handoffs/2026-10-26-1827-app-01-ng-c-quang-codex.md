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
