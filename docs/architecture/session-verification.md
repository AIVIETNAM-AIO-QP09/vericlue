# Các bộ kiểm tra trong phiên xác thực

## Chọn ảnh chính diện từ video — FLOW-05

`IDENTITY_LAB_URL` tiếp tục bật QR/OCR và so mặt thật. Thêm
`IDENTITY_FACE_FROM_VIDEO=true` để dùng `VideoFaceMatchDetector` thay selfie đầu tiên.
Chế độ này yêu cầu phiên dynamic có lịch server và video; không tự quay lại ảnh
tĩnh nếu video, timestamp, lịch hoặc tư thế sai.

Server đưa nguyên snapshot challenge từ DB và mã phiên/lượt vào detector.
Khung gần `frontal_capture_at_ms` nhất trong 100 ms được chọn theo timestamp decoder,
hòa thì lấy khung sớm hơn. Không dùng FPS, seek hoặc timestamp client để dựng lại
thời gian. Chỉ giữ một khung trong RAM; cùng giới hạn 64 MiB/30 giây/1800 khung/
1920×1080 và ngân sách decoder hiện hành. SHA-256 video được kiểm trước/sau chọn
và sau so mặt; đây là kiểm toàn vẹn tệp nội bộ, không phải chữ ký thiết bị.

MediaPipe kiểm đúng một mặt, |yaw| ≤ 8°, |pitch/roll| ≤ 15° trên chính pixel đã
chọn. Đây là hằng chất lượng thử nghiệm, chưa nghiệm thu quy ước góc trên điện thoại.
SCRFD/LVFace nhận đúng khung đó; ảnh `image` do app gửi không được dùng ở nhánh này.
Version thêm `+video-frontal-v1`; artifact cho ảnh tĩnh không được dùng lại. Thiếu
ngưỡng đúng version vẫn trả điểm nhưng `degraded/unclear`.

## Mắt và quay đầu — LIVE-02/FLOW-04

`SESSION_FACE_CHECKS=true` nạp và chạy thêm `gaze_tracking` và `head_turn` thật trong
orchestrator, kể cả khi những mô-đun khác đang mock. Hai detector và bộ chọn ảnh
video dùng chung một reader/task MediaPipe; đo theo lịch server, không tin signals
client để cấp đạt. Mắt/quay đầu được lưu thành hai ModuleResult riêng. Lỗi, thiếu,
degraded hoặc gate không pass chặn pass/voice_challenge thành review. Reauth giữ
quy trình thụ động, không bị yêu cầu mắt/quay đầu.

Reader nạp một lần, IMAGE mode không giữ tracking giữa phiên; khóa native tuần tự
hóa các lời gọi. Mỗi mô-đun còn giải mã cửa sổ riêng, chưa phải một lượt đọc video.
Cleanup đợi worker hiện hành kết thúc rồi đóng task, không chặn shutdown theo native.
Gate mắt/đầu chỉ nói chuyển động phù hợp quy tắc, không chứng minh sống hoặc chiều sâu.

## Cấu hình thử

`SESSION_FACE_MODELS=true` thay PAD bằng FS-VFM-L và GenD bằng nhánh ba góc từ
video, đồng thời đo ChromaPulse thật từ cùng video. Cả ba dùng task MediaPipe
chung với mắt/đầu. Sampling mới có version riêng, luôn raw/degraded/unclear;
không áp calibrator MiniFASNet/GenD cũ. Ánh sáng hiện chỉ là phép đo, chưa chứng
minh phát hiện tấn công. Bật chế độ này chưa thể tự đạt khi chưa hiệu chỉnh.

`IDENTITY_CONSISTENCY_REQUIRED=true` yêu cầu thêm ba cosine front–left,
front–right, left–right cùng vượt ngưỡng riêng. Cần `IDENTITY_FACE_FROM_VIDEO=true`
và `IDENTITY_CONSISTENCY_CALIBRATION` trỏ artifact có version của video matcher
+ `+view-consistency-v1`. Thiếu ngưỡng/ảnh hoặc có cặp không đạt thì cổng identity
không cấp đạt; tuyệt đối không dùng ngưỡng so CCCD thay thế. So CCCD vẫn chỉ dùng front.

```powershell
$env:IDENTITY_LAB_URL='http://127.0.0.1:8010'
$env:IDENTITY_FACE_FROM_VIDEO='true'
$env:SESSION_FACE_CHECKS='true'
$env:MODELS_DIR='<thư mục có SCRFD, LVFace và mediapipe-face-landmarker>'
# Chỉ đặt IDENTITY_FACE_CALIBRATION khi có artifact thật cho đúng video version.
```

Runtime API cần MediaPipe và chỉ một distribution cv2 tương thích. Không cài đè
opencv-headless lên runtime MediaPipe. Cấu hình mặc định vẫn tắt hai cờ mới.
Không sửa UI hoặc hợp đồng HTTP: upload video/challenge_id dùng endpoint đã có.
Dynamic real/mixed vẫn bị chặn cho đến khi đủ các lớp bắt buộc còn lại.

Môi trường CPU riêng, không sửa runtime CUDA/lab hiện có:

```powershell
uv venv tmp/session-api-runtime --python .venv/Scripts/python.exe
uv pip install --python tmp/session-api-runtime/Scripts/python.exe --torch-backend cpu -r ml/requirements/session-api-cpu.txt -e ./ml -e ./services/api
```
