# NES2Net theo đoạn trên toàn bản thu — VOICE-13

Lab micro và A/V hiện kiểm lần lượt các đoạn phủ hết bản thu, thay cho chỉ
chấm 4 giây đầu. Tái sử dụng checkpoint/backend/runtime CPU của VOICE-09,
không tải mô hình mới. Đây là protocol do nhóm xây; chưa có số đo accuracy,
parity frontend Fairseq ↔ Transformers hoặc calibration tiếng Việt.

## Chạy và đọc kết quả

Dùng nguyên lệnh lab trong [hướng dẫn micro](qwen-asr-diagnostic.md) hoặc
[hướng dẫn A/V](av-lipsync-lab.md), có `--nes2net-python` trỏ runtime riêng
4.57.6. Worker tự dùng mã nguồn cùng checkout của lab. Không cần cài thêm
thư viện; các runtime, trọng số và recipe bên trong một đoạn không đổi.

1. Người dùng chủ động bấm thu, đọc câu rồi **Dừng & kiểm** như trước.
2. Tab **Giọng AI · theo đoạn** ghi số đoạn đo được, thời gian gốc được phủ
   và từng khoảng `bắt đầu → kết thúc`, kèm margin hoặc lý do chưa đo.
3. Đoạn thiếu tiếng nói qua cổng VAD là `not_applicable`; đoạn lỗi là `error`.
   Không được đếm các đoạn này thành đã chấm. Các đoạn khác vẫn hiện kết quả.
4. Hủy/Esc bỏ toàn lượt và dừng worker của lab; timeout 180 giây áp dụng cho
   **toàn request**, không phải từng đoạn. Có thể tăng bằng `--worker-timeout`
   tới 600 giây. Lượt dài cần nhiều lần inference CPU hơn, chưa có cam kết realtime.

CLI first4s của VOICE-09 vẫn là mặc định. Bật toàn bản thu bằng cờ riêng:

```powershell
$env:PYTHONPATH = "$PWD/ml/src"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
tmp/nes2net-runtime/Scripts/python.exe -m vericlue_ml.eval.nes2net_voice --whole-utterance --audio tmp/reading-16k-mono.wav --models-dir models/selected-2026-10-24 --output tmp/nes2net-timeline.json
```

File phải mono 16 kHz, tối đa 30 giây/32 MiB, output mới ngoài thư mục model.
CLI không mở thiết bị. Lab tối đa 20 giây; chỉ giữ PCM trong RAM, JSON xuất
theo nút bấm và không chứa waveform. Không thay UI sản phẩm/API/router.

## Cách chia đoạn

- Cửa sổ 64000 mẫu (4 giây), lưới cách 4 giây, neo thêm cửa sổ cuối đúng cuối
  bản thu nếu chưa trùng. Tối đa 8 cửa sổ/30 giây.
- Ví dụ 10 giây: `0–4`, `4–8`, `6–10`. Cửa sổ cuối chồng một phần để giữ
  nguyên đủ 4 giây, không lặp một mẩu đuôi ngắn thành 4 giây.
- Toàn input ngắn hơn 4 giây: lặp theo recipe gốc; dưới 1 giây không chấm.
- Mỗi đoạn giữ mẫu gốc, không trim, normalize hoặc nối các vùng tiếng.
  Cổng VAD dùng logic VOICE-09 trên cửa sổ được chấm; chưa đo accuracy VAD.
- Độ phủ bằng **hợp các khoảng gốc đã đo được**, không cộng trùng phần chồng
  hoặc phần mẫu lặp. 10 giây đo đủ thì vẫn là 10 giây, không phải 12 giây.

Độ phủ chỉ là phạm vi đã chạy mô hình. Không bảo đảm mô hình chú ý hoặc phát
hiện được mọi sự kiện trong khoảng; tấn công rất ngắn vẫn cần đánh giá riêng.

## Hợp đồng nội bộ và giới hạn

Detector mới `Nes2NetTimelineDetector`, factory/mock `get_nes2net_timeline`,
version `nes2net-x@<revision>+hf4576-cpu-fp32-timeline4s-tail-v1`.
`ModuleResult` bên ngoài không có `score` hoặc `prob_attack`, luôn `unclear`.
Nếu có đoạn lỗi, status tổng là `error`; có đoạn đo được và không lỗi thì
`degraded`; tất cả thiếu tiếng thì `not_applicable`. Không có trường hợp đạt.

Evidence `nes2net_windows` giữ sample index và giây trên bản thu gốc, cùng
`ModuleResult` first4s bên trong từng đoạn. Mỗi đoạn đo được có hai logit và
margin `spoof − bonafide`; **không gộp min/max/trung bình thành điểm toàn câu**.
Mọi margin chỉ tham khảo, không phải xác suất hoặc kết luận thật/giả.

Summary lưu số đoạn đo/lỗi/thiếu tiếng, `measured_samples`, `measured_seconds`,
`measured_fraction`, `all_source_samples_measured` và `aggregation=none`.
Worker/client giữ framing PCM/hash/request-id cũ, mode chọn qua argv lúc
khởi động. Client kiểm version, số mẫu, toàn bộ khoảng bắt buộc, từng kết quả
và tính lại coverage để chặn nhầm bản first4s thành toàn câu. Timeout/hủy
không trả timeline dở như kết quả hoàn tất; lỗi worker không xóa kết quả Qwen.

## Kiểm tra chức năng

Unit dùng tín hiệu số/backend giả; kiểm đuôi, overlap, phần sau 4 giây, VAD,
lỗi từng đoạn, version/hash/coverage, IPC process thật giả model và CLI đổi file.

```powershell
uv run pytest ml/tests/test_nes2net_timeline.py
$env:NES2NET_MODELS_DIR = "$PWD/models/selected-2026-10-24"
tmp/nes2net-runtime/Scripts/python.exe -m pytest ml/tests/test_nes2net_timeline.py -k real_cpu_timeline
```

Native smoke chạy checkpoint CPU trên nhiễu tổng hợp 5 giây, kiểm hai lần
inference/cache/hash/output hữu hạn, **bỏ qua cổng VAD bằng stub**. Không dùng
người hoặc thiết bị, không phải bằng chứng phát hiện giọng AI hay số liệu thi.
