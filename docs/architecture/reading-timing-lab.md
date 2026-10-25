# Nhịp đọc trong Voice Lab — VOICE-11

Tính năng nội bộ dùng lại CTC aligner của VOICE-05 để lấy mốc từng âm tiết
và khoảng ngắt từ cùng bản thu của Qwen/NES2Net. Chưa đánh giá độ chính xác;
chưa phát hiện cắt ghép hay xác minh người thật bằng các mốc này.

## Mở và dùng

Dùng runtime Qwen đã cài theo [hướng dẫn](qwen-asr-diagnostic.md), cùng thư mục
model có `ctc-aligner/` được tải bằng script của repo. Không cần cài thêm model
khác hoặc thay Transformers trong runtime webcam/NES2Net.

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
tmp/qwen-asr-runtime/Scripts/python.exe -m vericlue_ml.eval.voice_lab --models-dir models/selected-2026-10-24 --nes2net-python tmp/nes2net-runtime/Scripts/python.exe --with-reading-timing
```

Nếu chạy worktree mới nhưng editable trỏ checkout cũ, đặt `PYTHONPATH` tới
`<checkout mới>/ml/src`. Bỏ `--nes2net-python` vẫn dùng được Qwen + nhịp đọc;
bỏ `--with-reading-timing` giữ cách chạy trước đây, không nạp CTC.

1. Bấm **Thu âm**, chờ ĐANG THU rồi đọc câu, bấm **Dừng & kiểm**. Không có lượt
   đọc thêm. Micro tắt trước khi chạy các model, âm thanh chỉ giữ trong RAM.
2. Xem riêng ba tab: **Câu đọc**, **Giọng AI · 4 giây đầu**, **Nhịp đọc**.
   CTC căn toàn bộ bản thu (lab tối đa 20 giây), NES2Net vẫn chỉ chấm 4 giây đầu.
3. Tab nhịp đọc có tốc độ, khoảng ngắt dài nhất, mốc bắt đầu/kết thúc/thời lượng
   từng âm tiết và các cờ thời lượng từ VOICE-05. Có thanh cuộn để xem đủ.
4. **Hủy/Esc** bỏ toàn bộ kết quả lượt hiện tại. CTC chạy trong tiến trình Qwen,
   không ngắt cưỡng bức suy luận native; UI vẫn phản hồi nhưng phải chờ tác vụ
   kết thúc trước lượt mới, giống Qwen. Worker NES2Net riêng được dừng khi hủy.
5. Lỗi CTC không xóa kết quả Qwen/NES2Net. Mỗi model nạp lười và được giữ trong
   RAM giữa các lượt; lần đầu gồm kiểm hash/nạp model. Ba bước chạy lần lượt,
   chưa tối ưu bộ nhớ/tốc độ. CTC dùng cấu hình CPU 2 thread hiện có, chia sẻ
   thiết lập thread của PyTorch với Qwen trong tiến trình này.

`--ui-preview` luôn vô hiệu hóa micro/model, kể cả khi bật các cờ tính năng.
Không sửa màn xác minh web/app, API hoặc bộ quyết định.

## Cách đọc số đo

- **Mốc âm tiết:** căn **câu được yêu cầu** lên audio gốc, không phải nhận dạng
  lại người dùng đã nói gì. Thời gian tính từ đầu bản thu, không cắt khoảng lặng
  hai đầu. VAD chỉ kiểm có tiếng nói; không trim hay ghép waveform trước CTC.
- **Tốc độ:** số âm tiết / khoảng từ bắt đầu âm tiết đầu đến kết thúc âm tiết
  cuối, **bao gồm khoảng ngắt bên trong**; không phải tốc độ phát âm loại trừ lặng.
- **Khoảng ngắt:** vùng thời gian giữa hai span âm tiết do CTC gán; không phải
  phép đo độc lập chứng minh vùng đó thực sự im lặng. Bỏ lặng đầu/cuối khỏi số này.
- **Cờ thời lượng:** dùng lại luật tạm VOICE-05: âm tiết <60 ms hoặc >1,2 giây;
  khoảng ngắt >1 giây; wildcard nội bộ >1 giây. Không đổi ngưỡng, không suy ra
  xác suất hoặc kết luận cắt ghép từ cờ; có thể chịu ảnh hưởng giọng/vùng miền.

CTC có thể ép căn cả một câu **đọc sai**. Lab nhắc rõ khi Qwen chưa khớp/lỗi;
không thay transcript, WER, kết quả nội dung bằng các từ CTC đã được cho trước.
Timing trả `ModuleResult(module=voice_challenge)` với version riêng,
`degraded/unclear`, không `score`/`prob_attack`; lỗi hoặc không có tiếng cũng
không thành đạt. Không có ngưỡng tốc độ để quyết định chấp nhận.

## Model và báo cáo

Tái dùng `MahmoudAshraf/mms-300m-1130-forced-aligner` revision
`49402e9577b1158620820667c218cd494cc44486` (trọng số CC-BY-NC-4.0) và code căn
NumPy hiện có trong `voice/align.py`; không chép thêm code bên ngoài. Model
local safetensors, CPU FP32/eager, kiểm đủ khóa và SHA trước/sau load, cache;
không mạng/remote code. Thư mục model đọc từ config `alignment` hiện có (mặc
định `ctc-aligner`). Recipe nhịp đọc có version riêng `voice11-timing-v1-raw16k`.

JSON tùy chọn từ lab thêm `reading_timing`: ModuleResult, commit/model/hash/
runtime, số mẫu/rate và hash PCM 16 kHz. Nó dùng đúng buffer resample đã gửi
NES2Net nếu NES2Net được bật; root vẫn là kết quả nội dung Qwen. Có câu đề bài
và mốc từ nhưng không có waveform. Xóa các buffer chính sau lượt không phải
cam kết xóa an toàn mọi bản sao của thư viện native.

CLI riêng, không mở micro:

```powershell
tmp/qwen-asr-runtime/Scripts/python.exe -m vericlue_ml.eval.reading_timing --audio tmp/reading.wav --expected-text-file tmp/prompt.txt --models-dir models/selected-2026-10-24 --output tmp/timing.json
```

Audio local tối đa 30 giây/32 MiB, 8–192 kHz/mono hoặc stereo, resample/fold
theo decoder hiện có rồi căn raw 16 kHz. CLI không nhận đề từ URL, không ghi đè
input/model/report; hash input thay đổi trong xử lý làm mất toàn bộ evidence.
Report ghi rõ câu từ file local chưa được server xác thực; không phải bằng chứng
phiên eKYC. API RAM chỉ nhận mono float32/16 kHz hữu hạn trong [-1,1].

Test chức năng native tùy chọn bằng **sóng tổng hợp**, không dùng giọng người:

```powershell
$env:READING_TIMING_MODELS_DIR = "$PWD/models/selected-2026-10-24"
tmp/qwen-asr-runtime/Scripts/python.exe -m pytest ml/tests/test_reading_timing_real_smoke.py -m slow -ra
```

Smoke chỉ kiểm nạp/shape/output/cache/hash và chặn im lặng; chưa phải kết quả
độ chính xác timestamp, nhận dạng cắt ghép hay benchmark tiếng Việt.
