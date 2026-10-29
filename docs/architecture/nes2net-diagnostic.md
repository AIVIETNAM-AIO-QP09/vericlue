# NES2Net-X — diagnostic giọng giả (VOICE-09)

Backend riêng cho checkpoint đã tải, không thay AntiDeepfake của API và không
coi điểm thô là xác suất. **Luôn `degraded/unclear`, `prob_attack=None`** vì còn
thiếu parity frontend Fairseq ↔ Transformers và đánh giá/calibration tiếng Việt.

## Nguồn và checkpoint

- Mã tác giả: [Nes2Net_ASVspoof_ITW@c9fe1177](https://github.com/Liu-Tianchi/Nes2Net_ASVspoof_ITW/tree/c9fe1177f44040f002cb40def928332d2e261f1e).
  Head sao chép có chỉnh định dạng/tuple defaults và giữ attribution/Apache-2.0,
  xem `third_party/README.md`. Không chép Fairseq hoặc mã không rõ giấy phép.
- `checkpoint.pth`: link single-model ASVspoof 2021 DF do README công bố,
  [Drive](https://drive.google.com/file/d/1tjuSdbzgCnJSfy_eE_P52jRAonHY4YUT/view),
  SHA-256 `3158d10c6fc3c58e452a33981b409f5a65ecf91d548931b4ffbd675462799685`.
  Tên local/hash khóa chính xác file, không suy luận danh tính bằng tên tải xuống.
- File đã có cả `ssl_model.model.*` và `Nested_Res2Net_TDNN.*`; runtime này
  **không cần nạp `xlsr2_300m.pt`** để khởi tạo frontend rồi ghi đè trọng số.
  Không cài Fairseq, không `weights_only=False` hoặc unpickle config tùy ý.
- Graph XLS-R: [config chính thức facebook/wav2vec2-xls-r-300m](https://huggingface.co/facebook/wav2vec2-xls-r-300m/blob/main/config.json).
  Đối chiếu metadata XLS-R tải sẵn bằng pickletools chỉ đọc: 24 lớp, 1024 hidden,
  4096 FFN, 16 heads, pre-layernorm, extractor layernorm, convolution bias,
  required_seq_len_multiple=1. Config tĩnh nằm ở `ml/configs/nes2net.yaml`.

Strict mapping yêu cầu đủ mọi tensor suy luận của cả backbone và head, không
cho checkpoint thiếu/thừa khóa hoặc sai shape; chỉ bỏ quantizer/project_q/final_proj
của pretraining theo danh sách rõ ràng. Không có trọng số khởi tạo ngẫu nhiên
được giữ lại làm bằng chứng. SHA kiểm trước và sau load, tensor-only safe load,
CPU FP32, eager attention, eval, khóa inference và cache model một lần. Lỗi nạp
giữ unavailable tới khi khởi tạo lại process. Không tải mạng khi suy luận.

## Tiền xử lý và ý nghĩa kết quả

Chọn recipe `easy_inference_demo.py --test_mode 4s`: **64000 mẫu đầu** của audio
mono 16 kHz, ngắn hơn thì lặp đến đủ. Không waveform layer_norm, chuẩn hóa âm
lượng, cắt VAD hoặc chia cửa sổ như AntiDeepfake. Script benchmark khác trong
repo tác giả dùng 64600 mẫu; không được gắn số EER công bố của họ cho bản này.

CLI chỉ nhận mono 16 kHz, tối đa 30 giây/32 MiB; từ chối stereo/rate khác để
tránh âm thầm đổi recipe resampling. RAM API yêu cầu mono float32 hữu hạn trong
[-1,1] tại 16 kHz. Ít hơn 1 giây hoặc cửa sổ được chấm không có đủ tiếng thì
`not_applicable/unclear`; WebRTC VAD chỉ kiểm chất lượng, **không cắt mẫu đầu vào**.
Lỗi decode/dependency/model/output không hữu hạn trả `error/unclear`.

`data_utils_SSL.py genSpoof_list` ghi **0=spoof, 1=bonafide**. Xuất hai logit và
`score = logit_spoof - logit_bonafide`: cao hơn nghiêng về spoof trong model.
Không sigmoid thành “% giả”, không ngưỡng pass/fail. Dù margin âm/dương vẫn
degraded/unclear. Chưa chứng minh điểm phân biệt được tiếng Việt thật/AI.

Report ghi rõ `truncated`, `repeated_to_four_seconds`, `input_seconds`,
`scored_start_s=0`, `scored_seconds=4`. Với file dài, **phần sau 4 giây không
được chấm**. Không được dùng thử nghiệm này để kết luận cả video/câu nói sạch.
VOICE-13 thêm protocol/version riêng [theo đoạn toàn bản thu](nes2net-timeline-lab.md)
trong lab và CLI `--whole-utterance`. Bản first4s ở đây vẫn giữ nguyên;
protocol mới cũng chưa được đánh giá accuracy hoặc calibration.

## Chuẩn bị và chạy

VOICE-10 ghép worker NES2Net với cửa sổ micro Qwen: thu một lần, hai kết quả
riêng, PCM qua RAM pipe và child runtime riêng. Chạy theo
[hướng dẫn thử kép](qwen-asr-diagnostic.md#thu-một-lần-kiểm-cả-qwen-và-nes2net-voice-10).
Lab hiện dùng timeline VOICE-13; giới hạn parity/hiệu chỉnh vẫn giữ. CLI file
dưới đây tiếp tục dùng first4s mặc định, thêm `--whole-utterance` để bật timeline.

PowerShell từ gốc checkout; giữ nguyên runtime Qwen, webcam và CUDA:

```powershell
uv venv tmp/nes2net-runtime --python .venv/Scripts/python.exe
uv pip install --python tmp/nes2net-runtime/Scripts/python.exe --torch-backend cpu -r ml/requirements/nes2net-cpu.txt
uv pip install --python tmp/nes2net-runtime/Scripts/python.exe --no-deps -e ./ml
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
tmp/nes2net-runtime/Scripts/python.exe -m vericlue_ml.eval.nes2net_voice --audio tmp/reading-16k-mono.wav --models-dir models/selected-2026-10-24 --output tmp/nes2net-result.json
```

Report chỉ lưu khi chạy CLI rõ ràng, không mở microphone hay ghi âm. Có commit,
model/version/hash/load report/runtime, hash input, protocol, sample_count=1,
và ModuleResult. Output phải là file mới, ngoài models, không ghi đè input;
input thay đổi trong inference sẽ xóa score và trả lỗi integrity. Giữ JSON ở
ignored `tmp/`; không audio trong artifact. Factory opt-in `get_nes2net()`,
mock dùng mock `voice_spoof` có sẵn; API/full/MVP vẫn giữ backend trước đó.

## Kiểm chứng và phần còn thiếu

Unit dùng state giả/stream số, không cần Torch/trọng số. Native opt-in chạy
checkpoint thật trên tín hiệu tổng hợp, kiểm đầy đủ khóa, CPU FP32/eval/cache,
output hữu hạn/lặp lại và chặn im lặng. Có test so head port với các lớp gốc
đã khóa SHA trên feature tổng hợp; **parity head không phải parity frontend**.

```powershell
$env:NES2NET_MODELS_DIR = "D:/Projects/Data4Life/models/selected-2026-10-24"
# NES2NET_UPSTREAM_SOURCE tùy chọn: file nguồn chính thức đã khóa revision/SHA ở trên.
tmp/nes2net-runtime/Scripts/python.exe -m pytest ml/tests/test_nes2net_real_smoke.py -m slow -ra
```

Chưa có EER/accuracy tiếng Việt, baseline trước/sau, calibration hoặc so sánh
AntiDeepfake; không dùng tập test để chọn mô hình/ngưỡng. Native thử tổng hợp
không thay cho dữ liệu chia theo người. Không tuyên bố SOTA trên VeriClue,
không gán kết quả của tác giả cho bản port này, không tháo chốt HTTP.
