# Test Android qua USB — APP-06

Điện thoại Android 10+ nối laptop bằng cáp truyền dữ liệu, bật USB debugging và
chủ máy chấp nhận dấu vân tay RSA của laptop. Dùng ADB chính thức trong Android
Platform-Tools, không cần Android Studio hoặc mở ADB qua TCP/Wi-Fi.

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
Đăng ký → Đăng ký. Dùng OTP/QR mẫu, không CCCD thật. Cấp quyền camera/micro đúng
bước; không thu khi người test chưa biết. Bắt đầu phiên mới cho mỗi lần đổi kho
server. Bản USB dùng cùng flow và hợp đồng như app thường.

Đổi đường truyền không làm toàn hệ thống thành thật. Profile hiện bật AI mặt
từng phần (FS-VFM-L, GenD, mắt/đầu/màu), OTP/CCCD và một số module còn mô phỏng;
voice models tắt, chưa hiệu chỉnh hoặc tạo tài khoản thật. `review` không phải
pass hoặc chờ nhân viên trong product_mode ekyc. Chưa có accuracy từ test USB.

Kết thúc test, chỉ xóa mapping của đợt này:

```powershell
& $adb -d reverse --remove tcp:8421
```

Có thể tắt USB debugging/rút dây sau test. Không dùng `--remove-all`, `kill-server`
hoặc xóa dữ liệu app để tránh tác động tới công việc khác.
