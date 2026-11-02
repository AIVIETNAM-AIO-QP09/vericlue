# Bàn giao · VOICE-09 · Ngoc Quang+Codex · 2026-11-01 11:03

**Nhánh:** `codex/APP-01-demo-integration`, nền `61bcfed`.
**Trạng thái:** review phần binding; chưa hiệu chỉnh/nghiệm thu eKYC.

## Đã xong
- Tiếp quản nguyên bảy file WIP và bàn giao 10:53. Review độc lập phát hiện ba
  vấn đề: chưa bind graph/source, claim số sai kiểu và IPC claim mâu thuẫn.
- Bổ sung fingerprint AST graph/mapping/preprocessing/margin và config canonical.
  Đối chiếu trực tiếp source commit52cebaf: fingerprint số học hiện tại giống
  bản đã đo; chỉ loại phần quality instrumentation. Không sửa số đo parity.
- Pin nguồn/script đã review, kiểm số mẫu/duplicate/sign/tolerance, boolean/hash
  và trạng thái claim ở IPC/từng cửa sổ. Model cache kiểm lại trước inference.
- Smoke checkpoint thật Windows, VIVOS chỉ parity: first4s và timeline hai cửa
  sổ có marker true, vẫn degraded/unclear/null probability. Sai hash, đổi threads
  và đổi graph đều error/không score, thu hồi marker; vẫn cùng model cache.

## Đang dở / Bước tiếp theo
1. Phép gộp và đo toàn câu có version riêng; không gắn calibrator first4s.
2. Dữ liệu calib_fit/calib_ltt/test theo người/nguồn, cả thật và tấn công có quyền
   sử dụng. Không dùng 32 mẫu VIVOS parity để hiệu chỉnh.
3. Đồng bộ migration0011/server/APK, nghiệm thu ba luồng trên điện thoại. ADB
   kiểm trong phiên này chưa thấy thiết bị. OTP mô phỏng; thiếu artifact giữ chốt.

## Quyết định, lưu ý, bẫy
- Báo cáo parity bổ sung binding có SHA256
  `669bf62e4db134a46e8a0dd8f3d5b6a72bba90a984c3a7901fa8e866e8f21a48`.
  Chỉ pin bản đã review; đổi runtime/code/config cần kiểm chứng lại.
- Không sửa thresholds/contracts/ADR/STATUS. Không push/PR/xóa dữ liệu/model/tắt máy.
- Native smoke không phải accuracy. Timeline parity nói về các cửa sổ dùng graph
  đã đo; không chứng nhận quy tắc gộp hoặc cả câu thật.

## Câu hỏi cho nhóm
- Hiện data/raw chỉ thấy VIVOS; chưa có bộ giọng thật/tấn công và crosswalk
  người/nguồn đủ điều kiện hiệu chỉnh. Cần dữ liệu/quyền sử dụng đã xác nhận.

## Test đã chạy
- RED: 10 ca mới bắt lỗi claim/binding/IPC; GREEN sau sửa 129 passed,2 skipped
  (nhóm parity_binding/nes2net/timeline/session_voice_worker,6.51s).
- Ruff check sạch; plan_check 0 lỗi,10 cảnh báo tải kế hoạch hiện có; diff check sạch.
- Trọng số thật: `D:/vericlue/tmp/finish-2026-11-01/parity-binding-final-timeline-smoke.json`
  (pin cuối,76990 mẫu input,hai cửa sổ). Negative/cache smoke:
  `parity-binding-reviewed-smoke.json` (pin trước bổ sung fingerprint margin).
- Lượt chọn file dài nhất trước đó có cửa sổ thiếu tiếng nên không đủ marker
  toàn timeline; không bỏ VAD để ép qua. Smoke cuối dùng file có đủ tiếng.
- Chưa chạy lại toàn Python/Android/web ở checkpoint này.
