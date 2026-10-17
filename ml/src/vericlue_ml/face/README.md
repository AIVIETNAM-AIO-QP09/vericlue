# face/ — mô-đun khuôn mặt

## PAD: `pad.py` (FACE-01, bước 1 — bọc mô hình)

`FacePadDetector` (module `face_pad`): ảnh → SCRFD `det_10g` tìm mặt → MiniFASNet V2 → `prob_attack = 1 − p_real`.
Chạy bằng `onnxruntime` trực tiếp, KHÔNG thêm `uniface` vào dependency. Cài: `uv sync --all-packages --extra face`.

### Thẻ mô hình (chưa tinh chỉnh)

| Mục | Giá trị |
|---|---|
| Mô-đun | `face_pad` |
| PAD | MiniFASNet V2 (`minifasnet_v2.onnx`), nguồn `yakhyo/uniface-weights`, giấy phép trọng số Apache-2.0 theo `models/manifest.yaml`, SHA-256 `b32929ad…463907` |
| Bộ tìm mặt | SCRFD `det_10g.onnx` (cùng repo), **giấy phép nghiên cứu phi thương mại** (xem Q8 trong STATUS); GenD cũng dùng nó |
| Mã chép | tiền xử lý và giải mã từ `uniface` 4.0.0 (MIT) — ghi ở `third_party/README.md` |
| Hiệu chỉnh | CHƯA. `prob_attack` là xác suất thô của softmax; hiệu chỉnh ở FACE-04 / ROUT-* |
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

### Thử nhanh qua Swagger (chế độ `mixed`)

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
