# Thử thư viện UI từ awesome-android-ui

## Đã chọn

[`wasabeef/awesome-android-ui`](https://github.com/wasabeef/awesome-android-ui)
là danh mục thư viện, không phải một SDK hay app để chạy. Bản tham khảo local:
`tmp/ui-references/awesome-android-ui`, commit
`312f9be3c50b3ea33ff3ba7eb9aa1c21b52de8b2`, giấy phép MIT. Không đưa danh mục
hoặc các ảnh demo vào sản phẩm. Giấy phép từng thư viện cần kiểm riêng.

Chọn **Lottie Compose 6.6.2** trong mục Animation cho thử nghiệm đầu tiên.
Dependency khai báo qua version catalog và lấy từ Maven Central. POM chính
thức của 6.6.2 khai báo Kotlin 1.9.22 và Compose BOM 2024.02.01; app giữ
Kotlin 2.0.21/Compose BOM 2024.12.01 hiện có. Không thêm JitPack/JCenter hoặc
đổi nền Gradle/AGP cho thử nghiệm này. Đây là phiên bản ghim để kiểm chứng
trên app hiện tại, không phải tuyên bố phiên bản mới nhất.

Nguồn kiểm tra:

- [Mục Lottie trong danh mục](https://github.com/wasabeef/awesome-android-ui#animation).
- [Lottie Compose API tại v6.6.2](https://github.com/airbnb/lottie-android/tree/v6.6.2/lottie-compose/src/main/java/com/airbnb/lottie/compose).
- [POM chính thức](https://repo.maven.apache.org/maven2/com/airbnb/android/lottie-compose/6.6.2/lottie-compose-6.6.2.pom).
- [Giấy phép upstream](https://github.com/airbnb/lottie-android/blob/v6.6.2/LICENSE).

## Khai thác thêm các mẫu UI (lượt mở rộng APP-11)

Danh mục còn được dùng để chọn sáu nhóm mẫu cho các màn ngoài camera.
Lottie là dependency trực tiếp; các mẫu dưới đây được tự triển khai bằng
Compose/Material 3 đã có, không chép source, tài nguyên hoặc thêm AAR của
những thư viện View/XML vào app Compose.

| Tham khảo từ danh mục | Áp dụng trong VeriClue | Triển khai |
|---|---|---|
| [ComposeCookBook](https://github.com/Gurupreet/ComposeCookBook) | Thẻ mở đầu navy, hành trình đánh số, bố cục theo theme | `WelcomePanel`, `JourneyOverview`, `JourneyHeader` |
| [BottomSheet](https://github.com/Flipboard/bottomsheet), [material-dialogs](https://github.com/afollestad/material-dialogs) | Trợ giúp theo ngữ cảnh, đóng bằng nút hoặc thao tác hệ thống | `ModalBottomSheet` của Material 3, `HelpButton`/`HelpSheetContent` |
| [ExpandableLayout](https://github.com/skydoves/ExpandableLayout) | FAQ mở rộng từng câu, trạng thái mở/đóng cho trợ năng | `ExpandableAnswer`, `AnimatedVisibility` và cài đặt giảm chuyển động |
| [Material Code Input](https://github.com/glomadrian/material-code-input) | Mã 6 ô, số ký tự đã nhập, dán mã chủ động, giải thích lỗi | `OtpScreen`, giữ `OtpBoxes`, thêm `InputAssist` |
| [circular-progress-button](https://github.com/dmytrodanylyk/circular-progress-button) | Nút gửi/xác nhận báo bận trong lúc API xử lý | `PrimaryButton(loading)` nối với `busy` thật, khóa keypad và gửi lặp |
| Nhóm Progress trong danh mục | Thẻ chờ phản hồi/gửi dữ liệu và trạng thái tĩnh khi giảm chuyển động | `ProcessingPanel`, không tự tăng tiến độ hay dựng kết quả |

API bottom sheet đối chiếu [tài liệu Android chính thức](https://developer.android.com/develop/ui/compose/components/bottom-sheets).
Không thay navigation của các luồng, lịch camera/nháy màu hoặc hợp đồng API.
Màn kết quả/làm lại có thẻ hướng dẫn tiếp theo; số lần thử và nội dung đã
xác minh vẫn lấy từ dữ liệu hiện có. Màn âm thanh làm lại dùng đúng nhãn
đọc lại và bước bổ sung.

Clipboard chỉ được đọc khi người dùng bấm **Dán**, không tự đọc lúc mở
màn. Số `+84` được chuyển sang dạng `0`; nội dung không hợp lệ bị từ chối
nguyên vẹn, không cắt chuỗi để biến thành số/mã hợp lệ. Dán không tự gửi.
Trợ giúp hoạt động local; mở hoặc đóng không đồng ý điều khoản, gửi dữ liệu
hay bỏ qua bước. Có nút đóng rõ ràng để không phụ thuộc thao tác kéo.

## Điều chỉnh sau test thiết bị (APP-11)

Lượt trau chuốt tiếp dùng Compose animation cho thứ tự xuất hiện của hero/hành
trình và thu preview vào góc; Canvas cho hướng dẫn quay đầu nhẹ, rõ tư thế.
Three.js tăng chuyển động ghép lớp/xoay của vật thể, vẫn kết thúc ở 3 giây.
Không thêm dependency View/XML chỉ để có hiệu ứng: tiếp tục khai thác các mẫu
animation/progress trong danh mục bằng stack Compose hiện có. Skill
`ui-ux-pro-max` được dùng cho line wrapping tự nhiên, không đổi layout trong
animation, giảm chuyển động và các kiểm tra safe area/chữ lớn.

Áp dụng mẫu progressive disclosure của bottom sheet/material-dialogs cho mục
nhạy cảm ánh sáng: chỉ mở giải thích khi người dùng chọn, đóng sheet không
thoát phiên. Không hứa có phương thức thay thế nếu backend chưa cung cấp.
Three.js dùng như phần trang trí 3 giây, bỏ player và tab khỏi luồng xác minh.
Rà lại bằng skill `ui-ux-pro-max`: giới hạn chuyển động trang trí, giữ layout
ổn định, nội dung ngắn và nút native. Không thêm dependency từ danh mục chỉ
để có thêm hiệu ứng. Camera dùng bố cục chung để giữ mặt/oval không nhảy;
đối chiếu [CameraX PreviewView](https://developer.android.com/media/camera/camerax/preview).

## Setup

Không cần clone danh mục để build app. Gradle tự tải dependency:

```powershell
cd apps/android
.\gradlew.bat :app:assembleDebug
```

Cần JDK 17/SDK 35 như README. Lần đầu cần mạng; sau khi dependency đã cache
có thể thêm `--offline`. Nếu chỉ kiểm build chưa ký, dùng
`'-Pvericlue.deferSigning=true'` (giữ dấu nháy khi dùng PowerShell).

Nếu muốn đọc danh mục tại máy, chạy từ repo root:

```powershell
git clone --depth 1 --filter=blob:none --sparse https://github.com/wasabeef/awesome-android-ui.git tmp/ui-references/awesome-android-ui
git -C tmp/ui-references/awesome-android-ui fetch --depth 1 origin 312f9be3c50b3ea33ff3ba7eb9aa1c21b52de8b2
git -C tmp/ui-references/awesome-android-ui checkout --detach FETCH_HEAD
```

## Phần đã tích hợp

- `SuccessAnimation.kt`: nạp `R.raw.vericlue_success`; vẽ vòng viền một
  lần, pause theo lifecycle, dùng màu theme. Không tải animation từ URL.
- `Feedback.kt`: logo và dấu xác nhận tĩnh luôn có mặt, độc lập với Lottie.
- `res/raw/vericlue_success.json`: vector tự tạo, 36 frame ở 30 fps;
  không có ảnh/font ngoài. Chuyển động tắt thì vẽ trạng thái cuối.
- Animation chỉ trang trí màn đã thành công. Không nhận kết quả server,
  không phát callback xác minh, không chờ animation mới bật nút.
- Lỗi nạp asset dùng vòng tĩnh; không ảnh hưởng nội dung/kết quả. Camera,
  nháy màu, gaze và lịch quay đầu không dùng Lottie.
- Giấy phép Apache-2.0 được ghi ở `third_party/README.md` và đóng gói
  trong `assets/licenses/lottie-android.txt`.

Xem trên app debug: **Xem tất cả màn → Kết quả → Thành công**. Đây là
gallery mô phỏng để review UI, không phải bằng chứng xác minh thật.

Để xem phần nâng cấp hành trình, mở các nhóm **Bắt đầu → Đăng nhập / Đăng ký**,
**Danh tính → Số điện thoại / OTP** và **Kết quả** trong gallery. Chọn
**Các bước & trợ giúp** hoặc **Cần trợ giúp?** để mở bảng hướng dẫn.
Preview so với bản có Lottie: `tmp/app11-ui/upgrade/index.html`.

## Kiểm tra

```powershell
.\gradlew.bat :app:recordPaparazziDebug --tests '*SuccessAnimationSnapshotTest'
.\gradlew.bat :app:recordPaparazziDebug :app:lintDebug :app:assembleDebug '-Pvericlue.deferSigning=true'
```

Test parse asset bằng Lottie thật, kiểm không có ảnh/font ngoài, giới hạn
thời lượng, marker giảm chuyển động; render đầu/giữa/cuối và fallback ở
hai theme. Hai test motion riêng tua 1,5 giây và kiểm tiến độ đạt frame
cuối; mỗi test có đồng hồ Paparazzi mới để tránh tái sử dụng thời gian.
PNG ở `app/src/test/snapshots/images/`, animation APNG 46 frame ở
`app/src/test/snapshots/videos/` (không commit).
Trang xem thử tại máy: `tmp/app11-ui/lottie/index.html` từ repo root.
Kiểm thêm trên điện thoại: vào/ra nền giữa animation, tắt chuyển động,
thử theme tối, bấm Hoàn tất ngay mà không đợi vòng vẽ xong.

Lượt mở rộng có `InputAssistTest` (định dạng, độ dài, giữ số 0 đầu,
không cắt/dò chuỗi không hợp lệ), `OtpCooldownTest` (nhiều lượt gửi lại,
chặn chạm lặp, hủy ticker khi rời màn), `BusyActionSnapshotTest` (nút và
12 phím khai báo disabled qua semantics). `ExperienceSnapshotTest` render
42 trạng thái form/trợ giúp ở 375dp, chữ 200%, ngang và cả hai theme.
Ảnh trợ giúp kiểm phần nội dung sheet; động tác mở/đóng, focus TalkBack,
clipboard thật và thao tác trên điện thoại vẫn cần nghiệm thu thiết bị.
