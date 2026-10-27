# services/api — Máy chủ API (FastAPI)

LIVE-05 có API opt-in cấp chứng nhận BBS ngắn hạn từ cổng kết quả đã commit,
thêm chữ ký chấp thuận bằng khóa thiết bị, worker Node/key riêng và cache mã hóa.
Không cấp từ verdict client, không mở chốt sinh trắc thật hoặc cấp tuổi.
Chi tiết cấu hình/quyền/giới hạn: [private-credential-issuance.md](../../docs/architecture/private-credential-issuance.md).

API kiểm chứng BBS dùng credential tích hợp riêng, public pin và nonce DB qua
migration 0008. Restart/nhiều worker giữ dùng-một-lần, không lưu proof hoặc nym.
Xem [verifier bền vững](../../docs/architecture/private-credential-verifier.md).

**Phụ trách:** M5
**Trạng thái:** API v1 chạy với dữ liệu mock (PLAT-03 khung, **PLAT-04** endpoint + hợp đồng). DB đã chuyển sang SQLAlchemy/PostgreSQL ở PLAT-05. PLAT-06 đã có token HMAC, TTL và chặn nhận lặp; các phần bảo mật còn lại xem "Phần tạm". Chính sách ROUT-02 đã nối ML, ngưỡng/fusion đang provisional; PLAT-08 có orchestrator song song.

## Trách nhiệm

PLAT-06/FLOW-01 có khóa Ed25519 opt-in và kết quả phiên ký cho bên tích hợp:
[`signed-session-results.md`](../../docs/architecture/signed-session-results.md).
`GET /v1/result-signing-key` trả khóa công khai; bearer đúng phiên đọc `/result`.
Thiếu cấu hình trả 503, mock/phiên cũ/thiếu ràng buộc không được ký. Không mở chốt
sinh trắc, không ký báo cáo forensic hoặc thay ML-DSA; không sửa UI.

PLAT-06 ký báo cáo HTML giám định bằng khóa `REPORT_SIGNING_KEY_PATH` riêng:
[`forensic-report-signing.md`](../../docs/architecture/forensic-report-signing.md).
Job real thiếu khóa trả 503, không hạ về MOCK. `/v1/forensic/signing-key` và
`/verify` dùng StaffBearer, không cần DB/model; CLI kiểm đúng byte tệp bằng public
key đã pin. Checksum MOCK không còn được coi là chữ ký hợp lệ. Đây chưa phải gói
JSON/PDF và thang lời ENFSI của FOR-04.

FOR-04 đã có phần xuất gói PDF/JSON ký Ed25519, Node/Chromium opt-in:
[`forensic-pdf-bundle.md`](../../docs/architecture/forensic-pdf-bundle.md).
`GET /v1/forensic/jobs/{id}/report-bundle` chỉ cho staff, job done/real, có khóa
report và runtime. Thiếu runtime trả 503; HTML ký vẫn dùng độc lập. CLI xác minh
đúng ba tệp bằng public key đã pin, không giải nén/render. Chưa có LR/thang lời
ENFSI hoặc UI mới.

`POST /v1/forensic/jobs` thêm review_case_id tùy chọn; thiếu mã ca giữ file độc lập.
Gắn ca phải có quyết định ban đầu và file khớp byte media đang lưu, gồm SEC-01.
Checkpoint được ký trong báo cáo, chống ký lại đuôi đã cắt và không hạ mốc mới.
`POST /v1/forensic/review-audit/verify` kiểm JSON đã ký trước DB, phân biệt intact/
extended/truncated; scope không gồm byte PDF. Không khởi tạo mô hình khi verify.
Xem [liên kết và nhật ký](../../docs/architecture/forensic-review-audit.md).

Ảnh/phổ minh họa opt-in cho cả HTML và PDF:
[`forensic-report-evidence.md`](../../docs/architecture/forensic-report-evidence.md).
FORENSIC_REPORT_EVIDENCE=true cùng FORENSIC_REPORT_FFMPEG tuyệt đối; snapshot nguồn
kiểm SHA-256 trước trích, tối đa ba khoảng, giới hạn runtime/file/PNG. Thiếu nguồn/
runtime ghi rõ bỏ minh họa, không đổi verdict hoặc hạ chữ ký. Không phải heatmap
hay chứng nhận nội dung, không sửa UI. FFmpeg do người vận hành cài riêng.

FLOW-05 có nền lưu mẫu mặt/tài khoản mã hóa, gắn public key và dọn sau 24 giờ
(migration 0005): [`account-enrollment.md`](../../docs/architecture/account-enrollment.md).
`ACCOUNT_ENROLLMENT=true` nối worker trích mẫu và ghi danh sau `pass` onboarding
trong cùng transaction; mặc định tắt, lỗi rollback cả quyết định. Đã có receipt
theo bearer phiên, L0 và service khôi phục/thu hồi khóa (migration 0006), xem
[`account-authentication.md`](../../docs/architecture/account-authentication.md).
Chốt sinh trắc real/mixed và account-bound mock vẫn giữ. So cùng người
giữa mặt–giọng đã có opt-in riêng: [`face-voice-continuity.md`](../../docs/architecture/face-voice-continuity.md).
Thiếu ngưỡng riêng không được đạt. Không mở luồng thật/mixed.

SEC-02 có chữ ký media mặt/giọng theo phiên, nonce dùng một lần và client Android
opt-in: [`media-proof.md`](../../docs/architecture/media-proof.md). Cần migration
0004; khóa đã gắn tài khoản qua AccountStore, chưa mở luồng reauth thật.

Claim nonce nằm trong transaction request: lỗi lưu mặt/giọng rollback claim để
gửi lại cùng proof, không tiêu thụ nonce bởi savepoint SQLite. Test gồm hết hạn
trước/trong lúc đọc, proof lượt cũ sau đổi lượt/đọc lại và restart; CI kiểm tranh
nonce PostgreSQL. Đường legacy unsigned vẫn tương thích khi không bắt buộc proof,
không chứng minh được tuổi bản ghi. Ký media không chứng thực camera hoặc lúc quay.
Kịch bản tự động/thiết bị: [nghiệm thu media](../../docs/runbooks/media-proof-acceptance.md).

SEC-01 opt-in mã hóa snapshot/media phiên, hủy khóa theo TTL, che/mở thông tin và
credential/nhật ký truy cập nhân viên: [`session-privacy.md`](../../docs/architecture/session-privacy.md).
Cần migration 0003 và cấu hình khóa riêng; không tự chuyển dữ liệu demo cũ.

OCR/QR và LVFace-B opt-in cho UI Android: xem
[identity-integration.md](../../docs/runbooks/identity-integration.md).
`IDENTITY_LAB_URL` bật QR/OCR từ runtime cục bộ và LVFace-B thật trong orchestrator.
`IDENTITY_FACE_CALIBRATION` là artifact ngưỡng đúng version; thiếu thì so mặt vẫn
trả điểm nội bộ nhưng không đạt. Không dùng ngưỡng AdaFace `0.40` cũ. Luồng đầy đủ
vẫn có giới hạn mock/real nêu dưới đây.

`IDENTITY_FACE_FROM_VIDEO=true` chọn khung chính diện theo lịch server thay ảnh đầu;
`SESSION_FACE_CHECKS=true` chạy thêm mắt/quay đầu, dùng chung MediaPipe. Hai cờ mặc
định tắt, yêu cầu runtime MediaPipe tương thích. Xem
[`session-verification.md`](../../docs/architecture/session-verification.md).

FLOW-01/LIVE-01 đã có nền backend opt-in bằng body `purpose`/`nonce`, gói thử thách
động, kiểm mã lượt và chính sách theo luồng. **Hiện chỉ chạy mock**; real/mixed trả
503 cho luồng mới tới khi đủ detector và xác minh danh tính/thiết bị. API cũ không
gửi body giữ nguyên. Hướng dẫn cho người tích hợp (không sửa UI):
[`dynamic-session-api.md`](../../docs/architecture/dynamic-session-api.md).

- Phiên eKYC: tạo phiên, cấp thử thách màu, nhận media và tín hiệu, gọi bộ não, trả kết quả.
- Bàn duyệt: danh sách ca, hồ sơ bằng chứng, ghi quyết định vào nhật ký chuỗi băm.
- Giám định: nhận file, chạy phân tích theo đoạn, sinh và ký báo cáo.

## Quy ước

- Code trong `src/vericlue_api/`: `routers/` (HTTP), `services/` (nghiệp vụ), `schemas/` (model Pydantic khớp `packages/contracts/`), `core/` (cấu hình, lỗi, bảo mật, trạng thái), `db/` (sau PLAT-05).
- Router chỉ nhận/trả dữ liệu; nghiệp vụ nằm trong `services/`.
- Cấu hình chỉ đọc từ biến môi trường (`.env`), không hard-code.
- Mọi lỗi trả về theo một định dạng `{error_code, message}` (`ErrorResponse`).
- Phản hồi cho người dân (`/v1/sessions/*`) **không bao giờ** có điểm số hay chữ "giả mạo" — có test; đừng xóa.

## Giới hạn request (PLAT-06)

- `POST /v1/sessions`: mặc định **3 lần gọi/IP trong cửa sổ trượt 3600 giây**.
  `SESSION_CREATE_LIMIT` và `SESSION_CREATE_WINDOW_SECONDS` cấu hình số lượt và
  khoảng thời gian. Mỗi lần được nhận vào xử lý đều tính lượt, kể cả lỗi body hoặc
  nghiệp vụ sau đó; không hoàn lượt để tránh gọi lỗi nhằm vượt giới hạn.
  Vượt lượt trả **429 `session_rate_limited`**, `Retry-After` (giây), `Cache-Control:
  no-store`; không khóa các bước của phiên đã tạo. CORS cho phép đọc `Retry-After`.
- Bộ đếm nguyên tử ở RAM, dành cho **một worker của demo**; restart làm mất lượt,
  nhiều worker có bộ đếm riêng. Không coi đây là quota bền vững hoặc chống DDoS.
  Khóa bucket là HMAC của địa chỉ peer với khóa ngẫu nhiên của app, không giữ IP
  thô trong bộ đếm. Tối đa `SESSION_RATE_MAX_CLIENTS=10000` bucket; hết chỗ chưa
  có bucket hết hạn thì trả **503 `rate_limit_unavailable`**, không đẩy bucket
  còn hiệu lực ra để tạo lỗ vượt quota. Thiếu peer ASGI cũng trả 503.
- Chỉ lấy `scope.client` do ASGI server cung cấp, **không tự tin** `X-Forwarded-For`,
  `Forwarded` hoặc `CF-Connecting-IP`. Nếu dùng proxy/tunnel, chỉ cấu hình server
  tin proxy được kiểm soát và không mở đường đi trực tiếp giả header. Nếu chưa
  cấu hình, mọi người qua cùng proxy/NAT có thể dùng chung quota; cần thử cấu hình
  trên máy demo. Không dùng `forwarded-allow-ips=*` cho listener công khai.
- `MAX_UPLOAD_MB=50` vẫn giới hạn **từng file**. `MAX_REQUEST_MB=128` giới hạn
  **tổng body** (mọi file, JSON, phần bao multipart). Header `Content-Length` quá
  lớn bị chặn trước khi đọc body/khởi tạo nghiệp vụ; header trùng, sai hoặc đồng
  thời với `Transfer-Encoding` trả **400 `invalid_content_length`**. Body thiếu
  length hoặc khai length thấp vẫn bị đếm byte thực tế tại ASGI `receive`, trả
  **413 `request_too_large`** trước khi chuyển chunk vượt mức cho parser. Multipart
  đang dở đóng file tạm khi lỗi; chưa ghi media hoặc tiêu thụ bước phiên.
- Không đệm thêm bản sao toàn body hoặc ghi thêm file tạm ở middleware. Parser
  có thể đã nhận các chunk dưới mức giới hạn; đây không phải giới hạn RAM của
  toàn server hay băng thông mạng. Giới hạn kết nối/thời gian đọc/body ở proxy
  vẫn cần thiết khi triển khai ngoài demo. API không giải nén body.

Khi test nội bộ cần tạo nhiều phiên, đặt `SESSION_CREATE_LIMIT` phù hợp trước khi
khởi động lại API; không sửa mặc định hoặc dùng cờ mock để tự bỏ bảo vệ. Bộ test
nghiệp vụ cấu hình quota riêng; `test_request_limits.py` kiểm quota 3 và đồng thời.
Không đổi schema request/response; lỗi vẫn là `{error_code, message}` hiện có.

Tham chiếu giao thức: [ASGI HTTP request/receive](https://asgi.readthedocs.io/en/latest/specs/www.html#request-receive-event)
và [Starlette multipart parser](https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py)
(kiểm thêm phiên bản đã cài bằng test đóng file tạm).

## Truy cập nhân viên (PLAT-06)

Mọi endpoint `/v1/review/*` và `/v1/forensic/*` yêu cầu credential nhân viên,
**kể cả mock và SESSION_PRIVACY=false**. Khi nâng cấp từ bản cũ, cấu hình
`STAFF_ACCESS_TOKENS` trước khi dùng bàn duyệt/giám định; không có chế độ bỏ qua.

- Cấu hình server là JSON `{ "<token ngẫu nhiên>": "<mã nhân viên>" }`. Mỗi token
  nên sinh bằng `secrets.token_urlsafe(32)`, dài 32–512 ký tự ASCII theo cú pháp
  bearer; actor 1–100 ký tự in được, không chỉ khoảng trắng hoặc `staff-unverified`.
  Tối đa 256 credential/64 KiB cấu hình; JSON trùng token, token ngắn hoặc sai
  cấu trúc đều bị từ chối. Không có token mẫu mặc định hoặc token tự sinh fallback.
- Gửi **một** header `Authorization: Bearer <token>` qua HTTPS. Token người dân
  không dùng được cho nhân viên và ngược lại. Không nhận token từ URL, cookie,
  `X-Staff-Actor` hoặc body; actor lấy từ cấu hình server. Thiếu/sai bearer trả
  **401 `unauthorized`**, kèm `WWW-Authenticate: Bearer`. Thiếu/sai cấu hình trả
  **503 `staff_unavailable`**, không làm endpoint trở thành công khai.
- Guard chạy trước đọc body, transaction hoặc detector, kể cả upload forensic;
  kiểm đường dẫn đã giải mã và `root_path`. CORS preflight vẫn hoạt động, lỗi auth
  có CORS cho origin được phép. Phản hồi staff (kể cả báo cáo/lỗi) có
  `Cache-Control: no-store`. `/healthz`, OpenAPI và API người dân giữ cơ chế riêng.
- Nhật ký quyết định review dùng actor đã xác thực; nhật ký truy cập/che/mở PII
  vẫn thuộc SEC-01 khi bật riêng tư. Giám định chưa có nhật ký truy cập/owner từng
  job hoặc vault mã hóa eKYC; credential hiện có cùng quyền demo, chưa SSO/RBAC/MFA.
  Auth không chứng nhận chữ ký; HTML ký Ed25519 bằng cấu hình riêng, JSON/PDF vẫn thuộc FOR-04.
- Giữ credential trong cấu hình máy, không Git, log hoặc biến frontend
  `NEXT_PUBLIC_*`. Compose đã chuyển `STAFF_ACCESS_TOKENS` vào API. Đổi cấu hình
  cần khởi động lại; xóa token khỏi cấu hình thu hồi quyền gọi mới, không thu hồi
  dữ liệu người đó đã tải trước đây.

SDK web có `createApiClient({ getStaffToken: () => tokenTrongBoNho })`: chỉ các
method review đọc callback tại mỗi lần gọi và gửi request `cache: no-store`.
Không tự lưu token hoặc thêm màn đăng nhập; người làm UI nối nguồn credential
riêng. Chỉ cấu hình server chưa đủ để trình duyệt tự đăng nhập. Forensic client
tích hợp trực tiếp dùng cùng header bearer. Không đặt token vào URL tải báo cáo.

Tham chiếu cách truyền bearer và challenge 401:
[RFC 6750 §2.1/§3](https://www.rfc-editor.org/rfc/rfc6750.html).
Đây là credential demo, không triển khai authorization server OAuth.

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
| Bàn duyệt (StaffBearer) | `GET /v1/review/cases`, `GET /v1/review/cases/{id}`, `POST …/initial`, `GET …/ai` (409 nếu chưa có quyết định ban đầu), `POST …/decision` (422 `invalid_reason_code`), `GET /v1/review/reason-codes`, `GET …/audit/verify` |
| Giám định (StaffBearer) | `POST /v1/forensic/jobs`, `GET …/jobs/{id}`, `GET …/jobs/{id}/report`, `POST /v1/forensic/verify` |

Chạy mock (`USE_MOCK_MODELS=true`, mặc định) chọn kịch bản bằng header **`X-Mock-Scenario`** khi tạo phiên hoặc giám định: `genuine`, `print`, `replay`, `virtual_cam`, `faceswap`, `voice_clone`, `low_quality`, `error`. Khi tắt mock, header bị bỏ qua. App mock có sẵn 2 ca duyệt mẫu.

`USE_MOCK_MODELS=mixed` (FACE-01): module có mô hình thật (hiện `face_pad`, `voice_challenge`, `voice_spoof`) chạy thật và bỏ qua `X-Mock-Scenario`, module còn lại vẫn mock. `/healthz` giữ `mock_models` kiểu bool. Cần `uv sync --all-packages --extra face --extra voice` và trọng số trong `MODELS_DIR`; module preload lỗi nằm ở `failed_modules` và không bao giờ cho `pass`. Hướng dẫn thử: `ml/src/vericlue_ml/face/README.md`.

## Token, lượt, thử thách (ADR-0011)

- Token theo phiên, gửi `Authorization: Bearer`; thiếu hoặc sai → 401 (phiên không tồn tại cũng 401).
- Token ký HMAC-SHA256, gắn `session_id`, thời hạn và nonce ngẫu nhiên. DB chỉ lưu `token_hash`; token gốc chỉ xuất hiện trong phản hồi tạo phiên. Token tạm của phiên cũ không được nâng cấp: mở phiên mới sau khi cập nhật.
- `SESSION_SIGNING_SECRET` phải là khóa ngẫu nhiên ít nhất 32 byte trong chế độ thật/mixed; thiếu hoặc quá ngắn → 503 `security_unavailable` khi cấp/kiểm token. Khi chạy thuần mock và không cấu hình khóa, dùng khóa tạm gắn với instance Settings, không bảo đảm token qua restart. Dùng cùng khóa cấu hình cho mọi worker nếu cần giữ phiên qua restart; thay khóa làm token cũ mất hiệu lực.
- **Lượt = một challenge.** `finalize` trả `retry` (kèm `challenge` mới) hoặc `voice_challenge` thì mở lượt mới. Đọc lại câu tối đa 1 lần. Mỗi challenge sống 120 giây (`challenge.expires_at`), tách khỏi hạn token (`expires_at` ở gốc).
- **Chặn nhận lặp:** media/signals chỉ nhận một lần mỗi lượt; lần hai → 409 `step_already_received`, không ghi đè dữ liệu. Khi đã yêu cầu đọc câu, không nhận lại bước khuôn mặt (`step_not_allowed`). `pass` và `review` đều đóng phiên; mọi bước gọi lại → 409 `session_closed`. Khi `retry`, cấp challenge mới và xóa tham chiếu ảnh/video/âm thanh, tín hiệu và kết quả ML của lượt trước. File cũ còn trên đĩa được xử lý theo TTL, không được dùng làm đầu vào lượt mới.
- Challenge khuôn mặt hết hạn → 409 `challenge_expired` trước khi lưu file/chạy model. Mỗi câu đọc có hạn riêng tính từ khi cấp câu, không dùng lại hạn màu; câu đọc lại được cấp hạn mới. Token hết hạn → 401. Gia hạn và khôi phục sau gián đoạn thuộc LIVE-06 (ADR-0017), chưa được cài trong phần này.
- Chưa ràng buộc byte media vào `challenge_id`/chữ ký của client: chặn nhận lặp endpoint không thay thế ký media/kiểm nonce ở LIVE-03 và SEC-02.
- Upload quá `MAX_UPLOAD_MB` → 413 `upload_too_large`.
- Cấu hình: `SESSION_TTL_SECONDS` (300), `CHALLENGE_TTL_SECONDS` (120), `MAX_RETRIES` (2), `MAX_UPLOAD_MB` (50), `CHALLENGE_PALETTE` (bảng màu, phân cách bằng dấu phẩy; bộ sinh từ chối bảng vi phạm giới hạn độ chói 0,064 hoặc R/(R+G+B) >= 0,8).

## Bàn duyệt và nhật ký băm (REV-01)

- **Hồ sơ `GET /cases/{id}` không có điểm AI** (chống thiên kiến tự động hóa); `ModuleResult[]` chỉ ở `GET …/ai`, và chỉ sau khi nhân viên ghi quyết định ban đầu (chưa thì 409 `initial_decision_required`). Hồ sơ có `history` (quyết định, mã lý do, ghi chú, người ghi, giờ).
- **Mã lý do** (`services/review_reasons.py`, *danh sách tạm — M2 chỉnh*): xem `GET /v1/review/reason-codes`. Quyết định cuối có mã ngoài danh sách, hoặc `OTHER` thiếu ghi chú → 422 `invalid_reason_code`. Quyết định ban đầu không cần mã lý do. Schema giữ `reason_code` là chuỗi tự do.
- **Nhật ký `review_events`** chỉ ghi thêm (trigger DB chặn UPDATE/DELETE), mỗi ca một chuỗi. Định nghĩa băm, "‖" là nối chuỗi ký tự không dấu phân cách:

  `hash = sha256( prev_hash ‖ json_chuẩn_hóa(payload) )`

  `prev_hash` của sự kiện đầu là 64 ký tự `0`; JSON chuẩn hóa = `json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` mã hóa UTF-8. Code: `services/audit_log.py`.
- `verify_chain()` băm lại payload ĐÃ LƯU và báo sự kiện sai đầu tiên (sửa nội dung, sửa `prev_hash`, xóa/đảo/cắt đoạn giữa). **Không bắt được** việc cắt cụt phần đuôi nếu không neo hash cuối ở nơi khác. `GET …/audit/verify` chạy hàm này cho một ca.
- **Chặn quyết định lặp ở tầng DB (REV-03):** trước khi đọc đuôi chuỗi và thêm sự kiện, cập nhật `review_cases` bằng điều kiện nguyên tử: initial chỉ khi ca còn `open`, chưa có initial/final; final chỉ khi ca còn `initial_decided`, có đúng initial đã đọc và chưa có final. Không còn hàng khớp điều kiện → **409 `review_conflict`**, không ghi nhật ký hoặc quyết định phiên. Cập nhật trạng thái, sự kiện và quyết định phiên nằm trong cùng transaction; lỗi rollback toàn bộ, lượt sau vẫn ghi được. Không dùng khóa trong bộ nhớ làm bảo đảm.
- **Bảo đảm chuỗi không rẽ nhánh:** migration `0002` giữ `UNIQUE(case_id, prev_hash)` trên `review_events` (sự kiện đầu dùng hash genesis). `SELECT … FOR UPDATE` vẫn tuần tự hóa trên PostgreSQL, SQLite bỏ qua khóa hàng. UNIQUE chỉ chống rẽ nhánh; nếu request dùng trạng thái cũ nhưng đọc được đuôi chuỗi mới, nó có thể nối thêm một quyết định trùng mà không vi phạm UNIQUE. Điều kiện cập nhật ở trên chặn trường hợp đó. Xung đột UNIQUE vẫn rollback và trả 409 `review_conflict`; lần gọi lại đã đọc được initial/final có sẵn vẫn nhận mã 409 tương ứng của endpoint. Lỗi kho dữ liệu vẫn trả 503 theo chính sách hiện có.
- Nâng cấp lên `0002` giữ nguyên chuỗi hợp lệ cũ; chuỗi đã rẽ nhánh (không hợp lệ) làm `upgrade` lỗi. Hạ về `0001` chỉ bỏ index, không mất sự kiện.
- Ca mẫu (`seed_demo`) chỉ có khi `USE_MOCK_MODELS=true` hoặc `mixed`.

## Phần tạm (các task sau thay thế)

| Phần | Hiện nay | Thay bằng |
|---|---|---|
| Phiên | HMAC/hash token/TTL/chặn lặp; Ed25519 opt-in; quota tạo phiên 429 và giới hạn body ASGI đã có | **PLAT-06** còn nghiệm thu media cũ; FOR-04 nối ký báo cáo; LIVE-03/SEC-02 ràng buộc media và LIVE-06 gia hạn |
| Lưu trữ | **PLAT-05**: PostgreSQL, migration Alembic, transaction theo request | Đã có persistence; nghiệp vụ tiếp tục ở các task tương ứng |
| Chạy detector | **PLAT-08**: executor chung, preload lifespan, deadline/timeout và latency thực | Đã có; detector thật được bổ sung bởi các task mô hình |
| Luật quyết định | **ROUT-02**: ML TrustRouter, snapshot `ml/configs/thresholds.yaml`, provisional max-fusion | **ROUT-03**: ngưỡng LTT trên calib_ltt; logistic học trên calib_fit khi có dữ liệu thật |
| Giám định, chữ ký | **FOR-01 lõi (MVP)** chạy detector thật theo đoạn, thiếu bước → inconclusive. HTML job real đã ký Ed25519 với khóa report riêng; mock ghi rõ mô phỏng, checksum không verify được | **FOR-01** hiệu chỉnh riêng; **FOR-04** JSON/PDF/neo audit/LR/thang lời ENFSI |
| Bàn duyệt | **REV-01**: DB, nhật ký băm nối chuỗi, `verify_chain`, mã lý do cố định; URL media vẫn là chỗ giữ chỗ | **REV-02** (giao diện, phục vụ media) |
| Giới hạn upload | `MAX_REQUEST_MB` kiểm header/tổng byte trước parser; `MAX_UPLOAD_MB` kiểm riêng từng file | Reverse proxy: giới hạn kết nối, thời gian đọc và body ở lớp mạng |
| Xác thực nhân viên | StaffBearer bắt buộc cho review/forensic ở mọi chế độ; thiếu cấu hình chặn 503; actor từ server | **REV-02/FOR-02** nối credential vào UI; SSO/RBAC/owner job ngoài phạm vi demo |

Chính sách ROUT-02, thứ tự cổng: phiên/thời gian hợp lệ → quality (chụp lại tối đa 2 lần rồi `review`) → chromapulse/camprobe (fail → `review` ưu tiên cao; unclear → chụp lại; gate rỗng/không xác định → `review`) → ngưỡng trên **max `prob_attack`** của `face_pad` và `face_deepfake` (≤ B `pass`; trên B đến dưới A `voice_challenge`; ≥ A `review`). `error`/`degraded`/thiếu ở bước bắt buộc → `review`, không bao giờ `pass`.


## DB, migration và vòng đời file (PLAT-05)

`DATABASE_URL` đọc từ env/.env cho native. Compose dùng DATABASE_HOST và POSTGRES_* riêng; SQLAlchemy URL.create encode thông tin xác thực, không ghép mật khẩu thô vào URL. PostgreSQL 16 là DB của Compose; SQLite chỉ dùng
cho unit test độc lập. `create_app()` không kết nối DB; migration phải chạy trước
API. Container tự chạy `alembic -c services/api/alembic.ini upgrade head` trước Uvicorn.
Chạy native: `uv run alembic -c services/api/alembic.ini upgrade head`.

Các kho session/review/forensic dùng cùng transaction request và ghi snapshot
JSON tường minh; nested signals/challenge/ModuleResult được phục hồi sau restart.
Seed hai ca mock idempotent, có khóa PostgreSQL khi nhiều worker khởi động đồng thời.
`review_events` bị trigger DB chặn UPDATE/DELETE, không cascade xóa. Actor
`staff-unverified` chỉ thuộc dữ liệu cũ/nội bộ; HTTP mới dùng actor từ credential nhân viên. Test dùng
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

Cleanup lọc điều kiện hết hạn ngay trong SQL và dùng `FOR UPDATE SKIP LOCKED`; không khóa phiên/job chưa hết hạn. GET danh sách ca duyệt chỉ đọc, không khóa row. Phiên mới chỉ lưu `token_hash`, không lưu token gốc. Không có thay đổi DDL; metadata bảo vệ phiên nằm trong JSON snapshot hiện có. Các row cũ chứa token tạm không còn được chấp nhận để xác thực, nhưng không tự sửa/xóa dữ liệu lịch sử của chúng.

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
Registry hiện nối voice_challenge, voice_spoof và lipsync thật. VOICE-05 dùng
video của đúng lần đọc hiện tại; thiếu video không lấy lại clip mặt cũ. Thiếu
model hoặc bằng chứng bắt buộc thì review, không dùng gate đọc câu thay bằng
chứng chống giả giọng. CPU SyncNet có thể vượt deadline detector 4 giây hiện có;
đường API khi đó review/timeout. Thử wrapper trực tiếp ghi thời gian từng pha;
chưa nghiệm thu độ trễ đầu–cuối hoặc GPU.

Log detector_result chứa module/model_version/status/error_code/latency_ms đo bằng
perf_counter, không log media/transcript/prompt/score. Timing của mock (vốn cố
định trong model) được thay bằng thời gian thực của orchestrator. Helper trực tiếp
services/detection.py giữ cho unit/harness cũ; tất cả consumer của API dùng runner
được inject từ instance chung, kể cả seed mock và giám định mock.

PhoWhisper và AntiDeepfake public preload nhận MODELS_DIR từ Settings (.env), không phụ thuộc việc
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


## Cấu hình quyết định ROUT-02

Nguồn duy nhất là `ml/configs/thresholds.yaml` (override đường dẫn bằng
`THRESHOLDS_CONFIG`, container `/app/ml/configs/thresholds.yaml`). Không dùng
`PROVISIONAL_THRESHOLD_B/A` nữa. Snapshot được giữ suốt vòng đời API; đổi file cần restart.
`decisions.thresholds` lưu cả ngưỡng/nguồn/phương pháp tạm, `config_version` là SHA-256
byte YAML. Dùng cột JSON hiện có, **không có migration mới**. Quyết định tự động ở
SessionStore được ghi metadata này; nghiệp vụ quyết định nhân viên thuộc REV-01.
Hai file review_store.py/routers/review.py được giữ nguyên để tránh xung đột REV-01.
Consumer bàn duyệt/giám định đọc trực tiếp `settings.router_config.face.b/a`.

Quality fail → retry, retry, review; face degraded chưa xét khi quality fail.
Quality error/degraded và module bắt buộc lỗi ở bước đã tới → review. Voice dùng
`voice.spoof_threshold` riêng với biên ≤ pass, không dùng B và không trộn WER.
Cờ splice dương → review ưu tiên cao; giá trị không phải số/không hữu hạn → review; thiếu là absent. Sai câu chỉ đọc lại một lần.
SessionFlow tăng counters/cấp challenge hoặc câu mới; ML chỉ trả quyết định thuần.
Token không khớp/hết hạn → 401; challenge hết hạn trước bước → 409, không chạy
detector/ghi quyết định mới. Nếu hết hạn trong khi inference đang chạy, policy
không cho pass. Voice có hạn câu đọc riêng, không dùng lại hạn challenge màu.
Quota tạo phiên 429 đã có ở PLAT-06 (test smoke 7 kịch bản cần cấu hình đủ lượt).
Các chốt409/row lock/deadline/queue/503
storage_busy của PLAT-04/05/08 giữ nguyên. Công dân chỉ nhận schema cũ, không nhận
xác suất, Λ, hash cấu hình, ngưỡng, lý do nội bộ hay transcript.

Kiểm bảy kịch bản trên Compose đang chạy (mock):
`uv run python scripts/smoke_router.py --api-url http://localhost:8000 --web-url http://localhost:3000`.
Script đọc DATABASE_URL từ env/.env để đối chiếu decisions/hash và không in URL/credential;
`ROUTER_SMOKE_DATABASE_PORT` chỉ đổi port DB phía host khi dùng Compose project riêng.
Report mặc định `tmp/rout02-compose-smoke.json` (gitignored); xong chạy `docker compose down`.


## Hồ sơ MVP (ROUT-01, ADR-0012)

Opt-in Qwen/CTC/NES2Net/SyncNet cho API phiên và runtime tách riêng:
[`session-voice.md`](../../docs/architecture/session-voice.md). Cờ mặc định tắt;
khi bật cần đủ runtime local, không tự thay bằng mock khi thiếu mô hình.

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
chung và cài các extra face/voice. Cần đủ wrapper thật và calibrator để có thể pass;
module chưa sẵn sàng sẽ hiện trong health degraded. `USE_MOCK_MODELS=true` vẫn
chạy được với MVP để test. MVP cần calibrator PAD, deepfake và voice_spoof; full
còn bắt buộc lipsync. Mock `mock@` vẫn được miễn calibrator. Theo ADR-0012 §6,
lipsync trong MVP chỉ tham khảo: vẫn chạy và lưu kết quả cho người duyệt, nhưng
thiếu/lỗi/not_applicable/timeout hoặc điểm cao không quyết định phiên. Bước giọng
quyết bằng voice_challenge + voice_spoof. Đọc sai câu được đọc lại trước khi xét
cờ cắt ghép; khi câu khớp mà có cờ thì review ưu tiên cao. Full vẫn bắt buộc lipsync. Bước giọng cần trình duyệt có MediaRecorder WebM.

Nếu consumer yêu cầu module bị tắt bởi profile (ví dụ provenance khi giám
định bằng MVP), orchestrator vẫn trả ModuleResult status=error/E_INTERNAL với
orchestration_reason=disabled_by_profile và nhãn "Bước này đang tắt ở chế độ MVP".
Không chạy/preload module đó; không âm thầm bỏ kết quả. Giám định ra inconclusive,
bàn duyệt giữ được evidence, báo cáo hiển thị nhãn. Luồng người dân yêu cầu đúng
nhóm module của profile nên không đổi. /healthz giữ schema cũ: thêm router_profile
sẽ cần sửa packages/contracts/openapi.json và snapshot test, ngoài phạm vi đã duyệt.

`LIPSYNC_DEVICE=cpu` (mặc định; `cpu | cuda | auto`) chọn riêng thiết bị cho
SyncNet, CTC aligner và SCRFD của nhánh lipsync. `DEVICE` vẫn chọn thiết bị của
quality, PAD, GenD, PhoWhisper và AntiDeepfake. Ví dụ GPU 6 GB:
`ROUTER_PROFILE=mvp USE_MOCK_MODELS=false DEVICE=cuda LIPSYNC_DEVICE=cpu`.
Lipsync chỉ cấu hình lúc khởi động, nạp trọng số offline ở lần đầu có video,
audio và câu đề bài; không giữ model CTC/SyncNet trên GPU lúc preload. Lần đầu
có thể timeout trong ngân sách 4 s; kết quả vẫn là lỗi rõ ràng, MVP chỉ tham khảo,
full vẫn không coi lỗi là đạt. Đường dẫn/thiết bị cố định từ lần cấu hình đầu;
đổi cấu hình hoặc thử lại sau lỗi nạp cần khởi động lại tiến trình.
