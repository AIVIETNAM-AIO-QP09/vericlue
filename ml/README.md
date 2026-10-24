# ml — Bộ não phát hiện giả mạo (gói `vericlue_ml`)

**Phụ trách:** M3 (face/, presence/), M4 (voice/, forensic/provenance), M5 (router/, eval/)
**Trạng thái:** PLAT-03 đã khởi tạo giao diện, registry và mock; ROUT-01 bổ sung hiệu chỉnh xác suất.

## Cấu trúc

| Thư mục | Nội dung | Epic |
|---|---|---|
| `src/vericlue_ml/common/` | `ModuleResult`, hiệu chỉnh xác suất, đọc video/âm thanh | E0 |
| `src/vericlue_ml/mock/` | Mô-đun giả lập cho mọi bộ phát hiện | E0 |
| `src/vericlue_ml/face/` | PAD (MiniFASNet, FACE-01 bước 1 — xem `face/README.md`), GenD, SBI, gộp điểm theo khung | E4 |
| `src/vericlue_ml/presence/` | Phân tích ChromaPulse (độ trễ, mức khớp), chấm điểm CamProbe | E3 |
| `src/vericlue_ml/voice/` | AntiDeepfake, PhoWhisper, căn chỉnh câu, kiểm tra câu đọc, SyncNet | E5 |
| `src/vericlue_ml/router/` | Hợp nhất, cổng ngoài phạm vi, Learn-then-Test (MAPIE), chính sách | E6 |
| `src/vericlue_ml/forensic/` | Chia đoạn (`segment.py`), đọc media (`media.py`), chạy theo đoạn và kết luận (`pipeline.py`), quét nguồn gốc AudioSeal/C2PA (`provenance.py`); báo cáo ở `services/api` | E7 |
| `src/vericlue_ml/eval/` | Script sinh kết quả R1–R6 | E8 |
| `configs/models.yaml` | Mô hình nào, phiên bản nào, đường dẫn trọng số | |
| `configs/thresholds.yaml` | **Ngưỡng đã khóa** — chỉ sửa qua PR có kết quả đánh giá kèm theo | |
| `tests/` | Test (pytest) | |

## Quy ước bắt buộc

VOICE-10 ghép tùy chọn `--nes2net-python` vào Voice Lab: một bản thu RAM,
hai tab kết quả Qwen/NES2Net riêng. Worker giữ model trong runtime CPU riêng,
có timeout/hủy/đóng, chưa đưa điểm vào quyết định eKYC. Xem
[`qwen-asr-diagnostic.md`](../docs/architecture/qwen-asr-diagnostic.md).

VOICE-09 thêm NES2Net-X CPU diagnostic opt-in cho `voice_spoof`, checkpoint đầy
đủ XLS-R/head. Chỉ chấm 4 giây đầu, luôn degraded/unclear, chưa parity frontend
hoặc calibration tiếng Việt; không thay backend API. Xem
[`nes2net-diagnostic.md`](../docs/architecture/nes2net-diagnostic.md).

VOICE-07 thêm backend Qwen3-ASR-0.6B để kiểm nội dung câu đọc qua factory/CLI
diagnostic riêng. Cần runtime Transformers 5.13.0, không cài chung runtime mặt.
Chưa thay PhoWhisper/API và chưa đánh giá accuracy tiếng Việt; xem
[`qwen-asr-diagnostic.md`](../docs/architecture/qwen-asr-diagnostic.md).
VOICE-08 thêm `python -m vericlue_ml.eval.voice_lab` trong runtime Qwen riêng:
bấm thu micro → dừng/kiểm câu, audio trong RAM, hủy được và không chồng lượt.
Chỉ là công cụ nội bộ cho nhóm, chưa phải kiểm giọng AI hoặc luồng eKYC.

PRES-02 đã thêm diagnostic đo màu 5 vùng da + nền, dùng chung task MediaPipe
với mắt/quay đầu. Chưa hiệu chỉnh, luôn unclear và chưa đổi module ChromaPulse
trong full/MVP. Lệnh chạy, ý nghĩa R²/lag và giới hạn đồng hồ:
[`chromapulse-diagnostic.md`](../docs/architecture/chromapulse-diagnostic.md).

LIVE-02 đã có `gaze_tracking` và reader MediaPipe dùng chung cho dữ liệu mắt/tư
thế đầu. Đây là diagnostic riêng, chưa nằm trong profile full/MVP hoặc quyết định
API. Chạy bằng môi trường riêng để giữ dependency CUDA/OpenCV hiện có; xem
[`presence/README.md`](src/vericlue_ml/presence/README.md).

FLOW-04/FLOW-05 thêm diagnostic `head_turn` và `face_match` (LVFace-B + SCRFD).
Kiểm thứ tự quay đầu và tương đồng danh tính là hai kết quả riêng; chưa chứng
minh chiều sâu. Thiếu ngưỡng hiệu chỉnh thì so mặt luôn `degraded/unclear`.
Full vẫn 9 module, MVP vẫn 7; chưa bật hai module này trong quyết định HTTP.
`eval.video_face_match` đã ghép quay đầu → chọn/kiểm khung từ video → so mặt
trong RAM, không nhận ba ảnh query rời và không ghi khung ra đĩa.
Thêm `--with-gend` để chấm deepfake trên chính các khung đó; cần extra gend,
version/calibrator riêng cho ba góc, chưa ảnh hưởng luồng GenD cũ của API.
Thêm `--with-pad` để chấm PAD bằng FS-VFM-L FAS gốc FP32 (cùng extra face/gend).
Đây là diagnostic có version riêng, không thay MiniFASNet trong API. SCRFD
căn mặt khác MTCNN của dữ liệu gốc; chưa có hiệu chỉnh/độ chính xác cho biến thể này.
Lệnh chạy, định dạng artifact và giới hạn:
[`head-and-match.md`](../docs/architecture/head-and-match.md).
`--with-gaze` ghép thêm kiểm mắt bằng cùng reader MediaPipe: mắt và quay đầu
phải đạt trước khi chấm ba khung. Môi trường CPU dùng chung và lệnh kiểm
checkpoint tổng hợp: [`face-diagnostic-runtime.md`](../docs/architecture/face-diagnostic-runtime.md).
Thử trực tiếp webcam bằng cửa sổ nội bộ `python -m vericlue_ml.eval.webcam_lab`:
[`webcam-lab.md`](../docs/architecture/webcam-lab.md). Chỉ mở camera sau nút bấm,
không lưu ảnh/video và không thay UI sản phẩm.
Có nút **Thử ánh sáng · 6–8 giây**: dùng cùng task MediaPipe để đo màu trong
RAM, báo R²/lag biểu kiến với version đồng hồ host riêng, luôn unclear.

1. Mọi bộ phát hiện kế thừa giao diện `Detector` và trả `ModuleResult` (`docs/architecture/architecture.md` §3).
2. Mọi bộ phát hiện **phải có bản mock** cùng tên trong `mock/`.
3. Không hard-code đường dẫn: dùng `MODELS_DIR`, `configs/models.yaml`.
4. Tiền xử lý **đúng như repo gốc** của từng mô hình (ví dụ GenD: SCRFD, căn chỉnh 5 điểm, tỷ lệ 1,3, 224 px). Ghi rõ nguồn trong docstring.
5. Notebook chỉ để thử; code dùng thật phải chuyển vào `src/` và có test.
6. Kết quả đánh giá ghi kèm: commit, phiên bản mô hình, bộ dữ liệu, số mẫu.


## Mock hay mô hình thật (`USE_MOCK_MODELS`)

| Giá trị | Hành vi |
|---|---|
| `true` (mặc định) | mọi module dùng mock |
| `false` | mọi module dùng mô hình thật; module chưa có mô hình thật thì `NotImplementedError` |
| `mixed` | module có trong `_REAL_FACTORIES` (registry) dùng thật, còn lại mock |

Hiện có thật: `face_pad`, `face_deepfake` (GenD), `quality`, `camprobe`, `voice_challenge` và
`voice_spoof`; mixed cần `uv sync --all-packages --extra face --extra gend --extra voice` (CPU) hoặc
`--extra cuda` (GPU, thay cho cả ba; xem `src/vericlue_ml/face/README.md`).
`/healthz` luôn trả `mock_models` kiểu bool (`true` khi còn module mock, kể cả `mixed`).
Thử nhanh qua Swagger: xem `src/vericlue_ml/face/README.md`.

## Hiệu chỉnh xác suất (ROUT-01)

`common/calibration.py` dùng nhãn **0 = người thật, 1 = tấn công**; điểm thô càng
cao càng giống tấn công. AUC < 0,5 trên dữ liệu fit gây `CalibrationError` để phát
hiện nhầm chiều; không tự đảo dấu điểm.

Tập calib được chia **theo người**, không giao nhau, thành:
- **calib_fit:** chỉ để hiệu chỉnh xác suất và học trọng số hợp nhất.
- **calib_ltt:** chỉ để chọn ngưỡng LTT; ROUT-01 không đọc hay fit trên phần này.

`fit(calib_fit, ...)` nhận `CalibFit` có `scores`, `labels`, `subject_ids`, `dataset`
và `split="calib_fit"`. Caller phải lấy đúng phần đã chia, không truyền calib_ltt
hay test dưới tên calib_fit. Tiền xử lý ảnh/âm thanh do detector thực hiện trước;
calibration chỉ nhận điểm, không đổi tiền xử lý và không tải trọng số.

Chọn phương pháp bằng **GroupKFold theo subject**, mặc định 5 phần (ít người hơn
thì dùng số phần bằng số người, tối thiểu 2). Mỗi phần fit phải có cả hai lớp,
không đủ thì báo lỗi để bổ sung dữ liệu hoặc chọn số phần phù hợp. So sánh log-loss
trên toàn bộ dự đoán ngoài fold (OOF, trọng số theo số mẫu). Chỉ thử/chọn isotonic
khi toàn calib_fit có **ít nhất 100 mẫu mỗi lớp**, và chỉ chọn khi log-loss OOF
thấp hơn Platt **ít nhất 2% tương đối**. Trường hợp còn lại dùng Platt. Sau khi
chọn, fit lại phương pháp thắng trên **toàn bộ calib_fit** được đưa vào.

Platt dùng logistic một chiều, chuẩn hóa score lúc fit, không cân bằng lớp để giữ
tiền nghiệm quan sát. JSON lưu slope/intercept đã quy đổi về score gốc. Isotonic
đơn điệu tăng, nội suy tuyến tính và chặn ngoài miền score. Mọi xác suất hiệu chỉnh
được cắt trong **[1e-4, 1-1e-4]**, epsilon cố định cũng được ghi vào JSON.

Artifact ở `ml/configs/calibrators/<module>/<version>.json` (không dùng `models/`).
`CalibrationStore(root=...)` nhận root tùy cấu hình; hoặc dùng `CALIBRATORS_DIR`,
mặc định suy ra thư mục configs từ vị trí gói. Khi đóng gói/triển khai cần chuyển
artifact cùng cấu hình và truyền root tương ứng. Ký tự phiên bản không hợp lệ
trong tên file được percent-encode (ví dụ `v1:a/b` → `v1%3Aa%2Fb.json`). Store cache
calibrator theo module/version; dùng store mới khi triển khai artifact thay thế.

JSON có module, model_version, method, parameters, epsilon, n_pos, n_neg,
log-loss/ECE/Brier trước và sau, bảng reliability trước và sau, ngày UTC, commit,
dataset, split, số fold và log-loss của các phương pháp. `prior_attack` tính
**π = n_pos / (n_pos + n_neg)** từ calib_fit cho FOR-04, không phải tỷ lệ tấn công
trong dân số. Caller cung cấp commit thật của phiên chạy và tên bộ dữ liệu;
không ghi số liệu tổng hợp như kết quả trên dữ liệu thật.

Chỉ số trước/sau trong artifact đều trên cùng mẫu: trước là **điểm thô cắt vào
[epsilon, 1-epsilon]**, sau là dự đoán **OOF**, không phải dự đoán fit lại trên dữ
liệu học. Khi score là logit hay thang điểm khác [0,1], số đo trước chỉ là baseline
`clipped_raw_score`, không có nghĩa điểm thô vốn đã là xác suất. ECE dùng 10 bin
đều, bin trái đóng/phải mở, bin cuối gồm 1; bin rỗng có giá trị None. Brier là
trung bình `(p-y)^2`. EVAL-01 nhập `ece` từ đây, không định nghĩa lại.

```python
from vericlue_ml.common.calibration import CalibFit, CalibrationStore, fit, reliability_markdown

# scores, labels, subject_ids chỉ lấy từ calib_fit của cùng module/version.
data = CalibFit(scores=scores, labels=labels, subject_ids=subject_ids, dataset=dataset_name)
artifact = fit(data, module="face_pad", model_version=model_version, commit=git_commit)
store = CalibrationStore()  # Khởi tạo/nạp ở lifespan, tái dùng giữa các request.
store.save(artifact)
print(reliability_markdown(artifact.after_reliability))
calibrated_result = store.apply(module_result)
```

Hồ sơ full bắt buộc calibrator **face_pad, face_deepfake, voice_spoof, lipsync**; MVP chỉ bắt buộc ba module đầu. Miễn
**quality, chromapulse, camprobe, voice_challenge, provenance**, và mọi phiên bản
bắt đầu bằng `mock@` (fixture kịch bản PLAT-03). `store.apply` giữ score và các
trường hợp đồng, chỉ thay prob_attack trên bản sao. Kết quả không `ok` của module
bắt buộc được giữ nguyên status và xóa prob_attack. Thiếu/hỏng/sai phiên bản
calibrator hoặc thiếu score → **ném CalibrationError**, không fallback sang điểm
thô hay prob_attack có sẵn. **Lớp gọi phải bắt lỗi và trả ModuleResult status=error**
(với error_code hiện có, ví dụ E_INTERNAL); không được chuyển lỗi thành pass.
ROUT-01 cung cấp hàm dùng chung, không thay registry hay mock hiện tại; detector
thật/lớp orchestration phải gọi hàm này khi được triển khai.

`reliability_table` trả dữ liệu bin; `reliability_markdown` sinh bảng Markdown.
PNG chỉ dùng `plot_reliability(rows, destination)` khi cài extra tùy chọn:
`uv sync --all-packages --extra eval`. Matplotlib import lười, CI/test mặc định
không cần matplotlib. Không commit dữ liệu, trọng số hay PNG phát sinh; artifact
calibrator số và metadata có thể được review trong configs.

## Khung đánh giá EVAL-01

Dùng `vericlue_ml.eval.metrics` và `vericlue_ml.eval.report` cho các kết quả chung.
Hướng dẫn CSV, công thức, hai dòng BPCER@APCER 5%, bootstrap theo người, loại mẫu
không ok và CLI: [README của eval](src/vericlue_ml/eval/README.md).

predictions.csv bắt buộc `sample_id,subject_id,label,attack_type,prob_attack,status,module,model_version`.
Các cột metadata `path,source,region,score,compression` được giữ khi có; score không
thay xác suất. ECE/Brier nhập trực tiếp từ calibration, không định nghĩa lại.
Nghiệm thu EVAL-01 bằng tổng hợp có đáp án biết trước; xác nhận R1–R4 thật dùng
khung chung tại FACE-01/VOICE-01/ROUT-05. Không dùng calib_ltt/test để chọn cấu hình.

## Kiểm câu đọc VOICE-04

PhoWhisper CPU offline, VAD và so khớp hai lớp: [hướng dẫn voice](src/vericlue_ml/voice/README.md).
Thư viện inference nằm trong extra `voice`; mock/normalization test không cần model.

### Preload trong API (PLAT-08)

VoiceChallengeDetector.preload() gọi PhoWhisperASR.preload() dưới khóa, nạp weights
local một lần trước request; không nhận audio/prompt. API truyền models_dir từ
Settings/.env; thay root sau khi đã nạp bị từ chối để tránh trộn phiên bản.
ML_MODELS_CONFIG trỏ models.yaml khi chạy wheel ngoài source tree (Dockerfile API
đã cấu hình). Không đổi tiền xử lý/threshold/ModuleResult; lỗi preload được API
lưu là unavailable tới restart và báo health degraded.


## TrustRouter (ROUT-02)

`router.policy.TrustRouter` đọc snapshot `ml/configs/thresholds.yaml` khi API khởi động;
`THRESHOLDS_CONFIG` cho phép chọn file khác. Thiếu/hỏng YAML làm startup báo lỗi, không lấy
ngưỡng môi trường cũ làm mặc định. `provisional: true`: chưa có bảo đảm LTT trước ROUT-03.
Mỗi giá trị có nguồn trong YAML; phiên bản quyết định là `sha256:` + SHA-256 byte file gốc.
Khởi động lại API sau khi đổi file; không reload giữa các request.

Thứ tự: phiên/thời gian hợp lệ → quality → chromapulse/camprobe → OOD nếu được cung cấp
→ hiệu chỉnh từng module → fusion mặt. Quality fail được retry hai lần rồi review,
trước khi xét face degraded; chính quality error/degraded luôn review. Module bắt buộc
thiếu, error, degraded, timeout hoặc busy tại bước đã tới không bao giờ cho pass.
Hiện fusion là **max xác suất đã hiệu chỉnh**, không có trọng số học giả:
Λ ≤ face.b thì pass; Λ ≥ face.a thì review; vùng giữa yêu cầu đọc câu.
Giọng dùng `voice.spoof_threshold` riêng, ≤ ngưỡng thì pass. VOICE-04 chỉ là cổng nội dung:
score WER không phải xác suất và không vào fusion. Cờ cắt ghép dương → review ưu tiên cao; cờ không phải số/không hữu hạn → review;
không có cờ thì giữ absent, không tạo số 0 hay feature thay thế (chờ VOICE-05).
Sai câu cho đọc lại một lần; chưa rõ/lỗi chuyển review.

`FusionFit(..., split="calib_fit")` và `fusion.fit(calib_fit, commit=...)` chuẩn bị cho
học logistic sau DATA-03. Đầu vào phải là **calib_fit đã chia theo subject**, chỉ gồm
`prob_attack:<module>` và quality có tên `quality:<module>:<key>`, đủ module/version,
nhãn, subject_id, dataset. Không dùng score thô, WER, calib_ltt hay test. StandardScaler
và logistic có thiết lập cố định, không chọn mô hình/ngưỡng. Artifact JSON ghi thứ tự
feature, scaler, hệ số thật, nguồn, ngày, commit và số mẫu hai lớp; predict/load kiểm
kích thước và giá trị. Artifact học được **chưa tự kích hoạt**: cần dữ liệu thật và
quyết định cấu hình được duyệt. Unit test chỉ fit dữ liệu tổng hợp, artifact ở thư mục tạm.
SBI chưa có ModuleResult riêng, OOD (ROUT-04), quality feature thật và splice (VOICE-05)
không được tự bịa hoặc điền số 0; tích hợp khi module tương ứng cung cấp đúng hợp đồng.

`Decision.results` chứa bản kết quả sau calibration để API lưu; không sửa input.
Thiếu calibrator đúng module/version → bản kết quả error, prob_attack=None → review.
Mock `mock@` được miễn theo ROUT-01. Router chỉ đọc counters, không tăng lượt thử;
SessionFlow của API giữ counters/challenge/prompt/khóa hàng và persist snapshot quyết định.


## VOICE-01 — AntiDeepfake wrapper (R3 chưa làm)

`voice.antispoof.AntiDeepfakeDetector` nạp MMS-300M local từ
`MODELS_DIR/antideepfake-mms300m`; config qua ML_MODELS_CONFIG/models.yaml.
Factory thật voice_spoof được cache, không nạp weights/importTorch khi importregistry.
`preload()` kiểm SHAconfig vàsafetensors rồi ánh xạ Fairseq→HF trong RAM, zero missing
và strictshape; chỉ cho dư các thành phần pretraining đã liệt kê. Không gọi mạng,
không sửa weights, không randomhead/môhình/mockfallback. API truyền Settings.models_dir
vào preload trước khi nhận request; native dùng MODELS_DIR/DEVICE hoặc truyền
models_dir/device trực tiếp. MODELS_DIR tương đối (kể cả mặc định models) được
giải theo gốc repo, không theo CWD. Đổi thư mục sau khi model đã nạp cần restart. Giấy phép weights CC-BY-NC-SA-4.0 chỉ nghiên cứu.

Cài optionalvoice: `uv sync --all-packages --extra voice`. Torch CPU là mặc định;
GPU cần bản TorchCUDA phù hợp thiết bị, DEVICE=cuda sẽ dùng fp16/batch1 từngwindow.
CPUfloat32 được hỗ trợ; không tự đổiGPU/CPU khi nạp lỗi. Decoder mono16k, WebRTC VAD
trimngoài, window4s/hop1s/tail, meanlogits→softmaxfake0. Im lặng hoặc <1s trước/sau
trim là not_applicable; lỗi decode/model là error. `score` là rawscore;
`prob_attack=None` để CalibrationStore/TrustRouter xử lý theo version.

Evidence window_scores chứa logits/rawscore/start_s/end_s theo file gốc. Không có
score/transcript đưa sang citizen response. Xem [model card](model_cards/antideepfake-mms300m.md).
Parity CPU đã đạt với Fairseq0.12.2:4file/9window, max abs logits2.956390380859375e-05≤1e-4;
chi tiết môi trường/nguồn trong model card. Phải kiểm lại khi đổi backend/mapping.
Unit test dùng fakebackend/numpytensors, không GPU/checkpoint/network; smoke local
4file chỉ kiểm chiều, không phải R3 và không dùng chọn ngưỡng/mô hình.


### Cặp phiên bản Torch / TorchAudio

Môi trường CPU kiểm wrapper dùng `torch==2.14.1` + `torchaudio==2.11.0`.
Theo [bảng tương thích chính thức](https://docs.pytorch.org/audio/master/installation.html#compatibility-matrix),
TorchAudio 2.11 dùng stable ABI, hỗ trợ Torch từ 2.11 trở lên. Với các bản cũ,
phải chọn đúng cặp trong bảng (ví dụ 2.6.0/2.6.0), không ghép tùy ý. Cài cùng
backend CPU/CUDA theo hướng dẫn PyTorch; CUDA chưa được nghiệm thu ở PR này.
Môi trường Fairseq tham chiếu riêng dùng Torch/TorchAudio 2.2.2/2.2.2 (CPU).

Chế độ mixed hiện dùng face_pad, voice_challenge, voice_spoof và lipsync thật:
`uv sync --all-packages --extra face --extra voice`. Thiếu model/dependency vẫn
error/degraded, không tự đổi mock; voice_spoof còn cần calibrator đúng phiên bản.


## Hồ sơ MVP (ROUT-01, ADR-0012)

`ROUTER_PROFILE=full` mặc định giữ nguyên chính sách và tập module hiện có.
`ROUTER_PROFILE=mvp` chỉ chạy/preload `quality`, `face_pad`, `face_deepfake`,
`camprobe`, `voice_challenge`, `voice_spoof`, `lipsync`; không chạy ChromaPulse hay
provenance. Đợt 2 theo ADR-0012 §5 đưa SyncNet trở lại bước giọng nói. Presence chỉ
dùng CamProbe; mặt lấy max xác suất PAD/deepfake; giọng phải qua câu thử thách,
chống giọng tổng hợp và cổng cắt ghép. Khớp môi chỉ tham khảo ở MVP (ADR-0012 §6).
Ngưỡng trong `thresholds.yaml` không đổi. Thiếu/lỗi/degraded hoặc thiếu calibrator
đúng phiên bản ở bước bắt buộc → review. Metadata quyết định MVP ghi
`router_profile`; hash cấu hình ngưỡng vẫn là hash YAML.

Chạy thật: đặt `ROUTER_PROFILE=mvp`, `USE_MOCK_MODELS=false`, `MODELS_DIR` tới kho
chung và cài các extra face/gend/voice (hoặc `cuda` cho máy GPU). Cần đủ wrapper thật và calibrator để có thể pass;
module chưa sẵn sàng sẽ hiện trong health degraded. `USE_MOCK_MODELS=true` vẫn
chạy được với MVP để test. MVP cần calibrator PAD, deepfake và voice_spoof; full
còn bắt buộc lipsync. Mock `mock@` vẫn được miễn calibrator. Theo ADR-0012 §6,
lipsync trong MVP chỉ tham khảo: vẫn chạy và lưu kết quả cho người duyệt, nhưng
thiếu/lỗi/not_applicable/timeout hoặc điểm cao không quyết định phiên. Bước giọng
quyết bằng voice_challenge + voice_spoof. Đọc sai câu được đọc lại trước khi xét
cờ cắt ghép; khi câu khớp mà có cờ thì review ưu tiên cao. Full vẫn bắt buộc lipsync. Bước giọng cần trình duyệt có MediaRecorder WebM.

### Identity cho MVP — không cần dữ liệu

Theo ADR-0012 mục 2 cập nhật 18/10, PAD dùng artifact `method=identity`:
`prob_attack = clip(score, 1e-4, 1-1e-4)`. Voice_spoof cũng dùng identity theo duyệt PR #28; Platt cũ được thay vì
làm ngưỡng giọng lỏng hơn trên tập fit nhỏ. GenD dùng identity ngay khi wrapper được merge và chốt model_version; không cần
chia tập hoặc fit thêm để xem luồng chạy. Hôm nay không chạy công việc dữ liệu.

```powershell
uv run --no-sync python scripts/create_identity_calibrator.py --module face_pad --model-version "minifasnet-v2@bfcc7d48+scrfd-10g@bfcc7d48"
# Khi FACE-02 chốt version runtime sau preload (không dùng tên generic trong constructor):
uv run --no-sync python scripts/create_identity_calibrator.py --module face_deepfake --model-version "<model_version chính xác của wrapper GenD>"
```

Version PAD lấy từ `pad.py` và hai revision trong `models/manifest.yaml`, không
cần nạp mô hình hoặc ảnh. CLI chỉ đọc mã/config/JSON calibrator, không mở dữ liệu,
không chạy detector. Commit implementation trước khi sinh để JSON ghi commit
thực thi. Lưu bằng `CalibrationStore.path`; dấu `+` trong version được encode `%2B`.
CLI mặc định từ chối thay artifact đã fit (Platt/isotonic) bằng identity. Voice
đã được thay một lần theo quyết định trưởng nhóm; scripts/fit_calibrators.py giữ
lại để hiệu chỉnh học ở giai đoạn sau. Trên Windows, chạy `git config core.longpaths true`
tại gốc repo trước checkout/fetch vì tên calibrator có thể vượt MAX_PATH.

`IdentityCalibrator` là artifact riêng, được `CalibrationStore` nhận như calibrator
thường: `provisional=true`, ghi chú **MVP — không dùng cho báo cáo**, `n_pos=n_neg=0`,
`dataset=not_fitted`, `split=none`, `metrics_scope=not_evaluated`. Không có số đo
before/after hoặc CV giả; đọc `prior_attack` sẽ báo lỗi vì chưa có tiền nghiệm.
`Calibrator` Platt/isotonic giữ schema và kiểm định cũ. Router vẫn cần đúng
module/version; thiếu artifact, lỗi/degraded/not_applicable hoặc score không hữu
hạn vẫn không được pass. Ngưỡng tạm giữ nguyên; identity chỉ giúp cắm mô hình để
xem luồng, không phải xác suất đã được kiểm chứng hay kết quả R.

### Hiệu chỉnh học từ dữ liệu — công việc thay thế sau MVP

Phần dưới mô tả công cụ đã có; không chạy trong cập nhật MVP hôm nay.
Fit calibrator bằng detector thật qua registry:

```powershell
uv run python scripts/fit_calibrators.py --module voice_spoof --data-dir D:\Projects\vericlue-store\data --models-dir D:\Projects\vericlue-store\models
uv run python scripts/fit_calibrators.py --module face_pad --datasets zalo2022 --data-dir D:\Projects\vericlue-store\data --models-dir D:\Projects\vericlue-store\models
uv run python scripts/fit_calibrators.py --module face_deepfake --datasets wilddeepfake --data-dir D:\Projects\vericlue-store\data --models-dir D:\Projects\vericlue-store\models
```

Chỉ đọc `splits/<dataset>/calib_fit.csv`. Tên dataset đổi bằng `--datasets`.
Voice mặc định VSASV, ViMD, MLAAD-vi: dương chỉ TTS/VC, replay bị loại trước inference.
CV dùng connected `group_id` đã chia, fallback `dataset:subject_id`; thiếu nhóm thì
dừng. PAD video lấy khung giữa, tương tự ảnh người dùng chụp; GenD video dùng wrapper
gốc. Mẫu không có score với not_applicable/E_LOW_QUALITY được thống kê loại theo
dataset/lớp/lý do trong provenance. Mẫu được fit phải ok, đúng module/version và có
score hữu hạn; error/degraded hoặc not_applicable khác dừng toàn lượt. Dưới 100 mẫu
mỗi lớp chỉ Platt theo hàm fit hiện có. Runtime vẫn review khi thiếu bằng chứng.

Commit implementation trước khi chạy (script từ chối working tree bẩn). Artifact
JSON ghi `provisional: true`, commit thực thi, n_pos/n_neg, hash manifest, cách lấy
ảnh và số mẫu loại trong dataset provenance; version lấy trực tiếp detector.
JSON được commit vào `ml/configs/calibrators/`. Chỉ số trong artifact là OOF trên
calib_fit, không phải kết quả R hay bảo đảm LTT. Hiệu chỉnh đã học sẽ thay identity
ở giai đoạn đánh giá sau; không chặn MVP. Thiếu calibrator ở bước được chạy thì review.

`LIPSYNC_DEVICE=cpu` (mặc định; `cpu | cuda | auto`) chọn riêng thiết bị cho
SyncNet, CTC aligner và SCRFD của nhánh lipsync. `DEVICE` vẫn chọn thiết bị của
quality, PAD, GenD, PhoWhisper và AntiDeepfake. Ví dụ GPU 6 GB:
`ROUTER_PROFILE=mvp USE_MOCK_MODELS=false DEVICE=cuda LIPSYNC_DEVICE=cpu`.
Lipsync chỉ cấu hình lúc khởi động, nạp trọng số offline ở lần đầu có video,
audio và câu đề bài; không giữ model CTC/SyncNet trên GPU lúc preload. Lần đầu
có thể timeout trong ngân sách 4 s; kết quả vẫn là lỗi rõ ràng, MVP chỉ tham khảo,
full vẫn không coi lỗi là đạt. Đường dẫn/thiết bị cố định từ lần cấu hình đầu;
đổi cấu hình hoặc thử lại sau lỗi nạp cần khởi động lại tiến trình.
