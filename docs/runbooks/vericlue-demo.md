# Chạy demo VeriClue: một app, một server

Theo yêu cầu ngày 29/10, demo dùng một app **VeriClue** (`vn.vericlue.app`) và
một tiến trình API tại cổng **8421**. QR/chân dung chạy trực tiếp trong API,
dùng chung session SCRFD theo thư mục model và thiết bị. Không mở 8010/8011,
không có server OCR hoặc API mock riêng trong cấu hình demo này.

## App

Chỉ workflow **Android VeriClue APK** xuất một artifact `vericlue-android`,
gồm **VeriClue.apk**, SHA256SUMS và build-info. Đã bỏ workflow/package riêng
USB, QR và remote. USB/Wi-Fi ADB hoặc Tailscale là cách kết nối tới cùng API,
không tạo thêm ứng dụng. Endpoint build chính lấy từ `VERICLUE_REMOTE_API_URL`
của repo, mặc định localhost:8421 nếu không cấu hình HTTPS riêng.

APK xuất bản phải dùng khóa ký demo ổn định, kiểm bằng
`apps/android/demo-signing-cert.sha256`. Khóa riêng/mật khẩu chỉ nằm trong thư
mục riêng của chủ máy; chuyển lên encrypted Actions secrets cần chấp thuận rõ.
Chưa cấu hình secrets thì CI chỉ build/test, không xuất APK có chữ ký ngẫu nhiên.
Hai secrets cần cho bước xuất APK là `VERICLUE_ANDROID_KEYSTORE_B64` và
`VERICLUE_ANDROID_KEYSTORE_PASSWORD`. Không in khóa/mật khẩu, đưa vào Git hoặc artifact.

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
