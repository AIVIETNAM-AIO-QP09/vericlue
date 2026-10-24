# VOICE-04 — kiểm câu đọc

VOICE-09 thêm diagnostic giọng giả NES2Net-X trong runtime CPU riêng, không
thay default AntiDeepfake/API. Luôn degraded/unclear, chỉ chấm 4 giây đầu;
xem [NES2Net diagnostic](../../../../docs/architecture/nes2net-diagnostic.md).

VOICE-07 có lựa chọn Qwen3-ASR-0.6B HF-native trong runtime CPU riêng, factory
opt-in và CLI cho file audio. Giữ nguyên lựa chọn PhoWhisper/API bên dưới.
Xem [Qwen ASR diagnostic](../../../../docs/architecture/qwen-asr-diagnostic.md).
VOICE-08 bổ sung cửa sổ thử microphone `eval.voice_lab`: RAM-only, nút thu/dừng/hủy,
cùng VAD/ASR/luật khớp; không nạp Qwen vào runtime mặt hoặc thay lựa chọn API.

`VoiceChallengeDetector.predict(DetectorInput)` đọc `audio` và câu phía server ở
`metadata["prompt"]`. Trả `ModuleResult(module="voice_challenge")`:

- `ok/pass`: nội dung khớp; chưa phải kết luận giọng thật hoặc cho qua eKYC.
- `ok/fail`, `E_CHALLENGE_MISMATCH`: sai câu; API có thể cấp câu mới một lần.
- `error/unclear`: thiếu model/dependency, audio hỏng, lỗi ASR; không được pass.
- `not_applicable/unclear`: không tìm thấy tiếng nói; không được pass.

WER, tương đồng và transcript chỉ nằm trong evidence nội bộ, không gửi cho người dân.
`score` là tỷ lệ lỗi đọc (WER), không phải xác suất tấn công.
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

27 câu tự soạn, mỗi câu 8–12 âm tiết và đủ sáu thanh; ngân hàng phủ tr/ch, s/x,
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
Hai bộ sinh dùng bốn ca cố định: đúng, sai hoàn toàn, đổi một âm tiết (mẹ → bố),
đổi một thanh (mẹ → mè). Hai ca gần đúng dự kiến pass theo dung sai cố định,
không đồng nghĩa đọc nguyên văn; ASR có thể sửa lại thanh. Không chỉnh ngưỡng theo kết quả.
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

## VOICE-05 — căn câu và SyncNet (MVP đợt 2)

Registry đã có `SyncNetDetector` cho `lipsync`; cài cả extra `face` và `voice`.
Chỉ nạp file có sẵn trong `MODELS_DIR/ctc-aligner`, `syncnet`, `scrfd-10g`, kiểm
SHA-256 trước khi đọc checkpoint. Không gọi mạng hoặc remote code. Model/processor
CTC dùng local safetensors; SyncNet dùng `weights_only=True`, strict state dict.
Preload một lần; CPU mặc định. DEVICE=cuda/cuda:N/auto dùng GPU khi runtime có,
thiếu GPU thì lùi CPU và ghi log qua common.device, giữ chung khóa cache SCRFD.

`ForcedAligner.align(audio_path, prompt)` căn **câu phía server**, không nhận câu
ASR. Dùng CTC blank 0, wildcard `<star>`, bước 20 ms; chuẩn hóa tiếng Việt bằng
NFC/chữ thường/chuyển số như VOICE-04 rồi bỏ dấu/đ→d để khớp vocab Latin. Đây là
nhánh tiếng Việt, không thay thế romanizer đa ngôn ngữ. Không cắt VAD hoặc nối
thời gian. Cờ tạm: khoảng trống nội bộ >1 s, âm tiết <60 ms hoặc >1,2 s, wildcard
nội bộ >1 s. Evidence `splice_flags` là số nguyên, `splice_positions` chứa vị trí;
router đưa sang review ưu tiên cao khi số cờ dương. Cờ là gợi ý kiểm tra, không
chứng minh âm thanh đã bị sửa.

SyncNet stable LatentSync dùng 16 khung/25 fps, RGB 256² chuẩn hóa [-1,1], chỉ
nửa dưới; âm thanh mono 16 kHz, preemphasis 0,97, mel Slaney 80×52, FFT800/hop200.
Dùng lại hộp mặt SCRFD của PAD để cắt mặt, **khác bước affine theo landmark của
upstream**; chưa tuyên bố tương đương hay độ chính xác. Mọi cửa sổ hình/tiếng và
31 vị trí dò ±600 ms (gồm support FFT/preemphasis) đều nằm trong đoạn câu đã căn; tối đa 4 mốc cách đều,
không chọn mốc theo điểm. Đo trên timestamp từng khung, kể cả WebM/VFR; chọn frame
gần nhất khi resample25fps, thiếu timestamp/không tăng hoặc cách quá40ms → degraded.
Không nối các đoạn có khoảng nghỉ; giới hạn đọc120s/36.000frame.
Đoạn quá ngắn để dò đầy đủ → degraded; không có video/mặt → not_applicable;
thiếu prompt/audio, checksum sai hoặc inference lỗi → error. Kết quả được lưu nguyên trạng; full dùng các trạng thái này để review, MVP chỉ
tham khảo và không coi lipsync là điều kiện quyết định (ADR-0012 §6). Video bước giọng nói phải là video tải lên **lần đọc hiện
tại**, không lấy lại clip khuôn mặt ở bước trước.

Evidence gồm `av_offset_ms` (dương = tiếng trễ), `sync_confidence` (cosine tại
mốc gốc) và `best_offset_confidence`. Hằng số tạm theo ADR-0012 §5:
`score = clip(max(1 - confidence_at_zero, abs(offset_ms)/500), 0, 1)`;
điểm tăng là đáng nghi hơn, `prob_attack=None`. Không dùng cosine sau sửa lệch để
cho qua. Identity lipsync được lưu đúng version và luôn ghi **MVP — không dùng
cho báo cáo**. Đây không phải xác suất được kiểm chứng hay kết quả R.

```powershell
uv sync --all-packages --extra face --extra voice
$env:MODELS_DIR = 'D:\Projects\vericlue-store\models'
$env:ROUTER_PROFILE = 'mvp'
$env:USE_MOCK_MODELS = 'mixed'
# Không đọc media để lấy version; chỉ constructor/config:
$version = uv run --no-sync python -c "from vericlue_ml.voice.syncnet import SyncNetDetector; print(SyncNetDetector().version)"
uv run --no-sync python scripts/create_identity_calibrator.py --module lipsync --model-version $version
```

Code kiến trúc Apache-2.0, trọng số SyncNet OpenRAIL++, trọng số aligner CC-BY-NC
4.0; giấy phép code và weights là riêng. Nguồn ghim/văn bản giấy phép ở
`third_party/README.md`. Thử tay dùng clip local chỉ kiểm luồng, không fit/chia
tập/chọn ngưỡng, không phân phối lại video hoặc transcript.
Thử tay một bản ghi local có audio/video đồng hồ chung (prompt là câu thực sự
được đọc, lưu trong file UTF-8 local). Script tạo hai WAV biến thể trong thư mục
output, giữ nguyên bản gốc; không đọc danh mục hoặc tập split. Chạy BLAS một luồng
để tránh thiếu RAM trên máy đang mở nhiều phiên AI:

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
uv run --no-sync python scripts/smoke_voice_lipsync.py --video tmp/voice05-smoke/original.mp4 --audio tmp/voice05-smoke/original.wav --prompt-file tmp/voice05-smoke/prompt.txt --models-dir $env:MODELS_DIR --output-dir tmp/voice05-smoke/run --device cpu
```

Smoke nạp CTC rồi giải phóng trước khi nạp SyncNet để giảm RAM; `smoke.json` ghi
thời gian từng pha, không phải độ trễ API đầu–cuối. Không in hoặc lưu transcript
vào báo cáo; không commit media/JSON smoke. Nếu không có Torch CUDA thì chỉ báo
CPU, không suy ra số GPU. Ghi nguồn clip, lệnh, commit và kết quả thực trong bàn giao.

### Quyết định sau review — ADR-0012 §6

MVP vẫn preload/chạy lipsync nhưng chỉ dùng voice_challenge + voice_spoof để
quyết định. Kết quả lipsync giữ status/score/evidence gốc và nhãn chỉ tham khảo
cho người duyệt; lỗi, không có mặt/video, timeout, điểm cao hoặc thiếu calibrator
lipsync không tự chuyển phiên sang review. Cờ `splice_flags` vẫn có tác dụng sau
khi câu đọc khớp; đọc sai câu được cấp lần đọc lại trước khi xét cờ. Full giữ
lipsync là bước bắt buộc và vẫn review khi thiếu/lỗi/không áp dụng.

**Bước giọng cần trình duyệt có MediaRecorder WebM.** Hiện web ghi video và WAV
bằng hai bộ ghi khác nhau; độ lệch bắt đầu không biết trước nên chưa thể diễn giải
độ lệch SyncNet là dấu hiệu giả. Việc tiếp theo là ghi video kèm track audio trong
cùng một MediaRecorder (hoặc truyền độ lệch bắt đầu theo hợp đồng được duyệt),
thử trên câu thật và nghiệm thu GPU trong ngân sách trước khi dùng lipsync quyết định.
Câu ngắn dưới khoảng1,9s cũng chưa đủ cửa sổ dò lệch đầy đủ; CPU vượt trần4s sẽ timeout.

Hậu tố pipeline `voice05-v2` ghi nhận thay đổi tiền xử lý và cách tính sau review;
identity lipsync được sinh lại theo version này, không dùng artifact v1. Các cửa
sổ mel duy nhất được gộp theo lô, tối đa4 trên CPU/8 trên GPU, vẫn giữ thứ tự
mốc và offset. Giới hạn lô là hằng số có tên, không thay ngưỡng hoặc fit dữ liệu.

## Chặn PhoWhisper lặp token (18/10, VOICE-04)

ASR chỉ nhận thêm `expected_syllable_count` dạng số nguyên, không nhận nội dung
câu đề bài. Detector đếm âm tiết sau chuẩn hóa. Ngân sách mỗi đoạn giải mã là
`min(MAX_NEW_TOKENS=256, count * TOKENS_PER_SYLLABLE=8 + GENERATION_TOKEN_PADDING=16)`;
ngân hàng 8–12 âm tiết có 80–112 token. Gọi ASR không có số âm tiết dùng mặc định
128 token. Đây là giới hạn giải mã, không đổi ngưỡng so khớp hay chuẩn hóa/VAD.

`no_repeat_ngram_size=8` chặn lặp nguyên chuỗi tám token; không phạt mọi token
đã xuất hiện như repetition_penalty. Các tham số language/task/timestamps và
condition_on_prev_tokens giữ nguyên. Nếu sinh chạm trần ở bất kỳ chunk/fallback
nào, trả lỗi ASR thay vì xét đạt bằng transcript bị cắt; Whisper có thể bỏ EOS ở
đầu ra timestamp nên theo dõi bước decoder thô. Lỗi không bao giờ cho qua cổng
voice_challenge. Version wrapper tăng `voice04-v2`; không thay checkpoint hoặc
thresholds.yaml. Tối đa 120 s audio vẫn chia đoạn theo Whisper, không bỏ phần sau.

Replay hồi quy bốn TTS đã có (đúng/sai/gần đúng), không sinh audio hay quét dữ liệu:

```powershell
$env:MODELS_DIR='D:\Projects\vericlue-store\models'
$env:VOICE04_TTS_MANIFEST='D:\Projects\vericlue-store\data\eval\VOICE04\tts-mms\manifest.json'
$env:RUN_VOICE04_TTS_REGRESSION='1'
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'
.venv/Scripts/python.exe -m pytest ml/tests/test_voice_asr_local.py -k existing_local_tts
```

Test chạy cùng model CPU lần lượt với kwargs cũ và guard mới, yêu cầu transcript
khớp tuyệt đối ở cả bốn fixture. Mặc định bỏ qua vì cần model/audio ngoài repo.
Đây là test hồi quy luồng, không phải kết quả R hay phép đo tốc độ trên bộ audio
bị lặp ở demo.
