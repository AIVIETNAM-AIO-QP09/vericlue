# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-01 23:09

**Nhánh:** `codex/APP-01-real-ai-phone-demo`, base `72e5bbd7` của Draft PR125.
**Trạng thái task sau phiên này:** `doing` — chuẩn bị trước điện thoại đã hoàn tất;
APP-01/FLOW-04/SEC-09 chưa nghiệm thu trên thiết bị. Không merge main.

## Đã xong
- Source thực thi/APK cố định `7904d7092baaa338f06351688286c1f4dc440ea0`.
  Worker manual dùng raw AntiDeepfake/SyncNet, policy `manual-full-demo-v2`,
  `calibrated=false`, `prob_attack=null`, version/hash riêng. Chỉ raw thành công
  và evidence hợp lệ mới gate; NES2Net standard giữ diagnostic, lỗi/degraded
  không đổi thành đạt. Continuity manual không bị artifact cũ ghi đè.
- Android API thật mặc định trong bản giao; giữ mode/policy/receipt và nhãn
  demo qua lưu/khôi phục. Legacy không tự xóa hoặc đoán mode; lỗi giữ binding
  cũ. Gallery có nhãn xem trước; không fallback scripted success khi API lỗi.
- Gói ngoài Git `D:/vericlue/tmp/phone-demo-2026-11-02/`: source git archive
  có manifest hash, APK universal0.3.0, `.env`/DB/media/khóa demo riêng ổn định,
  launcher start/status/stop/connect/check, README và checksum. Không dùng
  DB/media gốc cho cleanup. Model cache đọc từ `selected-2026-10-24`.
- Model thật đã nạp; AntiDeepfake/Qwen/CTC đã suy luận một mẫu DNU `calib_fit`
  cố định trước kết quả. Không fit/chọn ngưỡng, không dùng VIVOS parity. CTC
  giữ `degraded/unclear`; SyncNet chỉ forward tensor audio/video hữu hạn, chưa
  video nói thực. API migrated0011, healthok, phiên đúng manual/hash, consent
  chưa tự cấp, finalize thiếu consent409, không cấp receipt khi chưa đủ điều kiện.
- Dừng/mở lại server qua launcher và kiểm API lại đã qua. Status xác minh PID
  và token HMAC ký mới đúng khóa/mode/policy, không chỉ tin healthz/cổng mở.
  STOP chỉ kiểm ownership, vẫn dừng được API treo HTTP. CONNECT xác nhận package
  cũ/chứng chỉ trước install-r; cho cài mới nếu package chưa có, không uninstall/reset.
- Review độc lập Task1/API và Task2/Android đã qua; review toàn source không có
  Critical/Important. Review bộ giao phát hiện hai lỗi stop phụ thuộc HTTP/cài
  mới, đã tái hiện RED, sửa, kiểm GREEN và review lại không còn lỗi chặn.
- [Bằng chứng tổng hợp](../results/APP-01-phone-demo-preflight-2026-11-01.json),
  [checklist sáng mai và phần thiếu](../../runbooks/android-02-11-checklist.md).

## Đang dở
- Chưa có điện thoại: chưa cài APK mới, chưa quay CCCD/mặt/giọng, chưa nghiệm thu
  onboarding → reauth → recovery, Keystore/binding thật, consent/withdrawal,
  quyền camera/micro, restart/mất kết nối, offset AV/crop và độ trễ CPU thực.
- Thiếu dữ liệu tấn công và artifact hiệu chỉnh/LTT/đánh giá cuối theo người/nguồn
  có quyền sử dụng. DNU có giọng thật chưa đủ fit hai lớp; VIVOS32 parity giữ ngoài fit.
  Ngưỡng `.50/.50/.30/.30/.50/.50` chỉ minh họa. Không có số accuracy hoặc chốt chuẩn.
- OTP vẫn mô phỏng; SMS thật/HTTPS phát hành/NFC/CSDL nhà nước chưa được nghiệm thu.
- Draft PR126 đã mở; CI đang kiểm sau follow-up workflow. Kết quả cuối lưu trong
  PR và checkpoint private của gói. Không suy CI xanh từ kết quả local; không merge.

## Bước tiếp theo
1. Sáng02/11 mở `START-DEMO.cmd`, đợi READY; cắm USB/bật và cho phép debugging,
   chạy `CONNECT-PHONE.cmd`, cho camera/micro và tự chọn consent trên app.
   Giữ USB/laptop hoạt động. Không mở launcher cũ song song.
2. Thử lần lượt checklist. Đăng ký đọc câu chỉ khi app yêu cầu. Khôi phục tạo
   alias mới trên cùng app đang giữ binding, không cần máy thứ hai hoặc xóa dữ liệu.
3. Ghi kết quả thật từng mục/giờ/lỗi. Không ép lượt bị model từ chối thành đạt.
   Phiên đạt nhưng receipt thiếu/lưu lỗi phải báo tài khoản chưa lưu; không nhận
   account-ready hoặc mở tài khoản. Thu video/log riêng có consent để sửa lỗi thực.
4. Sau demo tiếp tục nhận/tải dữ liệu tấn công, xác nhận quyền/người/nguồn, chia
   calib_fit/calib_ltt/test, fit và đánh giá độc lập; không dùng test để chọn ngưỡng.

## Quyết định, lưu ý, bẫy
- APK SHA256 `ee2444f2759cd7e545dbea1fbdcdefaea1420546a6cd7c0cd9509d393efd632b`.
  Package `vn.vericlue.app`, version0.3.0/code2, universal,
  localhost8421/signedMedia=true/liveByDefault=true/presenceTrace=false.
  Signer laptop `822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75`;
  APK v2=true/v3=false, khác public distribution signer; không chạy signer khác.
- Policy mặc định `2f7e8becee1dff4d23831acd791adc449af3e12c2e0f314501930b1109b25ca8`.
  Đổi policy/mode làm phiên/tài khoản cũ không tương thích; không nâng cấp ngầm.
  SMS mô phỏng hiển thị mã ngẫu nhiên lượt gửi, không dùng mã cố định123456.
- Draft [PR126](https://github.com/AIVIETNAM-AIO-QP09/vericlue/pull/126) đã mở.
  Review đóng gói còn phát hiện workflow APK GitHub chưa truyền liveByDefault;
  đã thêm cờ, kiểm BuildConfig thực và ghi metadata trước xuất artifact. Đây là
  thay đổi workflow/test, không thay code/source/checksum APK local7904d70.
- Profile mới có startup timeout300s; `scripts/server.py` thêm timeout có kiểm
  finite30..600/default120 trước spawn. Worker manual preload thật trước ready.
- Không sửa contracts, thresholds.yaml, ADR, proposal hoặc STATUS. Không commit
  dữ liệu/model/.env/khóa/media. Không đổi số liệu/bản ghi parity canonical.
  Giữ nguyên worktree tích hợp cũ `android-merged-review/vericlue` và mọi dữ liệu cũ.
- Người dùng đã yêu cầu tắt máy sau khi hoàn tất và review cuối; chỉ root thực hiện
  sau lưu checkpoint, kiểm CI cần thiết và dừng tiến trình sở hữu. Không tự bật lại.

## Câu hỏi cho nhóm
- Khi có máy, người tham gia trực tiếp thử/cho consent và xác nhận ba luồng theo
  checklist; chưa có số liệu thực để nhóm nghiệm thu.
- Nhóm cung cấp/duyệt nguồn giọng tấn công và dữ liệu mặt/AV phù hợp có quyền dùng,
  mã người/nguồn. Không cần người dùng tự fit model, chọn ngưỡng hoặc build APK.

## Test đã chạy
- `python -m pytest --junitxml=<private-bundle>/python-full.xml`: **4998 passed,
  100 skipped**, không lỗi. Local chưa bật PostgreSQL và một số native/browser/
  FFmpeg/dependency opt-in; CI PostgreSQL16 và native integration kiểm riêng.
- `ruff check .`, `ruff format --check .`: sạch,876 file đã format;
  `gen_openapi.py --check`: khớp, `uv lock --check`: khớp.
- `plan_check.py`: **0 lỗi,10 cảnh báo** tải/đường găng đã tồn tại.
- Android `testDebugUnitTest lintDebug assembleDebug verifyPaparazziDebug` với
  các property gói trên: **223 test,0 lỗi; BUILD SUCCESSFUL**. Golden ignored đã
  record trước verify, không gọi đây là so sánh với baseline hình lịch sử.
- Native frozen-source preload + inference qua worker/protocol thật đã ghi
  report private và aggregate public; SyncNet2048-dim hữu hạn chỉ tensor smoke.
- `test_delivery.py`: **7 passed**; kiểm khác signer/không có phone không install,
  cài mới khi chưa có package, ownership/HMAC và stop không phụ thuộc HTTP.
- API freshDB/migration0011, thiếu consent409, receipt chặn và stop/restart đã qua.
  Chưa có camera/CCCD/giọng/ba luồng trên điện thoại thật.
- Workflow artifact: hai test thực thi bước kiểm artifact bằng file tổng hợp,
  **2 RED** (gallery không bị chặn, thiếu metadata) → **2 GREEN** sau sửa; không
  ký hoặc thay APK sáng mai. Test signer hiện có kiểm tương thích riêng.
