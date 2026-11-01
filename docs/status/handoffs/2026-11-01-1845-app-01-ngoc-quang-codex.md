# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-01 18:45

**Nhánh:** codex/APP-01-demo-integration, code0998247; PR118→119→120 Draft.
**Trạng thái task sau phiên này:** doing; đã chuẩn bị cập nhật, chờ dữ liệu/thiết bị.

## Đã xong
- Kiểm GitHub: main vẫn7fc2ce9; PR118head4b1cd8f,119ae8c077,120bf6af52 đều
  Draft/OPEN,chưa review người/chưa merge. Lần check mới nhất10/10,8/8,8/8 đạt.
  PR119 có run cũ bị concurrency hủy; dùng lần mới nhất mỗi tên job để đọc.
- Build APK debug current source0998247, tree Android bằng PR118. Chữ kýv2 và
  certificate822e5e44…95c75 khớp bản debug đã cài trước đó, không dùng pin khóa
  phát hànhe6795060…82954. Packagevn.vericlue.app/code2/version0.3.0/arm64-v8a,
  localhost8421,signed_media=true,trace=false. Hash/body đầy đủ trong runbook.
  File sẵn tại D:/vericlue/tmp/publish-review-2026-11-01/ready-apk/.
- Smoke bằng runtime API/model thật, nguồn0998247 sạch; dùng backup SQLite và
  empty-media riêng, không enter lifespan hoặc chạy cleanup. DB gốc SHA không
  đổi, integrityok,FK0,migration0011. Nạp31,681s,healthok/failed_modules=[].
- Tạo onboarding tổng hợp trong bản sao: mode/policy manual_full_demo đúng,
  dynamicv2/12000ms; consent xử lý/lưu mẫu mặc định not_granted. Finalize chưa
  consent409privacy_consent_required. Không thu sinh trắc hoặc tạo tài khoản.
- Kiểm guard standard cả3purpose trả503flow_unavailable. Năm artifact
  identity/continuity chưa có, router policyprovisional vẫntrue. Không ép đạt.
- Cập nhật runbook: server đang dừng/ADB không thiết bị, APK mới chưa cài;
  phân biệt lịch sử sáng01/11 với kết quả review/smoke hiện tại.
- Rà primary publisher VoiceSpoof-VN/RADAR/VietPrism, ghi rõ ứng viên/quyền/
  metadata còn thiếu. Không tải audio mới hoặc đưa evalVI vào fit; không đổi
  data-plan,thresholds/contracts/ADR/STATUS.
- Đã collect toàn câu native3mẫu DNU/3người calib_fit chọn cố định trước đo,
  code6b75896. Cả3có rawscore đủ cửa sổ,giữdegraded/unclear/không xác suất;
  không fit,không chấm calib_ltt/test. Checkpoint/model/runtime/report SHA ở
  research; output ở dnu-train-smoke/ ngoài Git. Không accuracy/deploy.

## Đang dở
- ADB không thấy điện thoại; đã hỏi availability bất đồng bộ. Chưa cài APK mới
  hoặc thử CCCD/quay mặt/đọc câu. Thiết bị trước đây vẫn sourcea542a47.
- Server8421 đang dừng. Không tự mở launcher trên dữ liệu gốc vì có cleanup
  worker; yêu cầu không xóa media/tài khoản/model vẫn giữ. Smoke bản sao không
  đồng nghĩa dịch vụ/điện thoại đã nối lại hoặc nghiệm thu.
- DNU chỉ bonafide; thiếu TTS/VC đủ quyền/crosswalk và các artifact/LTT/test.
  Không thay MLAAD bằng nguồn khác khi chưa kiểm nguồn,người,quyền.

## Bước tiếp theo
1. Khi máy nối ADB, kiểm đúng package và certificate đang cài trước
   `adb install -r` APK ready; không uninstall/clear. Báo đúng kết quả cài,
   thiết lập reverse8421 khi dịch vụ sẵn và người dùng có thể thử.
2. Xử lý bước vận hành dịch vụ sao cho giữ yêu cầu không xóa media hiện có;
   không suy việc runtime nạp được thành đã mở guard/AI thật.
3. Nhận quyền MLAAD và meta/people/source, hoặc kiểm archive/quyền/nguồn ứng
   viên mới trước quyết định dùng. Chốt split theo người/nhóm trước inference;
   VIVOS32parity/test-only không chuyển vào fit.
4. Chỉ fit khi đủ hai lớp/cỡ mẫu trên calib_fit; LTT và test riêng. Không đổi
   ngưỡng hoặc nối aggregate vào API để ép demo. Giữ ba DraftPR,không merge.

## Quyết định, lưu ý, bẫy
- Smoke không có dữ liệu sinh trắc mới và không có test accuracy. Không dùng
  thiếu consent như số liệu chống giả mạo. OTP vẫn mô phỏng,profile mock=true
  với sessionface/sessionvoice chạy thật theo cấu hình; nhãn demo vẫn cần.
- Logs/report/DBbackup/APK/metadata ngoài Git tại
  D:/vericlue/tmp/publish-review-2026-11-01/. Không commit file runtime hoặc secret.
- Lần Gradle đầu lỗi do PowerShell tách -P URL; chạy lại đối số có quote đã đạt.
  Không đổi build script để né lỗi gọi lệnh.

## Câu hỏi cho nhóm
- Quyền/metadata tấn công,artifact đúng protocol; người thao tác Android và
  thời điểm chạy dịch vụ phù hợp yêu cầu giữ media; việc SEC07 theo task riêng.

## Test đã chạy
- `assembleDebug` explicit localhost/signedMedia/tracefalse:BUILD SUCCESSFUL5s.
  apksigner verifyv2 và aapt package/version/ABI đạt, hash APK kiểm lại.
- `native_runtime_readiness.py` ngoài Git:exit0,report.json có kết quả nêu trên;
  health/consent/challenge/guard chạy code thật trên bản sao. Models preloaded,
  không thay detector bằng fake hoặc tạo calibrator để smoke.
- Code0998247 trước đó:full console pytest4695passed/118skip/2warning;
  Android206/0failure,build/snapshot/lint đạt; các head đã lên GitHubCI xanh.
  Không chạy lại toàn suite cho lượt chỉ sửa tài liệu này.
- `plan_check.py`:0lỗi/10cảnh báo đã có; gitdiffcheck sạch. Không đánh APP01
  hoặc VOICE09 done khi còn điều kiện thiếu. Các bản report/APK/DB không stage.
