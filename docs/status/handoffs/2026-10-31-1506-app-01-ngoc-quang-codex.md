# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-10-31 15:06

**Nhánh:** `codex/APP-01-demo-integration`, nền `acef2c6`
**Trạng thái task sau phiên này:** doing — đã khóa 4 lỗ hổng an toàn của `MANUAL_FULL_DEMO`, phân tách rõ kết quả thử nghiệm với hiệu chỉnh chuẩn; chờ hoàn thiện parity/calibration cho giọng nói và khẩu hình trên mô hình thật

## Đã xong
- **1. Chặn chấp nhận giọng nói `degraded`/`error` hoặc cửa sổ chưa đo (`ml/src/vericlue_ml/common/manual_demo.py`):**
  - Sửa `ManualDemoThresholds.accepts_voice_spoof()` bắt buộc `status == Status.OK`, `error_code is None`, `diagnostic_only != True`, không phải `mock`.
  - Khi có `nes2net_windows`, bắt buộc `error_windows == 0`, `low_quality_windows == 0`, `all_source_samples_measured is True`, mọi cửa sổ con đều `status == "ok"`, `error_code is None`, `diagnostic_only != True` và `score <= 2.0`. Không bao giờ bỏ qua cửa sổ `not_applicable`/`degraded`.
  - Giữ nguyên đầu ra chẩn đoán hiện tại của `NES2Net` (`status="degraded", gate="unclear", diagnostic_only=True`); khi chạy `NES2Net` thật chưa hiệu chỉnh, phiên dừng ở `review` thay vì giả đạt.
- **2. Chốt `lipsync` bắt buộc trong `recovery` và cấp tài khoản có bước giọng nói (`session_flow.py`, `accounts.py`, `router/profiles.py`):**
  - Giữ nguyên `advisory_voice_modules=(Module.LIPSYNC,)` trong `router/profiles.py` cho các phiên MVP thông thường không gắn tài khoản.
  - Bỏ `Module.LIPSYNC` khỏi tập skip của `AccountStore._validate_biometrics()` (`accounts.py`), bắt buộc `LIPSYNC` đạt `status="ok"`, `gate="pass"`, `error_code=None` (và không phải `mock`) khi tạo hoặc khôi phục tài khoản có bước giọng nói.
  - Bổ sung `_lipsync_gate()` và kiểm tra `splice_flags` trong `SessionFlow.voice()` / `_manual_full_demo_voice()` cho `session.purpose == "recovery"` và `onboarding` có `account_enrollment`.
- **3. Khóa chính sách ngưỡng (`policy_id`) theo phiên và truy vết kết quả thử nghiệm (`session_flow.py`, `routers/sessions.py`, `accounts.py`, `enrolled.py`, `continuity.py`):**
  - `SessionFlow.create()` lưu `session.created_model_mode = "manual_full_demo"` và `session.manual_demo_policy_id = policy.policy_id`.
  - `_ensure_evaluation_binding()` kiểm tra trên mọi endpoint phiên (`media`, `signals`, `challenge`, `id-card`, `finalize`, `voice`, `account`): đổi bất kỳ ngưỡng nào (`pad_max`, `gend_max`, `match_min`, `consistency_min`) hoặc chuyển chế độ giữa phiên sẽ trả `409 session_expired`, buộc tạo phiên mới.
  - `match_enrolled()` (`enrolled.py`) và `FaceContinuityDetector` (`continuity.py`) gắn hậu tố `+manual-demo-<policy_id[:16]>` và `demo_policy_id`, đồng thời kiểm tra khớp `demo_policy_id` với kết quả `face_match` tham chiếu.
  - `DecisionRow.thresholds` và `AccountRow.encrypted_payload` lưu rõ `evaluation_mode="manual_full_demo"`, `demo_policy_id`, `manual_thresholds` và `calibrated=False`.
- **4. Chặn đăng ký lại tự hủy tài khoản cũ, cô lập tài khoản thử nghiệm và khóa cấu hình `protected` (`accounts.py`, `config.py`, `security_profile.py`):**
  - Xóa đoạn tự động đánh dấu `destroyed_at` khi trùng `id_number_hmac` trong `AccountStore.create()`; lượt đăng ký trùng CCCD bị từ chối với `409 enrollment_not_available`, giữ nguyên tài khoản hiện hữu.
  - Cô lập tài khoản `manual_full_demo` khỏi tài khoản chuẩn `standard` trong `AccountStore.create()`, `recover()` và `get()` thông qua binding trong payload mã hóa (`evaluation_mode` + `demo_policy_id`).
  - Thêm hàm quản trị có phạm vi rõ ràng `AccountStore.destroy_manual_demo_account(account_id=..., id_number_hmac=...)` chỉ hoạt động khi `manual_full_demo=True` và `security_profile="synthetic"`, không bao giờ xóa tài khoản `standard`.
  - Khóa `manual_full_demo` trong `Settings` và `security_profile_checks` (`no_manual_demo`): từ chối `security_profile="protected"`, `product_mode="tools"`, `router_profile="full"`, `use_mock_models=False`, `private_credentials=True` và `result_signing_key_file`.

## Đang dở
- **Phần còn thiếu để chạy mô hình thật đạt chuẩn hiệu chỉnh (không dùng mock/ngưỡng thủ công):**
  1. `VOICE_SPOOF` (`NES2Net`): hiện `Nes2NetTimelineDetector` trả `status="degraded", gate="unclear", diagnostic_only=True` vì còn thiếu đối chiếu frontend Fairseq↔Transformers và hiệu chỉnh ngưỡng tiếng Việt trên tập `calib_ltt`.
  2. `LIPSYNC` (`SyncNet`): cần hiệu chỉnh ngưỡng điểm tin cậy/độ lệch AV trên dữ liệu thực tế để `SyncNetDetector` trả `status="ok", gate="pass"` ổn định trên video điện thoại.
  3. Artifact hiệu chỉnh mặt và đối sánh (`ml/configs/thresholds.yaml` + các file calibration JSON cho `FACE_PAD`, `FACE_DEEPFAKE`, `FACE_MATCH`, `FACE_CONTINUITY` từ tập `calib_ltt` chia theo người, cộng quyền lưu mẫu `SEC-09`).
- Chưa thực hiện nghiệm thu trực tiếp trên điện thoại trong phiên này (không tự cài APK hay restart server đang dùng).

## Bước tiếp theo
1. Thực hiện checklist nghiệm thu trên điện thoại cho 3 luồng `đăng ký → đăng nhập lại → khôi phục` (gồm ca đạt và các ca từ chối: sai người, đọc sai câu, mất mạng, hết hạn phiên, đăng ký trùng CCCD).
2. Khi cần đặt lại một tài khoản thử nghiệm trên môi trường `synthetic` + `MANUAL_FULL_DEMO`, gọi tường minh `AccountStore.destroy_manual_demo_account(...)` thay vì đăng ký đè cùng CCCD.
3. Hoàn thiện parity + calibration cho `NES2Net` và `SyncNet` để bước giọng nói/khôi phục với mô hình thật trả `status="ok"` hợp lệ.

## Quyết định, lưu ý, bẫy
- Không sửa `ml/configs/thresholds.yaml`, `packages/contracts/`, `docs/adr/` hay `docs/status/STATUS.md`.
- Trên đường truyền HTTP (`CreateSessionResponse` / `FinalizeResponse`), schema hiện hành trong `packages/contracts/schemas/session.schema.json` chỉ cho phép `evaluation_mode` nhận `"standard"` hoặc `"manual_demo"` (và bắt buộc `status` của `"manual_demo"` thuộc `["review", "retry"]`). Do đó `MANUAL_FULL_DEMO` truy vết đầy đủ trong `Session`, `DecisionRow.thresholds`, `AccountRow.encrypted_payload` và hậu tố `model_version` (`+manual-demo-<policy_id[:16]>`), mà không phá vỡ schema hợp đồng hiện tại.

## Câu hỏi cho nhóm
- **Đề xuất cập nhật hợp đồng (`packages/contracts/schemas/session.schema.json`):** Nếu nhóm muốn client Android/Web nhận trực tiếp nhãn `evaluation_mode="manual_full_demo"` kèm `demo_policy_id` trên HTTP response của `POST /v1/sessions`, `POST /v1/sessions/{id}/finalize` và `POST /v1/sessions/{id}/voice`, đề xuất mở rộng enum `evaluation_mode` thành `["standard", "manual_demo", "manual_full_demo"]` trong `packages/contracts/schemas/session.schema.json` (giữ ràng buộc `status in ["review", "retry"]` cho `"manual_demo"`, và cho phép `"manual_full_demo"` chỉ trong `SECURITY_PROFILE=synthetic`).
- **Đề xuất thiết kế `LIPSYNC` trong `mvp`:** Hiện tại `router/profiles.py` giữ `LIPSYNC` là `advisory` cho phiên eKYC đơn lẻ không tạo tài khoản, trong khi `SessionFlow` và `AccountStore` bắt buộc `LIPSYNC` đạt `ok/pass` cho `recovery` và `onboarding` có `account_enrollment`. Nếu nhóm muốn nâng `LIPSYNC` thành bắt buộc cho mọi phiên `mvp`, cần hiệu chỉnh xong `SyncNet` trước rồi cập nhật `router/profiles.py` + ADR liên quan.

## Test đã chạy
```
RED → GREEN TDD (synthetic/mock unit & integration tests, không phải nghiệm thu điện thoại):
d:\vericlue\.venv\Scripts\python.exe -m pytest ml/tests/test_manual_demo.py ml/tests/test_face_continuity.py ml/tests/test_face_match.py services/api/tests/test_manual_face_demo.py services/api/tests/test_accounts.py services/api/tests/test_account_auth.py services/api/tests/test_enrollment_pipeline.py services/api/tests/test_mvp_lipsync_advisory.py services/api/tests/test_dynamic_flows.py services/api/tests/test_security_profile.py -q
-> 293 passed in 11.4s

Lint & Format:
d:\vericlue\.venv\Scripts\ruff.exe check . -> All checks passed!
d:\vericlue\.venv\Scripts\python.exe scripts/plan_check.py -> OK
```
