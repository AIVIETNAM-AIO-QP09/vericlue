# Bàn giao · VOICE-09 · Ngoc Quang+Codex · 2026-11-01 10:53

**Nhánh:** `codex/APP-01-demo-integration`.
**HEAD:** `61bcfed`; thay đổi bên dưới **chưa commit**.
**Trạng thái:** checkpoint giữa chừng theo yêu cầu chuyển chat, chưa nghiệm thu tích hợp.
**Repo:** `C:/Users/Admin/.codex/worktrees/android-merged-review/vericlue`.

## Yêu cầu và phạm vi đã được giao

Tiếp tục hoàn thiện VeriClue Android/API/ML để chạy ba luồng đăng ký, đăng nhập
lại, khôi phục. Ưu tiên nối bằng chứng parity NES2Net, đo/gộp toàn câu và chuẩn bị
hiệu chỉnh. OTP vẫn mô phỏng; không nối SMS. Người dùng sẽ thử điện thoại sau.
Yêu cầu mới nhất: tóm tắt để mở chat mới và dọn phần công việc của phiên này.
Chưa có yêu cầu bỏ thay đổi đang làm. Không push/PR, không tắt máy, không xóa
DB/tài khoản/media/model hoặc đổi điều kiện để ép xác minh đạt.

Đọc AGENTS gốc và theo khu vực trước khi làm. Không sửa STATUS.md. Không dùng
test để chọn ngưỡng; không coi error/degraded là đạt. Giữ nhãn demo khi chưa hiệu
chỉnh. Không commit dữ liệu/âm thanh/video/trọng số/bí mật.

## Đã commit trước checkpoint này

1. `a542a47`: consent SEC-09 lưu mẫu riêng, migration
   `0011_account_template_consent`, receipt/binding API–Android và nhãn
   `manual_full_demo`; sửa readiness reauth và khởi tạo matcher video khi không
   bật CCCD. Có APK debug đã ký, chưa cài trong phiên tiếp quản.
2. `52cebaf`: sửa CLI parity WAV, lớp upstream Fairseq, task/config tương thích,
   FP32/eval và cùng bốn CPU threads; instrument runtime/logits/hash.
3. `61bcfed`: ghi kết quả parity thật và giới hạn. Nguồn chi tiết:
   `docs/status/handoffs/2026-11-01-1015-app-01-ngoc-quang-codex.md`,
   `2026-11-01-1030-voice-09-ngoc-quang-codex.md`,
   `docs/status/results/VOICE-09-parity-2026-11-01.json`,
   `docs/runbooks/real-ekyc-next-steps.md`.

Kiểm tra ở phiên trước: Python toàn bộ 4661 đạt/81 bỏ qua; Android 202 test và
assembleDebug đạt; web 1319 đạt/10 bỏ qua. Đây là kết quả trước checkpoint, **không
phải** toàn bộ test được chạy lại sau thay đổi mới. Test luồng chủ yếu dùng mock,
không chứng minh ba luồng AI thật đã được nghiệm thu.

## Parity đã đo thật trước checkpoint

- VIVOS publisher `AILAB-VNUHCM/vivos`, revision
  `3cbfb2502e5e84776b4b778b020a09759f723f52`; 32 PCM/window duy nhất, chín speaker.
  Chỉ dùng cho parity; VIVOS test-only, tuyệt đối không đưa số mẫu này vào calib_fit.
- NES2Net checkpoint SHA256
  `3158d10c6fc3c58e452a33981b409f5a65ecf91d548931b4ffbd675462799685`.
- WSL HF Torch2.2.2CPU/Transformers4.57.6/NumPy1.26.4 so với Fairseq0.12.2,
  Torch2.2.2CPU, cùng bốn threads: max margin diff `2.47955322265625e-05`,
  32/32 cùng dấu. Windows Torch2.14.1CPU/HF4.57.6/NumPy2.5.4/bốn threads:
  max margin diff `7.271766662597656e-05`, 32/32 cùng dấu. Giới hạn 1e-4 không đổi.
- Hai lượt trước khác số threads không đạt vẫn được giữ. PASS chỉ là số học trên
  mẫu/runtime đã đo, không phải accuracy, chống tấn công hoặc hiệu chỉnh.
- Báo cáo gốc: `D:/vericlue/tmp/finish-2026-11-01/nes2net-parity-matched-runtime.json`
  và `nes2net-parity-windows.json`. Dữ liệu/provenance tại
  `D:/vericlue/data/diagnostics/nes2net-parity-vivos/`.

## Đang dở

**Bảy file code/test chưa commit:**

- Mới `ml/src/vericlue_ml/voice/nes2net_parity.py`: kiểm SHA256 report, checkpoint,
  version, provenance, runtime Python/Torch/HF/NumPy/CPU threads, số mẫu độc lập,
  duplicate, sign agreement và sai số. Dùng báo cáo tổng hợp đã commit làm bằng
  chứng numerical parity, không dùng làm artifact cho quyết định.
- `voice/nes2net.py`: opt-in hai biến `NES2NET_PARITY_REPORT` và
  `NES2NET_PARITY_SHA256`. Thiếu một biến thì lỗi. Kiểm sau khi nạp và mỗi lần dùng
  model đã cache; runtime/report lệch thì không có điểm hợp lệ. Có report hợp lệ
  thì quality ghi parity/report SHA; vẫn degraded/unclear, prob_attack=null.
- `voice/nes2net_timeline.py`: chỉ tổng hợp marker parity khi mọi cửa sổ đã đo có
  cùng binding. Vẫn không có điểm toàn câu và không nâng status.
- `eval/nes2net_worker.py`, `eval/nes2net_voice.py`, `eval/nes2net_client.py`: truyền
  marker đúng qua CLI/IPC; giữ raw-only và các chốt không cấp đạt.
- Mới `ml/tests/test_nes2net_parity_binding.py`: runtime/hash/count/duplicate/synthetic
  và lỗi evidence; kiểm không mở pass, thu hồi marker khi runtime đổi, IPC timeline.

Đã format/lint các file này. **Chưa review độc lập, chưa smoke trọng số thật với
code mới, chưa cập nhật README/task card, chưa bật hai biến môi trường trên server.
Chưa tạo phép gộp toàn câu hay công cụ fit mới.** Không coi phần WIP này đã hoàn tất.

## Bước tiếp theo

1. Đọc git status/diff và bảy file trên, tiếp tục từ checkpoint; không reset,
   clean hoặc làm lại ba commit cũ. Review binding của evidence với model/runtime;
   kiểm phạm vi chứng cứ nguồn/recipe/config/implementation. Cân nhắc kiểm chặt
   claim SHA/kiểu số và consistency trên IPC. Chưa được dùng marker làm chốt đạt.
2. Smoke code mới bằng runtime NES2Net thật, report tổng hợp đã pin hash; chứng
   minh parity=true nhưng status vẫn degraded. Thử sai hash/runtime; không nới sai
   số. Dùng file có quyền sử dụng và giữ báo cáo ngoài Git.
3. Cập nhật README/runbook/handoff/task card nếu hoàn thành phần này; kiểm lint,
   test liên quan, plan_check rồi commit có `[VOICE-09] [APP-01]`; không push.
4. Tiếp tục phần đo/gộp cả câu có protocol/version riêng và công cụ fit dùng
   Calibrator hiện có, giữ cửa sổ lỗi/thiếu và split theo người/nguồn. Candidate
   max raw margin đã được cân nhắc nhưng **chưa triển khai/chưa nghiệm thu/chưa
   chốt cho quyết định**. Không gắn calibrator first4s cho timeline mới.
5. Tìm/chuẩn bị dữ liệu calib_fit/calib_ltt/test có nhãn/quyền sử dụng, đúng
   protocol, đủ thật/tấn công và không giao người/nguồn. Thiếu dữ liệu thì ghi
   thiếu; không bịa artifact. Chốt dữ liệu/ngưỡng ROUT-03 là bước riêng.
6. Đồng bộ migration0011/server/APK/models/artifact và nghiệm thu vật lý ba luồng,
   gồm sai người/sai câu/không khớp môi/hết hạn/mất mạng. Chưa hứa AI thật toàn
   luồng sẽ đạt; giữ consent/receipt và OTP mô phỏng.

## Quyết định, lưu ý, bẫy

- API/light Python: `D:/vericlue/tmp/session-api-runtime/Scripts/python.exe`.
- NES2Net thật: `D:/vericlue/tmp/nes2net-cpu/Scripts/python.exe`.
- WSL Ubuntu-24.04, user ngocquang: `/home/ngocquang/nes2net-fairseq-ref/bin/python`
  và `/home/ngocquang/nes2net-hf-parity/bin/python`. Không để env cần giữ trong /tmp.
- Models: `D:/vericlue/models/selected-2026-10-24`; XLS-R gốc 3,8 GB đã có,
  không báo thiếu như bàn giao cũ của Anti. Không xóa để dọn ổ.
- JDK17 `D:/tools/jdk17`, SDK `D:/tools/android-sdk`.
- APK đã ký: `D:/vericlue/tmp/finish-2026-11-01/apk/VeriClue-SEC09-debug.apk`,
  source phần Android `a542a47`. SHA256
  `eacd8b07f76f4025ee42d69152cd3136b5a2821c14af449304cab31b973acbd5`;
  signer `822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75`.
  Chưa cài trong phiên này. Cài đè khi cần, không xóa app hoặc dữ liệu tài khoản.
- Launcher API8421 `D:/vericlue/tmp/full-demo-setup/VeriClue.cmd`; trạng thái chạy
  hiện chưa kiểm. Không đọc/in .env, khóa hay media cá nhân. Không khẳng định đã
  áp migration, cài APK hoặc test điện thoại. Phiên mới có thể cần ghép ADB lại.
- `ml/configs/thresholds.yaml` còn provisional; thiếu artifact PAD/GenD, identity,
  voice/lipsync đúng protocol vẫn chặn chế độ chuẩn. Không đổi flag để lách.
- `eval.session_calibration collect|fit`, `eval.video_face_match`,
  `eval.face_continuity` là entrypoint thật. Các script cũ tên
  `measure_video_face_match.py`, `fit_identity_thresholds.py` không tồn tại.

## Câu hỏi cho nhóm

Chưa tìm thấy dữ liệu hiệu chỉnh/đánh giá theo người cho các model/giao thức mới.
Cần nguồn dữ liệu/quyền sử dụng và người tham gia thu nếu không có sẵn. Việc thu
thật/đánh nhãn/đánh giá không tự sinh được bằng test mock hoặc 32 file parity.

## Test đã chạy

RED: test mới ban đầu lỗi do chưa có module/binding; test IPC lỗi do timeline
chưa truyền marker. Sau triển khai và format, GREEN ở checkpoint:

```
PYTHONPATH=ml/src;services/api/src
D:/vericlue/tmp/session-api-runtime/Scripts/python.exe -m pytest -o addopts=
  ml/tests/test_nes2net_parity_binding.py ml/tests/test_nes2net.py
  ml/tests/test_nes2net_timeline.py ml/tests/test_session_voice_worker.py
  -q --tb=short --junitxml=D:/vericlue/tmp/finish-2026-11-01/parity-binding-checkpoint.xml
115 passed, 2 skipped in 8.89s
```

Log `D:/vericlue/tmp/finish-2026-11-01/parity-binding-checkpoint.log`.
Hai skip không phải test trọng số thật đã đạt. Ruff check bảy file đạt;
ruff format 5 file/2 giữ nguyên; git diff --check sạch; plan_check 0 lỗi, 10 cảnh
báo tải/đường găng hiện có. Chưa chạy toàn bộ test
Python/Android/web sau WIP này; chưa đo model thật với code binding mới.

## Dọn dẹp và bảo toàn checkpoint

Không tạo script tạm ở gốc repo trong lượt này, không có file tạm mới cần xóa.
Giữ WIP để chat mới review. Bản sao diff tracked, hai file mới và bàn giao nằm tại
`D:/vericlue/tmp/finish-2026-11-01/chat-checkpoint-1053/`.
Không reset/clean, không xóa dữ liệu/model/log bằng chứng, không tắt server/máy.
