# Hiện diện và chuyển động mắt

## LIVE-02 — trạng thái

`GazeDetector` đã có backend MediaPipe thật và mock; trả `ModuleResult` với tên
`gaze_tracking`. **Chưa nằm trong profile full/MVP và chưa tham gia quyết định
xác minh.** Luồng purpose mới vẫn giữ chốt 503 ở real/mixed của FLOW-01/LIVE-01.

MediaPipe cung cấp landmark mống mắt/mặt và ma trận tư thế ước lượng. Nó không
tự trả tọa độ điểm người dùng đang nhìn, danh tính hoặc bằng chứng chiều sâu vật
lý. Mô-đun này so **chuyển động tương đối của mống mắt** với đường chấm bằng luật
thử nghiệm; chưa được hiệu chỉnh hay đo APCER/BPCER trên người thật.

Nguồn API/model: [Face Landmarker Python](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).
Giới hạn của iris tracking: [tài liệu chính thức](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/iris.md).
Topology chỉ số mắt: `google-ai-edge/mediapipe`, tag `v0.10.21`,
`mediapipe/python/solutions/face_mesh_connections.py`. Không chép triển khai nguồn ngoài.

## Đầu vào và thuật toán

- Đầu vào video giai đoạn B và `metadata.expected_challenge` **do server cấp**,
  `metadata.challenge_id`, `session_id`. Không đọc số đo mắt trong `signals` client.
- `FaceObservationReader` dùng cùng một task CPU IMAGE-mode, có khóa tuần tự;
  không có trạng thái tracking hoặc timestamp SDK nối từ phiên trước sang phiên sau.
- Phát hiện tối đa hai khuôn mặt để không âm thầm lấy người đầu tiên khi có nhiều
  người. Lấy vòng mống mắt tương đối với khóe mắt/mí mắt; loại mắt quá nhỏ/nhắm.
- Quy ước hiện tại: video camera trước **chưa lật gương**, tư thế thẳng. Bản preview
  có thể soi gương nhưng file gửi server không được lật. Dấu x chuyển về phía người
  dùng nhìn trên màn hình; y tăng xuống dưới. Phải kiểm quy ước này trên từng thiết bị.
- Đọc timestamp từ decoder, không dựng thời gian từ FPS khai báo. Lấy mẫu khoảng
  10 Hz, dùng nội suy tuyến tính đường chấm theo mốc trong gói. Video thiếu/không
  tăng timestamp không được tự sửa để khớp thử thách.
- Cần đủ thời lượng, độ phủ, số mẫu và độ liên tục. Nhiều mặt, mất mặt, nhắm mắt
  lâu, góc đầu không phù hợp hoặc chuyển động đầu lớn không được thành pass.
- So tương quan **cả hai trục**, xét độ trễ dương trong khoảng giới hạn trên cùng
  một cửa sổ dữ liệu. Loại mắt đứng yên và biên độ quá nhỏ. Không tự thử cả hai
  dấu/lật gương rồi chọn kết quả đẹp nhất.
- Hằng số trong `gaze.py` đều **provisional**; không sửa thresholds.yaml và không
  coi tương quan là xác suất tấn công. `prob_attack` để trống; chỉ có gate và số đo
  nội bộ. API người dân không được nhận các số đo này.

FLOW-04 đã dùng yaw/pitch/roll từ reader cho `HeadTurnDetector` để kiểm thứ tự
và thời gian thử thách. Đây là góc từ ma trận ước lượng, **chưa kiểm mặt
phẳng/chiều sâu**. Chưa bật quyết định API. Lệnh diagnostic và giới hạn ở
[`head-and-match.md`](../../../../docs/architecture/head-and-match.md).
Video tối đa 30 giây, 1800 khung, 1920×1080; ngân sách đọc 15 giây được kiểm giữa
các khung. Không coi đây là khả năng ngắt một lời gọi native đang treo. Khi đưa
vào orchestrator cần đo lại ngân sách 4 giây hiện có và chính sách quá tải.

## Chạy thử riêng, không thay môi trường CUDA

MediaPipe PyPI kéo `opencv-contrib-python`, trong khi môi trường API hiện dùng
OpenCV headless/GPU extras. Chưa thay các dependency đó. Dùng môi trường riêng
cho diagnostic ở gốc repo (PowerShell):

```powershell
uv venv tmp/liveness-runtime --python .venv/Scripts/python.exe
uv pip install --python tmp/liveness-runtime/Scripts/python.exe -e ./ml mediapipe==1.1.1 "opencv-contrib-python>=4.10,<5" "numpy<3" "pillow<13"
tmp/liveness-runtime/Scripts/python.exe -m vericlue_ml.eval.gaze_video --video tmp/capture.mp4 --server-response tmp/session-response.json --models-dir models/selected-2026-10-24 --output tmp/gaze-diagnostic.json
```

Smoke với trọng số thật, tự sinh video không có mặt (không phải đo độ chính xác):

```powershell
uv pip install --python tmp/liveness-runtime/Scripts/python.exe pytest
$env:GAZE_MODELS_DIR = "D:/Projects/Data4Life/models/selected-2026-10-24"
tmp/liveness-runtime/Scripts/python.exe -m pytest ml/tests/test_gaze_real_smoke.py -m slow
```

`--models-dir` là ví dụ nơi đã tải, có thể đổi. Reader tìm đường dẫn tương đối và
SHA-256 trong `ml/configs/models.yaml`; bản wheel cần `ML_MODELS_CONFIG` tới file
này. Không tự tải model khi suy luận, không ghi lại trọng số hoặc đổi độ chính xác.
Ảnh/video/thử thách có thể chứa dữ liệu cá nhân: chỉ để trong thư mục ignored.

Báo cáo diagnostic có commit/dirty, phiên bản, hash model/video, số clip và kết quả;
không xuất landmark/ảnh mặt ra báo cáo mặc định. Đây không phải tập test đánh giá
độ chính xác. Chỉ chọn ngưỡng từ tập calib theo người, không dùng tập test.

## Còn phải làm trước khi bật thật

FLOW-04/FLOW-05 đã có `video_identity.match_video_views`: head_turn → chọn ba
khung bằng timestamp decoder → kiểm lại tư thế → so mặt trong RAM. Dùng lại
task MediaPipe; không nạp LVFace nếu bước trước chưa đạt. Đây vẫn là diagnostic
độc lập. Lệnh `eval.video_face_match`, giới hạn và giả định ở
[`head-and-match.md`](../../../../docs/architecture/head-and-match.md).

Tùy chọn `--with-gend` chấm deepfake trên đúng ba khung này, không đọc/lấy mẫu
video lần nữa. Kết quả độc lập với so danh tính, dùng version lấy mẫu riêng và
chưa hiệu chỉnh; runtime cần có extra gend. Mặc định chưa bật tùy chọn này.

Đo trên điện thoại thật, ánh sáng/thiết bị/kính/tư thế khác nhau; kiểm dấu hai trục,
đồng bộ mốc video, độ phủ và lỗi. Hiệu chỉnh trên calib, thử video phát lại/đường
khác, kiểm head-turn/so mặt/chữ ký. Chọn cấu hình dependency dùng chung và nối
orchestrator/router có kiểm fail-closed cho từng lớp. Chưa bỏ chốt real/mixed.
