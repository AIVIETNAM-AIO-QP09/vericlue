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

## Đọc CCCD từ ảnh thật, OTP vẫn mô phỏng

Theo yêu cầu chủ máy ngày 29/10, runtime cục bộ đã bật đường tích hợp có sẵn;
không đổi APK hoặc hợp đồng API. Bắt đầu phiên mới trong **API thật**. Chụp rõ
hai mặt thẻ của người đồng ý tham gia test; **không bấm “Dùng mã QR mẫu (debug)”**
vì nút này thay ảnh gửi lên bằng ảnh QR tổng hợp. Kiểm tra thông tin trả về trước
khi tiếp tục bước khuôn mặt. Không gửi ảnh/thông tin thẻ lên chat hoặc GitHub.

- Bộ đọc riêng ở `tmp/identity-real`, interpreter `tmp/identity-ocr-runtime`, chỉ
  nghe `127.0.0.1:8010`. Dùng `CardScanner` hiện có: OpenCV đọc QR từ pixel, nếu
  không có QR hợp lệ thì detector trường CCCD của nhóm + VietOCR vgg_seq2seq đọc
  ảnh. Ảnh gửi vào bộ đọc nằm trong RAM, không ghi ảnh/nội dung OCR vào log.
- Gói detector lấy từ link trong `tools/identity_lab/HANDOFF.md`; hash ZIP và
  `best.pt` đã khớp bản bàn giao. VietOCR dùng trọng số cục bộ. Không gửi thẻ ra
  dịch vụ OCR bên ngoài. Không commit trọng số, môi trường hoặc dữ liệu test.
- API vẫn ở `tmp/remote-android-ai`, khóa/kho giữ nguyên. Chỉ đổi
  `IDENTITY_LAB_URL=http://127.0.0.1:8010`, `IDENTITY_LAB_TIMEOUT_SECONDS=45` và
  `IDENTITY_FACE_FROM_VIDEO=true`. Bridge bỏ qua QR client tự khai, đọc từ ảnh.
  LVFace-B + SCRFD so ảnh trên thẻ với khung hình chính diện do server chọn từ
  video; không đem từng góc nghiêng so trực tiếp với ảnh thẻ.
- Giữ mã hóa phiên/media và yêu cầu ký media; TTL media đang là một giờ cho cả
  phiên đạt và chưa đạt. OTP tiếp tục mô phỏng; quality/CamProbe còn mock, voice
  chưa bật. Chưa có calibration chấp nhận danh tính, chưa bật tạo tài khoản hoặc
  đồng ý lưu mẫu qua API. Lượt này kiểm tra xử lý dữ liệu thật trong nội bộ,
  chưa phải cấu hình triển khai chính thức.

VietOCR 0.3.13 được cài `--no-deps` cùng tập dependency suy luận đã kiểm tra
native, giữ Pillow 12.3.0; metadata upstream còn pin dependency cũ và yêu cầu
training extras. Đây là môi trường suy luận riêng có giới hạn, không tuyên bố
đạt `pip check` hoặc hỗ trợ mọi chức năng training của VietOCR.

Sau khi khởi động lại laptop, mở bộ đọc trước rồi mở API, kiểm cả hai health:

```powershell
& .venv/Scripts/python.exe tmp/identity-real/start.py
& .venv/Scripts/python.exe tmp/remote-android-ai/start.py
```

Các helper trên là cấu hình cục bộ ngoài Git. Nếu cổng đang hoạt động, kiểm tra
thay vì chạy thêm instance. Chỉ dừng đúng PID đã xác minh thuộc runtime này;
không xóa DB/khóa để khắc phục lỗi. Kiểm lại ADB reverse sau khi đổi kết nối.

Kiểm tra đã chạy: detector/VietOCR suy luận native trên ảnh tổng hợp, QR đọc
từ ảnh, ảnh trắng không sinh trường. Qua HTTP API: ảnh trắng kèm QR client hợp
lệ vẫn `retry`; ảnh có QR tổng hợp trả trường từ QR trong ảnh; video không có
mặt kết thúc `review`. Payload phiên/kết quả trong DB có mã hóa, phiên ghi nhận
version LVFace thật. Chưa dùng thẻ thật để đo accuracy hoặc xác nhận toàn luồng
trên camera điện thoại. Đọc đúng thông tin không chứng minh thẻ do cơ quan nhà
nước cấp; chưa có đối chiếu cơ sở dữ liệu nhà nước hoặc kiểm chứng chip/NFC.
