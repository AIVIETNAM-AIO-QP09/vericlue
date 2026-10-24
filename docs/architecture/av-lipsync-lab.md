# Lab thu hình–tiếng và khớp môi — VOICE-12

Công cụ nội bộ Windows, dùng lại Qwen/NES2Net/CTC và lõi Stable SyncNet hiện có.
Một FFmpeg DirectShow input mở cả camera lẫn micro, xuất hai track trong một
Matroska qua pipe; không dùng hai bộ ghi độc lập. Đây là bản xây tính năng,
chưa đánh giá độ chính xác hoặc dùng để quyết định xác minh.

## Chuẩn bị

Tạo **runtime riêng**, giữ nguyên runtime webcam/Qwen/NES2Net đang dùng:

```powershell
uv venv tmp/av-lab-runtime --python .venv/Scripts/python.exe
uv pip install --python tmp/av-lab-runtime/Scripts/python.exe --torch-backend cpu -r ml/requirements/av-lab-cpu.txt
$env:PYTHONPATH = "$PWD/ml/src"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
```

Cần FFmpeg executable có DirectShow trên PATH, hoặc truyền `--ffmpeg <path>`.
Không chép FFmpeg hoặc thêm code bên ngoài vào repo. Runtime pin PyAV 19.0.2,
Transformers 5.13.0, OpenCV, ONNX Runtime và Torch CPU; NES2Net vẫn dùng child
runtime riêng 4.57.6. Direct pins không phải transitive lockfile.

- `--models-dir`: Qwen và CTC của lab, ví dụ `models/selected-2026-10-24`.
- `--lipsync-models-dir`: root có `syncnet/stable_syncnet.pt` và `scrfd-10g/det_10g.onnx`
  theo manifest. Nếu để trống dùng cùng `--models-dir`. Thư mục selected hiện
  không có Stable SyncNet; máy nhóm đã có tại `D:/Projects/vericlue-store/models`.
  Không nhầm trọng số `synchformer-lrs3` với checkpoint Stable SyncNet.

Ví dụ máy nhóm (thay đường dẫn nếu máy khác):

```powershell
tmp/av-lab-runtime/Scripts/python.exe -m vericlue_ml.eval.av_lab --models-dir models/selected-2026-10-24 --lipsync-models-dir D:/Projects/vericlue-store/models --nes2net-python tmp/nes2net-runtime/Scripts/python.exe
```

Nếu editable trỏ checkout cũ, đặt PYTHONPATH tới `ml/src` của checkout/worktree
mới. Bỏ `--nes2net-python` thì không bật chấm giọng AI. Lab micro cũ không đổi.

## Sử dụng

1. Trong tab **Camera & micro**, chọn **Chọn camera & micro…**. Liệt kê tên bằng
   FFmpeg, chưa ghi hình/tiếng. Chọn nguồn rồi bấm **Dùng hai thiết bị này**.
2. Bấm **Thu hình & tiếng**, chờ **ĐANG THU**, nhìn camera và đọc câu. Preview
   chỉ hiện trong lượt đang thu; cần đủ ánh sáng và một mặt rõ. Không dùng
   camera đồng thời ở lab khác nếu driver không cho phép chia sẻ.
3. Bấm **Dừng & kiểm**. FFmpeg đóng hai track trước khi các model xử lý. Tối đa
   20 giây, RAM encoded 64 MiB, video ≤640×480/MJPEG, tối đa 1200 frame, audio
   mono PCM16/16 kHz. Hình/tiếng không lưu ra file. Nén MJPEG là recipe lab mới.
4. Xem riêng **Câu đọc**, **Giọng AI · 4 giây đầu**, **Nhịp đọc**, **Khớp môi**.
   Cùng audio được dùng cho cả bốn bước; không có kết luận tổng hợp. Khi xong,
   tab camera tự chuyển sang khớp môi nếu người dùng vẫn đang ở tab camera.
5. **Hủy/Esc** bỏ toàn lượt. FFmpeg được yêu cầu kết thúc; không đáp ứng sau
   3 giây hoặc quá watchdog thì kill/reap đúng tiến trình đã tạo, dữ liệu bị loại.
   Qwen/CTC/SyncNet native đang chạy không bị ngắt giữa chừng; chờ kết thúc trước
   lượt mới. Đóng cửa sổ cũng yêu cầu dừng thu, nhưng process Python có thể còn
   chạy tới khi native kết thúc để hoàn tất cleanup. Không đóng lab khác tự động.

Các model chạy lần lượt, nạp lười/cache; CTC dùng chung instance với nhịp đọc
nhưng có thể suy luận lại khi chấm SyncNet. Lần đầu có thể chậm trên CPU; chưa
tối ưu RAM/tốc độ. Số thread Torch là thiết lập dùng chung trong parent. Không
phải suy luận SyncNet realtime trong lúc preview.

CLI có `--video-device`/`--audio-device` để chọn sẵn tên, `--list-devices` để in
danh sách rồi thoát, `--ui-preview` vô hiệu hóa tất cả thiết bị/model. Không tự
liệt kê hoặc bật thiết bị khi mở/import/construct lab. Chỉ thu sau nút bấm.

## Đồng hồ, kết quả và giới hạn

Giữ PTS của cả hai track từ cùng container. Lấy PTS audio đầu làm **một origin
chung**, không reset riêng video; video có thể có timestamp âm nếu xuất hiện
trước audio. Không trim lặng, normalize waveform, tự thêm khoảng lặng hoặc
dịch track để được điểm đẹp. Audio không liên tục quá sai số lượng tử hóa 2 ms,
timestamp thiếu/không tăng, budget vượt hoặc capture lỗi đều bị loại.

CTC căn câu đề bài trên audio gốc. Video được chọn gần mốc 25 fps trong đúng
đoạn đã căn, giữ guard sai số frame ≤40 ms và phạm vi dò ±600 ms của VOICE-05.
Chỉ decode/cắt các JPEG cần dùng; giữ tiền xử lý SCRFD/Stable SyncNet của lõi cũ.
SCRFD crop khác affine landmark upstream, MJPEG/capture driver cũng chưa đánh giá.

Tab khớp môi hiển thị **độ lệch ms** (dương = tiếng trễ), **cosine tại mốc gốc**
và cosine tốt nhất trong khoảng dò. Không tự sửa track trước khi chấm, không
đổi cosine thành xác suất. Capture latency/driver/phần cứng chưa được kiểm chứng;
không suy ra độ lệch là deepfake. CTC ép căn cũng không chứng minh đọc đúng.

`RamLipSyncDetector` có version recipe riêng, trả ModuleResult `lipsync`, luôn
`unclear`, đo được vẫn `degraded`, không score/prob_attack. Không có mặt/clip
quá ngắn/lỗi đều không đạt. Factory/mock chỉ opt-in; HTTP SyncNet/MVP/full,
thresholds và UI sản phẩm không đổi. License/checkpoint vẫn theo VOICE-05.

**Lưu JSON** là thao tác riêng của người dùng, chỉ lưu câu/metrics/commit/model/
hash/runtime, hash container/PCM và hash JPEG+PTS theo thứ tự, không waveform
hay pixel. Không lưu tên thiết bị vào report. Buffer chính được wipe sau lượt;
không cam kết secure erasure mọi bản sao của native/Python hoặc preview.

## Kiểm tra chức năng

Unit dùng packet/process/model giả, không cần PyAV/FFmpeg/model hoặc thiết bị.
Native opt-in dùng FFmpeg lavfi, không đọc camera/micro, không dữ liệu người:

```powershell
$env:AV_LIPSYNC_MODELS_DIR = "D:/Projects/vericlue-store/models"
tmp/av-lab-runtime/Scripts/python.exe -m pytest ml/tests/test_av_lipsync_real_smoke.py -m slow -ra
```

Smoke chấm SyncNet thật trên pattern với **span CTC và hộp mặt giả**, thử SCRFD
thật bằng ảnh trống; kiểm hash/cache/output hữu hạn. Test thứ hai dừng FFmpeg
thật đang phát nguồn tổng hợp, kiểm process/pipe đã đóng. Không phải kiểm cả
bốn model thật cùng phiên, không chứng minh driver DirectShow hoặc độ chính xác.
Chưa tự thu thiết bị thật; cần người dùng chủ động thử sau merge.

Nguồn API: [FFmpeg DirectShow](https://github.com/FFmpeg/FFmpeg/blob/n8.0/libavdevice/dshow.c),
[PyAV](https://pypi.org/project/av/19.0.2/), [PyAV container/PTS](https://pyav.org/docs/stable/api/container.html).
