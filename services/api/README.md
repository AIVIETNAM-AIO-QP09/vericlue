# services/api — Máy chủ API (FastAPI)

**Phụ trách:** M5
**Trạng thái:** API v1 chạy với dữ liệu mock (PLAT-03 khung, **PLAT-04** endpoint + hợp đồng). Token, DB, orchestrator và luật quyết định đầy đủ còn là phần TẠM, xem "Phần tạm" bên dưới.

## Trách nhiệm

- Phiên eKYC: tạo phiên, cấp thử thách màu, nhận media và tín hiệu, gọi bộ não, trả kết quả.
- Bàn duyệt: danh sách ca, hồ sơ bằng chứng, ghi quyết định vào nhật ký chuỗi băm.
- Giám định: nhận file, chạy phân tích theo đoạn, sinh và ký báo cáo.

## Quy ước

- Code trong `src/vericlue_api/`: `routers/` (HTTP), `services/` (nghiệp vụ), `schemas/` (model Pydantic khớp `packages/contracts/`), `core/` (cấu hình, lỗi, bảo mật, trạng thái), `db/` (sau PLAT-05).
- Router chỉ nhận/trả dữ liệu; nghiệp vụ nằm trong `services/`.
- Cấu hình chỉ đọc từ biến môi trường (`.env`), không hard-code.
- Mọi lỗi trả về theo một định dạng `{error_code, message}` (`ErrorResponse`).
- Phản hồi cho người dân (`/v1/sessions/*`) **không bao giờ** có điểm số hay chữ "giả mạo" — có test; đừng xóa.

## Lệnh

```bash
uv sync --frozen --all-packages
uv run uvicorn vericlue_api.main:app --reload --app-dir services/api/src   # http://localhost:8000/docs
uv run pytest services/api
uv run python scripts/gen_openapi.py        # sinh lại packages/contracts/openapi.json
```

## Endpoint (API v1)

| Nhóm | Endpoint |
|---|---|
| Sức khỏe | `GET /healthz` |
| Phiên (Bearer, trừ tạo phiên) | `POST /v1/sessions`, `POST /v1/sessions/{id}/{media,signals,finalize,voice}` |
| Bàn duyệt | `GET /v1/review/cases`, `GET /v1/review/cases/{id}`, `POST …/initial`, `GET …/ai` (409 nếu chưa có quyết định ban đầu), `POST …/decision` |
| Giám định | `POST /v1/forensic/jobs`, `GET …/jobs/{id}`, `GET …/jobs/{id}/report`, `POST /v1/forensic/verify` |

Chạy mock (`USE_MOCK_MODELS=true`, mặc định) chọn kịch bản bằng header **`X-Mock-Scenario`** khi tạo phiên hoặc giám định: `genuine`, `print`, `replay`, `virtual_cam`, `faceswap`, `voice_clone`, `low_quality`, `error`. Khi tắt mock, header bị bỏ qua. App mock có sẵn 2 ca duyệt mẫu.

## Token, lượt, thử thách (ADR-0011)

- Token theo phiên, gửi `Authorization: Bearer`; thiếu hoặc sai → 401 (phiên không tồn tại cũng 401).
- **Lượt = một challenge.** `finalize` trả `retry` (kèm `challenge` mới) hoặc `voice_challenge` thì mở lượt mới. Đọc lại câu tối đa 1 lần. Mỗi challenge sống 120 giây (`challenge.expires_at`), tách khỏi hạn token (`expires_at` ở gốc).
- **Kiểm thứ tự luồng (đã cài, không phải máy trạng thái PLAT-06):** `/voice` chỉ nhận khi `finalize` vừa trả `voice_challenge` (không thì 409 `voice_not_requested`, và không ghi file nào); `finalize` luôn đặt lại yêu cầu giọng nói và bộ đếm đọc lại; phiên đã vào bàn duyệt là trạng thái cuối, `finalize`/`voice` gọi lại → 409 `session_closed`. Không có đường tắt tới `pass` bỏ qua cổng khuôn mặt.
- Upload quá `MAX_UPLOAD_MB` → 413 `upload_too_large`.
- Cấu hình: `SESSION_TTL_SECONDS` (300), `CHALLENGE_TTL_SECONDS` (120), `MAX_RETRIES` (2), `MAX_UPLOAD_MB` (50), `CHALLENGE_PALETTE` (bảng màu, phân cách bằng dấu phẩy; bộ sinh từ chối bảng vi phạm giới hạn độ chói 0,064 hoặc R/(R+G+B) >= 0,8).

## Phần tạm (các task sau thay thế)

| Phần | Hiện nay | Thay bằng |
|---|---|---|
| Token | chuỗi ngẫu nhiên, chỉ so khớp | **PLAT-06**: HMAC gắn `session_id`, TTL ~5 phút, 409 và máy trạng thái "mỗi bước một lần mỗi lượt", 429 (3 phiên/giờ/IP), hết hạn challenge 120 giây thật |
| Lưu trữ | bộ nhớ (`core/state.py`) | **PLAT-05**: PostgreSQL |
| Chạy detector | tuần tự (`services/detection.py`) | **PLAT-08**: orchestrator song song |
| Luật quyết định | `services/provisional_decision.py`, B=0,15, A=0,60 trong cấu hình (`PROVISIONAL_THRESHOLD_B/A`) | **ROUT-02**: TrustRouter, ngưỡng từ `ml/configs/thresholds.yaml` |
| Giám định, chữ ký | segment và chữ ký `MOCK-<sha256>` | **FOR-01 / FOR-04**, khóa Ed25519 ở PLAT-06 |
| Bàn duyệt | kho bộ nhớ, URL media giả | **REV-01**: DB và nhật ký chuỗi băm |
| Giới hạn upload | `MAX_UPLOAD_MB` chỉ kiểm **sau khi** Starlette đã nhận multipart (và trước khi xác thực token vẫn nhận được body) | **PLAT-06** / reverse proxy: giới hạn cứng ở lớp trước ứng dụng |
| Xác thực nhân viên | `/v1/review/*` và `/v1/forensic/*` chưa có xác thực | **PLAT-06** / REV-02 |

Luật quyết định tạm, thứ tự cổng: quality (chụp lại tối đa 2 lần rồi `review`) → chromapulse/camprobe (fail → `review` ưu tiên cao; chưa rõ → chụp lại) → ngưỡng trên **max `prob_attack`** của `face_pad` và `face_deepfake` (dưới B `pass`; từ B đến dưới A `voice_challenge`; từ A trở lên `review`). `error`/`degraded`/thiếu ở bước bắt buộc → `review`, không bao giờ `pass`.
