# services/api — Máy chủ API (FastAPI)

**Phụ trách:** M5
**Trạng thái:** API v1 chạy với dữ liệu mock (PLAT-03 khung, **PLAT-04** endpoint + hợp đồng). DB đã chuyển sang SQLAlchemy/PostgreSQL ở PLAT-05. Token và luật quyết định đầy đủ còn là phần TẠM; PLAT-08 đã có orchestrator song song, xem "Phần tạm" bên dưới.

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
| Lưu trữ | **PLAT-05**: PostgreSQL, migration Alembic, transaction theo request | Đã có persistence; nghiệp vụ tiếp tục ở các task tương ứng |
| Chạy detector | **PLAT-08**: executor chung, preload lifespan, deadline/timeout và latency thực | Đã có; detector thật được bổ sung bởi các task mô hình |
| Luật quyết định | `services/provisional_decision.py`, B=0,15, A=0,60 trong cấu hình (`PROVISIONAL_THRESHOLD_B/A`) | **ROUT-02**: TrustRouter, ngưỡng từ `ml/configs/thresholds.yaml` |
| Giám định, chữ ký | segment và chữ ký `MOCK-<sha256>` | **FOR-01 / FOR-04**, khóa Ed25519 ở PLAT-06 |
| Bàn duyệt | DB và sự kiện append-only/chuỗi băm cơ bản; URL media vẫn là chỗ giữ chỗ | **REV-01**: nghiệp vụ và phục vụ media hoàn chỉnh |
| Giới hạn upload | `MAX_UPLOAD_MB` chỉ kiểm **sau khi** Starlette đã nhận multipart (và trước khi xác thực token vẫn nhận được body) | **PLAT-06** / reverse proxy: giới hạn cứng ở lớp trước ứng dụng |
| Xác thực nhân viên | `/v1/review/*` và `/v1/forensic/*` chưa có xác thực | **PLAT-06** / REV-02 |

Luật quyết định tạm, thứ tự cổng: quality (chụp lại tối đa 2 lần rồi `review`) → chromapulse/camprobe (fail → `review` ưu tiên cao; chưa rõ → chụp lại) → ngưỡng trên **max `prob_attack`** của `face_pad` và `face_deepfake` (dưới B `pass`; từ B đến dưới A `voice_challenge`; từ A trở lên `review`). `error`/`degraded`/thiếu ở bước bắt buộc → `review`, không bao giờ `pass`.


## DB, migration và vòng đời file (PLAT-05)

`DATABASE_URL` đọc từ env/.env cho native. Compose dùng DATABASE_HOST và POSTGRES_* riêng; SQLAlchemy URL.create encode thông tin xác thực, không ghép mật khẩu thô vào URL. PostgreSQL 16 là DB của Compose; SQLite chỉ dùng
cho unit test độc lập. `create_app()` không kết nối DB; migration phải chạy trước
API. Container tự chạy `alembic -c services/api/alembic.ini upgrade head` trước Uvicorn.
Chạy native: `uv run alembic -c services/api/alembic.ini upgrade head`.

Các kho session/review/forensic dùng cùng transaction request và ghi snapshot
JSON tường minh; nested signals/challenge/ModuleResult được phục hồi sau restart.
Seed hai ca mock idempotent, có khóa PostgreSQL khi nhiều worker khởi động đồng thời.
`review_events` bị trigger DB chặn UPDATE/DELETE, không cascade xóa; actor hiện là
`staff-unverified`, xác thực nhân viên vẫn thuộc PLAT-06. Test dùng
`app.state.vericlue.transaction()` để setup/kiểm snapshot, không sửa object RAM toàn cục.

- `MEDIA_DIR/<session_id>/`: file phiên; tên và đuôi do server kiểm soát.
- `MEDIA_DIR/forensic/<job_id>/`: byte nguồn và HTML báo cáo; hash tính trên byte nguồn.
- Pass chưa vào review: 24 giờ từ quyết định cuối (`MEDIA_TTL_PASS_HOURS`).
- Ca review chưa `closed`: **không xóa media**, kể cả mở quá 30 ngày. Khi nhân viên đóng ca, `sessions.decided_at` ghi thời điểm đóng; từ mốc đó giữ 30 ngày (`MEDIA_TTL_REVIEW_DAYS`), kể cả được chấp nhận, không rút xuống 24 giờ.
- Phiên bỏ dở/retry/đang đọc câu: 24 giờ từ hoạt động thành công cuối (`MEDIA_TTL_INCOMPLETE_HOURS`).
- **Giám định KHÔNG tự xóa mặc định:** `FORENSIC_TTL_DAYS=` để trống. Số ngày dương bật TTL từ lúc tạo job; chỉ bật sau khi nhóm phê duyệt quyền xóa chứng cứ/chuỗi bằng chứng.

Lifespan chạy dọn lúc khởi động rồi mỗi `MEDIA_CLEANUP_INTERVAL_SECONDS` (300 giây).
Mỗi lượt thêm `cleanup_audits` và ghi một dòng `media_cleanup_audit`, gồm file thực
đã xóa và lý do, job giám định được bảo vệ, lỗi nếu có; không có file để xóa vẫn
có audit. Xóa từng phần gặp lỗi vẫn giữ dấu file đã xóa. Nếu DB không commit được
sau unlink, log vẫn ghi sự việc để đối soát; filesystem và DB không có transaction
phân tán. Không xóa metadata/audit theo TTL file. Từ chối traversal/symlink ngoài
MEDIA_DIR. Upload mới và report được tạo lại sẽ reset dấu đã dọn.

Container phải có `CHROMAPULSE_CONFIG=/app/config/chromapulse.json`; Dockerfile
chép đúng file nguồn chung. Không dùng đường dẫn suy từ site-packages. Model/data
là volumes read-only, media là volume writable, không có weights trong image.

Kiểm PostgreSQL thật: đặt `TEST_DATABASE_URL` tới DB test đã cấp quyền rồi chạy
`uv run pytest services/api/tests/test_db_postgres.py`; không đặt thì test này skip.
Job Python CI có service PostgreSQL16 với credential mẫu chỉ cho DB test tạm;
các bước CI hiện có được giữ nguyên. Tuyệt đối không dùng credential CI cho triển khai.

Cleanup lọc điều kiện hết hạn ngay trong SQL và dùng `FOR UPDATE SKIP LOCKED`; không khóa phiên/job chưa hết hạn. GET danh sách ca duyệt chỉ đọc, không khóa row. Token tạm hiện lưu **dạng rõ** trong `sessions.payload`; PLAT-06 phải đổi sang lưu hash (không lưu token gốc).

## Điều phối detector (PLAT-08)

API preload một instance mỗi module trong lifespan, trước khi nhận request. Hook
`preload()` nạp trọng số thật, không dùng audio giả hay câu đề bài để warmup.
Mock không cần weights. Preload lỗi không làm API dừng: module đó trả error cho
đến khi restart; không tự đổi sang mock và không thử nạp lại mỗi request.
`/healthz` trả status degraded và failed_modules (chỉ tên module), không có
exception, đường dẫn hay thông tin xác thực. Khởi tạo/import app để sinh OpenAPI
không kết nối DB hay preload model.

- DETECTOR_TIMEOUT_SECONDS: mặc định/tối đa 4 giây cho mỗi nhóm chạy song song,
  tính từ submit, bao gồm chờ hàng đợi. Exception/kết quả sai module -> error
  E_INTERNAL; hết hạn/hàng đợi đầy -> error E_TIMEOUT. error/degraded không
  bao giờ được dùng để pass; B/A và cổng quyết định vẫn giữ nguyên cho ROUT-02.
- DETECTOR_WORKERS: mặc định 9. Mỗi module có một driver trong pool và chỉ một
  predict tại một thời điểm, bảo vệ model instance dùng chung. Tác vụ chờ nằm
  trong FIFO riêng, không giữ thread để chờ khóa của model.
- DETECTOR_QUEUE_SIZE: mặc định **3 tác vụ chờ mỗi module**, ngoài một tác vụ
  đang chạy/được giao cho pool (tối đa 4 được nhận/module/process). Đặt 0 để
  không xếp hàng. Vượt giới hạn trả error E_TIMEOUT; evidence nội bộ
  orchestration_reason và log reason=busy phân biệt với reason=timeout khi hết
  deadline. Không trả các chi tiết này cho công dân; không thay ErrorCode.
  Cả queue wait và inference dùng chung hạn 4 giây. Tác vụ chờ đã quá hạn bị
  loại, không gọi model; kết quả chạy quá hạn bị bỏ, không ghi session/DB muộn.
  Thread inference đang chạy không thể bị giết an toàn. Shutdown ngừng nhận việc,
  kết thúc task chờ bằng error; detector native treo cần restart process.
- DB_LOCK_TIMEOUT_SECONDS: mặc định 2 giây, PostgreSQL SET LOCAL lock_timeout cho
  transaction finalize/voice, đặt trước SELECT FOR UPDATE xác thực phiên. Hết chờ
  khóa trả HTTP503 storage_busy với thông báo chung; transaction rollback, không
  trả pass. Timeout cục bộ không rò sang connection pool. SQLite unit không giả
  lập khóa PostgreSQL; test CI dùng service PostgreSQL16 thật.
- INFERENCE_BUDGET_SECONDS: mặc định/tối đa 4,8 giây, lấy từ Settings.
  Finalize/voice chia sẻ deadline inference tính từ dependency request,
  gồm thời gian chờ khóa; phần đã chờ DB được trừ khỏi ngân sách detector. Chừa
  200ms cho policy/commit/response trên DB bình thường để nghiệm thu endpoint
  <=5 giây. Lock timeout không giới hạn toàn bộ connect/query/commit nếu DB hỏng;
  không tuyên bố SLA5s cho sự cố DB/mạng hay thời gian upload của client.

Worker chỉ nhận bản sao DetectorInput, không cầm ORM/store. Luồng nghiệp vụ giữ
khóa hàng tới commit, lưu module_results và quyết định. /voice offload inference
khỏi event loop; prompt lấy từ session server. recognized_text/expected_text,
WER, similarity và evidence chỉ nội bộ; response công dân chỉ dùng schema hiện có.
VOICE-04 đã được registry nối vào nhánh voice; không mở rộng VOICE-05/06 trong task
này. Voice spoof/lipsync chưa có mô hình thật thì error, không dùng gate đọc câu
để thay bằng chứng chống giả giọng.

Log detector_result chứa module/model_version/status/error_code/latency_ms đo bằng
perf_counter, không log media/transcript/prompt/score. Timing của mock (vốn cố
định trong model) được thay bằng thời gian thực của orchestrator. Helper trực tiếp
services/detection.py giữ cho unit/harness cũ; tất cả consumer của API dùng runner
được inject từ instance chung, kể cả seed mock và giám định mock.

PhoWhisper public preload nhận MODELS_DIR từ Settings (.env), không phụ thuộc việc
.env đã được export thành os.environ. Khi cài wheel, đặt ML_MODELS_CONFIG tới
models.yaml; Dockerfile đã đặt /app/ml/configs/models.yaml. Không có model/data
trong image, không download lúc inference. Dependency/model thật thiếu sẽ hiện
trong health degraded theo chính sách trên.

Đo mock HTTP finalize (bao gồm auth/DB/commit/inference, loại upload) bằng
`uv run python scripts/benchmark_finalize.py --api-url http://localhost:8000 --runs 20`.
Báo cáo ignored tmp/plat-08-latency.json ghi máy, OS/CPU, commit/dirty, từng mẫu,
median/p95/max và số lần chạy. Đây là kiểm mock cho PLAT-08, chưa phải số R6 của
mô hình thật. Test không cần GPU/weights; test timeout dùng fake CPU/event.

### Giới hạn để chạy demo có nhiều người

Kịch bản nghiệm thu: **3 người với 3 phiên khác nhau finalize đồng thời**, detector
mock chậm 1 giây, tất cả nhận đúng kết quả, không bị review chỉ vì tranh slot.
Với một lần predict/module/process, ba lượt cùng đến cần khoảng 3 giây ở detector
1 giây; cấu hình mặc định vẫn nằm trong deadline4 giây. Hàng đợi nhận tối đa4 tác
vụ/module (1 chạy +3 chờ), nhưng không bảo đảm người thứ4 kịp hạn khi mỗi lượt
mất1 giây, cũng không bảo đảm3 người với mô hình thật chậm hơn. **Demo giới hạn
3 người quét đồng thời trên một process**, điều phối lượt tiếp theo; đo lại trước
khi tăng giới hạn hay đổi mô hình/CPU. Đây là test fake CPU, không phải số R6.

DB dùng SQLAlchemy QueuePool mặc định: pool_size=5, max_overflow=10, pool_timeout=30s
**mỗi process API**; nhiều process sẽ nhân số connection. Không nhầm pool_timeout
với lock_timeout2s của finalize/voice. Nếu hết connection pool, thời gian chờ có
thể vượt ngân sách endpoint; không nhận quá tải làm pass. Với demo3 người, vẫn
chừa connection cho các bước lưu trữ/cleanup. Chưa thêm tham số pool mới trong PR.
