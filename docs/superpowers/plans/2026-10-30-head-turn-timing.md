# Slower Head Turn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax. Người dùng đã chọn triển khai trực tiếp trong chat.

**Goal:** Cho người dùng 4 giây mỗi hướng quay đầu bằng lịch server v2, giữ đủ kiểm chứng và cập nhật bản Android để thử lại.

**Architecture:** Contract-first: v1/6000 và v2/12000 là hai cặp hợp lệ. Generator phát v2; detector và Android dùng lịch gắn phiên, giữ tương thích lượt v1. Version hiệu chỉnh phụ thuộc protocol, chọn theo request mà không sửa trạng thái version chung.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, JSON Schema, pytest, Kotlin/Compose, Gradle/Paparazzi, OpenAPI TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-30-head-turn-timing-design.md` (người dùng duyệt ngày 30/10).

## Global Constraints

- v1 = 6000 ms, v2 = 12000 ms; v2 có ba đoạn 4000 ms. Thứ tự server chọn trái/phải/giữa như cũ.
- Giữ trần 30000 ms, 64 MiB và giới hạn decoder, không đổi góc/coverage/thời gian giữ hoặc thresholds.yaml.
- Không đổi màu/nhịp nháy, không thêm animation camera, TTS hoặc bước tập riêng.
- Không dùng calibrator v1 cho v2. Thiếu artifact tiếp tục degraded/unclear; lỗi không được coi là đạt.
- Không export media hoặc fit từ hai lượt thử; không sửa STATUS/ADR, không triển khai iOS, không push/PR.
- Build/ký cùng debug key, kiểm checksum/chữ ký trước install -r; không gỡ app/xóa Keystore.

## Review Focus

1. Version/duration đúng riêng lẻ nhưng sai cặp hoặc vượt 30 giây: phải từ chối (Task 1/2/3).
2. Request v1/v2 xen kẽ chọn nhầm calibrator vì mutable self.version/cache chung (Task 2).
3. Collector gộp hai protocol, kể cả mẫu lỗi, thành một report/version (Task 2).
4. Cạnh chuyển đoạn/kết thúc v2 làm clip ngắn, nhãn countdown lệch hoặc tự fallback mock (Task 3).
5. Server phát v2 nhưng APK/server cũ hoặc app iOS bị hiểu là đã tương thích (Task 4).

## Task 1: Hợp đồng và bộ sinh lịch v2

**Files:**
- Modify: `packages/contracts/schemas/session.schema.json`, `packages/contracts/openapi.json`, `packages/contracts/examples/session.CreateSessionResponse.dynamic.json`.
- Modify: `services/api/src/vericlue_api/schemas/session.py`, `services/api/src/vericlue_api/services/dynamic_challenge.py`.
- Modify: `apps/web/src/lib/api/schema.d.ts` (sinh từ OpenAPI, không sửa tay).
- Test: `services/api/tests/test_contract_schema.py`, `services/api/tests/test_dynamic_flows.py`, `services/api/tests/test_contract_examples.py`.

**Interfaces:**
- Produces: `DynamicChallenge` với version 1 hoặc 2, duration lần lượt 6000 hoặc 12000; head end <= 30000, voice start == head end.
- `generate_dynamic_challenge(settings, *, session_id, nonce)` giữ signature, phát v2.

- [ ] Thêm test schema/Pydantic cho hai cặp; `(1,12000)`, `(2,6000)`, version lạ/bool, duration 8000, head end >30000 hoặc sai voice offset bị chặn. Kiểm nguyên vẹn các field/điều kiện cũ.
- [ ] Thêm test generator/refresh trả version 2 và duration 12000; thứ tự ba hướng như cũ, voice start đúng; cấu hình hold màu nhỏ/lớn hợp lệ đều kết thúc <=30000.
- [ ] Run: `python -m pytest services/api/tests/test_contract_schema.py services/api/tests/test_dynamic_flows.py -q`. Expected: các test v2 mới FAIL vì contract/generator chỉ có v1.
- [ ] Sửa JSON Schema trước: version enum và conditional ràng buộc hai cặp; thêm test các ràng buộc thời gian chéo bằng Pydantic khi JSON Schema không biểu diễn phép cộng. Sau đó Pydantic dùng after-validator, generator phát v2 và HEAD_DURATION_MS=12000. Không cho client quyết định duration.
- [ ] Cập nhật ví dụ thành v2/12000/voice start tương ứng; giữ fixture v1 trong test để kiểm tương thích.
- [ ] Run: `python scripts/gen_openapi.py`; trong `apps/web`: `npm run gen:api`, `npm run typecheck`. Expected: exit 0, type sinh có cả hai duration/version.
- [ ] Run: `python -m pytest services/api/tests/test_contract_schema.py services/api/tests/test_dynamic_flows.py services/api/tests/test_contract_examples.py -q`; `python scripts/gen_openapi.py --check`. Expected: PASS và OpenAPI khớp.
- [ ] Commit: `feat(api): issue longer versioned head challenge [LIVE-01] [contract]`.

## Task 2: ML đọc hai protocol và tách provenance hiệu chỉnh

**Files:**
- Modify: `ml/src/vericlue_ml/presence/challenge.py`, `ml/src/vericlue_ml/presence/head_turn.py`.
- Create: `ml/src/vericlue_ml/presence/head_protocol.py` (hàm thuần kiểm protocol, không import native model).
- Modify: `ml/src/vericlue_ml/face/session_attack.py`, `ml/src/vericlue_ml/eval/session_calibration.py`, `ml/src/vericlue_ml/face/video_match.py`, `ml/src/vericlue_ml/face/match.py`.
- Test: `ml/tests/test_head_turn.py`, `ml/tests/test_gaze.py`, `ml/tests/test_session_attack.py`, `ml/tests/test_session_calibration.py`, `ml/tests/test_video_identity.py`, `ml/tests/test_video_frontal_match.py`, `ml/tests/test_face_match.py`.

**Interfaces:**
- Consumes: hai cặp protocol Task 1, metadata expected_challenge server-owned.
- Produces: `head_protocol_version(inp: DetectorInput) -> int` trong head_protocol.py; gọi expected_dynamic rồi kiểm cặp version/duration và head end <=30000.
- Produces: `session_model_version(base: str, protocol: int) -> str`: `base + '+session-video-v1'` hoặc `base + '+session-video-v2'`.
- Adapter chọn version bằng local variable; cache `dict[str, Calibrator | None]` và lock cho lần load đầu, gồm cả negative cache. `self.version` không bị đổi theo request.
- Collector một report chỉ có một protocol, xác định từ toàn manifest trước nạp model; report version có đúng suffix, fit dùng nguyên version đó.

- [ ] Thêm trace synthetic 12 giây đúng thứ tự và sai thứ tự; kiểm v1 vẫn như cũ, sai cặp/version/quá trần bị E_CHALLENGE_MISMATCH. Các trace hụt cửa sổ vẫn degraded; không nới hằng chất lượng.
- [ ] Thêm test gaze và các phần dùng expected_dynamic đọc v2 đúng session/challenge; version lạ, sai ID vẫn bị chặn.
- [ ] Thêm test adapter cùng instance v1→v2→v1 và xen kẽ bằng threads: chỉ artifact đúng suffix được dùng, self.version ổn định; thiếu/provisional/lỗi v2 không mượn v1, exception trả đúng local result version khi xác định được protocol.
- [ ] Thêm test collector v2/report/fit exact version; manifest chứa cả v1/v2 (kể cả mẫu video lỗi) bị từ chối trước make_runtime. Report version không hợp lệ vẫn bị chặn.
- [ ] Thêm test VideoFaceMatch có consistency: result v2 mang `VIDEO_MATCH_VERSION + '+head12s-v2'`; threshold mặt và consistency v1 không tạo gate pass v2. Không-consistency chỉ dùng frame chính diện vẫn giữ protocol/version cũ.
- [ ] Run: `python -m pytest ml/tests/test_head_turn.py ml/tests/test_gaze.py ml/tests/test_session_attack.py ml/tests/test_session_calibration.py ml/tests/test_video_identity.py -q`. Expected: test v2 FAIL trước thay đổi.
- [ ] Implement head_protocol, cho expected_dynamic nhận 1/2 đúng kiểu int; parse_head_plan kiểm pair và end bound. Giữ parse/evaluate chuyển động hiện có.
- [ ] Implement version/cache local của adapter và kiểm đồng nhất protocol toàn manifest trước collect. SessionReport chấp nhận suffix v1/v2, giữ report cũ v1 và mọi kiểm split/hash/nhãn hiện có. Không sửa raw backend identity.
- [ ] VideoFaceMatch tính result_version theo request khi with_consistency; mở rộng FaceMatch.predict_frames/_predict bằng optional `result_version: str | None = None` để giữ call cũ. Chỉ dùng threshold khi threshold.model_version khớp local result version; consistency phải khớp local version + '+view-consistency-v1'. Preload xác thực artifact trong tập version mà lớp detector hỗ trợ, không gán self.version theo request. Artifact đúng v2 được nhận, v1 không được dùng cho v2. Template/enrollment chưa đủ evidence tiếp tục chặn theo guard hiện có.
- [ ] Run suite phía trên cộng `ml/tests/test_session_views.py`, `ml/tests/test_calibration.py`, `services/api/tests/test_session_motion.py`, `services/api/tests/test_video_identity_api.py`, `services/api/tests/test_session_calibration_guards.py`, `services/api/tests/test_account_auth.py`. Expected: PASS, không mở guard và không nâng degraded/error.
- [ ] Ruff check/format phần Python thay đổi. Commit: `feat(ml): isolate longer head protocol calibration [FLOW-04]`.

## Task 3: Android theo lịch 4 giây và hiển thị thời gian

**Files:**
- Modify: `apps/android/app/src/main/java/vn/vericlue/app/capture/FaceTimeline.kt`.
- Modify: `apps/android/app/src/main/java/vn/vericlue/app/ui/screens/FaceScreens.kt`.
- Test: `apps/android/app/src/test/java/vn/vericlue/app/FaceTimelineTest.kt`, `apps/android/app/src/test/java/vn/vericlue/app/screenshots/FaceChallengeSnapshotTest.kt`.

**Interfaces:**
- Consumes: DynamicChallenge version/duration từ Task 1, giữ `FaceTimeline.from(challenge): FaceTimeline?`.
- Produces: `headRemainingSeconds(t: Double): Int?` và `nextHeadDirection(t: Double): TurnDir?` trên FaceTimeline; chỉ gọi next khi có segment tiếp theo (center biểu diễn null); UI phân biệt đoạn cuối bằng index.
- Không đổi shape Phase.Head hiện có để tránh snapshot/call-site không liên quan.

- [ ] Test v2 nhận đúng hai thứ tự, các mốc headStart+3999/4000/7999/8000/11999/12000; v1 vẫn 2 giây/đoạn. Duration/version sai, head end >30000, voice offset sai, thứ tự thiếu/không kết thúc center trả null.
- [ ] Test countdown ceil thời gian còn lại: 4 đầu đoạn, 1 cuối đoạn; null ngoài Head. Chuỗi hướng tiếp theo giữ đúng order và center. Phải có nhãn rõ cho đoạn cuối, không hiện bước thứ tư.
- [ ] Run từ apps/android: `./gradlew testDebugUnitTest --tests '*FaceTimelineTest*'`. Expected: test v2 validation/countdown mới FAIL.
- [ ] Implement kiểm cặp/biên trong FaceTimeline.from, helper thuần; giữ demo/passive riêng, không fallback khi lịch API sai.
- [ ] FaceTimelineScreen lấy thời gian từ CaptureClock như cũ, giữ mốc t0/điểm dừng, truyền remaining/next vào presentation. Hiện chữ đếm ngược và 'Tiếp theo: ...'; nhắc giữ hướng đến khi đổi. Không đổi camera/capture hoặc chèn delay/TTS/animation. Cập nhật preview giả lập dùng 4 giây/đoạn cho trải nghiệm nhất quán.
- [ ] Run: `./gradlew testDebugUnitTest assembleDebug` tuần tự. Expected: PASS; CitizenCopyTest và ThemeAccessibilityTest vẫn xanh.
- [ ] Run: `./gradlew recordPaparazziDebug --tests '*FaceChallengeSnapshotTest*'`; giữ ảnh trước/sau tại tmp/head-turn-4s và xem ảnh thật. Expected: nhãn không che mặt/nút dừng ở light/dark/compact/font200; nếu fixture chưa có biến thể thì thêm ca snapshot tương ứng.
- [ ] Commit: `feat(android): guide four-second head turns [APP-01]`.

## Task 4: Review, bàn giao và cập nhật máy thử

**Files:** cập nhật `docs/architecture/dynamic-session-api.md`, `docs/runbooks/session-face-calibration.md`, `docs/runbooks/android-recording-rehearsal.md`, `apps/android/README.md`, task LIVE-01/FLOW-04 và dòng backlog; tạo handoff bằng script.

**Interfaces:** consumes ba task trước; APK localhost:8421/signedMedia=true, backend v2, cùng signer debug đã cài.

- [ ] Chạy regression ML/API liên quan một lần trên tree cuối, OpenAPI --check, Ruff phần đổi, web typecheck. Expected: exit 0, guard mock/mixed/account-bound vẫn không bị mở.
- [ ] Fresh whole-branch review theo executing-plans; sửa phát hiện quan trọng bằng test RED→GREEN và chạy lại suite liên quan. Không sửa minor ngoài phạm vi.
- [ ] Ghi bàn giao: `python scripts/new_handoff.py --task LIVE-01 --who 'Ngoc Quang+Codex'`; cập nhật tiêu chí phần đã xong, giữ doing cho mục thiếu calibration/hardware. Ghi iOS chưa hỗ trợ v2 và giữ giới hạn kết quả thật. `python scripts/plan_check.py`, `git diff --check`. Expected: 0 lỗi kế hoạch/diff; ghi riêng cảnh báo có sẵn.
- [ ] Commit cuối có [LIVE-01] [APP-01] [contract], giữ local. Không cần hỏi lại push/PR vì đã có yêu cầu không push/PR.
- [ ] Xác minh APK output đã ký v2 bằng SDK apksigner, fingerprint phải đúng signer bản đang cài `822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75`. Sao APK và metadata mới vào `D:/vericlue/tmp/full-demo-setup/apk`, giữ backup APK cũ riêng trước thay; ghi SHA256 và commit Android thực tế. Không tạo key mới.
- [ ] Dùng launcher hiện có stop/start server, không đổi .env/DB/khóa; có update restart thì tạo phiên synthetic mới kiểm dynamic v2/12000/voice offset, không lưu token hoặc chạm media thật. Health phải ok/failed_modules rỗng, mock_models true vẫn đúng do OTP demo.
- [ ] ADB devices, chọn đúng máy Samsung đã ghép; install -r chỉ sau checksum/signer đúng, reverse tcp:8421, mở app. Nếu offline, giữ APK và hướng dẫn kết nối lại; không tự gỡ app/xóa dữ liệu khi khác signer.
- [ ] Người dùng bắt đầu phiên mới và tự thử. Chỉ báo 'đã cài/đã kiểm phần mềm' khi có output thật; chưa báo 'đạt xác minh' hoặc 'UX đã nghiệm thu' trước lượt mới.
