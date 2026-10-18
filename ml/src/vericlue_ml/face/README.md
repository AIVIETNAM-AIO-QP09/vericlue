# face/ — mô-đun khuôn mặt

## PAD: `pad.py` (FACE-01, bước 1 — bọc mô hình)

`FacePadDetector` (module `face_pad`): ảnh → SCRFD `det_10g` tìm mặt → MiniFASNet V2 → `score = 1 − p_real`; `prob_attack` để trống (xác suất sau hiệu chỉnh do TrustRouter tính từ `score`).
Chạy bằng `onnxruntime` trực tiếp, KHÔNG thêm `uniface` vào dependency. Cài: `uv sync --all-packages --extra face`.

### Thẻ mô hình (chưa tinh chỉnh)

| Mục | Giá trị |
|---|---|
| Mô-đun | `face_pad` |
| PAD | MiniFASNet V2 (`minifasnet_v2.onnx`), nguồn `yakhyo/uniface-weights`, giấy phép trọng số Apache-2.0 theo `models/manifest.yaml`, SHA-256 `b32929ad…463907` |
| Bộ tìm mặt | SCRFD `det_10g.onnx` (cùng repo), **giấy phép nghiên cứu phi thương mại** (xem Q8 trong STATUS); GenD cũng dùng nó |
| Mã chép | tiền xử lý và giải mã từ `uniface` 4.0.0 (MIT) — ghi ở `third_party/README.md` |
| Hiệu chỉnh | CHƯA. `score` là điểm thô (1 − p_real của softmax); `prob_attack` luôn trống; calibrator `face_pad` thuộc ROUT-01 / FACE-04 |
| Dữ liệu huấn luyện | không tinh chỉnh ở bước này |
| Kết quả R1 | CHƯA có (chờ DATA-03 ảnh + EVAL-01) |

### Hành vi

| Tình huống | `status` | `error_code` |
|---|---|---|
| Một mặt | `ok` | — |
| Không có mặt | `not_applicable` | `E_NO_FACE` |
| ≥ 2 mặt cỡ tương đương (mặt nhỏ hơn có diện tích ≥ 0,5 mặt lớn nhất) | `degraded` | `E_MULTI_FACE` |
| Mặt phụ nhỏ hơn rõ rệt (< 0,5 diện tích) | `ok`, dùng mặt lớn nhất | — |
| Thiếu ảnh hoặc ảnh hỏng | `error` | `E_DECODE` |
| Thiếu trọng số, lỗi nạp, lỗi bất kỳ | `error` | `E_INTERNAL` |
| Sai SHA-256 trọng số | `error` | `E_INTEGRITY` |

`SECOND_FACE_AREA_RATIO = 0,5` là hằng số trong `pad.py`, không nằm trong `thresholds.yaml`.
Mã **không gọi mạng**: thiếu file hoặc sai SHA-256 là `error`.

### Trọng số và thiết bị

- Đọc từ `MODELS_DIR/minifasnet/minifasnet_v2.onnx` và `MODELS_DIR/scrfd-10g/det_10g.onnx`, kiểm SHA-256 theo `models/manifest.yaml`. Tải bằng `scripts/download_models.py`.
- Mặc định dùng CUDA nếu `onnxruntime-gpu` có sẵn (cài `onnxruntime-gpu` thay cho `onnxruntime`), ngược lại CPU. `DEVICE=cpu` ép CPU.

## GenD: `gend.py` (FACE-02, bước 1 — bọc mô hình)

`FaceDeepfakeDetector` (module `face_deepfake`): video (hoặc `images` nếu không có video) → N khung đều nhau → SCRFD `det_10g` → mặt lớn nhất → căn 5 điểm (tỷ lệ 1,3) → 224 px, mean/std CLIP → GenD (CLIP ViT-L/14 + đầu tuyến tính) → softmax → `p_fake` mỗi khung. `score = max(mean, top25_mean)`; `prob_attack` để trống chờ hiệu chỉnh (ROUT-01).

| Mục | Giá trị |
|---|---|
| Số khung | `EKYC_FRAMES = 8`; giám định 32 (`metadata["mode"] = "forensic"`, `FORENSIC_FRAMES`) |
| Đọc video | tuần tự bằng `cv2` (`frames.py`), đếm khung thật bằng `grab()` — không tin số khung trong webm |
| Trọng số | `MODELS_DIR/gend-clip-l14/{config.json,model.safetensors}`, `MODELS_DIR/clip-vit-large-patch14/{config.json,preprocessor_config.json}`, `MODELS_DIR/scrfd-10g/det_10g.onnx`; kiểm SHA-256 theo manifest; không gọi mạng |
| Phụ thuộc | Extra `gend` (torch, transformers, safetensors, pillow) — KHÔNG nằm trong `face` để CI không kéo torch. Máy chạy GenD: `uv sync --all-packages --extra face --extra gend` (torch CPU từ PyPI) hoặc `--extra cuda` (GPU, xem dưới). Thiếu torch thì `face_deepfake` ra `error`, không bao giờ là đạt |
| Phiên bản mô hình | `gend-clip-l14@<rev>+clip@<rev>+scrfd-10g@<rev>+agg-maxmeantop25-v1` — hậu tố `agg-…` là cách gộp điểm khung; đổi cách gộp thì đổi hậu tố (calibrator khóa theo version). Số khung (8/32) nằm ở evidence |
| Hiệu chỉnh | CHƯA. `score` là điểm thô; calibrator `face_deepfake` thuộc ROUT-01 |

| Tình huống | `status` | `error_code` |
|---|---|---|
| Đủ khung có mặt | `ok` | — |
| Không có mặt ở mọi khung | `not_applicable` | `E_NO_FACE` |
| Ít khung có mặt hơn `min(MIN_VALID_FRAMES = 3, số khung đã lấy)` | `degraded` | `E_LOW_QUALITY` |
| Không có video lẫn ảnh, video/ảnh hỏng hoặc không mở được | `error` | `E_DECODE` |
| Thiếu trọng số, lỗi nạp, lỗi bất kỳ | `error` | `E_INTERNAL` |
| Sai SHA-256 trọng số | `error` | `E_INTEGRITY` |

Evidence: `frame_scores` (timeseries `{frame, p_fake}`), `mean`, `top25_mean`; `quality.frames_sampled/frames_used`.

**Tốc độ và thiết bị:** `DEVICE=cpu|cuda|auto` (Settings) được truyền tới mọi detector; yêu cầu GPU mà không có thì tự lùi CPU và ghi log `device_fallback`. Chạy CPU, torch dùng tối đa `GEND_CPU_THREADS = 4` luồng. Trên CPU GenD vượt ngân sách detector 4 s (`detector_timeout_seconds`) nên MVP demo chạy GPU. Muốn đo trên máy mình: `ml/scripts/bench_mvp_latency.py` (thử tay, không phải R6); số đo thử ngày 18/10 ghi trong bàn giao FACE-02.

### Chạy bằng GPU (máy demo Windows, RTX)

```powershell
uv sync --all-packages --extra cuda            # torch/torchaudio cu130 + onnxruntime-gpu; thay face/gend/voice
$env:DEVICE = "cuda"                            # hoặc DEVICE=cuda trong .env
uv run --no-sync uvicorn vericlue_api.main:app --app-dir services/api/src
```

Cần driver NVIDIA hỗ trợ CUDA 13 (kiểm `nvidia-smi`). Mặc định và CI vẫn là CPU; `uv lock --check` không đổi. `uv run` thường sẽ đồng bộ lại về extra mặc định và gỡ bản GPU — dùng `--no-sync` (hoặc `UV_PROJECT_ENVIRONMENT=.venv-gpu` để giữ một venv riêng cho GPU).

## Chất lượng ảnh phía server: `quality.py` (MVP, ADR-0012)

`QualityDetector` (module `quality`): ảnh đầu tiên của phiên (không có ảnh thì khung giữa video) → SCRFD (dùng chung phiên onnxruntime với `face_pad`/`face_deepfake`) → mặt lớn nhất → cỡ mặt, độ nét (phương sai Laplacian), độ sáng, yaw thô, lệch tâm. `gate = pass | fail`; `fail` kèm `error_code` và evidence `retry_hint` (mã hợp đồng: `MOVE_CLOSER`, `MOVE_BACK`, `MORE_LIGHT`, `HOLD_STILL`, `FACE_CENTER`). Không có mặt → `gate=fail` `E_NO_FACE` (chụp lại, hết lượt thì router đưa sang review); lỗi hạ tầng → `error`. Ngưỡng là hằng số TẠM trong file (`MIN_FACE_PX`, `MIN_ILLUM`, `MIN_SHARPNESS`, `MAX_YAW_DEG`, …), chờ ROUT-03; không nằm trong `thresholds.yaml`. Quá sáng/chói nắng chưa có mã `retry_hint` trong hợp đồng nên chưa chặn (chỉ ghi `illum`).

### Thử nhanh qua Swagger (chế độ `mixed`)

> `mixed` là chế độ **demo/phát triển**, không phải chế độ an toàn: module mock vẫn trả kết quả giả. Không dùng để đánh giá hay báo cáo số liệu.

```bash
uv sync --all-packages --extra face
# .env: MODELS_DIR=<thư mục models>   USE_MOCK_MODELS=mixed
uv run uvicorn vericlue_api.main:app --reload --app-dir services/api/src   # http://localhost:8000/docs
```

API cần một DB khi khởi động (xem "DB, migration" trong `services/api/README.md`; chạy máy riêng có thể dùng `DATABASE_URL=sqlite:///./tmp/dev.db` rồi `uv run alembic -c services/api/alembic.ini upgrade head`).

Mở `http://localhost:8000/docs`: `POST /v1/sessions` → `POST /v1/sessions/{id}/media` (tải ảnh mặt, kèm token Bearer) → `POST …/finalize`. Với `mixed`, `face_pad` chạy thật, các module khác vẫn mock theo `X-Mock-Scenario`. `/healthz` cho biết module nào preload lỗi (`failed_modules`).
**Lưu ý — phiên sẽ ra `review`:** TrustRouter (ROUT-02) chỉ dùng xác suất đã hiệu chỉnh và KHÔNG có đường lùi. `face_pad` thật chưa có file hiệu chỉnh `ml/configs/calibrators/face_pad/<model_version>.json` (cần dữ liệu `calib_fit` của DATA-03 và ROUT-01), nên router trả `face_pad` là `error` và `finalize` ra `review` cho mọi ảnh. Đó là hành vi an toàn đúng thiết kế, không phải lỗi. Điểm thô vẫn xem được ở bàn duyệt: tạo quyết định ban đầu rồi `GET /v1/review/cases/{id}/ai`, mục bằng chứng `p_real` của `face_pad`.
Người dân chỉ thấy `pass | retry | review | voice_challenge`.
Chế độ `mixed` cũng nạp `voice_challenge` thật; nếu chưa cài `--extra voice` hoặc chưa có PhoWhisper thì module đó vào `failed_modules` (`/healthz` báo `degraded`).
