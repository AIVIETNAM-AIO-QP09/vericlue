# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-01 18:20

**Nhánh:** codex/APP-01-demo-integration, code review tại5ea1928.
**Trạng thái task sau phiên này:** doing; đã xuất bản ba Draft PR, chưa nghiệm thu AI thật.

## Đã xong
- Người dùng yêu cầu tiếp tục sau khi tạm dừng. Đã xử lý fixture timestamp
  renderer, verify Android đầy đủ, commit review và push ba nhánh mới.
- [PR118](https://github.com/AIVIETNAM-AIO-QP09/vericlue/pull/118): Android/API/SEC-09,
  base main;153file. Consent/migration/luồng demo, recovery protocol, policy
  provisional và capture timestamp có chốt. Code head38dcbc9.
- [PR119](https://github.com/AIVIETNAM-AIO-QP09/vericlue/pull/119): parity/runtime
  NES2Net và công cụ toàn câu, base nhánh PR118;29file. Head19c7558.
- [PR120](https://github.com/AIVIETNAM-AIO-QP09/vericlue/pull/120): chuẩn bị DNU
  trên Colab, base nhánh PR119;12file code/docs trước bàn giao này.
- Giữ lịch sử nguồn52cebaf/140beb5. Tree tip stack trước bàn giao bằng tree
  integration5ea1928. Không checkout/reset worktree đang chạy demo hoặc force-push.
  Chỉ xuất bản code/test/docs, không dữ liệu/model/.env/DB/APK/ZIP/khóa.

## Đang dở
- CI GitHub đang chạy tại lúc lập bàn giao; Guard đã đạt ở cả ba. Chưa gọi CI
  xanh hoặc đề nghị merge. Kết quả cập nhật xem checks và mô tả từng PR.
- Web build local còn SecurityFatalError Next16.4.0 kế thừa main (SEC-07).
  Không đổi dependency hoặc bỏ chặn trong lượt này.
- Thiếu lớp giọng tấn công đủ quyền/mã người/nguồn và artifact hiệu chỉnh/LTT.
  DNU520mẫu/26người chỉ lớp thật, calibration_ready=false; VIVOS32 ngoài fit.
- Ba luồng đăng ký/đăng nhập lại/khôi phục Android chưa nghiệm thu bằng người.
  APK trên máy vẫn sourcea542a47, chưa có fix review mới; OTP mô phỏng.

## Bước tiếp theo
1. Review theo thứ tự PR118→119→120, xem diff riêng và checks mỗi head.
   Chưa merge hoặc đổi ready khi còn tiêu chí/CI chưa xử lý.
2. Nếu nhóm chấp thuận merge nền thì retarget PR sau về main, kiểm diff/CI lại;
   tránh squash/rebase làm mất ancestry nguồn các phép đo và job đã chạy.
3. SEC-07 xử lý web theo task riêng. Nhận/quyền dữ liệu tấn công, xác minh
   người/nguồn, chia tập trước fit; fit chỉ calib_fit, LTT/test tách riêng.
4. Khi có đủ artifact và người cầm máy, đồng bộ server/migration/APK và nghiệm
   thu ba luồng. Không suy unit test hoặc parity thành độ chính xác sinh trắc.

## Quyết định, lưu ý, bẫy
- Bốn lỗi review được sửa: recovery dùng nhầm protocol threshold; camera
  timestamp bất định thành hiện tại; policy provisional mở standard flow;
  MVP thiếu ChromaPulse nhưng vẫn mở account flow. Không đổi thresholds.yaml.
- Fixture snapshot lấy clock renderer thay fixed-future100ms; không đổi clock
  global, production guard hoặc golden để nhận cảnh báo sai. OTP-filled chụp
  sau100ms cho autofill/màu nút settle. Xem bàn giao1425 và log bên dưới.
- Không restart API/cài APK, xóa tài khoản/model/media hoặc merge main trong
  lượt xuất bản. Các chốt missing/error/degraded giữ nguyên.

## Câu hỏi cho nhóm
- Quyền/metadata MLAAD hoặc nguồn TTS/VC khác, artifact đúng model/protocol,
  người thử máy và việc SEC-07. Không sửa STATUS.md hoặc đánh APP-01 done.

## Test đã chạy
- Full integration Python trước tạm dừng:4695passed/118skipped/2warnings;
  code Python không đổi sau đó. Ref tách APP:227passed; voice:114passed/18skip;
  data Windows:15passed/2skip, WSL:17passed. Ref test chỉ khác dọn một dòng trắng
  cuối file test Android so với head xuất bản, đã đối chiếu diff bỏ blank-lines.
- Native NES2Net CPU2passed với checkpoint và canonical parity report. Không
  phải đo EER/APCER. Full web unit1319passed/10skip; lint/type/format đạt,
  build bị chặn như trên.
- Android `testDebugUnitTest assembleDebug verifyPaparazziDebug lintDebug` sau
  tiếp tục:206tests/0failure/0error/0skip, BUILD SUCCESSFUL1m32s;
  lint0error/43warning/3information. Đã review hình đúng Hold/tilt/quá góc.
- Ruff850file sạch; OpenAPI --check khớp code; plan_check0lỗi/10cảnh báo.
  Audit46commit/184path chưa thấy chữ ký secret thuộc bộ quét, media/model/
  file lớn/notebook output; audit không thay thế review nội dung.
- Log, bản xuất tree và PR body ngoài Git:
  D:/vericlue/tmp/publish-review-2026-11-01/. PR body ghi rõ phạm vi kiểm thử,
  nguồn số đo, dependency, giới hạn và các mục DoD chưa đạt.
