# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-10-31 16:27

**Nhánh:** `codex/APP-01-demo-integration`
**Trạng thái task sau phiên này:** `doing`

## Đã xong
- **Mục 1 (Gỡ chặn OTP mô phỏng cho đường chạy chuẩn `USE_MOCK_MODELS=false` — `APP-01` / `FLOW-02` / `SEC-05`):**
  - Thêm cờ cấu hình riêng `simulated_otp: bool = False` (biến môi trường `SIMULATED_OTP`, mặc định tắt `false`) trong `services/api/src/vericlue_api/core/config.py`, `.env.example`, và `docs/runbooks/protected-profile.md`.
  - Tách `ensure_otp_available(settings)` trong `services/api/src/vericlue_api/core/security_profile.py` khỏi `USE_MOCK_MODELS`: cho phép OTP mô phỏng (`simulated_sms`) khi `SECURITY_PROFILE=synthetic` và `SIMULATED_OTP=true`, kể cả khi `USE_MOCK_MODELS=false` hoặc `USE_MOCK_MODELS=mixed`.
  - Bổ sung kiểm tra `"no_simulated_otp": not settings.simulated_otp` vào `security_profile_checks(settings)` để cấu hình `SECURITY_PROFILE=protected` từ chối ngay (`503 security_profile_unavailable`) nếu `SIMULATED_OTP=true`.
  - Thay thế toàn bộ chỗ gán trực tiếp `sess.otp_verified = True` / `ksess.otp_verified = True` trong test đường chạy chuẩn (`services/api/tests/test_dynamic_flows.py`) bằng lời gọi HTTP thật tới `POST /v1/sessions/{id}/otp` và `POST /v1/sessions/{id}/otp/verify`, kiểm tra nhãn `delivery_mode == "simulated_sms"`.
  - Bổ sung integration test `test_standard_real_simulated_otp_endpoints_and_error_cases` kiểm chứng: mặc định `SIMULATED_OTP=false` trả `503 otp_unavailable`, `SECURITY_PROFILE=protected` từ chối `SIMULATED_OTP=true`, nhập mã sai trả `status="retry"`, quá 5 lần sai trả `409 otp_locked`, hết hạn trả `409 otp_expired`, và gửi quá 3 lần trả `409 otp_too_many`.
- **Mục 2 (Đồng bộ CLI & sửa worker Fairseq tham chiếu của `parity_nes2net.py` — `VOICE-08` / `VOICE-09`):**
  - Đồng bộ `ml/scripts/README-parity-nes2net.md` và `docs/status/handoffs/2026-10-31-1550-app-01-ngoc-quang-codex.md` với đúng tùy chọn CLI thực tế của `ml/scripts/parity_nes2net.py`: `--models-dir`, `--audio-list`, `--synthetic-smoke`, `--reference-python`, `--upstream-dir`, `--xlsr-checkpoint`, `--output` (bỏ hẳn tên cờ không tồn tại `--export-reference` / `--compare-reference`).
  - Đối chiếu trực tiếp với mã nguồn upstream `Liu-Tianchi/Nes2Net_ASVspoof_ITW@c9fe1177f44040f002cb40def928332d2e261f1e` (`model_scripts/wav2vec2_Nes2Net_X.py`, `easy_inference_demo.py`) và sửa 4 lỗi trong `REFERENCE_WORKER_CODE` / `_run_reference_python`:
    1. Import đúng lớp `wav2vec2_Nes2Net_no_Res_w_allT as UpstreamModel` từ `model_scripts.wav2vec2_Nes2Net_X` (upstream không định nghĩa tên `Model` trong `wav2vec2_Nes2Net_X.py`).
    2. Thêm `n_output_logits = 2` vào `Args` (bắt buộc ở dòng 205 của `wav2vec2_Nes2Net_X.py`).
    3. Ép `model.to(device="cpu", dtype=torch.float32)` trước `load_state_dict` và `.eval()` trước vòng lặp suy luận, đồng thời kiểm tra `not model.training and not model.ssl_model.model.training` (vì `SSLModel.extract_feat` dòng 21–24 tự gọi `self.model.train()` nếu `dtype`/`device` của tham số lệch với `input_data`!).
    4. Tách `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` khỏi tiến trình con `_run_reference_python` để Python của môi trường Fairseq không bị nhiễm gói của môi trường gọi.
  - Bổ sung test `test_parity_reference_worker_executes_upstream_wav2vec2_nes2net_contract` trong `ml/tests/test_nes2net.py` kiểm chứng tiến trình con `_run_reference_python` chạy trọn vẹn hợp đồng `SSLModel` + `wav2vec2_Nes2Net_no_Res_w_allT`.
  - Giữ nguyên trạng thái `NES2Net` là `degraded` (`frontend_parity_verified=False`, `calibrated=False`) và `parity_nes2net.py --synthetic-smoke` trả `status="UNVERIFIED"` (exit code `2`).
- **Mục 3 (Dọn hàm test bị định nghĩa trùng trong `services/api/tests/test_dynamic_flows.py`):**
  - Đối chiếu từng dòng giữa hai bản `_setup_ready_real_env` và 3 hàm `test_standard_real_*`, xác nhận nội dung tương đương, xóa bản lặp và bổ sung thêm `test_standard_real_simulated_otp_endpoints_and_error_cases`. `ruff check .` sạch hoàn toàn (0 lỗi `F811`).

## Đang dở
- Chưa có môi trường Fairseq (`Python 3.10` + `fairseq==0.12.2`), bản clone `Liu-Tianchi/Nes2Net_ASVspoof_ITW@c9fe1177f44040f002cb40def928332d2e261f1e`, trọng số gốc `xlsr2_300m.pt` và `>= 32` mẫu âm thanh tiếng nói thật để chạy nhánh đối chiếu Fairseq của `ml/scripts/parity_nes2net.py`.
- Chưa có dữ liệu sinh trắc thật có đồng thuận (`calib_fit` và `calib_ltt`) để sinh bộ artifact hiệu chỉnh thật (`Calibrator` với `provisional=False` và `MatchThreshold` với `split="calib_ltt"`) cho đường chạy chuẩn `USE_MOCK_MODELS=false`.

## Bước tiếp theo
1. Tạo môi trường Fairseq (trên WSL Ubuntu-24.04 hoặc Linux, Python 3.10 + `fairseq==0.12.2`), tải `Liu-Tianchi/Nes2Net_ASVspoof_ITW@c9fe1177f44040f002cb40def928332d2e261f1e` và `xlsr2_300m.pt`, chuẩn bị `>= 32` file WAV 16 kHz mono tiếng nói thật (`audio_list.txt`), rồi chạy `ml/scripts/parity_nes2net.py --models-dir ... --audio-list ... --reference-python ... --upstream-dir ... --xlsr-checkpoint ... --output ...` để lấy báo cáo `status="PASS"`.
2. Sau khi có parity `PASS` và hoàn thiện bộ gộp điểm toàn câu của NES2Net, dùng dữ liệu `calib_fit` và `calib_ltt` (chia theo `subject_id`, tuyệt đối không đụng tập `test`) để fit đủ `Calibrator` (`face_pad`, `face_deepfake`, `voice_spoof`, `lipsync`) và `MatchThreshold` (5 giao thức LVFace).
3. Khởi chạy API ở chế độ chuẩn (`USE_MOCK_MODELS=false`, `SECURITY_PROFILE=synthetic`, `SIMULATED_OTP=true`, `REQUIRE_PRIVACY_CONSENT=true`) để nghiệm thu ba luồng `onboarding -> reauth -> recovery` trên điện thoại Android.

## Quyết định, lưu ý, bẫy
- `SIMULATED_OTP=true` chỉ được phép khi `SECURITY_PROFILE=synthetic`; trong `SECURITY_PROFILE=protected` bắt buộc `SIMULATED_OTP=false`.
- Trong `Liu-Tianchi/Nes2Net_ASVspoof_ITW/model_scripts/wav2vec2_Nes2Net_X.py`, `SSLModel.extract_feat` có đoạn kiểm tra `dtype`/`device` và gọi `self.model.train()` nếu lệch — luôn phải ép toàn bộ mô hình sang `float32` trên `cpu` trước khi gọi `.eval()`.

## Câu hỏi cho nhóm
- Giữ nguyên đề xuất cập nhật `packages/contracts/schemas/session.json` từ bàn giao trước để truyền `evaluation_mode: "manual_full_demo"` + `demo_policy_id` tới client Android/Web khi chạy chế độ ngưỡng thủ công.

## Test đã chạy
```powershell
# 1. Test với fake/stub detectors & HTTP TestClient (D:\vericlue\.venv):
& "D:\vericlue\.venv\Scripts\python.exe" -m pytest `
  services/api/tests/test_security_profile.py `
  services/api/tests/test_dynamic_flows.py `
  services/api/tests/test_identity_steps.py `
  services/api/tests/test_account_auth.py `
  services/api/tests/test_accounts.py `
  services/api/tests/test_privacy_consent.py `
  services/api/tests/test_manual_face_demo.py `
  ml/tests/test_nes2net.py `
  ml/tests/test_session_attack.py -q
# -> 324 passed

# 2. Test chạy trọng số mô hình thật NES2Net-X trên CPU (D:\vericlue\tmp\nes2net-cpu):
& "D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe" ml/scripts/parity_nes2net.py --models-dir D:\vericlue\models\selected-2026-10-24 --synthetic-smoke --output C:\Users\Admin\.gemini\antigravity\brain\10a6af3b-b776-40ef-b9b1-baae80937bc4\scratch\nes2net_parity_smoke.json
# -> ExitCode 2 (status="UNVERIFIED", mapped_keys=422, head_keys=560, missing=[], unexpected=[])

& "D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe" -m pytest ml/tests/test_nes2net_real_smoke.py ml/tests/test_nes2net.py -m "slow or not slow" -q
# -> 42 passed

# 3. Lint, format & git diff --check:
& "D:\vericlue\.venv\Scripts\ruff.exe" check .
& "D:\vericlue\.venv\Scripts\ruff.exe" format --check .
git diff --check
# -> All checks passed!
```
