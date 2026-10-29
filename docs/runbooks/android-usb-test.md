# Test Android qua ADB (USB hoặc Wi-Fi TLS) — APP-06

Điện thoại Android 10+ nối laptop bằng cáp truyền dữ liệu, bật USB debugging và
chủ máy chấp nhận dấu vân tay RSA của laptop. Dùng ADB chính thức trong Android
Platform-Tools, không cần Android Studio. Cấu hình USB ở dưới; cách chuyển sang
Wireless debugging có ghép đôi TLS nằm ở cuối tài liệu.

Tài liệu: [ADB](https://developer.android.com/tools/adb),
[Platform-Tools](https://developer.android.com/tools/releases/platform-tools).

## Bản cài riêng

Workflow **Android USB test APK** tạo artifact `vericlue-android-usb-test` gồm
APK ARM64, SHA256SUMS và build-info. Package **`vn.vericlue.app.usbtest`**, nhãn
**VeriClue USB**, URL cố định **`http://localhost:8421/`**, ký media bật. Bản này
cài song song, không gỡ hoặc xóa dữ liệu/Keystore của app Tailscale đã cài.

```bash
cd apps/android
./gradlew testDebugUnitTest assembleDebug -Pvericlue.usbTest=true -Pvericlue.apiBaseUrl=http://localhost:8421/ -Pvericlue.signedMedia=true
```

Profile USB từ chối URL khác, thiếu ký media hoặc build release. Build bình
thường giữ app ID/nhãn/cấu hình cũ; không mở rộng cleartext ngoài debug localhost
đã có. HTTP chỉ đi qua đường USB/loopback, không dùng địa chỉ LAN hoặc URL công
khai. API vẫn chỉ bind loopback.

## Nối điện thoại với API

Trên laptop kiểm `http://127.0.0.1:8421/healthz` trước. Runtime mặt từng phần và
giới hạn ở mục 6 của [test từ xa](android-remote-test.md). Trên laptop này ADB ở
`tmp/android-usb-tools/platform-tools/adb.exe`, API test ở `tmp/remote-android-ai`;
các công cụ, khóa, model và dữ liệu không nằm trong Git.

```powershell
$adb = 'D:/Projects/Data4Life/tmp/android-usb-tools/platform-tools/adb.exe'
& $adb devices -l
& $adb -d reverse tcp:8421 tcp:8421
& $adb -d reverse --list
# APK vừa tải từ CI, đã đối chiếu SHA-256/build-info:
& $adb -d install '<đường dẫn>/vericlue-usb-debug-arm64-v8a.apk'
& $adb -d shell am start -n vn.vericlue.app.usbtest/vn.vericlue.app.MainActivity
```

`-d` chọn một thiết bị USB; có nhiều thiết bị phải chọn đúng bằng `-s`, không
đoán. Nếu `unauthorized`, mở khóa và chấp nhận lời nhắc trên điện thoại. Nếu
không thấy thiết bị, kiểm cáp có truyền dữ liệu, chế độ USB và driver đúng hãng.
Không bật OEM unlocking, root, factory reset, `adb tcpip` hoặc thay driver tùy ý.

Mở Chrome điện thoại tại `http://localhost:8421/healthz` để kiểm đường truyền;
`localhost` ở đây là phía điện thoại được ADB nối tới laptop. Mapping có thể mất
sau khi rút dây, reboot hoặc khởi động lại ADB; chạy lại đúng lệnh reverse.
Điện thoại và laptop không cần Tailscale cho đường USB này; cấu hình Tailscale
phục vụ các bản cài khác giữ nguyên.

Nếu máy đã có package USB với chữ ký khác, không tự gỡ/cài đè xóa dữ liệu.
Ghi nhận lỗi chữ ký để chủ máy quyết định; debug key CI không giữ ổn định giữa
mọi runner. Không xóa app chính để xử lý lỗi cài bản USB.

## Test trong app

Mở đúng **VeriClue USB** → Xem tất cả màn → API thật → `genuine` → Đăng nhập /
Đăng ký → Đăng ký. Profile mặc định dùng OTP/QR mẫu; cấu hình đọc ảnh CCCD thật
theo yêu cầu chủ máy nằm ở mục cuối. Cấp quyền camera/micro đúng
bước; không thu khi người test chưa biết. Bắt đầu phiên mới cho mỗi lần đổi kho
server. Bản USB dùng cùng flow và hợp đồng như app thường.

Đổi đường truyền không làm toàn hệ thống thành thật. Profile AI mặt ban đầu
bật FS-VFM-L, GenD, mắt/đầu/màu; OTP/CCCD và một số module còn mô phỏng;
voice models tắt, chưa hiệu chỉnh hoặc tạo tài khoản thật. `review` không phải
pass hoặc chờ nhân viên trong product_mode ekyc. Chưa có accuracy từ test USB.

Kết thúc test, chỉ xóa mapping của đợt này:

```powershell
& $adb -d reverse --remove tcp:8421
```

Có thể tắt USB debugging/rút dây sau test. Không dùng `--remove-all`, `kill-server`
hoặc xóa dữ liệu app để tránh tác động tới công việc khác.

## ADB Wi-Fi có ghép đôi TLS

Theo yêu cầu chủ máy 29/10 khi cáp liên tục mất kết nối, giữ nguyên APK VeriClue
USB và URL localhost, chuyển transport sang Wireless debugging của Android 11+.
Không dùng `adb tcpip 5555`. [Hướng dẫn Android](https://developer.android.com/tools/adb#connect-to-a-device-over-wi-fi).

1. Điện thoại và laptop cùng Wi-Fi. Bật **Gỡ lỗi Wi-Fi / Gỡ lỗi không dây** trong
   Tùy chọn nhà phát triển rồi mở **Ghép đôi bằng mã**.
2. Giữ màn đó mở, dùng đúng IP:cổng pairing và nhập mã ở prompt. Không lưu mã
   vào script/log/repo. Endpoint mDNS phải thuộc đúng điện thoại đã được cho phép.
3. Sau khi pair, lấy **cổng kết nối** từ màn chính Wireless debugging hoặc
   `_adb-tls-connect._tcp`; cổng này khác cổng pairing và có thể đổi.

```powershell
& $adb pair '<IP-WIFI>:<PAIR-PORT>'
# Nhập mã ở prompt, không ghi mã trong lệnh hoặc tài liệu.
& $adb connect '<IP-WIFI>:<CONNECT-PORT>'
& $adb -s '<IP-WIFI>:<CONNECT-PORT>' get-state
& $adb -s '<IP-WIFI>:<CONNECT-PORT>' reverse tcp:8421 tcp:8421
& $adb -s '<IP-WIFI>:<CONNECT-PORT>' shell am start -n vn.vericlue.app.usbtest/vn.vericlue.app.MainActivity
```

Khi Wi-Fi ở trạng thái device, rút cáp và tải lại
`http://localhost:8421/healthz` trong Chrome điện thoại. Dùng `-s` endpoint Wi-Fi
cho lệnh tiếp theo; `-d` chỉ chọn USB. Không cần build/cài lại app, mở API ra LAN,
đổi firewall hoặc đổi kho/khóa backend khi chỉ đổi transport.

Lượt cấu hình 29/10 đã pair TLS, reverse qua Wi-Fi, kiểm đúng model và route card
Wi-Fi laptop; không còn transport USB. Chủ máy xác nhận health ok sau rút cáp,
app đã mở qua ADB Wi-Fi. Endpoint giữ cục bộ trong
`tmp/android-usb-tools/wifi-device.json`, không có mã pairing. Chưa từ đó suy ra
accuracy hoặc đã nghiệm thu toàn bộ luồng AI.

Giữ Wi-Fi và Wireless debugging trong buổi test. Khi đổi mạng/bật tắt debugging,
kiểm lại IP/cổng và nối lại. Kết thúc bằng `reverse --remove tcp:8421` trên đúng
endpoint; có thể tắt Wireless debugging hoặc Forget đúng laptop trong Paired
devices. Không revoke toàn bộ thiết bị khác.

## Quét CCCD tự động bằng QR, không OCR — APP-08

Workflow **Android QR test APK** tạo artifact `vericlue-android-qr-test`: APK
`vericlue-qr-debug-arm64-v8a.apk`, SHA256SUMS và build-info. Package riêng
**`vn.vericlue.app.qrtest`**, nhãn **VeriClue QR**, localhost:8421, ký media bật.
Cài song song; không gỡ app USB/Tailscale hoặc xóa Keystore để khắc phục khác chữ ký.

Luồng mới trong **API thật**, bắt đầu phiên mới:

1. Đưa mặt có ảnh chân dung vào camera. App hiện một gợi ý, tự quan sát QR và
   chân dung; không có nút chụp mặc định. Chỉ khóa kết quả từ ảnh tĩnh đã kiểm lại.
2. Nếu mặt trước đã đọc được QR thì tự gửi; nếu chưa có, app hướng dẫn lật mặt
   có QR. Không dùng ảnh QR mẫu trong lượt test thẻ thật.
3. Server dùng ZXing-C++/OpenCV đọc QR và SCRFD kiểm chân dung. Không đọc được
   QR thì chụp lại hoặc dừng, không fallback OCR/nhân viên. Timeout có chụp thủ công,
   nhưng ảnh vẫn phải đọc được QR. QR không xác minh thẻ do cơ quan nhà nước cấp.
4. Kiểm tra/xác nhận thông tin trước khi chuyển sang bước khuôn mặt. Các mô hình
   mặt, ngưỡng và chốt tạo tài khoản giữ nguyên; OTP tiếp tục mô phỏng.

### Runtime trên laptop này

- Bộ đọc mới: `tmp/identity-qr`, venv `tmp/identity-qr-runtime` Python 3.12,
  `127.0.0.1:8010`. Source là `qr_app`/`qr_scanner` trong worktree APP-08.
  Chỉ nạp SCRFD, không nạp Torch/VietOCR. `uv pip check` đạt cho 24 package.
- API: `tmp/remote-android-ai`, cổng 8421, dùng source APP-08. Giữ nguyên DB,
  khóa, mã hóa phiên/media, signed media và retention; thêm
  `IDENTITY_CARD_PORTRAIT_REQUIRED=true`. `IDENTITY_LAB_URL` vẫn trỏ 8010.
- Bộ đọc OCR cũ `tmp/identity-real` đã dừng. Không dùng helper khởi động OCR cũ
  cho luồng app. Trọng số/dữ liệu cũ được giữ, không đưa vào Git.
- Người dùng tạm ngưng test thiết bị ngày 29/10 để tiếp tục điều chỉnh app.
  API chưa khởi động lại vì RAM trống dưới 3 GiB; dịch vụ QR test cũng đã dừng.
  Khi test lại, đóng bớt ứng dụng, mở bộ đọc trước rồi API; không bỏ chốt bộ nhớ.

```powershell
& .venv/Scripts/python.exe tmp/identity-qr/start.py 8010
& .venv/Scripts/python.exe tmp/remote-android-ai/start.py
```

Kiểm `8010/health` có `mode=qr_only`, `ocr_enabled=false`, `portrait_loaded=true`,
rồi `8421/healthz`; nối lại ADB đúng thiết bị và reverse cổng 8421. Các helper
cục bộ không nằm trong Git. Không xóa DB/khóa hoặc chạy thêm instance khi cổng đang bận.

Native bridge và HTTP đã đọc QR tổng hợp, từ chối ảnh trắng/ảnh lỗi/thiếu chân dung;
không dùng thẻ thật cho các phép kiểm này. CI e19f481 có đủ 12 kiểm tra thành công,
gồm API/contract, Android build/unit/lint/snapshot và ba loại APK test.
Chưa nghiệm thu lấy nét, crop/xoay, lóa, thời gian đọc hoặc chuyển bước trên camera
thật. Chưa kết luận chất lượng quét hoặc độ chính xác eKYC từ kết quả CI.
