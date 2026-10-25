# Chạy chung các bộ kiểm tra khuôn mặt

## Phạm vi

Runtime CPU riêng cho MediaPipe (mắt/quay đầu), SCRFD, LVFace-B, GenD và
FS-VFM-L FAS. Không dùng môi trường này để khởi động API sản phẩm. Không đổi
`.venv` CUDA, router/full/MVP, calibrator hoặc ngưỡng hiện hành.

Có hai phép kiểm khác nhau:

- `eval.face_runtime`: nạp mọi backend và chạy suy luận trên tensor màu đồng
  nhất, giữ các model cùng tồn tại trong một tiến trình. Không cần người tham
  gia; `sample_count=0`. Chỉ kiểm khả năng nạp/chạy, không đo chống giả mạo.
- `eval.video_face_match --with-gaze --with-gend --with-pad`: chạy từ video và
  lịch thử thách server; dò mắt/quay đầu trước, rồi chọn ba khung trong RAM cho
  các model. Phải dùng clip nội bộ có sự đồng ý khi đánh giá với người thật.

## Cài môi trường riêng

PowerShell, chạy tại gốc repo, Python 3.12 và uv đã cài:

```powershell
# Chỉ tạo một lần. Không trỏ lệnh này vào .venv CUDA đang dùng.
uv venv tmp/face-diagnostic-runtime --python .venv/Scripts/python.exe
uv pip install --python tmp/face-diagnostic-runtime/Scripts/python.exe --torch-backend cpu -r ml/requirements/face-diagnostic-cpu.txt -e ./ml
```

Lần sau chỉ chạy lệnh `uv pip install` để kiểm/cài lại phiên bản. Profile pin
dependency trực tiếp; chưa phải lockfile mọi dependency bắc cầu. uv dùng nguồn
CPU PyTorch cho torch; không thêm index lẫn lộn cho mọi package.

Không cài `--extra face` hoặc `--extra cuda` vào runtime này: MediaPipe đã kéo
**opencv-contrib-python**; chỉ giữ một distribution cung cấp `cv2`, không cài
kèm opencv-python-headless. API/CI hiện hành vẫn dùng dependency cũ. Có thể
xem phiên bản thực trong báo cáo, hoặc lưu `uv pip freeze --python ...` vào tmp.
Các lệnh ở đây dành cho Windows; môi trường Linux chưa được nghiệm thu bằng
checkpoint trong phiên làm việc này.

Tải các checkpoint bằng script pinned hiện có vào một MODELS_DIR riêng; không
tải trong lúc suy luận. CLI dùng `--models-dir`, không giả định thư mục ví dụ.

## Kiểm runtime và checkpoint

```powershell
tmp/face-diagnostic-runtime/Scripts/python.exe -m vericlue_ml.eval.face_runtime --models-dir models/selected-2026-10-24 --output tmp/face-runtime-report.json
```

Mỗi backend được kiểm riêng trong cùng tiến trình. Một backend lỗi không xóa
kết quả đã có của backend khác. CLI trả 1 nếu có lỗi, 0 khi cả bốn backend
chạy được. Không coi mã 0 là xác minh đạt. Không có ảnh, vector nhận dạng hoặc
điểm phân loại từ tensor tổng hợp trong báo cáo; chỉ có phiên bản, hash, kiểm
đầu ra hữu hạn, provider/device và thời gian chẩn đoán từng bước. Không xuất
đường dẫn lỗi nội bộ. Không cho ghi output vào thư mục model.

`diagnostic_elapsed_ms` gồm nạp thư viện/model và lần suy luận đầu tiên, có
thể chịu ảnh hưởng cache/ổ đĩa. Không dùng làm latency eKYC hay benchmark.
Trọng số/hình ảnh/tensor mẫu không được commit. Chưa có phép đo VRAM của toàn
bộ mô hình giọng + mặt trong profile sản phẩm từ kiểm CPU này.

## Chạy video với đủ phần mắt và mặt

```powershell
tmp/face-diagnostic-runtime/Scripts/python.exe -m vericlue_ml.eval.video_face_match --video <clip.mp4> --reference <portrait.png> --server-response <session-response.json> --models-dir <models-root> --device cpu --with-gaze --with-gend --with-pad --output tmp/face-video-report.json
```

`--with-gaze` là opt-in để giữ tương thích CLI trước. Cả gaze và head phải
`status=ok` và `gate=pass` mới chọn/chấm ảnh; `degraded` không được coi là đạt.
Cả hai dùng cùng reader/task MediaPipe IMAGE-mode nhưng **hai lượt giải mã**
theo cửa sổ riêng; thêm một lượt chọn khung nếu các gate đạt. Không phải một
lượt đọc video, chưa đo hiệu năng cả phiên. Hash nguồn được kiểm sau đo chuyển
động và sau lấy khung; nguồn thay đổi/không đọc lại được thì không giữ gate đạt.
Các giới hạn video, timestamp và ngân sách mỗi lượt giữ như reader hiện hành.

`gaze_tracking` là ModuleResult riêng. Khi không bật cờ, không chạy và không
thêm trường này vào báo cáo. Lỗi gaze vẫn có thể giữ số đo head hợp lệ để chẩn
đoán, nhưng downstream bị chặn. Gaze/head pass chỉ là luật thử nghiệm; chưa có
bằng chứng chiều sâu hoặc chống tấn công. Điểm GenD/PAD chưa hiệu chỉnh; so mặt
thiếu artifact ngưỡng vẫn degraded. Không hợp nhất chúng thành kết luận xác minh.

Video bắt đầu tại mốc 0, file không lật gương. Chỉ dùng `session-response` đã
lưu từ server của nhóm, gồm đầy đủ `gaze_points`/head plan gắn session/lượt.
CLI tin file cục bộ, không chứng minh chữ ký server/media; không thay LIVE-03/
SEC-02. Đầu vào production phải lấy lịch và ảnh tham chiếu từ kho server.

## Nguồn

Muốn ngồi trước laptop và thử live preview, mắt/góc đầu cùng AI cập nhật nền:
xem [Webcam Lab nội bộ](webcam-lab.md). Không cần tự quay clip hoặc tạo file
thử thách để dùng lab; kết quả của lab không phải phản hồi phiên server.

- [MediaPipe Face Landmarker Python](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).
- [PyTorch cài backend CPU](https://pytorch.org/get-started/locally/).
- [Giới hạn và phiên bản từng model](head-and-match.md), [reader/dò mắt](../../ml/src/vericlue_ml/presence/README.md).
