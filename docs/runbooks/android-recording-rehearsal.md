# Chuẩn bị quay demo Android trên laptop hiện tại

Ngày 30/10/2026. Đây là kịch bản quay và checklist, không phải biên bản nghiệm thu
điện thoại. Máy chưa có thiết bị ADB kết nối khi kiểm tra.

## Tệp và server

- APK đã ký debug: `D:/vericlue/tmp/full-demo-setup/apk/VeriClue-demo-debug.apk`.
- Mã Android trong APK: `94be648`; backend hiện tại: `a1427ac`.
- SHA256 APK: `17100bd4a076a326e734c37f9cf58ac1920bd0aa12230edc1c4deaf45b2613ec`.
- Launcher: `D:/vericlue/tmp/full-demo-setup/VeriClue.cmd start|status|stop`.
- API chỉ bind localhost:8421. Không chia sẻ `.env`, khóa, DB hoặc log thô.

```powershell
& 'D:\vericlue\tmp\full-demo-setup\VeriClue.cmd' start
Invoke-RestMethod http://127.0.0.1:8421/healthz
$adb = 'D:\tools\android-sdk\platform-tools\adb.exe'
& $adb devices -l
# Thực hiện sau khi điện thoại hiện trạng thái device, không phải unauthorized:
& $adb reverse tcp:8421 tcp:8421
& $adb install -r 'D:\vericlue\tmp\full-demo-setup\apk\VeriClue-demo-debug.apk'
& $adb shell am start -n vn.vericlue.app/.MainActivity
```

Nếu nhiều máy, thêm `-s <serial>` ngay sau adb cho từng lệnh. Nếu khác chữ ký,
dừng để chọn phương án giữ dữ liệu/Keystore; không tự gỡ app hoặc xóa dữ liệu.
USB ổn định hơn Wi-Fi cho lần tập đầu. Không tái sử dụng mã ghép Wi-Fi cũ.

## Kịch bản quay đề xuất

### Đoạn 1: trải nghiệm giao diện mô phỏng

Hiện chú thích trong video: **“Mô phỏng giao diện — không phải kết quả AI”**.
Trong “Xem tất cả màn”, chọn “Giả lập trên máy”, luồng Đăng ký và kết quả mô
phỏng mong muốn. Quay lại màn đầu và chạy đường đi bình thường, không ghép
màn API lỗi sang màn pass giả lập mà thiếu chú thích chuyển chế độ.

Trình bày đồng ý, OTP mẫu, thẻ mẫu, hướng dẫn mặt, nhánh kết quả và màn hoàn
tất/tài khoản mẫu. Màn ngân hàng hiện tại là mô phỏng, chưa phải trang tài khoản
có chức năng đăng xuất/đăng nhập lưu bền. Không nói đã mở tài khoản thật.

### Đoạn 2: tích hợp API và AI thật

Hiện chú thích **“OTP mô phỏng; các mô-đun AI phiên bật thật; chưa nghiệm thu
độ chính xác toàn luồng”**. Mở “Xem tất cả màn” → “API thật”, quay lại đầu,
Đăng ký → đồng ý → OTP mô phỏng → CCCD/QR → xác nhận → quay mặt.
Chỉ thu giọng khi server yêu cầu. QR là đọc dữ liệu từ ảnh, không phải đọc chip
CCCD/NFC hoặc xác thực với cơ sở dữ liệu nhà nước.

Dùng dữ liệu của người đã đồng ý; che CCCD, QR, số điện thoại và thông tin cá
nhân trong video công khai. Không quay màn `.env`, bearer hoặc bảng điểm nội bộ.
Quay đúng kết quả server; `retry/review/degraded` chưa phải đạt. Nếu chưa đủ
artifact hiệu chỉnh thì trình bày được phần tích hợp, không kết luận AI đã
phê duyệt mở tài khoản. Guard không cho tạo account thật từ phiên mock/mixed.

## Tập thử trước buổi quay

- Quyền camera/micro, hướng camera, ánh sáng và ảnh CCCD/QR đọc được.
- Chụp lại, back, thoát/rút đồng ý, mất mạng và bắt đầu phiên mới hoạt động.
- Chế độ quay màn hình có ghi được âm thanh nếu phần thuyết minh cần; kiểm
  video thử ngắn trước. Tránh thông báo cá nhân bằng chế độ Không làm phiền.
- Không phát lại video đã thu dưới challenge mới để thử đạt; làm lượt mới.
- Chạy một lượt đầy đủ trước quay chính thức, ghi thời gian thực tế; chưa có
  số đo nên không hứa thời gian xử lý trên máy CPU này.

## Chưa đủ để tuyên bố demo thật toàn luồng đã hoàn tất

Phải bổ sung dữ liệu/artifact đúng protocol PAD/GenD và các protocol danh tính,
presence/giọng, quyền lưu mẫu SEC-09, giải quyết OTP/guard theo thiết kế riêng,
rồi nghiệm thu trên điện thoại. Xem `session-face-calibration.md` và thiết kế
`../superpowers/specs/2026-10-30-demo-recording-completion-design.md`.
