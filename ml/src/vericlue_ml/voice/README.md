# VOICE-04 — kiểm câu đọc

`VoiceChallengeDetector.predict(DetectorInput)` đọc `audio` và câu phía server ở
`metadata["prompt"]`. Trả `ModuleResult(module="voice_challenge")`:

- `ok/pass`: nội dung khớp; chưa phải kết luận giọng thật hoặc cho qua eKYC.
- `ok/fail`, `E_CHALLENGE_MISMATCH`: sai câu; API có thể cấp câu mới một lần.
- `error/unclear`: thiếu model/dependency, audio hỏng, lỗi ASR; không được pass.
- `not_applicable/unclear`: không tìm thấy tiếng nói; không được pass.

WER, tương đồng và transcript chỉ nằm trong evidence nội bộ, không gửi cho người dân.
`prob_attack` để trống: đây là cổng nội dung, không giả định xác suất giọng giả.
Registry cache detector/model; mock riêng không cần thư viện inference.

## Chuẩn bị và chạy CPU offline

```powershell
uv sync --all-packages --extra voice
$env:MODELS_DIR = 'E:\shared\vericlue\models'
$env:DATA_DIR = 'E:\shared\vericlue\data'
uv run --all-packages --extra voice python scripts/download_models.py --only phowhisper --verify
```

Mô hình/processor chỉ đọc `MODELS_DIR/phowhisper`, `local_files_only=True`, không
remote code. PyTorch >=2.6 đọc checkpoint `.bin` với `weights_only=True`; CPU FP32,
4 thread mặc định trong `ml/configs/models.yaml`. Cài dependency là bước chuẩn bị;
inference không tải mạng. Không cần CTranslate2 hoặc thêm checkpoint VAD.

`asr.transcribe(audio_path)` **không nhận câu đề bài**. Audio được đọc local, mono
16 kHz; WebRTC VAD mode 1, frame 20 ms, padding 200 ms cắt lặng hai đầu và giữ
khoảng lặng bên trong. Whisper dùng `language="vi"`, `task="transcribe"`,
`condition_on_prev_tokens=False`; không prompt/hotword. Audio tối đa 120 giây.

## Câu và so khớp

24 câu tự soạn, mỗi câu 8–12 âm tiết và đủ sáu thanh; ngân hàng phủ tr/ch, s/x,
r/d/gi và n/ng cuối. `generate_prompt(previous=...)` dùng `secrets.choice`, loại
câu trước; RNG có seed chỉ dành test. TTL, số lần đọc lại, chống gọi trùng thuộc API.

Chuẩn hóa NFC, chữ thường, dấu câu thành khoảng trắng, số nguyên/thập phân thành
chữ (linh, mốt, tư, lăm; số có 0 đầu đọc từng chữ số). Dấu chấm/phẩy giữa chữ số
được hiểu là dấu thập phân, không tự đoán ngày/điện thoại. Canonical oa/oe/uy,
giữ nguyên uyê và nguyên âm dài khác. Sau chuẩn hóa, âm tiết là token cách trắng.

Phải đạt **cả** `jiwer.wer <= 0.3` và `rapidfuzz.fuzz.ratio / 100 >= 0.9` trên
chuỗi bỏ dấu (`đ → d`). Hằng số có tên ở challenge.py, nguồn thẻ VOICE-04/proposal;
ROUT-02 chuyển vào thresholds.yaml mục voice. Không chỉnh bằng ViMD/test.

## TTS và báo cáo

```powershell
uv run --all-packages --extra voice python scripts/prepare_voice_tts.py --provider mms --download-model
uv run --all-packages --extra voice python -m vericlue_ml.eval.voice_challenge `
  --manifest "$env:DATA_DIR/raw/vimd/selected_manifest.json" `
  --output "$env:DATA_DIR/eval/VOICE04/evaluation.json" `
  --report docs/status/results/VOICE-04.md `
  --tts-manifest "$env:DATA_DIR/eval/VOICE04/tts-mms/manifest.json"
```

Mặc định dùng `facebook/mms-tts-vie`, revision
`b58928d033932a49aa8e3d6cf11625b25fe928d2`, CC BY-NC 4.0. Chuẩn bị tải weights
safetensors 145.271.288 byte vào MODELS_DIR/mms-tts-vie, xác minh SHA-256 đã ghim;
sinh CPU local, seed 42 trước mỗi câu. Không có dịch vụ TTS mạng, không phân phối audio.
Nguồn/điều khoản: https://huggingface.co/facebook/mms-tts-vie/blob/b58928d033932a49aa8e3d6cf11625b25fe928d2/README.md.

Thử nghiệm eSpeak trước đó đọc đúng bị ASR từ chối; giữ ở thư mục TTS riêng.
MMS dùng **cùng hai văn bản cố định**, không chỉnh ngưỡng theo kết quả.
Có thể tái lập eSpeak bằng `--provider espeak --download-tool`.
eSpeak NG 1.52.0 chỉ chạy riêng để chuẩn bị thử nghiệm. Windows script tải MSI chính thức và extract vào DATA_DIR/tools, không
cài hệ thống. Mạng chỉ dùng để chuẩn bị công cụ; không có dịch vụ TTS mạng.
GPL-3.0-or-later áp dụng công cụ; không chép/liên kết vào sản phẩm, không phân phối
binary hoặc audio. Không gán giấy phép CC/public domain cho output.

Evaluator dùng **mọi hàng** trong manifest, xác minh bốn người mỗi miền trước
inference, không lấy mẫu hoặc fit. JSON có transcript chỉ ở DATA_DIR; Markdown
chỉ chứa thống kê, speakerID, commit và model revision. CP95 theo câu là mô tả,
không tính độc lập theo người; lỗi xử lý tính riêng và cũng là không đạt.
Thử nghiệm nhỏ; câu ViMD dài, chưa tương đương câu thử thách 8–12 âm tiết.

Kiểm kê nguồn (chỉ metadata, cần extra data):
`uv run --all-packages --extra voice --group data python scripts/audit_voice_vimd.py`.
VOICE-05/06 ghép căn chỉnh, phát hiện giọng giả và khớp môi; VOICE-04 không đổi API/web.

## Test

`uv run --all-packages --extra voice pytest` chạy test mock/oracle, không dùng weights. Test
`slow` chỉ chạy khi đặt cả MODELS_DIR/DATA_DIR và đủ model/audio/dependency local;
CI thiếu chúng thì skip. Trọng số, TTS, raw audio, JSON chi tiết không commit.
