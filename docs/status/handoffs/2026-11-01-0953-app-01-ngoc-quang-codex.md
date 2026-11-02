# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-11-01 09:53

**Nhánh:** `codex/APP-01-demo-integration`
**Trạng thái task sau phiên này:** `doing`

> Cập nhật tiếp quản: phần code/API/Android của bàn giao này đã được kiểm tra,
> bổ sung regression/snapshot và commit tại `a542a47`. Công cụ parity tiếp tục
> tại `52cebaf`; xem bàn giao 10:15 và10:30 ngày01/11 cho kết quả mới.
> Các ghi chú “chưa commit” bên dưới là trạng thái lúc Anti bàn giao09:53.

## Đã xong
- **Mục 1 (Sửa 2 lỗi đã tìm thấy — `SessionFlow._ensure_standard_flow_ready` & `README-parity-nes2net.md`):**
  - Tách điều kiện sẵn sàng trong `services/api/src/vericlue_api/services/session_flow.py` (`_ensure_standard_flow_ready` và `ensure_flow_available`) theo đúng từng luồng (`onboarding`, `reauth`, `recovery`) và từng chặng (`voice_step=False` / `voice_step=True`):
    - `reauth` ở chặng mặt (`voice_step=False`) chỉ yêu cầu các thành phần thực sự dùng cho xác thực mặt + thiết bị L0 (`QUALITY`, `presence_modules`, `FACE_PAD`, `FACE_DEEPFAKE`, `FACE_MATCH`, `REAUTH_MATCH_VERSION`, calibrator đơn khung `FACE_PAD` + `FACE_DEEPFAKE`, khóa master, `require_media_proof`, `id_hmac_key >= 32B`). Không còn bị chặn sai bởi thiếu `voice_step_modules`, calibrator giọng/lipsync hay ngưỡng `onboarding`/`recovery` trừ khi `reauth` leo thang sang thử thách giọng (`voice_step=True` / `session.voice_requested`).
    - Bổ sung test `test_standard_real_reauth_does_not_require_voice_or_onboarding_calibrators` trong `services/api/tests/test_dynamic_flows.py`.
  - Sửa và kiểm chứng thực tế hướng dẫn setup WSL2 trong `ml/scripts/README-parity-nes2net.md`: dùng `uv venv --seed --python 3.10 "$HOME/nes2net-fairseq-ref"`, cài `"numpy<2"` trước bước `--no-build-isolation` và cài `fairseq` từ tag gốc `"git+https://github.com/facebookresearch/fairseq.git@v0.12.2"` (vì sdist trên PyPI thiếu `fairseq/clib/libbase/balanced_assignment.cpp` và `/tmp` trên WSL2 systemd tự xóa khi VM nghỉ).
- **Mục 2 (Hoàn thiện môi trường Fairseq tham chiếu & kiểm tra tính độc lập mẫu cho NES2Net — `VOICE-08` / `VOICE-09`):**
  - Đã dựng xong môi trường tham chiếu Fairseq tách biệt trong WSL2 `Ubuntu-24.04` tại `/home/ngocquang/nes2net-fairseq-ref` (`Python 3.10.22`, `torch==2.2.2+cpu`, `torchaudio==2.2.2+cpu`, `fairseq==0.12.2`, `numpy==1.26.4`, `soundfile==0.14.0`).
  - Đã clone `Liu-Tianchi/Nes2Net_ASVspoof_ITW` tại `/home/ngocquang/Nes2Net_ASVspoof_ITW`, checkout đúng commit `c9fe1177f44040f002cb40def928332d2e261f1e`, và xác minh SHA-256 của `model_scripts/wav2vec2_Nes2Net_X.py` (`8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f`).
  - Bổ sung `check_sample_diversity(records)` vào `ml/scripts/parity_nes2net.py`: kiểm tra SHA-256 của file âm thanh, sóng âm nguồn và cửa sổ 64.000 mẫu; chỉ cho phép `status == "PASS"` khi `independent_sample_count >= 32` và `diversity.all_unique == True` (các bản lặp không được đếm gộp thành nhiều mẫu).
  - Giữ nguyên trạng thái `Nes2NetDetector` và `Nes2NetTimelineDetector` là `status="degraded"`, `gate="unclear"`, `prob_attack=None` cho tới khi có đủ `xlsr2_300m.pt` và `>= 32` mẫu tiếng nói thật độc lập để chạy parity đạt `PASS`.
- **Mục 3 (Kiểm kê dữ liệu & artifact hiệu chỉnh trên máy):**
  - Đã rà soát toàn bộ repo, `D:\vericlue\models`, `D:\vericlue\data` và `D:\vericlue\tmp`:
    - `D:\vericlue\models\selected-2026-10-24` đã có đủ trọng số cho `scrfd-10g`, `lvface-b`, `mediapipe-face-landmarker`, `fs-vfm-vit-l-fas`, `gend-clip-l14`, `clip-vit-large-patch14`, `qwen3-asr-06b-hf`, `ctc-aligner`, `nes2net-x-xlsr/checkpoint.pth`, `syncnet/stable_syncnet.pt`, và `D:\vericlue\models\cccd_detector\best.pt`.
    - Chưa có `xlsr2_300m.pt` (~3,8 GB, chỉ cần cho nhánh Fairseq tham chiếu), chưa cấu hình `HF_TOKEN` / `kaggle.json`, và `D:\vericlue\data` hiện mới có `README.md` (chưa tải tập dữ liệu hiệu chỉnh công khai hay thu tập dữ liệu phiên v2 có đồng thuận).
- **Mục 4 (Hoàn thiện `SEC-09` consent lưu mẫu khuôn mặt mã hóa `[contract]`):**
  - Cập nhật `packages/contracts/schemas/privacy.schema.json`, `packages/contracts/openapi.json` và `apps/web/src/lib/api/schema.d.ts` với `AccountTemplateConsentRequest` (`policy_version`, `purpose: "account_template"`, `consent: true` — strict, từ chối `retention_seconds` tùy ý từ client) và `AccountTemplatePrivacyState` (`scope: "account_template"`, `purpose: "account_template"`, `retention_seconds: 86400`, `status: "not_granted" | "granted" | "withdrawn"`, `consent_receipt_id`).
  - Thêm bảng append-only `account_template_consents` + cột `consent_receipt_id` trên `accounts` (`0011_account_template_consent.py`), endpoint `GET/POST /v1/sessions/{session_id}/privacy/account-template(/consent)`, và bắt buộc biên nhận lưu mẫu hợp lệ trong cả `AccountStore.validate_enrollment` (trước khi trích mẫu) lẫn `AccountStore.create` (trước khi ghi DB).
  - Trên Android (`Privacy.kt`, `Api.kt`, `SessionPrivacyFlow.kt`, `Flow.kt`, `StartScreens.kt`), tách riêng checkbox đồng ý lưu mẫu khuôn mặt mã hóa (tự xóa sau 24 giờ, dùng cho đăng nhập lại/khôi phục, rút đồng ý phiên không tự xóa tài khoản) khỏi checkbox xử lý trong phiên; từ chối lưu mẫu dừng tạo tài khoản theo đúng D1.
- **Mục 5 (Đồng bộ hợp đồng API–Android và các luồng tài khoản cho `manual_full_demo` `[contract]`):**
  - Bổ sung `"manual_full_demo"` vào `evaluation_mode` của `CreateSessionResponse`, `FinalizeResponse`, `VoiceResponse` trong `packages/contracts/schemas/session.schema.json`, `packages/contracts/openapi.json`, `apps/web/src/lib/api/schema.d.ts`, FastAPI (`schemas/session.py`, `services/session_flow.py`) và Android (`Api.kt`, `LiveFlow.kt`, `App.kt`, `VoiceResultScreens.kt`).
  - Hiển thị rõ banner `"Demo · Ngưỡng chưa hiệu chỉnh"` trên `SuccessScreen` của Android khi phiên chạy ở chế độ `manual_full_demo` (tách biệt rõ với kết quả đường chạy chuẩn đã hiệu chỉnh).

## Đang dở
- **CHƯA COMMIT:** toàn bộ thay đổi của phiên này đang nằm trong working tree (41 file, HEAD vẫn là `c7613cc`). Cần rà `git diff`, chạy lại test rồi commit theo mã task (APP-01 / SEC-09 / VOICE-08). Không push.
- Chưa record/verify lại Paparazzi snapshot cho `TermsScreen` sau khi thêm checkbox lưu mẫu; mới chạy unit test và `assembleDebug`.
- Chưa tải `xlsr2_300m.pt`, nên parity Fairseq ↔ Transformers **chưa chạy**; NES2Net vẫn `degraded`.
- Để mở đường chạy chuẩn (`USE_MOCK_MODELS=false`, `MANUAL_FULL_DEMO=false`) đạt `pass` thực sự trên điện thoại, còn thiếu:
  1. File Fairseq `xlsr2_300m.pt` (`https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt`) và `>= 32` mẫu WAV 16 kHz mono tiếng nói thật độc lập có phép để chạy `ml/scripts/parity_nes2net.py` đạt `PASS`.
  2. Dữ liệu hiệu chỉnh chia theo người (`calib_fit` / `calib_ltt`, không đụng tập `test`) để sinh bộ `Calibrator` (`provisional=False`) và `MatchThreshold` (`split="calib_ltt"`) đúng chuỗi phiên bản mô hình thật.

## Bước tiếp theo
1. Tải `xlsr2_300m.pt` về máy và chuẩn bị danh sách `>= 32` file WAV 16 kHz mono tiếng nói thật độc lập (ví dụ từ `vivos` qua `uv run --group data python scripts/download_data.py --only vivos`), chạy `ml/scripts/parity_nes2net.py` với `/home/ngocquang/nes2net-fairseq-ref/bin/python` và `/home/ngocquang/Nes2Net_ASVspoof_ITW`.
2. Chuẩn bị các tập `calib_fit` và `calib_ltt` (chia theo `subject_id`) và chạy các script fit hiệu chỉnh (`ml/scripts/fit_session_face_calibration.py`, `ml/scripts/fit_identity_thresholds.py`, calibrator giọng/lipsync) để tạo artifact `provisional=False`.
3. Chạy nghiệm thu thực tế trên điện thoại Android cho cả chế độ `manual_full_demo` (đã ghi rõ nhãn `"Demo · Ngưỡng chưa hiệu chỉnh"`) và chế độ chuẩn khi đủ artifact hiệu chỉnh.

## Quyết định, lưu ý, bẫy
- Trên WSL2 `Ubuntu-24.04` có `systemd`, thư mục `/tmp` bị xóa khi máy ảo WSL tự tắt sau vài giây nghỉ; luôn giữ môi trường `/home/ngocquang/nes2net-fairseq-ref` và `/home/ngocquang/Nes2Net_ASVspoof_ITW` trong `$HOME`.
- `AccountTemplateConsentRequest` tuân thủ schema strict: không nhận `retention_seconds` từ client; thời hạn 24 giờ (`86400` giây) do server cố định trong `AccountTemplatePrivacyState`.
- Sửa vị trí bảng metadata của `FLOW-04` trong `docs/plan/epics/E9-app-flows.md` lên ngay dưới tiêu đề `### FLOW-04` để `scripts/plan_check.py` đạt `0 lỗi`.

## Câu hỏi cho nhóm
- Không có câu hỏi chặn cho phần hợp đồng/code; cần nhóm cung cấp hoặc xác nhận nguồn dữ liệu phiên v2 có đồng thuận (`calib_fit` / `calib_ltt`) để sinh artifact hiệu chỉnh thật (`provisional=False`) trước khi tắt `MANUAL_FULL_DEMO`.

## Test đã chạy
```powershell
# 1. Python contract, OpenAPI, privacy consent, account, dynamic flows, manual demo & ML tests (D:\vericlue\.venv):
$env:PYTHONPATH = "ml\src;services\api\src"
& "D:\vericlue\.venv\Scripts\python.exe" -m pytest `
  services/api/tests/test_contract_examples.py `
  services/api/tests/test_contract_schema.py `
  services/api/tests/test_openapi.py `
  services/api/tests/test_openapi_snapshot.py `
  services/api/tests/test_privacy_consent.py `
  services/api/tests/test_accounts.py `
  services/api/tests/test_account_auth.py `
  services/api/tests/test_dynamic_flows.py `
  services/api/tests/test_manual_face_demo.py `
  services/api/tests/test_session_voice_runtime.py `
  ml/tests/test_nes2net.py `
  ml/tests/test_nes2net_timeline.py `
  ml/tests/test_av_lipsync.py `
  ml/tests/test_voice_syncnet.py `
  ml/tests/test_session_voice_worker.py `
  ml/tests/test_manual_demo.py -q
# -> exit 0; output -q: 457 mục, 456 passed, 1 skipped, 0 failed (đếm từ dấu chấm).
#    Các test này dùng stub/mock detector + TestClient, KHÔNG chạy mô hình thật.

# 2. Test mô hình thật NES2Net-X trên CPU (D:\vericlue\tmp\nes2net-cpu):
$env:PYTHONPATH = "ml\src"
$env:NES2NET_MODELS_DIR = "D:\vericlue\models\selected-2026-10-24"
& "D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe" -m pytest ml/tests/test_nes2net_real_smoke.py -k "test_nes2net_checkpoint_cpu_and_repeatability" -q
# -> 1 passed

# 3. Kiểm chứng môi trường Fairseq tham chiếu trong WSL2 Ubuntu-24.04:
wsl -d Ubuntu-24.04 --exec /home/ngocquang/nes2net-fairseq-ref/bin/python -c "import torch, fairseq, soundfile, numpy; print('REF_ENV_READY', torch.__version__, fairseq.__version__, numpy.__version__)"
# -> REF_ENV_READY 2.2.2+cpu 0.12.2 1.26.4

# 4. Web typecheck & unit tests (apps/web):
npm run typecheck && npm run test
# -> 22 passed (1319 tests)

# 5. Android unit tests & assembleDebug (apps/android, JAVA_HOME=D:\tools\jdk17):
./gradlew testDebugUnitTest --tests "vn.vericlue.app.*Test" --continue
./gradlew assembleDebug
# -> BUILD SUCCESSFUL

# 6. Ruff, plan_check & git diff --check:
& "D:\vericlue\.venv\Scripts\ruff.exe" check .
& "D:\vericlue\.venv\Scripts\ruff.exe" format --check .
& "D:\vericlue\.venv\Scripts\python.exe" scripts/plan_check.py
git diff --check
# -> ruff check sạch sau khi `ruff format` 8 file; plan_check 0 lỗi / 10 cảnh báo tải; git diff --check exit 0
```
