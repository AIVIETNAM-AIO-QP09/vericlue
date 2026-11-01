# Offline report integrity and fixture coverage — Implementation Plan

> For agentic workers: dùng executing-plans/TDD; audit và review độc lập bằng sub-agent. Giữ nguyên các worktree và bằng chứng cũ.

**Goal:** sửa các thiếu sót đã tái hiện trước khi có dữ liệu/điện thoại: diagnostic report ghi được vào kho cấu hình, và các test âm thanh nhẹ chưa được chạy trong CI.

**Architecture:** tái dùng quy tắc bảo vệ output của candidate consumers cho producer diagnostic; không chặn output calibrator được yêu cầu rõ ở session.fit_report. Dev dependencies nhẹ để chạy fixture, không cài model/Torch vào CI.

**Tech Stack:** Python3.12, pytest, SoundFile, JiWER/RapidFuzz đã có trong voice extras; uv lock.

**Spec:** AGENTS §6.4/6.5/6.8/6.9; VOICE-09; ROUT-03; runbook nes2net-utterance-calibration và face-candidate-scoring.

## Global Constraints

- Không đổi thresholds/contracts/ADR/proposal/STATUS hoặc mã số học/parity của NES2Net. Không merge main.
- Không dùng dữ liệu thật để thêm test; không VIVOS fit, không nạp trọng số, không thao tác DB/media thật.
- Diagnostic luôn không triển khai; không fake runtime thực để mở chốt. Fixture mô phỏng phải có runtime mô phỏng rõ ràng.
- Tôn trọng session.fit_report ghi calibrator vào output_dir được người chạy chỉ định; chỉ diagnostic reports bị cấm vào kho config/model/data/calibrator.
- Không thay tập, bỏ lỗi hoặc nới yêu cầu để làm xanh test. Quyền/quần thể/crosswalk thật vẫn cần nhóm xác nhận.

## Review Focus

- Mọi entry point diagnostic dùng guard, kể cả CLI prepare/readiness/collect/fit-wrapper.
- Guard trước nạp model/inference và kiểm lại ngay trước ghi; output mới, không đè input.
- Kho trong repo và MODELS_DIR/DATA_DIR/CALIBRATORS_DIR ngoài repo được resolve đúng.
- Test synthetic không gọi Torch thật; native collect vẫn đọc runtime thật, không có fallback.
- Dev dependency không kéo extras nặng; CI thực thi các fixture từng bị skip.

## Task 1: Diagnostic output guards

- [x] Tái hiện qua API thật dùng fixture: readiness_report và session.collect ghi được vào từng kho env.
- [x] Test RED cho các kho env/repo; sửa shared guard nhỏ, áp dụng utterance._write và producer preflight/final checks. Không đổi intended calibrator writes.
- [x] Kiểm không output, không inference khi target sai và kiểm lại target trước ghi; test ổn định không mirror implementation.

## Task 2: Lightweight fixture coverage

- [x] Thêm SoundFile/JiWER/RapidFuzz dev bounds như voice extra; refresh lock, không thay dependencies production.
- [x] Sửa runtime fixture synthetic sau RED7 ca ModuleNotFoundError torch; không sửa runtime_identity production.
- [x] Chạy WAV native decoding/split/hash và library-oracle tests:144 đạt/0 skip; nhóm toàn bộ liên quan354 đạt/0 skip.

## Task 3: Verification and delivery

- [x] Review độc lập SPEC/QUALITY pass;354test liên quan/4907full suite đạt,100skip; lint/format/lock/plan_check sạch.
- [x] Sửa ghi chú dữ liệu/LTT lỗi thời, taskcard/backlog/handoff đúng trạng thái còn thiếu.
- [ ] Draft PR riêng sau PR124, đợi CI riêng. Không merge hoặc tuyên bố AI toàn luồng đạt.

## Evidence / rulings

- Baseline c154abf sạch, PR124 CI4906 đạt/78 skip. SoundFile0.14.0 đã có trong lock, cài riêng vào env test D:/vericlue/.venv không đổi package khác.
- RED native fixtures sau cài SoundFile:7 fail/54 pass vì test dùng fake backend nhưng collect gọi runtime_identity thật cần Torch. Đây là lỗi isolation của test, không lý do thêm runtime fallback vào production.
- Audit độc lập tái hiện6 lần diagnostic output trong3 kho env qua readiness_report/session.collect; output calibrator của session.fit_report là chủ ý, không coi đó là lỗi.
- Ruling: chỉ sửa các bug/coverage đã xác định; không thiết kế schema dữ liệu mặt hoặc tự tuyên bố quyền/nguồn/độc lập.
- Smoke source501c9e5:15CLI sai kho bị chặn trước input/model; đọc lại report DNU360hàng/356usable/4excluded, không đổi report và không inference/fit. Không dùng các con số này làm accuracy.
