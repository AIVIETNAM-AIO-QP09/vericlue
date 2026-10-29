# VeriClue iOS

SwiftUI, iOS 16+, Xcode. Font Be Vietnam Pro đóng gói sẵn. Bản phụ cho demo,
không tuyên bố ứng dụng định danh thương mại hoặc tài khoản ngân hàng thật.

## Cài và chạy Debug

1. Mở `apps/ios/VeriClue.xcodeproj`, chọn scheme **VeriClue**.
2. Chọn simulator có trên máy hoặc iPhone qua cáp. Với iPhone: Trust, Developer
   Mode, chọn Apple ID/team trong Signing & Capabilities; không commit signing cá nhân.
3. Khởi động backend đã được nhóm thống nhất. Từ gốc repo, ví dụ backend mock
   trên nhánh này (không cấp receipt tài khoản thật):

   ```bash
   uv sync --frozen --all-packages
   mkdir -p tmp/media
   export DATABASE_URL="sqlite:///$PWD/tmp/dev.db"
   export MEDIA_DIR="$PWD/tmp/media"
   export USE_MOCK_MODELS=true
   uv run --frozen alembic -c services/api/alembic.ini upgrade head
   uv run --frozen uvicorn vericlue_api.main:app --app-dir services/api/src --host 0.0.0.0 --port 8000
   ```

   Nếu đang dùng backend riêng ở 8001 thì giữ backend đó và dùng đúng cổng;
   không chạy hai server trùng cổng. SQLite không cần Docker/PostgreSQL.
4. Mac và iPhone cùng Wi-Fi; `ipconfig getifaddr en0` lấy IP Mac. Đổi
   `Config/Debug.xcconfig`, ví dụ `API_BASE_URL = http:/$()/192.168.1.5:8000/`.
   `$()` tránh xcconfig coi `//` là comment. Không đổi thành IP của iPhone.
5. Run. Debug mặc định demo offline; để gọi server: **Xem tất cả màn → API thật**,
   chọn scenario, quay về luồng đăng ký. Gallery nhảy thẳng màn không thay nghiệm thu
   end-to-end. Camera/giọng phải kiểm trên iPhone, không dùng Simulator thay thế.

## Release chỉ HTTPS — IOS-07

1. Xin domain HTTPS được nhóm duyệt và trỏ tới đúng backend. Không tự đưa API
   chứa dữ liệu sinh trắc ra Internet. Tunnel demo cần phối hợp giới hạn truy cập,
   dữ liệu thử và chính sách lưu trữ với người vận hành backend.
2. Copy `Config/Release.local.xcconfig.example` thành
   `Config/Release.local.xcconfig` (Git ignore), thay placeholder bằng domain thật:

   ```ini
   API_BASE_URL = https:/$()/your-approved-host/
   ```

   Không nhúng token, mật khẩu, query hay fragment vào URL. Không bỏ xác minh TLS.
3. Xcode chọn **VeriClue-Release → iPhone → Run**. Scheme này dùng Release và
   không attach LLDB (probe debugger Release phải được đo không có debugger).
   Giữ scheme VeriClue cho Debug/test; Archive của cả hai scheme dùng Release.
4. Build Release dừng nếu URL trống/HTTP/placeholder/sai định dạng. Release dùng
   `Config/Release-Info.plist` không có ATS exception/local-network description;
   Debug vẫn dùng `VeriClue/Info.plist`. Khi đổi permission/font phải cập nhật cả hai.
5. Release mặc định API thật, không Gallery/mock selector và không gửi header
   `X-Mock-Scenario`. Backend mock không có override sẽ dùng genuine. Muốn thử
   low_quality/voice_clone: dùng Debug qua HTTPS, hoặc nhờ backend bố trí môi trường
   thử riêng được duyệt; không thêm công tắc debug vào Release để tick checklist.

Lệnh từ gốc repo (thay domain; build không ký không cài được lên iPhone):

```bash
xcodebuild -project apps/ios/VeriClue.xcodeproj -scheme VeriClue-Release \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios-release CODE_SIGNING_ALLOWED=NO \
  API_BASE_URL=https://your-approved-host/ build
.venv/bin/python scripts/check_ios_release.py \
  --app /tmp/vericlue-ios-release/Build/Products/Release-iphoneos/VeriClue.app
```

URL hợp lệ và build/artifact đạt **không** chứng minh DNS/TLS/API hoạt động.
Số đo và các ca iPhone: [checklist IOS-07](docs/ios07-release-device-checklist.md).
Personal Team/provisioning phải còn hợp lệ trên ngày demo; kiểm mở app trước buổi trình bày.

## Test (chỉ chạy khi được yêu cầu)

Liệt kê simulator: `xcrun simctl list devices available`. Thay ID rồi chạy:

```bash
xcodebuild -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=<SIMULATOR-UUID>' \
  -parallel-testing-enabled NO test
```

Unit API dùng MockURLProtocol; không gọi mạng thật. `build-for-testing` chỉ compile,
không phải test xanh. Kết quả 159/159 trước IOS-07 không chứng minh code mới đã xanh.

## Giới hạn và an toàn

- Onboarding: confirm CCCD **sau quay, trước media/signals/finalize**. Chỉ pass
  thành công; voice_challenge mới đọc câu. Retry dùng challenge/ack server.
- Recovery bỏ CCCD theo quyết định iOS, khác Android tham chiếu; không tự sửa
  để giả định tài khoản đã khôi phục thật.
- Receipt, key binding/device proof/media signing đã nối opt-in theo Android,
  **SIGNED_MEDIA=NO mặc định**; đã kiểm ký mặt/giọng và khóa thử trên iPhone,
  binding tài khoản thật vẫn chưa nghiệm thu.
  [Cách bật và giới hạn](docs/account-binding.md). GET 200 cấp receipt thật chưa
  kiểm chứng; receipt không thay device proof. Backend mới có thể đòi proof: phải kiểm
  phiên bản/cấu hình tương thích, không tắt kiểm tra server chỉ để demo thành công.
- Không commit ảnh thẻ/mặt, audio/video, DB, token, receipt hoặc khóa ký.
  Artifact/số đo cá nhân ở `tmp/` hoặc ngoài repo; bàn giao chỉ ghi metadata cần thiết.
- Xem [API](docs/api-client.md), [đồng bộ Android](docs/android-alignment.md),
  [receipt](docs/account-receipt.md), [kế hoạch](docs/plan-ios.md).
- Sếp đã mở rộng yêu cầu sang toàn app: xem [tiến độ parity](docs/android-full-parity.md).
  Auth/LiveFlow/binding đã được nối, các giới hạn tài khoản ở trên vẫn áp dụng.
  Không gọi là đã tương đương toàn bộ trước test và nghiệm thu.

## OTP hệ thống và rung

OTP vẫn có sáu ô và keypad trong app. Nút **Dùng mã SMS hoặc bàn phím hệ thống**
mở ô nhập native với `oneTimeCode`; iOS có thể đề xuất mã từ SMS phù hợp. Xong chỉ
đóng ô nhập, không xác nhận; không đọc hộp thư hay xin quyền SMS. SMS mô phỏng từ
API không phải SMS thật. Backend demo chưa chứng minh gửi qua nhà cung cấp SMS.
Giữ ASCII/tối đa sáu số, deadline 45 giây và ngân sách sai từ server.

Rung hệ thống nhẹ khi có ảnh CCCD đã chụp và khi mở màn thành công; không rung
trong lịch nháy/chấm/quay mặt/ghi giọng, không dùng waveform/timer riêng.
Nhập native/rung đã được sếp thử trên iPhone; gợi ý SMS thật còn pending.
Tham khảo [Apple AutoFill](https://developer.apple.com/documentation/security/enabling-password-autofill-on-a-text-input-view).
