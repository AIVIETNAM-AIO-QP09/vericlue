# Kiểm câu đọc bằng Qwen3-ASR — diagnostic riêng

VOICE-07 thêm lựa chọn `Qwen/Qwen3-ASR-0.6B-hf`, revision
`7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c`, giấy phép Apache-2.0.
Đây là bản **HF-native**, dùng Transformers 5.13.0 được pin riêng. Không dùng
`qwen-asr` legacy hoặc nâng runtime Transformers 4.x của GenD/PhoWhisper.

Nguồn chính thức: [model card](https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf),
[Transformers API](https://huggingface.co/docs/transformers/model_doc/qwen3_asr),
[processor tại v5.13.0](https://github.com/huggingface/transformers/blob/v5.13.0/src/transformers/models/qwen3_asr/processing_qwen3_asr.py).
Chỉ dùng thư viện đã cài; không chép mã nguồn model hoặc chạy remote code.

## Chuẩn bị và chạy

Chạy tại gốc repo bằng PowerShell; không đổi môi trường webcam/CUDA:

```powershell
uv venv tmp/qwen-asr-runtime --python .venv/Scripts/python.exe
uv pip install --python tmp/qwen-asr-runtime/Scripts/python.exe --torch-backend cpu -r ml/requirements/qwen-asr-cpu.txt
uv pip install --python tmp/qwen-asr-runtime/Scripts/python.exe --no-deps -e ./ml
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
tmp/qwen-asr-runtime/Scripts/python.exe -m vericlue_ml.eval.qwen_voice --audio tmp/reading.wav --expected-text-file tmp/expected.txt --models-dir models/selected-2026-10-24 --output tmp/qwen-content.json
```

`expected.txt` chứa câu tiếng Việt UTF-8 dự kiến. Tự chuẩn bị file audio local
(WAV mono 16 kHz thuận tiện nhất); CLI không mở microphone, không ghi âm và
không gửi audio lên dịch vụ bên ngoài. Hỗ trợ tối đa 30 giây, 32 MiB, mono/stereo
8–192 kHz qua decoder hiện có rồi đổi về mono 16 kHz. Model giữ nguyên trọng số
gốc, nạp FP32 CPU; không tuyên bố parity với BF16 hoặc runtime khác.

Có thể thay `--expected-text-file` bằng `--server-response tmp/session.json`
của lượt dynamic đầu tiên. CLI kiểm session/challenge/version và đọc câu từ
dynamic; JSON phải được giữ từ nguồn server đáng tin. CLI không xác thực chữ
ký JSON, TTL hoặc media nonce, và chưa hỗ trợ gói đọc lại đã đổi câu ở `/voice`.
Không gửi báo cáo này vào API như bằng chứng phiên xác minh.

`ml/configs/qwen3_asr.yaml` ghim hash của **7 file runtime**, kiểm trước và sau
khi nạp. `QWEN_ASR_CONFIG` trỏ config khi dùng wheel ngoài source tree. Lỗi nạp
giữ unavailable tới restart; không tự đổi checkpoint/backend. Model nạp một
lần, generation tuần tự dưới khóa; root mới sau khi nạp bị từ chối.

## Luồng xử lý và kết quả

1. Audio local được kiểm độ dài/kênh/rate/giá trị hữu hạn, WebRTC VAD cắt lặng
   hai đầu, giữ khoảng lặng bên trong. Không có tiếng nói hoặc phần tiếng quá
   ngắn thì `not_applicable/unclear`.
2. Processor chỉ nhận audio và ngôn ngữ Vietnamese. **Không đưa câu đề bài,
   prompt, context hoặc hotword cho ASR**. Số âm tiết chỉ giới hạn budget token.
3. Greedy generate với budget có giới hạn; thiếu EOS hoặc chạm budget là lỗi.
   Decode raw envelope; không dùng hậu xử lý sửa đoạn lặp của processor.
   Sai envelope/ngôn ngữ/control token là lỗi, không âm thầm sửa thành câu khớp.
4. Chuẩn hóa và so khớp hai lớp dùng `compare_transcripts` của VOICE-04 và
   cấu hình ngưỡng hiện có, không chỉnh ngưỡng. `ok/pass` **chỉ có nghĩa nội dung
   khớp**. `ok/fail` là sai câu; lỗi không thành pass. WER là lỗi nội dung,
   không phải xác suất tấn công; không có `prob_attack`.

Version có hậu tố `+cpu-fp32-content-v1`. `registry.get_qwen_voice_challenge()`
là factory opt-in, mock dùng mock `voice_challenge` hiện có. `get_detector`
và API/full/MVP vẫn dùng lựa chọn PhoWhisper hiện hành; chốt dynamic real/mixed
giữ nguyên. Backend này không phát hiện giọng AI, đo nhịp đọc hoặc khớp môi.

Artifact chứa commit, version/revision, hash audio, hash model kỳ vọng/đã kiểm,
model_loaded, runtime, nguồn câu và `sample_count=1`. Transcript/câu dự kiến
chỉ ở báo cáo nội bộ; để file trong thư mục ignored. Không lưu audio vào JSON.
CLI kiểm hash audio trước/sau và không cho output ghi đè input/model.

## Kiểm chứng và giới hạn

Unit test dùng provider giả kiểm đúng/sai câu, trường hợp thiếu tiếng/lỗi,
token budget, integrity và việc không đưa câu dự kiến vào ASR. Đây không phải
đo độ chính xác nhận dạng. Smoke opt-in nạp checkpoint thật, chạy generation
trên audio 0 tự sinh rồi kiểm đường VAD công khai từ chối im lặng: **0 mẫu người**.
Audio 0 ở nhánh generation cố ý bỏ qua VAD chỉ để kiểm native code, không
được dùng như bằng chứng ASR có thể hiểu tiếng Việt.

```powershell
$env:QWEN_ASR_MODELS_DIR = "D:/Projects/Data4Life/models/selected-2026-10-24"
tmp/qwen-asr-runtime/Scripts/python.exe -m pytest ml/tests/test_qwen_asr_real_smoke.py -m slow -ra
```

Chưa có đánh giá câu tiếng Việt thật/miền giọng/tiếng ồn hoặc so sánh với
PhoWhisper. Kết quả nghiệm thu PhoWhisper của VOICE-04 không chuyển sang Qwen.
Không chọn model hay ngưỡng từ test. Trước khi thay API cần đo/calib theo người,
kiểm tải/latency và chính sách fail-closed của phiên; chưa bỏ gate hiện có.
