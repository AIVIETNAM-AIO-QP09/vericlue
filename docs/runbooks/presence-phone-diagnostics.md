# Đối chiếu góc Android và video server

Đây là công cụ chẩn đoán opt-in, không phải bằng chứng pass hoặc hiệu chỉnh.
Không cần thay OTP mô phỏng, ký media hay các chốt tài khoản. Phiên bản mắt
hiện vẫn gaze-rules@0.3+face-landmarker-f16-1. Không thay model hoặc ngưỡng
vì một người thử chưa đạt.

## Bật cho một đợt kiểm tra

Từ apps/android, JAVA_HOME=D:/tools/jdk17:

```powershell
./gradlew testDebugUnitTest assembleDebug '-Pvericlue.presenceTrace=true'
```

Bản thường và release tắt trace mặc định. APK arm64 tại
app/build/outputs/apk/debug/app-arm64-v8a-debug.apk. Giữ signer và cài -r,
không uninstall/clear. Phải cài xong rồi mới bắt đầu lượt mới. Chạy đúng một
lượt và để nguyên màn kết quả; đừng bắt người thử lặp nhiều lần khi chưa đọc
bằng chứng của lượt trước.

CameraSession sở hữu một PresenceDebugTrace dùng chung qua App và timeline.
Trace ghi pose và thời điểm nhận/chụp, phase của frame, trạng thái hướng dẫn,
vị trí chấm khi draw. Không ghi video/ảnh, CCCD, token, khóa hoặc embedding.
Digest SHA256 của challenge_id chỉ để nối đúng attempt local; không vào API
Signals hoặc làm bằng chứng xác minh.

## Lấy và đối chiếu

File private: cache/presence-debug.json của vn.vericlue.app. Lấy ngay sau
lượt thử, trước khi thoát/quay lại hoặc bắt đầu lượt mới. Dữ liệu được giữ
qua ACK media để còn chẩn đoán, nhưng xóa khi bỏ lượt/rút đồng ý và có timer
prune 15 phút khi process còn chạy; khởi tạo lại cũng prune file hết hạn.
Trace runtime chỉ lưu ở thư mục tmp ignored, không đưa raw số đo vào chat/PR.

Lệnh ADB được phép cho file số đã biết, chọn serial từ `adb devices -l`:

```powershell
$adb = 'D:\tools\android-sdk\platform-tools\adb.exe'
# Thay SERIAL bằng thiết bị thực tế. Không dùng lại mã pairing cũ.
& $adb -s SERIAL shell run-as vn.vericlue.app cat cache/presence-debug.json
```

Khi tự động lấy file, chuyển stdout thẳng vào file local private bằng UTF-8,
chỉ báo nhận được/chưa có. Đừng in toàn trace ra hội thoại. Nếu công cụ từ
chối thao tác thì báo đúng việc chưa kiểm, không tìm cách lách.

Sau khi đã có file, từ repo:

```powershell
$py = 'D:\vericlue\tmp\session-api-runtime\Scripts\python.exe'
& $py scripts/compare_presence_trace.py --trace '<private-tmp>\phone-trace.json' `
  --server-dir 'D:\vericlue\tmp\full-demo-setup\server' `
  --output '<private-tmp>\paired-report.json'
```

CLI đọc cấu hình hiện có, không in/copy .env. Chỉ chọn đúng attempt có digest
khớp; không fallback sang lượt gần nhất. Phiên hết hạn/đã xóa bị từ chối trước
giải mã. Video dùng lease tạm và luôn release, không xuất media. Reader nạp
đúng settings.models_dir. Báo cáo chỉ có tổng hợp và provenance commit/version/
hash trace; ghi source_dirty đúng thực tế.

## Diễn giải

- pose_pairs và max_pose_pair_offset_ms cho biết có đủ cặp đúng thời điểm
  hay chưa. Delta góc chưa chứng minh provider nào đúng hoặc hệ số cần sửa.
- So frame_ms với PTS; at_ms là thời điểm nhận/render, không thay thế frame_ms.
- Đếm cả Hold lẫn Completed vì cả hai hiện xanh; màu xanh không là API pass.
- Chấm so ở thời điểm draw với lịch tuyến tính server, không tối ưu lag để
  che lệch render. Correlation mắt vẫn là phép thử khác, hai trục đều bắt buộc.
- Không có trace thì ghi thiếu, không dựng lại góc ML Kit từ MediaPipe.
- Tách kết luận prefix mắt/quay đầu với toàn eKYC. Calibrator video v2 và các
  artifact danh tính thiếu vẫn chặn toàn luồng dù prefix pass.

## Lượt 23:25 ngày 30/10/2026

Mắt ok/pass; đầu 125/125 pose hợp lệ, không mất mặt, max abs yaw 47,0°,
pitch 11,7°, roll 16,2°. Tám mẫu roll vượt 15° trong head+6356..7055ms;
head_turn trả pose_out_of_range. Số liệu chỉ chẩn đoán một lượt, không là
accuracy hoặc bằng chứng chống tấn công.

Bản chẩn đoán đầu còn lỗi cleanup: callback media ACK dùng method reference
camera::deleteVideo, đã xóa file trace trước khi lấy. Không phục hồi được
trace đó; chưa có cặp góc app–server. Đã tách cleanup ACK khỏi drop và có
regression test mediaAcknowledgmentPreservesTheDiagnosticUntilDropOrExpiry.
Đừng ghi đã hoàn tất đối chiếu hay yêu cầu thêm lượt thử khi người dùng mệt.
