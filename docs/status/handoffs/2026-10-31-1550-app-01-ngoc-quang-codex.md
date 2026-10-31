# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-10-31 15:50

**Nhánh:** `codex/APP-01-demo-integration`
**Trạng thái task sau phiên này:** `doing`

## Đã xong
- **Mục 1 (Kiểm tra Git & dọn import thừa):**
  - Xác minh thay đổi chưa commit ở `services/api/tests/test_manual_face_demo.py` là 3 dòng import thừa (`ec`, `serialization`, `json`) từ phiên trước (`256e27c`), dọn sạch bằng `ruff check --fix` và `ruff format`.
- **Mục 2 (NES2Net-X — `VOICE-08` / `VOICE-09` / `VOICE-13` / `VOICE-14`):**
  - Xác định rõ lý do NES2Net hiện tại vẫn trả `status="degraded"`, `gate="unclear"`, `prob_attack=None`, `quality.diagnostic_only=True`:
    1. `frontend_parity_verified=False`: cổng chuyển Fairseq `wav2vec2` sang HuggingFace Transformers (`xls_r_300m` + `Nested_Res2Net_TDNN`) mới khớp kiểm tra cấu trúc/shape (422 tensor frontend + 560 tensor head), chưa có bằng chứng đối chiếu số học (`max_abs_diff <= 1e-4`, 100% cùng dấu trên >= 32 mẫu thật) với Fairseq gốc.
    2. `calibrated=False`: chưa có dữ liệu `calib_fit` tiếng Việt có phép để fit `Calibrator` (Platt/Isotonic) cho phiên bản `nes2net-x@c9fe1177f44040f002cb40def928332d2e261f1e+hf4576-cpu-fp32-timeline4s-tail-v1`.
    3. `aggregation="none"`: `Nes2NetTimelineDetector` (`voice/nes2net_timeline.py`) chỉ xuất logit theo từng cửa sổ 4 giây trong `evidence`, chưa gộp thành điểm toàn câu `score` trên `[0, 1]`.
  - Xây dựng công cụ đối chiếu parity `ml/scripts/parity_nes2net.py` và hướng dẫn `ml/scripts/README-parity-nes2net.md` hỗ trợ 3 chế độ (`--export-reference`, `--compare-reference`, `--synthetic-smoke`), kiểm tra nghiêm ngặt `max_abs_diff <= 1e-4`, 100% cùng dấu logit và tối thiểu 32 mẫu thật (thiếu điều kiện trả `status="UNVERIFIED"` với mã thoát `2`, lệch số học trả `status="FAIL"` với mã thoát `1`).
  - Bổ sung unit test parity trong `ml/tests/test_nes2net.py` và chạy smoke test mô hình thật trên CPU (`D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe`) với trọng số `D:\vericlue\models\selected-2026-10-24\nes2net-x\checkpoint.pth`.
- **Mục 3 (SyncNet — `VOICE-05` / `VOICE-12` / `VOICE-14`):**
  - Kiểm chứng tiền xử lý (`25 fps`, 16 khung miệng 256×256 chuẩn hóa `[-1, 1]`, phổ mel Slaney 80 băng chuẩn hóa `[-4, 4]`, 52 cột/cửa sổ), đơn vị độ lệch AV (`offset_ms = best * 1000 / 25`, quét `±15` khung = `±600 ms`), chiều điểm số (`score = clip(max(1 - confidence_at_0, abs(offset_ms) / 500.0), 0, 1)`, tăng = giống tấn công), và đồng bộ timestamp Android (`audioOffsetMs = t_wav_start - t_video_first_frame` trong `App.kt` & `CameraSession.kt`, truyền tới `syncnet.py` qua `position / 25 + audio_offset_s`).
  - Chạy toàn bộ test tích hợp và smoke test mô hình thật của SyncNet / voice worker bằng `D:\vericlue\tmp\av-lab-cpu\Scripts\python.exe` (83 test xanh).
  - Xác định khoảng trống artifact hiện tại: file `ml/configs/calibrators/lipsync/stable-syncnet@c42c7e6c%2Bctc-aligner@49402e95%2Bscrfd-10g@bfcc7d48%2Bvoice05-v2.json` là `IdentityCalibrator` (`provisional=True`, `n_pos=0, n_neg=0`) và chưa có hậu tố `+session-offset-v1` của `SessionVoiceDetector`.
- **Mục 4 (Đường chạy chuẩn khi `USE_MOCK_MODELS=false`):**
  - Thay chốt chặn cứng `503 flow_unavailable` trong `SessionFlow.create` và `SessionFlow.ensure_flow_available` bằng kiểm tra điều kiện sẵn sàng cụ thể theo từng luồng (`_ensure_standard_flow_ready`, `_require_fitted_calibrator`, `_require_match_threshold`).
  - Chỉ mở từng luồng (`onboarding`, `reauth`, `recovery`) khi đủ: `use_mock_models is False`, không bật `manual_*_demo`, `require_privacy_consent=True` (và phiên đã cấp đủ category consent cho bước đang chạy), đủ khoá bảo mật tài khoản, mọi detector yêu cầu đã nạp thành công (không lỗi preload, không có `mock` trong `model_version`, không phải bản chỉ chẩn đoán `NES2NET_TIMELINE_VERSION`), có `Calibrator` đã fit (`provisional=False`) khớp chính xác `model_version` cho `FACE_PAD`, `FACE_DEEPFAKE`, `VOICE_SPOOF`, `LIPSYNC`, và có `MatchThreshold` (`split="calib_ltt"`) khớp chính xác `model_version` cho từng luồng.
  - Sửa 3 điểm nghẽn trên đường chạy chuẩn đã hiệu chỉnh:
    1. `ml/src/vericlue_ml/face/session_attack.py`: cho phép `purpose == "reauth"` chấm khung chính diện 500 ms cả ở chế độ chuẩn (`manual_demo=None`) và truyền `self.router.calibrators` vào `SessionAttackDetector` trong `Orchestrator._default_detector`.
    2. `services/api/src/vericlue_api/services/session_flow.py` (`_identity_gate`) & `accounts.py` (`_validate_biometrics`): chấp nhận `VIDEO_MATCH_VERSION + "+head12s-v2"` khi chạy `onboarding` chuẩn với thử thách động v2 (12 giây xoay đầu).
    3. `services/api/src/vericlue_api/services/session_flow.py` (`_lipsync_gate`): ở chế độ chuẩn (`use_mock_models=False`, không `manual_full_demo`), áp dụng `Calibrator` không provisional của `Module.LIPSYNC` và gán `gate = Gate.PASS` khi `0 <= prob_attack <= spoof_threshold` để bước cấp tài khoản/khôi phục kiểm tra nhất quán.
  - Bổ sung bộ test tích hợp đầy đủ cho cả trường hợp đủ điều kiện (`onboarding` -> `reauth` -> `recovery` đạt `200 OK`) và 15 trường hợp thiếu từng điều kiện trả `503 flow_unavailable` trong `services/api/tests/test_dynamic_flows.py` và `ml/tests/test_session_attack.py`.
- **Mục 5 (Kiểm tra hợp đồng API–Android cho `manual_full_demo`):**
  - Rà soát toàn bộ `packages/contracts/schemas/session.json`, `services/api/src/vericlue_api/schemas/session.py`, `services/api/src/vericlue_api/services/session_flow.py`, `apps/android/`, `apps/web/` và lập đề xuất cập nhật hợp đồng (chưa tự sửa `packages/contracts/` khi chưa được duyệt).

## Đang dở
- Chưa có dữ liệu sinh trắc thật có phép (`calib_fit` và `calib_ltt`) để sinh các file hiệu chỉnh thật (`Calibrator` và `MatchThreshold`) cho đường chạy chuẩn `USE_MOCK_MODELS=false`.
- Chưa có môi trường Fairseq trên Linux/WSL để xuất file tham chiếu `--export-reference` trên >= 32 mẫu thật cho `parity_nes2net.py`.

## Bước tiếp theo
1. Chuẩn bị môi trường Fairseq (Linux/WSL, Python 3.10 + `fairseq`) để chạy `parity_nes2net.py --export-reference` trên >= 32 mẫu âm thanh thật, sau đó chạy `--compare-reference` trên Windows (`D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe`) để xác nhận `status="PASS"`.
2. Thu thập dữ liệu có đồng thuận (`calib_fit` và `calib_ltt`, tách người theo `subject_id`, tuyệt đối không dùng tập `test`) và chạy các script đo/fit để sinh đủ bộ artifact hiệu chỉnh (`Calibrator` cho `face_pad`, `face_deepfake`, `voice_spoof`, `lipsync` và `MatchThreshold` cho 5 giao thức LVFace).
3. Sau khi nhóm duyệt đề xuất hợp đồng `evaluation_mode: "manual_full_demo"`, cập nhật `packages/contracts/schemas/session.json`, API schemas, `SessionFlow._evaluation_fields` và Android/Web trong cùng một PR.

## Quyết định, lưu ý, bẫy
- Giữ nguyên nguyên tắc fail-closed: khi `USE_MOCK_MODELS=false`, thiếu bất kỳ detector thật, calibrator đã fit (`provisional=False`), `MatchThreshold` khớp `model_version`, hoặc consent đều trả `503 flow_unavailable` — tuyệt đối không fallback sang mock hoặc ngưỡng thủ công.
- Phiên L0 (`reauth`/`recovery` bước tạo phiên và `/device-proof`) vẫn hoạt động độc lập trước khi mở bước sinh trắc (`media`/`signals`/`finalize`/`voice`).

## Câu hỏi cho nhóm
- **Đề xuất cập nhật hợp đồng `packages/contracts/schemas/session.json` cho `manual_full_demo`:**
  1. Trong `packages/contracts/schemas/session.json`: mở rộng `evaluation_mode` từ `enum: ["manual_demo"]` thành `enum: ["manual_demo", "manual_full_demo"]` ở `CreateSessionResponse` và `FinalizeResponse`, đồng thời thêm `evaluation_mode` và `demo_policy_id` (tuỳ chọn, đi kèm nhau) vào `VoiceResponse`.
  2. Trong `services/api/src/vericlue_api/schemas/session.py` và `session_flow.py`: cập nhật `Literal["manual_demo", "manual_full_demo"]` và `_evaluation_fields(session)` để trả `evaluation_mode="manual_full_demo"` + `demo_policy_id` cho cả `CreateSessionResponse`, `FinalizeResponse`, `VoiceResponse`.
  3. Trong `apps/android/app/src/main/java/vn/edu/vericlue/ekyc/FlowModels.kt` và `ui/FlowSteps.kt`: parse `evaluation_mode` và `demo_policy_id` ở `CreateSessionResponse`, `FinalizeResponse`, `VoiceResponse`; hiển thị nhãn cảnh báo chế độ thử nghiệm ngưỡng thủ công (`manual_full_demo`) rõ ràng trên màn kết quả để không nhầm với kết quả đã hiệu chỉnh chuẩn.

## Test đã chạy
```powershell
& "D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe" -m pytest ml/tests/test_nes2net_real_smoke.py ml/tests/test_nes2net_timeline.py -m slow -ra
# -> 2 passed in 50.08s

& "D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe" ml/scripts/parity_nes2net.py --models-dir D:\vericlue\models\selected-2026-10-24 --synthetic-smoke --output C:\Users\Admin\.gemini\antigravity\brain\10a6af3b-b776-40ef-b9b1-baae80937bc4\scratch\nes2net_parity_smoke.json
# -> exit code 2 (UNVERIFIED on synthetic smoke, 422 mapped frontend keys, 560 head keys, 0 missing/unexpected)

& "D:\vericlue\tmp\av-lab-cpu\Scripts\python.exe" -m pytest ml/tests/test_voice_worker_real_smoke.py ml/tests/test_syncnet_timestamps.py ml/tests/test_syncnet_checkpoint.py ml/tests/test_syncnet_batching.py ml/tests/test_voice_syncnet.py ml/tests/test_session_voice_worker.py -ra
# -> 83 passed

& "D:\vericlue\.venv\Scripts\python.exe" -m pytest ml/tests/test_nes2net.py ml/tests/test_session_attack.py services/api/tests/test_dynamic_flows.py services/api/tests/test_account_auth.py services/api/tests/test_accounts.py services/api/tests/test_manual_face_demo.py services/api/tests/test_privacy_consent.py services/api/tests/test_security_profile.py -q
# -> 292 passed in 68.12s

& "D:\vericlue\.venv\Scripts\ruff.exe" check .
& "D:\vericlue\.venv\Scripts\ruff.exe" format --check .
# -> All checks passed!
```
