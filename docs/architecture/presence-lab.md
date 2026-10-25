# Thử mặt liên tục — PRES-05

Công cụ nội bộ gộp **ánh sáng → mắt → quay đầu** vào một lượt, dùng lại
camera/reader/model của Webcam Lab. Không mở camera khi khởi động, không đổi
app/web/API/router, không tạo quyết định xác minh. Tham chiếu và pixel chỉ ở RAM.

## Mở và thử

Dùng nguyên runtime CPU theo [hướng dẫn mặt](face-diagnostic-runtime.md),
không tải thêm trọng số hoặc cài thêm thư viện:

```powershell
$env:PYTHONPATH = "$PWD/ml/src"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
tmp/face-diagnostic-runtime/Scripts/python.exe -m vericlue_ml.eval.presence_lab --models-dir models/selected-2026-10-24
```

- **Bật camera**, đợi ảnh hiện; `--camera 1` khi cần chọn camera khác.
- **Chụp tham chiếu** nếu muốn thử so mặt. Đây là mẫu local, không phải CCCD;
  có thể bỏ qua để chỉ đo ba phần chuyển động/ánh sáng.
- Bấm **Thử mặt · ánh sáng → mắt → quay đầu**. Chỉ cần bấm một lần, rồi làm
  theo Bước 1/3, 2/3, 3/3. Không cần bật AI liên tục trước đó.
- Xem riêng số đo màu, mắt và thứ tự quay đầu. Nếu có tham chiếu và mắt/đầu
  đủ `ok/pass` theo luật diagnostic hiện có, ba ảnh đúng tư thế được chấm
  LVFace/GenD/FS-VFM-L trong worker CPU. Thiếu/lỗi motion hoặc thiếu ảnh thì
  không chấm nhánh ba góc đó. Màu vẫn là tín hiệu tham khảo.
- **Thử riêng** giữ hai lượt cũ: mắt/đầu 18 giây hoặc ánh sáng 6–8 giây.
  AI liên tục và thao tác tham chiếu chỉ dùng khi không có lượt đang chạy.
- **Dừng/Esc** tắt camera, bỏ lượt/kết quả cũ. Thu nhỏ hoặc chuyển tiêu điểm
  sang ứng dụng khác hủy toàn lượt; camera có thể còn preview tới khi bấm Dừng.
  Không tự tiếp tục sau khi quay lại cửa sổ.

Lượt AI native đang chạy phải kết thúc trước lượt mới, không cưỡng bức ngắt
giữa inference. Hủy khi đối chiếu thì chờ worker trả về rồi bỏ kết quả.
Không mở cùng camera ở lab A/V hoặc ứng dụng khác nếu driver không chia sẻ.

## Lịch chung và phạm vi đo

| Bước | Lịch so với đầu lượt |
|---|---|
| Ánh sáng | Baseline + 8 màu + tail theo nguyên `chromapulse.json`, khoảng 5,9–7,9 giây |
| Mắt | Bắt đầu sau tail màu, giữ nguyên 7 giây |
| Quay đầu | Tiếp sau mắt, giữ nguyên 6 giây; trái/phải ngẫu nhiên rồi về giữa |

Tổng khoảng **18,9–20,9 giây**, cộng chờ lấy mẫu cuối 0,2 giây. Đây là thời
lượng từ cấu hình, không phải benchmark xác minh/model. Không tăng nhịp hay
đổi palette. Ba góc lấy từ vị trí trên lịch đã dịch, không dùng mốc cố định
của lượt 18 giây cũ.

Một lần đọc MediaPipe cho cả mắt/pose và màu trong giai đoạn cần thu màu.
Dùng chung thời điểm acquire từ đồng hồ host và mã lượt local; không reset
đồng hồ giữa các phần. Màu ghi thời điểm yêu cầu Tk vẽ, chưa chứng minh lúc
compositor/màn hình phát sáng hoặc cảm biến chụp.

Khoảng 10 Hz; tối đa 240 observations mặt, 75 ảnh RAM ở vùng cần chọn ba góc;
màu tối đa 120 observations/512 draw requests. Hủy/hoàn tất đối chiếu dọn ảnh
của lượt; ảnh giao worker được dọn sau chấm. Không cam kết secure erasure
mọi bản sao Python/native.

## Kết quả và báo cáo

Không có nhãn xác minh đạt của lượt gộp. Mắt/đầu `pass` chỉ nghĩa là khớp
chuyển động theo luật thử nghiệm. Màu luôn unclear, chưa chứng minh phản chiếu
da thật hoặc phát hiện ảnh/video giả. Quay đầu chưa chứng minh chiều sâu;
so ảnh tham chiếu tự chụp chưa chứng minh danh tính trên giấy tờ.

**Lưu báo cáo JSON** giữ cấu trúc Webcam Lab: `motion`, `plan`, `color`,
`color_plan`, `results`, `source`, commit/runtime/hash/model metadata. `plan`
và `color_plan` cùng trial_id; có recipe/thời lượng và
`authentication_decision=not_provided`. Không pixel/video/embedding hoặc micro.
Lỗi một phần được ghi riêng, không xóa phần khác.

Chỉ số/giới hạn: [Webcam Lab](webcam-lab.md),
[ChromaPulse diagnostic](chromapulse-diagnostic.md).

## Kiểm tra

Unit dùng trajectories/pixel tổng hợp và widget giả; không người hay thiết bị.

```powershell
uv run pytest ml/tests/test_presence_trial.py ml/tests/test_webcam_trial.py ml/tests/test_webcam_color.py
$env:GAZE_MODELS_DIR = "$PWD/models/selected-2026-10-24"
tmp/face-diagnostic-runtime/Scripts/python.exe -m pytest ml/tests/test_presence_trial.py -k native_reader
```

Native smoke thử reader/checkpoint thật trên khung xám tự sinh, giữ một task
và đồng hồ chung; không làm số liệu accuracy hoặc nghiệm thu camera thật.
