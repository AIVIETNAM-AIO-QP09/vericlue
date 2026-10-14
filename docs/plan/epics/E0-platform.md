# E0 — Nền tảng (PLAT)

> Mục tiêu epic: repo chạy được đầu–cuối với mô-đun giả lập trước **17/10 (M0)**, để mọi người phát triển song song.

---

### PLAT-01 · Khởi tạo uv workspace, công cụ chất lượng, script setup

> ✅ **Đã xong 14/10** (Claude): `pyproject.toml` gốc (ruff, pytest, nhóm dev), `.pre-commit-config.yaml`, `scripts/setup.ps1`, `scripts/setup.sh`, `scripts/fetch_external.py`, `scripts/plan_check.py`, `scripts/new_handoff.py`, test cho script.
> **Phần chuyển cho task khác:**
> - PLAT-03: thêm `[tool.uv.workspace] members = ["services/api", "ml"]` khi tạo hai gói.
> - PLAT-07: chạy `fetch_external.py --pin` để ghim commit vào `repos.yaml`.

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 0,5 | S0 | P0 | — |

**Mục tiêu:** một lệnh setup cài đủ Python 3.12 và thư viện; có ruff và pytest dùng chung.
**Đọc trước:** `AGENTS.md`, `docs/adr/0001-*`, `docs/adr/0009-*`, `scripts/README.md`, `external/repos.yaml`.

**Đầu ra:**
- `pyproject.toml` ở gốc:
  - `[tool.uv.workspace] members = ["services/api", "ml"]`;
  - cấu hình `ruff` (line-length 100, target py312, rules E, F, I, B, UP);
  - cấu hình `pytest` (testpaths `services/api/tests`, `ml/tests`).
- Nhóm dev dependencies: `ruff`, `pytest`, `pytest-cov`, `nbstripout`, `pre-commit`.
- `scripts/setup.ps1` và `scripts/setup.sh`: kiểm tra `uv` → `uv python install 3.12` → `uv sync --all-packages` → copy `.env.example` → `.env` nếu chưa có → `npm install` trong `apps/web` nếu có `package.json`.
- `scripts/fetch_external.py`: đọc `external/repos.yaml`, clone hoặc checkout đúng commit vào `external/<name>`; bỏ qua nếu đã đúng commit.
- `.pre-commit-config.yaml`: ruff, ruff-format, trailing-whitespace, end-of-file-fixer, check-added-large-files (1 MB), nbstripout.

**Các bước:**
1. Viết `pyproject.toml` gốc (chưa có member nào thì `uv sync` vẫn phải chạy được; PLAT-03 sẽ thêm member).
2. Viết hai script setup, chạy thử trên Windows (PowerShell).
3. Viết `fetch_external.py`. Điền commit cụ thể (commit mới nhất ở `main` hôm nay) vào `repos.yaml`.

**Tiêu chí hoàn thành:**
- [ ] Trên máy mới: `./scripts/setup.ps1` chạy xong không lỗi.
- [ ] `uv run ruff check .` và `uv run pytest` chạy được (0 test cũng được).
- [ ] `uv run python scripts/fetch_external.py` clone đủ repo, chạy lại lần 2 không lỗi.
- [ ] `repos.yaml` không còn `TODO`.

**Lưu ý:** máy nhóm là Windows, không có `make`. Không thêm công cụ bắt mọi người phải cài thêm.

---

### PLAT-02 · Khởi tạo web Next.js

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 0,5 | S0 | P0 | — |

**Mục tiêu:** app Next.js chạy được với 3 khu vực `/verify`, `/review`, `/forensic` (trang trống có tiêu đề).
**Đọc trước:** `apps/web/README.md`, `docs/conventions/coding-standards.md`.

**Đầu ra:**
- `apps/web/` tạo bằng `create-next-app`: TypeScript, App Router, `src/`, ESLint, Tailwind.
- Thư mục: `src/app/{verify,review,forensic}/page.tsx`, `src/lib/{api,capture}/`, `src/components/`, `src/i18n/vi.ts`.
- Prettier; Vitest với 1 test mẫu; script `lint`, `test`, `build`.
- `.env.local.example` có `NEXT_PUBLIC_API_URL`.

**Tiêu chí hoàn thành:**
- [x] `npm run dev` mở được 3 trang (kiểm: 200 trên localhost và IP LAN).
- [x] `npm run lint`, `npm run test`, `npm run build` xanh.
- [x] Mở trên điện thoại cùng mạng Wi-Fi (`npm run dev -- -H 0.0.0.0`) hiển thị đúng — đã xác nhận trên điện thoại thật (14/10).

**Lưu ý:** camera trên điện thoại cần **HTTPS** (trừ localhost). Ghi vào README cách dùng `next dev --experimental-https` hoặc tunnel (cloudflared hoặc ngrok) để thử trên điện thoại.

---

### PLAT-03 · Khung FastAPI + gói vericlue_ml + ModuleResult + mô-đun giả lập

> ✅ **Đã xong 14/10** (nhánh `feat/PLAT-03-api-ml-skeleton`). Đã kiểm trên server chạy thật: `/healthz` và `/docs` trả 200. Thêm ngoài task card: test `test_contract_sync.py` bảo đảm model Python khớp hợp đồng JSON; cấu hình ruff cho FastAPI.

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S0 | P0 | PLAT-01 |

**Mục tiêu:** API chạy được, có giao diện `Detector` và mock cho mọi bộ phát hiện.
**Đọc trước:** `docs/architecture/architecture.md` §2–§3, `packages/contracts/schemas/module_result.schema.json`, `ml/README.md`, `services/api/README.md`.

**Đầu ra:**
- `ml/pyproject.toml` (gói `vericlue_ml`, layout `src/`). Phụ thuộc tối thiểu: `numpy`, `pydantic`, `pyyaml`. Thư viện nặng (torch…) để ở optional extras `[face]`, `[voice]`.
- `ml/src/vericlue_ml/common/result.py`: model Pydantic `ModuleResult`, `Evidence` khớp schema; enum `Module`, `Status`, `ErrorCode`, `Gate`.
- `ml/src/vericlue_ml/common/detector.py`: `Protocol Detector` + `DetectorInput` (đường dẫn ảnh, video, âm thanh, signals, metadata).
- `ml/src/vericlue_ml/mock/`: một mock cho mỗi module trong enum. Mock trả kết quả có tính quyết định (deterministic) theo `scenario` trong metadata: `genuine`, `print`, `replay`, `virtual_cam`, `faceswap`, `voice_clone`, `low_quality`, `error`.
- `ml/src/vericlue_ml/registry.py`: `get_detector(name)` → mock nếu `USE_MOCK_MODELS=true`, ngược lại là mô hình thật (tạm `NotImplementedError`).
- `services/api/pyproject.toml` (gói `vericlue_api`, phụ thuộc `vericlue_ml` qua workspace, `fastapi`, `uvicorn`, `pydantic-settings`).
- `services/api/src/vericlue_api/main.py`, `core/config.py` (đọc `.env`), `routers/health.py` (`GET /healthz`).
- Test: `ml/tests/test_result_schema.py` (mọi mock validate được với JSON Schema), `services/api/tests/test_health.py`.

**Tiêu chí hoàn thành:**
- [x] `uv run uvicorn vericlue_api.main:app --app-dir services/api/src` chạy; `/healthz` trả 200.
- [x] Mọi mock trả `ModuleResult` hợp lệ với JSON Schema (test tự động).
- [x] Mock `error` trả `status=error`; có test.
- [x] `uv run pytest` xanh trên CPU, không cần GPU hay mô hình.

---

### PLAT-04 · Chốt API v1 và hợp đồng; sinh type cho web

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 (+M1 duyệt) | 1 | S0 | P0 | PLAT-02, PLAT-03 |

**Mục tiêu:** toàn bộ endpoint ở `architecture.md` §4 tồn tại với dữ liệu mock, có OpenAPI, web dùng được type TypeScript.
**Đọc trước:** `docs/architecture/architecture.md` §4–§6, `packages/contracts/schemas/session.schema.json`.

**Đầu ra:**
- Router `sessions.py`: `POST /v1/sessions` (sinh `challenge` 8 màu ngẫu nhiên từ bảng ở proposal Phụ lục A; `hold_ms` 400–650; `transition_ms` 150), `POST /media`, `POST /signals`, `POST /finalize`, `POST /voice`.
  - Giai đoạn này `finalize` gọi mock + **luật quyết định tạm thời**; ROUT-02 thay sau.
- Router `review.py` và `forensic.py` trả dữ liệu mock đúng hình dạng.
- `packages/contracts/examples/*.json`: ví dụ cho mọi request/response.
- `apps/web/src/lib/api/`: type sinh bằng `openapi-typescript` từ `/openapi.json`, cộng một client nhỏ có gắn token. Script `npm run gen:api`.
- Cập nhật `session.schema.json` nếu có thay đổi, kèm `[contract]` trong PR.

**Tiêu chí hoàn thành:**
- [x] `/docs` (Swagger) liệt kê đủ endpoint (15; có test `test_openapi.py`).
- [x] Ví dụ trong `packages/contracts/examples` validate được bằng schema (test `test_contract_examples.py`).
- [x] Web gọi `POST /v1/sessions` và nhận challenge (test `client.test.ts` với fetch giả; API thật: `test_sessions_api.py`).
- [x] API **không bao giờ** trả score ra ngoài trong phản hồi cho `/verify` (có test cho create/finalize/voice và hồ sơ ca duyệt).

---

### PLAT-05 · Cơ sở dữ liệu, migration, Docker Compose

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S1 | P0 | PLAT-04 |

**Mục tiêu:** lưu phiên, kết quả, quyết định, ca duyệt, giám định vào PostgreSQL; chạy cả hệ thống bằng một lệnh.
**Đọc trước:** `docs/architecture/architecture.md` §5.

**Đầu ra:**
- SQLAlchemy 2 + Alembic: bảng `sessions`, `module_results`, `decisions`, `review_cases`, `review_events`, `forensic_jobs`, `forensic_segments`.
- `docker-compose.yml`: `db` (postgres:16), `api` (Dockerfile trong `services/api`), `web` (Dockerfile trong `apps/web`). Volume cho `MEDIA_DIR`.
- `services/api/src/vericlue_api/services/storage.py`: lưu file vào `MEDIA_DIR/<session_id>/`, hàm dọn file quá hạn (`MEDIA_TTL_*`) chạy định kỳ.
- `docs/runbooks/dev-setup.md` cập nhật lệnh chạy.

**Tiêu chí hoàn thành:**
- [ ] `docker compose up` → web :3000, api :8000, db chạy; một phiên mock đi hết luồng và được lưu vào DB.
- [ ] `alembic upgrade head` chạy trên DB trống.
- [ ] Test dọn file quá hạn.

---

### PLAT-06 · Bảo mật phiên và khóa ký

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 1 | S1 | P0 | PLAT-05 |

**Mục tiêu:** chống phát lại và dò hệ thống; có khóa ký báo cáo.
**Đọc trước:** proposal §2.7(a), §3.3; ADR-0008; **ADR-0011** (token theo phiên, chống phát lại).

**Đầu ra:**
- Token **theo phiên**, ký HMAC (`SESSION_SIGNING_SECRET`), gắn `session_id`, hết hạn sau `SESSION_TTL_SECONDS` (mặc định 300), gửi qua `Authorization: Bearer`.
- **Chống phát lại bằng máy trạng thái:** trong mỗi lượt, mỗi bước (media, signals, finalize, voice) chỉ nhận **một lần**.
- **Mỗi thử thách sống 120 giây** kể từ lúc cấp; chụp lại thì cấp thử thách mới; media gắn thử thách cũ hoặc hết hạn bị từ chối.
- Seed thử thách chỉ lưu ở server; client chỉ nhận chuỗi màu của phiên.
- Giới hạn lượt: tối đa 3 phiên/giờ/IP (cấu hình được); tối đa 2 lần chụp lại mỗi phiên, sau đó chuyển `review`.
- `scripts/gen_keys.py`: sinh `SESSION_SIGNING_SECRET` và cặp khóa Ed25519 vào `secrets/` (đã gitignore).
- `core/signing.py`: `sign(payload: bytes) -> sig`, `verify(...)`, `public_key_fingerprint()`.
- **Xác thực nhân viên** cho `/v1/review/*` và `/v1/forensic/*` (PLAT-04 để trống): đơn giản là đủ cho demo (ví dụ khóa API của nhân viên qua header, cấu hình trong `.env`).
- Kiểm `Content-Length` trước khi nhận upload (PLAT-04 chỉ kiểm `MAX_UPLOAD_MB` sau khi đã nhận multipart).
- Xem thêm danh sách việc để lại trong bàn giao PLAT-04 (`docs/status/handoffs/*plat-04*`).

**Tiêu chí hoàn thành:**
- [ ] Token sai chữ ký hoặc hết hạn → 401 (test).
- [ ] Gọi lại một bước đã nhận trong cùng lượt → 409 (test).
- [ ] Media gắn thử thách quá 120 giây hoặc thử thách cũ → bị từ chối (test).
- [ ] Vượt giới hạn lượt → 429 (test).
- [ ] Quá 2 lần chụp lại → `review` (test).
- [ ] Ký và xác minh chữ ký Ed25519 (test).
- [ ] Gọi `/v1/review/*`, `/v1/forensic/*` không có xác thực nhân viên → 401 (test).

---

### PLAT-07 · CI và pre-commit chạy thật

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S0 | P0 | PLAT-01, PLAT-02 |

**Mục tiêu:** mọi PR tự kiểm tra lint, test, chặn file lớn.
**Đọc trước:** `.github/workflows/ci.yml`.

**Tiêu chí hoàn thành:**
- [ ] Repo đã đẩy lên GitHub; bật branch protection cho `main` (cần PR, cần CI xanh, cần 1 người duyệt).
- [ ] CI xanh trên `main`.
- [ ] Thử commit một file `.wav` giả → job `guard` báo lỗi.
- [ ] Job `plan` trong CI chạy `scripts/plan_check.py`: backlog sai thì CI đỏ (đã có sẵn trong `ci.yml`).
- [ ] Chạy `uv run python scripts/fetch_external.py --pin` để ghim commit vào `external/repos.yaml`.
- [ ] `CODEOWNERS` đã điền tài khoản thật.

---

### PLAT-08 · Bộ điều phối phân tích (orchestrator)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S1 | P0 | PLAT-05 |

**Mục tiêu:** `finalize` chạy song song các bộ phát hiện, lưu kết quả, gọi TrustRouter, trả quyết định trong ≤ 5 giây.
**Đọc trước:** `docs/architecture/architecture.md` §6.

**Đầu ra:**
- `services/api/src/vericlue_api/services/orchestrator.py`: chạy các detector (thread pool), timeout mỗi detector (mặc định 4 giây → `status=error`), lưu `module_results`.
- Nạp mô hình **một lần** khi API khởi động (lifespan), không nạp mỗi request.
- Ghi `latency_ms` từng bước để làm R6.

**Tiêu chí hoàn thành:**
- [ ] Một detector bị lỗi hoặc timeout thì phiên **không** được `pass` (test).
- [ ] Log thời gian từng detector.
- [ ] Với mock, `finalize` < 1 giây.

---

### PLAT-09 · Kiểm thử đầu–cuối theo kịch bản

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P0 | PLAT-08, ROUT-02, CAP-06 |

**Mục tiêu:** mỗi lần gộp code, máy tự kiểm tra cả hệ thống vẫn ra đúng quyết định cho các kịch bản demo. Như vậy bản demo không bị "hỏng ngầm" trước ngày thi.
**Đọc trước:** proposal §1.4 (kịch bản demo); ROUT-02 (các nhánh quyết định); mock theo `scenario` (PLAT-03).

**Đầu ra:**
- `services/api/tests/e2e/test_scenarios.py`: gọi API (TestClient) với mock theo kịch bản. Kết quả mong đợi:

  | Kịch bản | Kết quả |
  |---|---|
  | `genuine` | `pass` |
  | `low_quality` | `retry`, sau 2 lần thì `review` |
  | `print`, `replay` | `review` |
  | `virtual_cam` | `review` ưu tiên cao |
  | `faceswap` | `review` |
  | `voice_clone` | `voice_challenge` → `review` |
  | `error` | không bao giờ `pass` |

- `apps/web/e2e/verify.spec.ts` (Playwright, nếu kịp): mở `/verify` với camera giả của Chromium (`--use-fake-device-for-media-stream`) và đi hết luồng `genuine`.
- Chạy trong CI.

**Tiêu chí hoàn thành:**
- [ ] Đủ 7 kịch bản ở mức API, chạy trong CI dưới 1 phút.
- [ ] Cố ý làm hỏng một mock → test đỏ (chứng minh test có tác dụng).
