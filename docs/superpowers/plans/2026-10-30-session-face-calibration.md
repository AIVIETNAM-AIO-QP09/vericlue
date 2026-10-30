# Session face calibration implementation plan

> For agentic workers: use executing-plans for direct execution after user review, or subagent-driven-development only if the user selects that method. Steps below track the required test cycle.

**Goal:** nối artifact hiệu chỉnh đúng protocol vào PAD/GenD video và cung cấp công cụ đo/fit tái lập được.

**Architecture:** dùng `session_views` và backend hiện có để đo; `CalibrationStore` theo module/version để nạp artifact; router vẫn quyết định và các guard vẫn đóng. Manifest/báo cáo là dữ liệu nghiên cứu local, không đổi hợp đồng HTTP/ModuleResult.

**Tech stack:** Python 3.12, Pydantic, NumPy, scikit-learn, pytest, Ruff; môi trường CPU đã setup.

**Spec:** [thiết kế đã duyệt](../specs/2026-10-30-session-face-calibration-design.md).

## Global constraints

- Không đổi thresholds.yaml hoặc guard sinh trắc; OTP demo giữ nguyên.
- Không fit từ calib_ltt/test, không giao nhóm người giữa split; không ẩn mẫu lỗi.
- Chỉ đúng module/version phiên, fitted non-provisional artifact mới được dùng.
- Error/degraded/not_applicable không được tạo xác suất hay đạt; không tin prob/gate backend gắn sẵn.
- Không commit media, model hoặc artifact chạy từ dữ liệu người thật. Test fixture tổng hợp ghi rõ mục đích.
- Không thu camera/micro; người dùng tự nghiệm thu điện thoại sau.

## Review focus

1. Artifact identity/provisional hoặc version gần giống bị dùng nhầm: Task 1 kiểm từ chối.
2. Backend báo lỗi nhưng vẫn có score/prob: Task 1 giữ lỗi, bỏ xác suất.
3. Nhóm giao split ẩn trong mẫu không chấm được: Task 2 kiểm toàn manifest trước lọc.
4. Video/lịch đổi sau đo, đường dẫn/symlink thoát data root: Task 2 kiểm hash trước/sau và đường dẫn đã resolve.
5. CLI fit/test tổng hợp bị hiểu là mở eKYC: Task 3 kiểm guard và bàn giao trạng thái chưa nghiệm thu.

## Task 1: Áp dụng calibrator đúng version trong adapter

**Files:** sửa `ml/src/vericlue_ml/face/session_attack.py`; mở rộng `ml/tests/test_session_attack.py`.

**Interfaces:** `SessionAttackDetector(backend, reader, calibrators: CalibrationStore | None = None)`; mặc định tạo store theo CALIBRATORS_DIR hiện có. Detector vẫn có name/version/preload/predict cũ.

- [ ] Viết test đỏ: valid fitted artifact cùng module/full session version tạo prob bằng `artifact.predict([raw_score])`; score không đổi, gate không thành pass.
- [ ] Viết test đỏ cho missing/identity/provisional/wrong-version artifact, backend sai module/version, score thiếu/NaN, backend error/degraded, video đổi. Backend prob/gate giả không được tin.
- [ ] Chạy `python -m pytest ml/tests/test_session_attack.py -q` và xác nhận lỗi vì hành vi chưa được thực hiện.
- [ ] Chuẩn hóa kết quả backend sau khi kiểm nguồn; chỉ khi backend ok/error_code=None/score hữu hạn trong [0,1] mới tìm artifact. Kiểm `Calibrator` non-provisional, module/version khớp; áp dụng xác suất. Không nâng trạng thái lỗi. Giữ depth_verified=false và các giới hạn model, không biến việc fit thành chứng minh chiều sâu/parity.
- [ ] Artifact không dùng được giữ degraded/unclear và prob=None. Không có fallback sang kho/version khác. Không sửa renderer hoặc API response.
- [ ] Chạy lại test adapter và `ml/tests/test_calibration.py`; commit có [FLOW-04].

## Task 2: Công cụ đo và fit riêng cho phiên video

**Files:** tạo `ml/src/vericlue_ml/eval/session_calibration.py`, `ml/tests/test_session_calibration.py`; tài liệu lệnh ở Task 3.

**Interfaces:**
- `load_manifest(path: Path, data_root: Path) -> list[SessionSample]`.
- `collect(manifest: Path, data_root: Path, models_dir: Path, module: Module, output: Path, device: str = 'cpu') -> dict`.
- `fit_report(report: Path, output_dir: Path, n_splits: int = 5) -> dict`.
- CLI `python -m vericlue_ml.eval.session_calibration collect|fit`.

Manifest JSON: `schema_version=1`, dataset opaque ID, `samples` gồm `sample_id`, `subject_id` (nhóm người/nguồn đã nối), `split` trong calib_fit/calib_ltt/test, `label` 0/1, `video` và `server_response` là đường dẫn tương đối data root. Không nhận frame/góc/timestamp do client chọn.

- [ ] Viết test đỏ cho manifest hợp lệ và các lỗi ở Review focus 3/4, ID/label/split sai, mẫu/file trùng, đường dẫn tuyệt đối/thoát root, lịch thiếu context. Từ chối output trùng input hoặc trong kho model.
- [ ] Viết test đỏ collector với fake backend/reader: cùng `session_views` và đúng pixel/version; giữ mẫu lỗi và hash; nguồn thay đổi thì không giữ score; không xuất ảnh/embedding. Test không tải model hoặc gọi thiết bị.
- [ ] Viết test đỏ fitter: chỉ calib_fit được dùng; nhóm không giao split kể cả mẫu lỗi; sai provenance/module/version hoặc thiếu hai lớp bị chặn. Các thống kê n_pos/n_neg/excluded phải khớp dữ liệu đã ghi.
- [ ] Xác nhận test đỏ. Implement Pydantic models strict cho manifest/report, checksum và đường dẫn; dùng source commit sạch khi xuất dữ liệu thực. Lịch server là fixture tin cậy trong công cụ local, không gọi đó là chứng minh chữ ký thiết bị/server.
- [ ] Implement collect qua `session_views` + backend.predict_frames; phiên bản report là full session version. Đo mọi split để kiểm provenance, không dùng nhãn test để chọn model. Lưu trạng thái mọi mẫu; lỗi không có score. Module chỉ nhận face_pad hoặc face_deepfake.
- [ ] Implement fit bằng `CalibFit`/`fit` hiện có; xuất bằng CalibrationStore tới output dir riêng không có file trùng. Dataset metadata giữ hash báo cáo/manifest, loại trừ theo lớp và số nhóm. Không tự chọn threshold hoặc đánh giá test trong lệnh fit.
- [ ] Chạy `python -m pytest ml/tests/test_session_calibration.py -q` và CLI --help; commit [FLOW-04]. Không chạy fit dữ liệu thật khi chưa có bộ phù hợp.

## Task 3: Kiểm chứng tích hợp và bàn giao

**Files:** thêm test trong `services/api/tests/test_session_motion.py` hoặc file chuyên biệt `test_session_calibration_guards.py`; cập nhật `docs/architecture/session-verification.md`, `ml/README.md`, task FLOW-04 và handoff.

- [ ] Viết/chạy test đỏ bảo đảm cấu hình mới không mở guard real/mixed/account-bound; tham khảo test hiện có, không fake toàn bộ lớp guard để kiểm chính nó.
- [ ] Kiểm fixture có classifier fitted nhưng mandatory motion error/degraded vẫn không ra pass; không sửa policy để làm test xanh.
- [ ] Chạy test ML adapter/collector/calibration/router, API motion/voice/identity/guards; Ruff check và format phần thay đổi. Mở rộng regression khi xuất hiện lỗi.
- [ ] Viết hướng dẫn manifest và lệnh collect/fit/kiểm artifact; giải thích thiếu dữ liệu thì vẫn degraded, giọng/danh tính/ánh sáng chưa được hiệu chỉnh bởi phần này. Không đưa test fixture tổng hợp vào kho artifact production.
- [ ] Ghi bàn giao bằng scripts/new_handoff.py; cập nhật tiêu chí FLOW-04 nhưng giữ doing, không đánh dấu ROUT-03 done; chạy plan_check.py, diff --check.
- [ ] Review độc lập phần code; sửa lỗi quan trọng và kiểm lại các ca liên quan. Commit cuối, giữ nhánh local, không push/PR.

## Điểm dừng có bằng chứng

Hoàn tất công cụ/adapter/test không đồng nghĩa có artifact thực. Nếu tiếp tục thiếu dữ liệu, bàn giao ghi rõ sample_count thực chưa có và đường API thật vẫn đóng; không điền số để chốt demo. Bước tiếp theo là quyền lưu mẫu SEC-09 và các protocol giọng/danh tính, mỗi phần có thiết kế riêng.
