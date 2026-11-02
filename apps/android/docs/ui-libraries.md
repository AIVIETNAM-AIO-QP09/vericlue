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

Các thư viện khác trong danh mục chưa được cài. Ở lượt này, app không có nhu
cầu thêm trình tải ảnh mạng, menu hay hệ navigation khác.

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
