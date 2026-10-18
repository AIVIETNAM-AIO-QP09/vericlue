# Bàn giao · CAP-06 · AIVIETNAM-AIO-QP09+Claude · 2026-10-18 11:56

**Nhánh:** feat/CAP-06-real-media-mvp (chưa commit, chưa mở PR tại thời điểm ghi)
**Trạng thái task sau phiên này:** doing — đây là **lõi MVP** theo ADR-0012. Theo yêu cầu giao việc, dòng CAP-05/06/07 và PRES-03 trong `backlog.md` **không đổi** (vẫn `todo`) và các tiêu chí cần thiết bị thật trong thẻ chưa được tick.

## Đã xong
- **Ảnh thật** (CAP-06): bấm "Bắt đầu" ở bước nháy màu thì chụp một khung JPEG từ camera, cạnh dài ≤ 1280 px, chất lượng 0,9 (`apps/web/src/lib/capture/media.ts`; thứ tự chụp → clip → nháy ở `mediaPhase.ts`, nối ở `VerifyFlow.tsx` `startFlash`). Chụp *trước* khi nháy, màn hình trung tính, hiện "Giữ yên".
- **Video 3 giây**: `startVideoClip` ghi webm bằng MediaRecorder (VP8/VP9), gửi trường `video` của `/media`. **Quay xong clip rồi MỚI chạy chuỗi màu** (quyết định trưởng nhóm khi duyệt PR #29: video quay lúc nháy màu làm GenD chấm mặt bị ám màu). Trình duyệt không có webm thì bỏ video (trường tùy chọn). Có hạn chót khi `stop()` mà không có sự kiện `stop`.
- **Giọng thật** (CAP-07): `voiceRecorder.ts` + `public/pcm-recorder.worklet.js` ghi bằng AudioWorklet ở tần số gốc, `wav.ts` hạ về 16 kHz (OfflineAudioContext, dự phòng `boxResample`) và mã hóa WAV PCM 16-bit mono ngay trên trình duyệt. Nút Bắt đầu/Dừng, tối đa 8 giây, tối thiểu 1 giây; tắt echoCancellation/noiseSuppression/autoGainControl. Micro chỉ được xin ở bước đọc câu. Kèm video khi trả lời giọng nếu có.
- **CamProbe phía trình duyệt** (CAP-05): `camprobe.ts` — cờ `api_tamper_flags` (toString còn `[native code]`, thuộc tính `prototype` lạ, thuộc tính riêng lạ, gán đè lên `navigator.mediaDevices`, so với bản gốc trong `<iframe>` sạch), thăm dò `applyConstraints` `exact` 640×480 và 320×240 trên **bản sao track** (đọc lại `getSettings()` và kích thước khung thật; so không phân biệt xoay dọc/ngang), `duplicate_frame_ratio` (30 khung, ảnh xám 24×24), `device_label`, `track_settings`, `track_capabilities`. **Chạy sau khi đã chụp ảnh + quay clip** để ảnh không bị hạ 320×240; kích thước ảnh thật ghi vào `signals.client_quality` (schema khai object tự do, không sửa contracts). Hết `FRAME_SIZE_SETTLE_MS` mà khung chưa đổi → `frame_size_changed=null` kèm `frame_wait_ms`, KHÔNG fail; chỉ `false` (fail) khi `getSettings()` báo đã đổi mà khung thật không đổi. Có hạn 8 giây, hủy được, tắt bản sao track khi rời trang/hết hạn. Gửi trong `signals.camprobe`. Viết lại kỹ thuật CreepJS, **không chép mã** nên không có `vendor/` và `third_party/README.md` không đổi.
- **`ml/src/vericlue_ml/presence/camprobe.py`** (PRES-03): `CamProbeDetector` → `ModuleResult` gate pass/fail theo thẻ; ngưỡng là hằng số có tên `MIN_APPLY_CONSTRAINTS_MS = 5.0`, `MAX_DUPLICATE_FRAME_RATIO = 0.5`; nhãn tiếng Việt cho cờ và cho luật thăm dò; tên thiết bị chỉ là bằng chứng phụ. Thiếu/sai dạng `camprobe` → `degraded` (không bao giờ pass). Đăng ký factory trong `registry.py` (chỉ thêm factory + một dòng) và `models.yaml`.
- **Người dân vẫn chỉ thấy** pass/retry/review/voice_challenge. Chuỗi mới nằm trong `vi.verify.voice`, không có điểm số hay chữ "giả mạo".
- **Trang dev-only `/lab/session?id=<mã phiên hoặc mã ca>`** (mục g): đọc API bàn duyệt có sẵn, hiện từng module (trạng thái, cổng, điểm thô, xác suất, phiên bản, thời gian, bằng chứng). `notFound()` khi `NODE_ENV !== "development"`; đã kiểm bản build: prerender status 404.
- Sau review (`reviewer`) và duyệt của trưởng nhóm đã sửa: false positive khung hình xoay/không đo được, `getCapabilities` thiếu ở trình duyệt cũ, CamProbe có hạn + hủy + tắt clone, dọn ghi âm dùng chung cho mọi nút "Bắt đầu lại"/pagehide/bfcache, race `startVoice`/`finishVoice`/`startFlash`, nối worklet qua Gain 0 và `resume()` lại cho iOS, không gửi `duplicate_frame_ratio: null`, quay clip TRƯỚC khi nháy màu, thăm dò `applyConstraints` SAU khi chụp.
- Test mới: `media.test.ts`, `wav.test.ts`, `voiceRecorder.test.ts`, `camprobe.test.ts` (156 test, gồm mediaPhase.test.ts kiểm thứ tự ảnh → clip → nháy màu), `ml/tests/test_camprobe.py` (71 test).

## Đang dở
- Chưa thử trên **thiết bị thật** (Android tầm trung, iPhone), chưa thử OBS/tiện ích giả camera/Deep-Live-Cam. Các tiêu chí thẻ CAP-05 (không cờ trên trình duyệt thường; có cờ với tiện ích giả; OBS bất thường), CAP-06 (đi hết phiên thật với API thật, mạng chậm), CAP-07 (xin quyền micro, đọc sai thử lại) **chưa tick**.
- Chưa có test hành vi cho `VerifyFlow.tsx` (môi trường vitest là `node`, không có jsdom/React Testing Library); `VerifyFlow.source.test.ts` chỉ quét chuỗi. Các hàm lõi đã có test; luồng ghép (startFlash/startVoice/finishVoice/restart) chỉ kiểm bằng typecheck, lint và đọc mã + review.
- `capture_at_ms` của máy chủ **chưa dùng** (ChromaPulse không chạy ở hồ sơ mvp); `frame_times` vẫn rỗng (CAP-04).

## Bước tiếp theo
1. Chạy API thật + web (`ROUTER_PROFILE=mvp`, `USE_MOCK_MODELS=false`) trên HTTPS, thử một phiên đầy đủ bằng mặt và giọng của mình trên Android và iPhone: kiểm WAV có dữ liệu (iOS Safari: AudioWorklet có gọi `process` không, `sampleRate` thực), webm có tới `/media`, camprobe không fail oan người thật.
2. Mở `/lab/session?id=<session_id>` ở `npm run dev` để xem điểm từng module. Lưu ý: API chỉ tạo ca cho phiên ra `review`; phiên `pass` không có ca nên không xem được ở đây (xem "Câu hỏi cho nhóm"). Ý kiến AI chỉ mở sau quyết định ban đầu nên nút trên trang ghi quyết định `request_retry` với ghi chú `dev-test` (ghi vào chuỗi băm kiểm toán của ca đó).
3. Thử bằng OBS Virtual Camera, một tiện ích giả camera và webview trong ứng dụng (Zalo/Messenger) để xem camprobe có bắt/oan không; ghi kết quả vào bàn giao của PRES-04 hoặc ROUT-03. Ngưỡng `5 ms` và `0,5` là TẠM, chưa có số liệu.
4. Khi đã đạt các tiêu chí trên thiết bị thật: tick thẻ CAP-05/06/07, PRES-03 và đổi dòng backlog (việc của người nhận task, không làm ở phiên này theo yêu cầu).

## Quyết định, lưu ý, bẫy
- **iOS micro khi camera đang mở:** bước đọc câu gọi `getUserMedia({audio})` lần hai trong khi stream camera còn mở. WebKit có lỗi (bug 179363) về yêu cầu `getUserMedia` thứ hai làm track trước bị `muted` (lỗi ghi nhận cho cùng loại media; chưa xác nhận với audio-sau-video). **Chưa thử trên iPhone; để thử ở CAP-08**, không làm hôm nay. Phương án nếu lỗi: xin cả audio ngay từ `getUserMedia` đầu tiên (đổi `openFrontCamera`, sẽ đổi số lần gọi trong e2e) hoặc dừng track video trước khi xin micro.
- **ADR-0012** đã có ở PR #30 (lúc làm phiên này chưa vào `main`; đọc tạm từ `D:\Projects\Data4Life\docs\adr\0012-mvp-chay-that.md`).
- **Khác thẻ CAP-06:** JPEG 0,9 (thẻ ghi 0,95); video ~2,5 Mbps, 3 giây (thẻ ghi 4–6 Mbps); chụp một ảnh tại lúc bấm Bắt đầu thay vì tại `capture_at_ms`. Theo yêu cầu giao việc/ADR-0012; đổi lại khi làm CAP-04.
- **Contracts không đổi** (không gắn `[contract]`): `Signals.camprobe.constraint_probes[]` trong schema chỉ là `{"type":"object"}`, nên tên trường được ghi ở hai phía (`camprobe.ts` kiểu `ConstraintProbe`, `camprobe.py` docstring): `kind, requested{width,height}, ok, apply_ms, settings_before/after, settings_changed, frame_size_after, frame_size_changed (bool|null)`. Cờ có dạng `<api>:<lý do>`.
- **Luật camprobe.py:** probe `ok=false` và `frame_size_changed` null/thiếu đều **bị bỏ qua**; `frame_size_unchanged` chỉ fail khi `settings_changed=true` mà khung thật đo được không đổi (tránh fail oan người thật; ví dụ `<video>` ẩn trên iOS không nhận khung, hay khung đổi chậm). Hệ quả đã biết: camera ảo từ chối mọi `exact` hoặc không báo đổi `getSettings()` không bị bắt bằng luật khung (vẫn có luật `apply_ms < 5 ms` khi `getSettings()` không đổi).
- Thăm dò chạy trên `track.clone()`; Chrome tách cấu hình theo track nhưng Firefox/Safari có thể đổi độ phân giải nguồn chung → cần xem ảnh chụp có lệch độ phân giải không khi thử máy thật.
- Tắt AEC/NS/AGC cho giọng là suy luận chưa có A/B; iOS có thể bỏ qua constraints (không ghi `getSettings()` vào metadata). Không phát câu thử thách bằng loa (AEC tắt thì tiếng loa lọt vào mic).
- `speechSynthesis` làm mute track getUserMedia trên iOS (WebKit bug 218815): đừng thêm đọc câu bằng giọng máy khi đang giữ stream.
- `apps/web/public/` mới tồn tại (chứa worklet); Dockerfile đã `COPY .../public`. Bản build production nạp worklet từ `/pcm-recorder.worklet.js` (cần `script-src 'self'`).
- 4 hàm bàn duyệt (`listReviewCases`…) nằm trong client dùng chung nên vào bundle của `/verify` (không hiện ra giao diện). Có thể tách sau.
- Test khác trong toàn bộ pytest đôi lúc **flaky khi máy bận** (lần chạy đầu: `test_orchestrator.py::test_timeout_uses_one_shared_deadline…`; reviewer thấy `test_review_audit_api.py::test_concurrent_initial_exactly_one_wins`); chạy lại đều xanh, không thuộc diff này.
- Máy đã có sẵn `.venv` chưa đủ gói: chạy `uv sync --all-packages` và `npm ci` trong `apps/web` ở worktree mới.

## Câu hỏi cho nhóm
- **Siết schema `Signals.camprobe`?** Đề xuất (cần PR `[contract]` riêng của người có quyền): khai `constraint_probes[]` với các trường trên, `api_tamper_flags` kèm mẫu `<api>:<lý do>`, `duplicate_frame_ratio` là `number` tùy chọn (web hiện bỏ khóa khi không đo được, không gửi `null`), `frame_size_changed` là `boolean|null`.
- **Phiên `pass` không có ca duyệt** nên người thử không xem được điểm từng module của phiên đạt. Có muốn thêm đường đọc kết quả module theo `session_id` cho môi trường dev (API) không?
- **Ngưỡng CamProbe** (`MIN_APPLY_CONSTRAINTS_MS`, `MAX_DUPLICATE_FRAME_RATIO`) là hằng số tạm trong `camprobe.py`; chờ ROUT-03/PRES-04 chọn chính thức hoặc chuyển vào `thresholds.yaml`.

## Test đã chạy
Chạy ở thư mục gốc repo và `apps/web`, sau tất cả sửa đổi cuối cùng:
```
cd apps/web && npm run lint        -> sạch
cd apps/web && npm run test        -> 22 file passed, 1 skipped; 1314 test passed, 10 skipped
cd apps/web && npx tsc --noEmit    -> sạch
cd apps/web && npm run build       -> Compiled successfully; /lab/session có mặt, prerender status 404 (kiểm .next/server/app/lab/session.meta ở bản build cuối)
uv run ruff check . && uv run ruff format --check .  -> All checks passed; 260 files already formatted
uv run pytest                      -> 2064 passed, 29 skipped
uv run pytest ml/tests/test_camprobe.py -> 71 passed
uv run python scripts/gen_openapi.py --check -> openapi.json khớp code
uv run python scripts/plan_check.py -> 0 lỗi, 0 cảnh báo (chạy lại sau khi thêm file bàn giao này)
```
Chưa chạy: Playwright (`npm run test:e2e`), thử máy thật, `runner.e2e.test.ts` với API thật (cần `E2E_API_URL`).
