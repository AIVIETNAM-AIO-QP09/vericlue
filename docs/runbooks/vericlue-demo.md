# Chạy demo VeriClue: một app, một server

Theo yêu cầu ngày 29/10, demo dùng một app **VeriClue** (`vn.vericlue.app`) và
một tiến trình API tại cổng **8421**. QR/chân dung chạy trực tiếp trong API,
dùng chung session SCRFD theo thư mục model và thiết bị. Không mở 8010/8011,
không có server OCR hoặc API mock riêng trong cấu hình demo này.

## App

Chỉ workflow **Android VeriClue APK** xuất artifact `vericlue-android` chứa bản
chưa ký, metadata/checksum và công cụ apksigner của Android SDK kèm NOTICE.
Package duy nhất `vn.vericlue.app`, nhãn VeriClue. USB/Wi-Fi ADB và Tailscale
là kết nối tới cùng API, không phải các bản ứng dụng khác nhau. Endpoint build
lấy từ `VERICLUE_REMOTE_API_URL`, mặc định localhost:8421 nếu chưa cấu hình.

**Khóa ký giữ trên laptop.** CI không nhận keystore hoặc mật khẩu, không cần
signing secrets. Bản chưa ký chỉ là đầu vào build, chưa cài lên điện thoại.
`scripts/sign_android.py` kiểm đủ checksum, commit/package/cấu hình trước khi
ký bằng khóa hiện có; sau đó kiểm chữ ký APK v2 và fingerprint công khai tại
`apps/android/demo-signing-cert.sha256`. Không tạo khóa thay thế nếu thiếu khóa.
Mật khẩu đọc từ file riêng, không truyền giá trị qua command line hoặc log.

Sau khi đối chiếu run/commit trên GitHub, tải artifact rồi ký cục bộ:

```powershell
.\.venv\Scripts\python.exe scripts/sign_android.py --build-dir <artifact-directory> --expected-source <full-head-sha> --java <java.exe> --store-dir <private-signer-directory> --output-dir tmp/vericlue-app
```

File cài duy nhất là **tmp/vericlue-app/VeriClue.apk**, kèm SHA256SUMS và
build-info chứa commit nguồn, fingerprint và trạng thái nghiệm thu. Các lần
cập nhật tiếp theo dùng cùng khóa. JRE portable chỉ là công cụ ký, không phải
server hoặc app mới. Laptop này giữ khóa tại `tmp/vericlue-signing` với ACL riêng;
JRE tại `tmp/vericlue-java`, nguồn [Temurin](https://adoptium.net/installation/ci-scripts).

Khi test lại: đối chiếu hash/source/signer rồi cài **một package duy nhất**.
Các bản test cũ đã cài trên điện thoại chưa được gỡ vì người dùng tạm ngưng
test, ADB mất kết nối. Lần chuyển đầu có thể khác chữ ký; không tự xóa dữ liệu
hoặc Keystore. Giữ receipt/khóa cần thiết trước khi chốt cách chuyển bản cài.

## Server trên laptop hiện tại

Một thư mục runtime: `D:/Projects/Data4Life/tmp/vericlue-server`.
Giữ nguyên DB `face.db`, kho `face-media`, khóa và giới hạn hiện có. Cấu hình
`.env` bật `IDENTITY_CARD_ENABLED=true`, `IDENTITY_CARD_PORTRAIT_REQUIRED=true`,
bỏ `IDENTITY_LAB_URL` và timeout gọi bridge. Môi trường Python hiện có là
`tmp/session-api-runtime`; đã thêm ZXing-C++, không cần venv QR riêng.

Từ gốc workspace, dùng **một lệnh** để mở server:

```powershell
.\tmp\vericlue-server\VeriClue.cmd
# Dừng hoặc xem trạng thái:
.\tmp\vericlue-server\VeriClue.cmd stop
.\tmp\vericlue-server\VeriClue.cmd status
```

Helper trỏ tới `scripts/server.py` của source APP-08 hiện tại. Sau khi source
đã nằm trong checkout chính có thể dùng `scripts/server.cmd`. Python helper
cho phép chỉ định `--runtime-dir` trên máy khác; phải chuẩn bị cấu hình/model
trước, không tự tạo lại khóa hoặc DB khi thiếu. Chỉ bind 127.0.0.1, một worker,
không access log, model chạy offline. Có khóa chống bấm mở trùng trong lúc nạp
model và kiểm PID trước khi dừng. Giữ chốt 3 GiB RAM cho các model mặt Large.

Kiểm một endpoint `http://127.0.0.1:8421/healthz`. App truy cập HTTPS Tailscale
đã cấu hình, hoặc ADB reverse cổng 8421 nếu app dùng localhost. Tailscale/ADB
chỉ chuyển tiếp kết nối, không phải server xử lý eKYC mới.

Các runtime cũ đã chuyển vào `tmp/vericlue-server/archive` và launcher đổi
đuôi `.retired`. Không dùng chúng để mở server. Lưu dữ liệu/khóa lịch sử để
tránh mất khả năng giải mã; các venv cũ là cache không được dùng cho demo.

## Luồng quét và giới hạn kiểm chứng

App quan sát QR/chân dung, tự chụp tĩnh rõ, kiểm lại ảnh rồi tự gửi. Mặt sau
chỉ cần khi mặt trước chưa đọc được QR. Server đọc QR trong ảnh; thiếu QR hoặc
chân dung yêu cầu chụp lại. Không lấy trường OCR hoặc chuỗi QR client thay thế.
Timeout có chụp thủ công/dừng; ảnh thủ công vẫn phải đọc được QR. Xác nhận
thông tin trước quay mặt. SCRFD tìm/căn chân dung; LVFace so với khung chính
diện server chọn, không đem hai góc nghiêng so trực tiếp với CCCD.

OTP còn mô phỏng. Không đổi ngưỡng, chốt real/mixed, voice, consent hoặc tạo
tài khoản trong thay đổi gom server. QR/chân dung không chứng minh thẻ thật,
chip/NFC hoặc dữ liệu nhà nước. Toàn bộ regression API, test engine/khởi động
và native QR bằng ảnh tổng hợp đã đạt; chưa nghiệm thu camera thật. Người dùng
tạm ngưng test thiết bị; server hiện dừng.
