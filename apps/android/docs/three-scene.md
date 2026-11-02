# Minh họa Three.js trên Android · APP-11

## Cách tích hợp

Three.js là JavaScript, app vẫn dùng Kotlin/Compose. `IdentityScene3D`
nhúng một WebView trang trí trong `WelcomePanel` ở màn bắt đầu. Cảnh tự
tạo bằng hình học: thẻ, chip, chân dung biểu tượng, vòng và các điểm màu;
không dùng ảnh, mô hình 3D tải ngoài, dữ liệu định danh hoặc kết quả xác minh.
Không dùng 3D trên camera, gaze, nháy màu hoặc màn chờ kết quả.

Ghim **Three.js r170 / 0.170.0**, không tuyên bố phiên bản mới nhất.
Build upstream được đóng gói tại `app/src/main/assets/three/vendor/`:

| File | SHA-256 |
|---|---|
| `three.module.min.js` | `08fd7545d13d2c7fb65ab691530a802dafefd638596501854f267d0fb13c39e7` |
| `LICENSE` | `4c40a1ef62450b857c3b2aaf294936304cd552d965fbcd9d32d4c5bcf4ba4454` |

Nguồn: [build r170](https://github.com/mrdoob/three.js/blob/r170/build/three.module.min.js),
[package](https://github.com/mrdoob/three.js/blob/r170/package.json),
[MIT license](https://github.com/mrdoob/three.js/blob/r170/LICENSE).
Giữ nguyên header copyright; license cũng nằm trong `third_party/licenses/`.
Không cần npm hoặc CDN để build/chạy app, không clone ví dụ/model upstream.

## Giới hạn hoạt động

- Chỉ bốn tài nguyên local trên origin riêng `https://appassets.androidplatform.net`
  được đọc bằng `WebViewClient`; đường dẫn khác trả 403, không rơi xuống mạng.
  `ThreeAssetPolicyTest` kiểm origin, scheme, userinfo, query, traversal và encoding.
- WebView chặn network/file/content access, mixed content, popup và quyền web;
  CSP chỉ cho script/style local. Không có `addJavascriptInterface`, lưu trữ DOM
  hoặc dữ liệu phiên. Native chỉ đọc trạng thái và gửi boolean chạy/dừng.
- Cảnh không nhận touch/focus hoặc xuất hiện trong cây trợ năng; kéo cuộn đi
  qua vùng minh họa vẫn do giao diện Compose xử lý. Nội dung/nút chính là native.
- Đặt pixel ratio tối đa 1,5, nhắm tối đa khoảng 30 lần vẽ mỗi giây và 6 giây
  hoạt động mỗi lần mở màn; sau đó vẽ tĩnh. Không có shadow map/postprocessing.
- Tạm dừng khi app ra nền hoặc vùng minh họa ra ngoài vùng nhìn; hủy tài nguyên
  khi rời màn. Tắt chuyển động ở Android thì dùng hình native ngay, không tạo WebView.
- Hình native luôn có lúc chờ nạp; thiếu WebView/WebGL, timeout nạp 3,5 giây,
  lỗi/mất context hoặc renderer bị hủy thì quay về hình native. Không chặn CTA.

Cách phục vụ local tham khảo [hướng dẫn Android](https://developer.android.com/develop/ui/views/layout/webapps/load-local-content).
App dùng allowlist nhỏ với `WebResourceResponse` thay vì thêm dependency WebKit
chỉ cho bốn file. Không đặt `file://` hoặc URL người dùng vào WebView.

## Kiểm tra và xem thử

```powershell
# Từ repo root; dùng Playwright đã có của apps/web, Edge trên Windows.
node apps/android/scripts/test-three-scene.mjs
# Có thể đặt VERICLUE_BROWSER_PATH nếu dùng Chromium ở đường dẫn khác.
cd apps/android
.\gradlew.bat :app:recordPaparazziDebug :app:lintDebug :app:assembleDebug '-Pvericlue.deferSigning=true'
```

Browser test dùng route local, không mở cổng HTTP: render WebGL thật,
pause/resume, hết ngân sách chuyển động, resize, dispose, reduced motion,
WebGL không có và mất context. Ảnh/kết quả ở `tmp/app11-ui/three/`.
Đây là kiểm tra chức năng bằng WebGL phần mềm, không đo hiệu năng điện thoại.

Preview tự chứa `tmp/app11-ui/three/index.html` mở trực tiếp từ file, chạy
cùng thư viện/cảnh qua Blob URL, không CDN. Preview này không dùng policy
WebView của APK. Paparazzi chỉ kiểm bố cục/hình native dự phòng.

Trên điện thoại cần kiểm: scene hiện và cuộn không bị giữ, chuyển nền/quay lại,
tắt chuyển động, rời màn trước khi nạp xong, WebView cũ và máy ít bộ nhớ.
Chưa coi render trình duyệt là bằng chứng đã kiểm WebView Android thực tế.
