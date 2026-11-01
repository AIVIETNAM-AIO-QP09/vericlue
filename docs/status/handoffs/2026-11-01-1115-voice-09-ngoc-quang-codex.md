# Bàn giao · VOICE-09/APP-01 · Ngoc Quang+Codex · 2026-11-01 11:15

**Nhánh:** `codex/APP-01-demo-integration`, nền `185c3db`.
**Trạng thái:** review công cụ offline; dữ liệu/thiết bị vẫn chưa nghiệm thu.

## Đã xong
- Công cụ `eval.nes2net_utterance prepare|collect|fit`: max raw margin có version
  timeline4s-tail-maxmargin-v1, chỉ gộp khi mọi cửa sổ đo được. Giữ evidence lỗi/
  thiếu, degraded/unclear/null probability. Không đổi timeline/API hiện hành.
- Manifest có nhãn/quyền/source/revision/SHA và mọi subject liên quan. Chặn
  path escape, duplicate byte/PCM và người/nguồn giao split; hợp nhóm liên kết
  cho cả GroupKFold. Không nhận VIVOS/test_only vào hiệu chỉnh.
- Fit tính lại timeline/gộp, kiểm header checkpoint/config/code và source manifest;
  chỉ dùng calib_fit, thống kê loại lỗi. Commit fit/đo riêng, đọc/hash cùng snapshot
  report và từ chối report đổi trong fit. Không cài artifact hay chọn ngưỡng LTT.
- Review độc lập đã tìm lỗi status dạng string, provenance thiếu, commit fit sai
  và hash report không đúng snapshot; regression RED rồi GREEN cho các lỗi đó.
- Native audio runtime: 19 tests đạt. Ruff toàn repo sạch, format chín file sạch.
- DB đã backup `D:/vericlue/tmp/finish-2026-11-01/before-migration0011.sqlite3`,
  integrity_check=ok, migration 0010 ->0011_account_template_consent.
- Cấu hình đúng hai biến parity có pin reviewed trong profile hiện có. API8421
  khởi động, health ok/failed_modules=[], vẫn mock_models=true ở profile hiện có.
- APK SEC09 hash/signer khớp pin; tree apps/android giống source a542a47 của APK.
  Chưa cài: adb devices không thấy thiết bị. Không gỡ/xóa dữ liệu tài khoản.

## Đang dở
- Full Python suite đang chạy, chưa kết luận ở checkpoint này. Log/XML:
  `D:/vericlue/tmp/finish-2026-11-01/continuation-python.*`.
- Sau commit sạch, smoke collector CLI bằng WAV thật parity-only, rồi kiểm fit
  bằng tín hiệu tổng hợp có provenance; không tạo calibrator cho quyết định từ đó.
- Nguồn mới chỉ có metadata/license/cards ghim revision; chưa audio/both classes.

## Bước tiếp theo
1. Hoàn tất verification và ghi kết quả thật sau các lượt đang chạy.
2. Theo runbook nes2net-utterance-calibration.md, chuẩn bị/nhận bundle trên Kaggle/
   Colab có quyền dùng, mã người/nguồn, thật+tấn công và split khóa trước đo.
3. Fit/calib_ltt/test theo đúng protocol; thiếu artifact tiếp tục chặn chuẩn.
4. Nối điện thoại và nghiệm thu đăng ký/reauth/recovery gồm ca từ chối. Giữ OTP
   mô phỏng; không suy health/test/smoke thành AI thật toàn luồng đã nghiệm thu.

## Quyết định, lưu ý, bẫy
- Người dùng xác nhận dữ liệu hiệu chỉnh chưa được chuẩn bị, không bị xóa lúc dọn.
- Nguồn đã rà publisher: DNU revision33b2a469901cb71b243403254d3cfef25170526c,
  Speech-MASSIVE revisionff792febc16187a21e5bca38fb02a55daf91dc05.
  Chỉ metadata ở D:/vericlue/data/diagnostics/nes2net-calibration-prep-2026-11-01/.
- Quyền public release không tự xác nhận mọi tác vụ clone/định danh; cần chốt
  đúng phạm vi. Theo ADR0015 dữ liệu dạy/hiệu chỉnh chuẩn bị trên Kaggle/Colab.
- Không sửa thresholds/contracts/ADR/STATUS. Không push/PR/xóa model/media/tắt máy.

## Câu hỏi cho nhóm
- Cần bundle có quyền dùng, nhãn, crosswalk người/nguồn và tấn công TTS/VC. Chưa
  có dữ liệu đủ điều kiện fit hoặc artifact thật đúng giao thức.
- Cần điện thoại ADB kết nối và người tham gia chủ động thử để nghiệm thu ba luồng.

## Test đã chạy
- `test_nes2net_utterance.py`: 19 passed trong runtime nes2net-cpu (SoundFile/Torch).
- Nhóm parity/nes2net/timeline/session worker: 129 passed,2 skipped trước extension.
- Ruff toàn repo và format9files đạt; diff check sạch; plan_check0lỗi/10cảnh báo.
- Full suite/native collector sau commit: sẽ bổ sung bằng kết quả thực tế.

## Verification và triển khai sau checkpoint (01/11)

- Commit công cụ `72b06ed6d61abc5fdd98303f0f55cbcec6cfc4e8`; parity `185c3db`.
- Full Python: **4689 passed,97 skipped,2 warnings in741.46s**. Hai warning
  đã có trước: Starlette/httpx deprecation và Pydantic serializer trong ca
  artifact sai module; không có lỗi.
  Log/XML: continuation-python.log/xml. Runtime API nhẹ không có SoundFile nên
  các test metadata/audio tùy chọn bỏ qua; chúng được chạy ở runtime audio.
- Audio regression với SoundFile/Torch: **149 passed,1 skipped in37.77s**,
  log continuation-audio-regression.log. Skip còn lại cần fixture/model slow riêng.
- Native collect trên source sạch72b06ed, WAV VIVOS **split=test,parity-only**:
  prepare/collect thật thành công,hai cửa sổ,aggregate raw có version riêng,
  degraded/unclear/null probability. Thử fit report chỉ-test bị từ chối, không
  sinh candidate. Files utterance-protocol-smoke-{manifest,audit,measurements}.json.
- Native IPC từ runtime API nhẹ sang NES2Net CPU thật: marker=true,worker_available,
  degraded/null probability. Report parity-native-ipc-smoke.json. Không phải accuracy.
- APK cài đè thành công sau khi điện thoại tự xuất hiện trong ADB: Samsung A04,
  package vn.vericlue.app,version0.3.0/code2; không uninstall/clear. Đã mở app và
  adb reverse8421. Người dùng được hỏi về khả năng trực tiếp thử ba luồng, chưa
  có bằng chứng thao tác/nghiệm thu ở thời điểm ghi dòng này.
- Phát hiện profile ban đầu SIMULATED_OTP=false. Đã đặt true đúng yêu cầu trong
  synthetic, restart chính server đã mở,healthok/failed_modules=[]; manual_full_demo
  vẫn true,không thay chốt AI. Report cuối:
  continuation-deployment-readiness-otp-simulated.json (bản readiness trước đó
  ghi OTPfalse được giữ làm lịch sử). Server đang chạy, không tắt máy.
- Manifest DNU lớp thật đã dựng từ metadata publisher, seed42/hash ID, bảo toàn
  người test gốc; metadata subject/fileSHA disjoint. File
  D:/vericlue/data/diagnostics/nes2net-calibration-prep-2026-11-01/DNU-bonafide-proposed-manifest.json.
  Đây là partial inventory: chưa audio/PCM check,thiếu tấn công/quyền clone.
  Không có calibrator thật,không coi bước dữ liệu hoàn tất.
- Không push/PR,không xóa tài khoản/DB/media/model. Không sửa STATUS/thresholds/
  contracts/ADR. Demo AI thật toàn luồng **chưa nghiệm thu**.

### Chốt vận hành trước khi trả chat

`continuation-final-readiness.json` là snapshot cuối: OTP mô phỏng bật, server
health ok, migration0011 và APK đã cài đè. Các JSON readiness cũ giữ làm lịch sử.
ADB reverse được thiết lập; probe HTTP bằng nc chưa xác nhận phản hồi từ điện
thoại, nên không coi kết nối ứng dụng/ba luồng đã nghiệm thu. UI dump chỉ thấy
giao diện hệ thống; không thao tác đồng ý, CCCD, camera hoặc micro thay người dùng.
Chờ người dùng trực tiếp thử sau câu hỏi availability trong chat.
