# Kiến trúc kỹ thuật VeriClue

> **Nguồn sự thật về thiết kế kỹ thuật.** Khi code khác tài liệu này, hoặc sửa code cho đúng, hoặc mở ADR mới (`docs/adr/`) rồi cập nhật tài liệu này **trong cùng PR**.
> Bản hình ảnh cho người không chuyên: `docs/architecture/architecture.html`.
> Yêu cầu sản phẩm: `docs/proposal/proposal.md`.

## 1. Tổng quan

```
 Trình duyệt (Next.js)                      Máy chủ (FastAPI)                         Bộ não (vericlue_ml)
 ┌──────────────────────┐   HTTPS/JSON     ┌──────────────────────────┐   gọi hàm   ┌──────────────────────────┐
 │ /verify  web xác minh │ ───────────────▶ │ sessions · uploads       │ ──────────▶ │ face/  presence/  voice/ │
 │ /review  bàn duyệt    │ ◀─────────────── │ orchestrator · router    │ ◀────────── │ router/  forensic/       │
 │ /forensic giám định   │                  │ review · forensic jobs   │  ModuleResult└──────────────────────────┘
 └──────────────────────┘                  └────────────┬─────────────┘
                                                        │
                                       PostgreSQL ◀─────┴────▶ thư mục file tạm (tự xóa)
```

**Nguyên tắc:**
1. **Mock trước, thật sau.** Mọi mô-đun AI có bản giả lập (`USE_MOCK_MODELS=true`) trả kết quả đúng định dạng. Web và API vì vậy chạy được từ ngày đầu, và mỗi người phát triển song song mà không chờ nhau.
2. **Hợp đồng cố định.** Mọi giao tiếp đi qua schema trong `packages/contracts/`. Muốn đổi schema phải sửa schema trước, rồi sửa code ở cả hai phía trong cùng PR.
3. **Không lộ điểm cho người dùng.** API trả cho trình duyệt chỉ `pass | retry | review | voice_challenge`, không trả điểm số.
4. **Server là nơi quyết định.** Dữ liệu do trình duyệt tính chỉ để tham khảo; server tính lại từ ảnh và video gốc.

## 2. Cấu trúc thư mục

```
Data4Life/
├── apps/web/                    Next.js (App Router, TypeScript)
│   └── src/
│       ├── app/verify/          luồng xác minh của người dân
│       ├── app/review/          bàn duyệt của nhân viên
│       ├── app/forensic/        cổng giám định của điều tra viên
│       ├── lib/capture/         camera, cổng chất lượng, ChromaPulse (phát màu), CamProbe
│       ├── lib/api/             client gọi API (sinh từ OpenAPI)
│       └── components/          UI dùng chung
├── services/api/                FastAPI
│   ├── src/vericlue_api/
│   │   ├── main.py
│   │   ├── routers/             sessions, uploads, review, forensic, health
│   │   ├── core/                config, security (token phiên), signing (Ed25519)
│   │   ├── db/                  models SQLAlchemy, migrations Alembic
│   │   └── services/            orchestrator, storage, audit_log
│   └── tests/
├── ml/                          Gói Python vericlue_ml, API import trực tiếp
│   ├── src/vericlue_ml/
│   │   ├── common/              ModuleResult, hiệu chỉnh, đọc video/âm thanh
│   │   ├── face/                pad.py, gend.py, sbi.py, aggregate.py
│   │   ├── presence/            chromapulse.py, camprobe.py
│   │   ├── voice/               antispoof.py, asr.py, align.py, challenge.py, syncnet.py
│   │   ├── router/              fusion.py, ood.py, ltt.py, policy.py
│   │   ├── forensic/            segment.py, provenance.py, report.py
│   │   ├── eval/                chạy kết quả R1–R6
│   │   └── mock/                mô-đun giả lập
│   ├── configs/                 models.yaml, thresholds.yaml (ngưỡng đã khóa), calibrators/ (ADR-0010)
│   └── tests/
├── packages/contracts/          JSON Schema + ví dụ: hợp đồng giữa các phần
├── scripts/                     setup, tải dữ liệu, tải mô hình, sinh dữ liệu giả
├── notebooks/                   thử nghiệm (không phải code sản phẩm)
├── data/  models/  external/    KHÔNG commit (xem README trong từng thư mục)
├── third_party/                 file chép từ dự án khác, kèm giấy phép gốc
└── docs/                        tài liệu (mục lục: docs/README.md)
```

## 3. Giao diện chung của mô-đun AI

VOICE-12 thêm A/V lab opt-in: một DirectShow input có hai track, PCM/JPEG và PTS
chung trong RAM, tái dùng CTC/SCRFD/Stable SyncNet. Kết quả `lipsync` version riêng
luôn unclear, không score/prob_attack; không thay HTTP hoặc kết luận xác minh.
Xem [lab khớp môi](av-lipsync-lab.md).

VOICE-11 thêm nhịp đọc opt-in trong lab/CLI: CTC hiện có nhận raw PCM 16 kHz
để căn câu đề bài, trả mốc âm tiết/khoảng ngắt và luật thời lượng tạm. Kết quả
`voice_challenge` có version riêng, luôn unclear, giữ riêng với ASR và giọng AI;
không thay hợp đồng/backend HTTP hoặc quyết định. Xem [hướng dẫn](reading-timing-lab.md).

VOICE-10 nối công cụ micro nội bộ với worker NES2Net CPU riêng: thu một lần,
Qwen kiểm nội dung, NES2Net đo margin thô 4 giây đầu; không hợp nhất hai kết quả.
PCM qua pipe giới hạn/hash/id, không lưu audio; worker có timeout/hủy và giữ
model giữa các lượt. Không đổi hợp đồng HTTP, backend hoặc chốt xác minh.

VOICE-09 bổ sung `get_nes2net()` opt-in cho `voice_spoof`, checkpoint NES2Net-X
với frontend Transformers CPU riêng. Chưa parity Fairseq hoặc calibration,
luôn degraded/unclear, không prob_attack; chấm raw 4 giây đầu theo demo tác giả.
Không đổi lựa chọn API/full/MVP hoặc HTTP contract. Xem
[`nes2net-diagnostic.md`](nes2net-diagnostic.md).

VOICE-07/08 cung cấp Qwen3-ASR opt-in để kiểm nội dung câu đọc trong CLI/cửa
sổ microphone nội bộ. Runtime CPU Transformers 5.13.0 riêng, audio RAM có
giới hạn và luật khớp dùng chung `VoiceChallengeDetector`; `ok/pass` chỉ là khớp
câu. Không thay backend PhoWhisper, full/MVP, hợp đồng HTTP hoặc UI sản phẩm.
Xem [`qwen-asr-diagnostic.md`](qwen-asr-diagnostic.md).

LIVE-02 bổ sung `gaze_tracking` và reader MediaPipe để diagnostic video ở server.
Mô-đun này dùng gate thử nghiệm, chưa ở profile full/MVP và chưa tham gia quyết
định API. Xem [`presence/README.md`](../../ml/src/vericlue_ml/presence/README.md).
Ngưỡng/chiều tọa độ chưa nghiệm thu trên điện thoại; không bỏ chốt real/mixed.

FLOW-04/FLOW-05 thêm `head_turn` (kiểm thứ tự/thời gian, chưa kiểm chiều sâu)
và `face_match` (SCRFD + LVFace-B, so tham chiếu với ảnh chính diện; evidence
nhất quán ba góc riêng). Cả ba vẫn bị loại khỏi profile full/MVP mặc định.
Khi bật `IDENTITY_LAB_URL`, orchestrator HTTP nạp/chạy riêng LVFace-B thật để
so CCCD–selfie, có chung deadline/hàng đợi và báo preload lỗi qua health.
Runtime identity bên ngoài chỉ còn được API gọi để đọc QR/OCR. Đầu vào so mặt dùng hợp đồng nội bộ
`detector_input.schema.json` cho `image_roles` và `reference_image` do server
quản lý. Thiếu ngưỡng hiệu chỉnh đúng version luôn `degraded/unclear`. Xem
[`head-and-match.md`](head-and-match.md).

Mọi bộ phát hiện (kể cả cổng chất lượng `quality`) đều trả một `ModuleResult` (schema: `packages/contracts/schemas/module_result.schema.json`):

```python
class Detector(Protocol):
    name: str  # "face_pad", "face_deepfake", "chromapulse", "camprobe", "voice_spoof", ...
    version: str

    def predict(self, inp: DetectorInput) -> ModuleResult: ...
```

| Trường | Ý nghĩa |
|---|---|
| `module`, `model_version` | Tên và phiên bản mô hình, ghi vào mọi quyết định để truy vết |
| `status` | `ok` · `not_applicable` (không có mặt / im lặng) · `degraded` · `error` |
| `score` | Điểm thô của mô hình |
| `prob_attack` | Xác suất là tấn công **sau hiệu chỉnh** (TrustRouter chỉ dùng trường này) |
| `quality` | Chỉ số chất lượng đầu vào |
| `evidence[]` | Bằng chứng cho người duyệt: chuỗi thời gian, ảnh, số đo |
| `latency_ms` | Thời gian xử lý |

Quy tắc: `error` và `degraded` **không bao giờ** được hiểu là "đạt".

## 4. API (bản nháp v1 — chốt ở task PLAT-04)

| Phương thức | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/healthz` | Kiểm tra sống |
| POST | `/v1/sessions` | Tạo phiên → `session_id`, `token` (theo phiên), `challenge` (chuỗi màu, sống 120 giây), `expires_at` |
| POST | `/v1/sessions/{id}/media` | Tải ảnh mặt chất lượng cao và đoạn video (multipart, gắn token) |
| POST | `/v1/sessions/{id}/signals` | Tín hiệu trình duyệt đo: thời điểm màu, thời điểm khung, CamProbe, chất lượng |
| POST | `/v1/sessions/{id}/finalize` | Chạy phân tích → `{status: pass\|retry\|review\|voice_challenge, retry_hint?, voice_prompt?}` |
| POST | `/v1/sessions/{id}/voice` | Tải âm thanh và video lúc đọc câu → `{status: pass\|review\|voice_challenge}`. `voice_challenge` = đọc sai câu, được đọc lại **1 lần** với câu mới |
| GET | `/v1/review/cases` | Danh sách ca cần duyệt (lọc theo trạng thái, ưu tiên) |
| GET | `/v1/review/cases/{id}` | Hồ sơ bằng chứng **không kèm điểm AI** |
| POST | `/v1/review/cases/{id}/initial` | Nhân viên ghi quyết định ban đầu (trước khi xem AI) |
| GET | `/v1/review/cases/{id}/ai` | Ý kiến AI — trả 409 nếu chưa có quyết định ban đầu |
| POST | `/v1/review/cases/{id}/decision` | Quyết định cuối + mã lý do + ghi chú |
| POST | `/v1/forensic/jobs` | Tải file giám định → `job_id` |
| GET | `/v1/forensic/jobs/{id}` | Trạng thái và kết quả theo đoạn |
| GET | `/v1/forensic/jobs/{id}/report` | Báo cáo HTML/PDF + chữ ký |
| POST | `/v1/forensic/verify` | Kiểm tra chữ ký của một báo cáo → hợp lệ / không |

**Bảo mật phiên (ADR-0011):**
- Mọi lần gọi trong phiên gửi `Authorization: Bearer <token>`. Token sai chữ ký hoặc hết hạn → 401.
- Trong mỗi lượt, mỗi bước (media, signals, finalize, voice) chỉ nhận một lần; gọi lại → 409.
- Thử thách sống 120 giây; chụp lại thì server cấp thử thách mới.

## 5. Dữ liệu lưu trữ (PLAT-05)

SQLAlchemy 2 + Alembic, PostgreSQL 16 khi chạy Compose. Mỗi request nghiệp vụ dùng
một transaction, commit trước khi gửi response; rollback khi lỗi. Không kết nối DB
khi import ứng dụng/sinh OpenAPI. SQLite dùng cho unit test; PostgreSQL thật được
kiểm riêng trong CI và khi smoke Compose.

REV-03 bảo vệ chuyển trạng thái bàn duyệt bằng `UPDATE review_cases ... WHERE`
trước khi đọc đuôi chuỗi nhật ký: initial chỉ từ `open` chưa có quyết định;
final chỉ từ `initial_decided`, initial khớp snapshot và final còn rỗng. Không
còn hàng khớp → 409 `review_conflict`. Cùng transaction với append sự kiện và
quyết định phiên, lỗi rollback toàn bộ. `SELECT FOR UPDATE` của PostgreSQL và
`UNIQUE(case_id, prev_hash)` vẫn giữ; riêng UNIQUE không ngăn request cũ nối
thêm quyết định lặp vào đuôi mới trên SQLite. Không migration/hợp đồng mới.

| Bảng | Nội dung chính |
|---|---|
| `sessions` | id, trạng thái, challenge/token tạm và snapshot luồng (JSON), thời điểm tạo/hoạt động cuối/quyết định cuối, cờ từng vào review, dấu media đã dọn |
| `module_results` | session_id, module, model_version, status, score, prob_attack, quality/evidence và payload JSON; snapshot mỗi lần quyết định |
| `decisions` | session_id, hành động, confidence nếu có (không tự bịa), ngưỡng tạm đã dùng, phiên bản cấu hình, thời điểm |
| `review_cases` | session_id duy nhất, ưu tiên, người nhận, trạng thái, quyết định ban đầu/cuối và snapshot bằng chứng |
| `review_events` | **Chỉ ghi thêm**: case_id, actor, hành động, lý do, ghi chú, payload, `prev_hash`, `hash`; trigger DB từ chối UPDATE/DELETE |
| `forensic_jobs` | SHA-256 trên byte gốc, filename/payload, trạng thái, kết luận, đường dẫn nguồn/báo cáo, chữ ký mock |
| `forensic_segments` | job_id, t_start, t_end, tín hiệu từng module và cờ applicable |
| `cleanup_audits` | mỗi lượt dọn một dòng: thời điểm, file thực đã xóa, lý do từng file, chứng cứ được bảo vệ và lỗi nếu có |

Media phiên nằm ở `MEDIA_DIR/<session_id>/`; chứng cứ/báo cáo giám định ở
`MEDIA_DIR/forensic/<job_id>/`. DB lưu metadata/kết quả/hash/path, không lưu byte media.
`MODELS_DIR` và `DATA_DIR` mount read-only, `MEDIA_DIR` mount writable; không bake
trọng số/dataset/bí mật vào image. PostgreSQL có volume bền vững riêng.

Chính sách dọn (quyết định trưởng nhóm 15/10):

- Pass chưa từng vào review: `MEDIA_TTL_PASS_HOURS=24`, từ quyết định cuối.
- Ca review chưa `closed`: không xóa media. Nhân viên đóng ca thì ghi `sessions.decided_at`; `MEDIA_TTL_REVIEW_DAYS=30` tính từ thời điểm đóng, kể cả được chấp nhận.
- Chưa kết luận: `MEDIA_TTL_INCOMPLETE_HOURS=24`, từ hoạt động thành công cuối, không từ thời điểm tạo/file mtime.
- Giám định: `FORENSIC_TTL_DAYS` để trống mặc định = **không tự xóa**. Số ngày dương là opt-in; nhóm phải phê duyệt chính sách chứng cứ trước khi bật.
- Job dọn chạy lúc API khởi động và mỗi `MEDIA_CLEANUP_INTERVAL_SECONDS=300`; mỗi lượt ghi audit DB và một dòng log, gồm cả lượt không xóa được file. Lỗi giữa chừng vẫn ghi các file đã xóa thành công. DB metadata/audit không bị dọn theo TTL media.

Token hiện vẫn là token tạm PLAT-04, không thêm HMAC/TTL enforcement/409 mới/429 ở task này.
Nhật ký ghi actor `staff-unverified` vì xác thực nhân viên thuộc PLAT-06; không coi đây là chữ ký giám định thật.

## 6. Luồng một phiên eKYC

**Luồng opt-in theo purpose (FLOW-01/LIVE-01, 24/10):** xem
[`dynamic-session-api.md`](dynamic-session-api.md). Body tạo phiên mới sinh gói
ánh sáng/ánh mắt/quay đầu/câu đọc, yêu cầu mã lượt ở upload/finalize/voice và luôn
đọc câu khi đăng ký/khôi phục. Chỉ mở mock; real/mixed chặn 503 cho tới khi có đủ
bộ kiểm chứng thật. Phần dưới mô tả MVP tương thích cũ khi không gửi body.

1. Web hiện màn đồng ý, xin quyền camera, rồi chạy cổng chất lượng (MediaPipe). Chưa đạt thì nhắc chụp lại, chưa gửi gì lên.
2. Đạt cổng chất lượng xong, web mới gọi `POST /v1/sessions` và nhận thử thách. Tạo phiên **ngay trước bước nháy màu** (không phải ngay sau đồng ý) vì thử thách chỉ sống 120 giây (ADR-0011); quyết định trưởng nhóm 15/10, CAP-01. Mỗi lần chụp lại cũng đi qua cổng chất lượng trước (CAP-02).
3. Web phát chuỗi màu, ghi thời điểm vẽ (`requestAnimationFrame`) và thời điểm từng khung (`requestVideoFrameCallback`), chạy CamProbe.
4. Web gửi media và signals, rồi gọi `finalize`.
5. Server chạy song song qua orchestrator preload trong lifespan → `ModuleResult[]`. Hiện nhóm finalize gồm quality, face_pad, face_deepfake, chromapulse, camprobe; SBI thuộc task mô hình, không thêm tên module ngoài hợp đồng.
6. ROUT-02 dùng TrustRouter: cổng hợp lệ/thời gian → chất lượng → hiện diện → OOD nếu có → hiệu chỉnh từng module → hợp nhất và ngưỡng khóa trong `ml/configs/thresholds.yaml`. Hiện max-fusion và ngưỡng vẫn `provisional: true`, chờ dữ liệu calib_fit và ROUT-03. Quality fail được retry trước khi xét face degraded; lỗi tại bước đã tới không pass. Mặt ≤ B pass, ≥ A review; giọng ≤ voice.spoof_threshold riêng thì pass. WER chỉ dùng khớp câu, không vào fusion. API giữ counters, khóa hàng và lưu snapshot ngưỡng/hash YAML trong decisions; không thêm migration.
7. Nếu ở vùng giữa → trả `voice_challenge` kèm câu tiếng Việt → web gửi `voice` → chạy bước giọng nói → quyết định cuối.
8. Ca `review` tạo `review_case`; mọi bước ghi nhật ký.

PLAT-08 dùng executor chung, một predict/module và FIFO tối đa3 tác vụ chờ/module
(DETECTOR_QUEUE_SIZE), với bản sao input riêng;
worker không truy cập DB/session. Deadline detector mặc định4 giây (kể cả queue),
error/degraded không pass; kết quả muộn bị bỏ. Preload lỗi giữ error tới restart,
health degraded chỉ công khai tên module. Finalize/voice dùng ngân sách inference
chung theo Settings INFERENCE_BUDGET_SECONDS (mặc định4,8 giây) tính trước chờ DB,
chừa200ms cho commit/response trên DB bình thường;
PostgreSQL lock_timeout mặc định2 giây trả503 storage_busy khi hết chờ khóa.
Latency thực từng detector được lưu trong ModuleResult và log không transcript.

## 7. Môi trường chạy

| Thành phần | Phiên bản |
|---|---|
| Python | 3.12 (quản lý bằng `uv`) |
| Node.js | ≥ 20 (npm) |
| PostgreSQL | 16 (Docker) |
| Chạy demo | Docker Compose trên một máy có GPU, không phụ thuộc mạng |


### Hồ sơ MVP (ADR-0012, ROUT-01)

`ROUTER_PROFILE=full` mặc định giữ luồng trên. `mvp` đợt 2 chọn bảy module quality,
face_pad, face_deepfake, camprobe, voice_challenge, voice_spoof, lipsync ngay từ preload
và mọi lần chạy orchestrator (cả lời gọi bàn duyệt/giám định). Router chỉ bắt buộc
CamProbe cho presence, voice_spoof cho quyết định giọng; lipsync chạy tham khảo
ở MVP (ADR-0012 §6). Câu thử thách và cờ cắt
ghép vẫn áp dụng, kiểm câu trước cờ. Calibrator MVP bắt buộc PAD/deepfake/spoof
đúng model_version; full còn bắt buộc lipsync. Kết quả lipsync MVP vẫn lưu và hiện
cho người duyệt, không tham gia quyết định dù thiếu/lỗi/timeout;
không đổi ngưỡng, hợp đồng, thứ tự cổng hay xử lý lỗi. Metadata thresholds của
quyết định MVP thêm router_profile; full giữ nguyên metadata. Script fit thật chỉ
đọc calib_fit; PAD video lấy khung giữa và voice loại replay, JSON tạm được commit.

ADR-0012 mục 2 cập nhật 18/10: MVP dùng artifact identity cho PAD, GenD, voice_spoof và lipsync (đợt 2 §5), cắt
điểm thô theo epsilon theo quyết định duyệt PR #28. Identity ghi provisional và
“MVP — không dùng cho báo cáo”, không tạo số mẫu hoặc metrics học giả. Store nạp
artifact theo method/version; router không có fallback ngầm. Sinh identity chỉ
cần mã/config/version wrapper, không cần dữ liệu. Công cụ fit ở trên để dùng ở
giai đoạn thay thế sau MVP, không phải điều kiện chạy demo hôm nay.

Module được yêu cầu nhưng nằm ngoài profile trả ModuleResult error/E_INTERNAL
với evidence disabled_by_profile và nhãn tiếng Việt, không bị bỏ qua. Module này
vẫn không được preload/chạy. Giám định MVP vì thế ra inconclusive khi thiếu bước;
JSON nội bộ giữ evidence và báo cáo HTML hiển thị lý do. Luồng người dân chỉ yêu
cầu module trong profile nên giữ phản hồi cũ. Health giữ schema hiện có vì thêm
router_profile sẽ cần đổi snapshot hợp đồng OpenAPI.
