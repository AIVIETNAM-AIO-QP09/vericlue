# Bàn giao · VOICE-09 · Ngoc Quang+Codex · 2026-11-01 19:40

**Nhánh:** codex/VOICE-09-readiness-audit, nền PR120 e572180.
**Trạng thái task sau phiên này:** review công cụ offline; dữ liệu/artifact còn thiếu.

## Đã xong
- Người dùng đã duyệt thiết kế báo cáo readiness: nhóm độc lập, loại tấn công,
  mẫu bị loại và khả năng chia CV sau loại lỗi. Không fit/LTT hoặc đổi API.
- Tạo checkout riêng bằng công cụ worktree của Codex tại
  C:/Users/Admin/.codex/worktrees/voice-readiness-audit/vericlue.
  Checkout android-merged-review giữ sạch ở 38ebb36 trong lúc đo thật.
- Mở rộng audit `prepare`; thêm CLI `readiness` đọc report đã đo, xác minh cùng
  validator với fitter. Bảo toàn nhóm liên kết của manifest đầy đủ ngay cả khi
  mẫu nối hai người/nguồn bị loại. Không suy loại tấn công cần có từ tập test.
- Phân biệt điều kiện số mẫu isotonic với cấu trúc CV cho Platt. Mọi báo cáo
  readiness vẫn `structural_only=true`, `calibration_ready=false`, chưa fit hoặc
  triển khai. Không thay trạng thái ModuleResult, xác suất hoặc ngưỡng/API.
- Agent viết test trước code: 10 ca RED đúng phần chưa có; cả 29 test mới/cũ
  sau triển khai đạt. Review độc lập không có Critical/Important; đã thêm trường
  dataset còn thiếu theo review, có RED rồi GREEN cho yêu cầu metadata này.
- Agent rà bốn nguồn tấn công theo publisher, không có ứng viên đủ điều kiện
  đưa ngay vào hiệu chỉnh. Report ngoài Git:
  D:/vericlue/tmp/voice-calibration-2026-11-01/attack-source-audit.json.

## Đang dở
- Đo toàn bộ 360 mẫu DNU calib_fit/18 người bằng collector/checkpoint/runtime
  đã pin, nguyên thứ tự, chọn trước inference. Chưa có kết luận đầy đủ tại
  checkpoint này. Giữ cả mẫu lỗi; không đọc audio calib_ltt/test hoặc fit.
  Source đo 38ebb36 ở checkout cũ; output mới nằm ngoài Git tại
  D:/vericlue/tmp/voice-calibration-2026-11-01/dnu-calib-fit-reviewed/.
- Full Python đang chạy, log/XML readiness-full-python.* ngoài Git. Kết quả
  cuối và báo cáo readiness trên dữ liệu thật được bổ sung sau khi hoàn tất.
- Chưa có dữ liệu TTS/VC đủ quyền và liên kết người/nguồn; chưa có artifact,
  LTT, test cuối hoặc nghiệm thu Android. Người dùng hiện không có điện thoại.

## Bước tiếp theo
1. Đợi collect hoàn tất; kiểm process, schema, source sạch trước/sau, hash và
   runtime. Tính lại aggregation/group cho mọi mẫu, giữ mọi lỗi/thiếu.
2. Chạy readiness trên report thật bằng code audit đã commit sạch, khai báo
   loại tấn công cần có trước xem kết quả; không chạy fit khi chỉ có lớp thật.
3. Hoàn tất kiểm tra, bàn giao và PR Draft phụ thuộc PR120. Không merge main.
4. Nhận quyền/metadata nguồn tấn công, chốt người/nguồn và split trước inference.
   LTT thuộc ROUT-03, không dùng ngưỡng benchmark thay thủ tục đó.

## Quyết định, lưu ý, bẫy
- Không sửa thresholds.yaml, contracts, ADR, proposal hoặc STATUS. Không xóa
  model/media/tài khoản; không khởi động dịch vụ live có cleanup, không thử máy.
- Lượt đo 360 đầu bị dừng sớm vì wrapper xử lý dict bằng thuộc tính ở phần
  tổng hợp. Giữ thư mục/log đã ngắt; chưa có report hoàn chỉnh để tái dùng.
  Wrapper sửa và review trước khi chạy lại vào thư mục mới; không đổi collector,
  model, mẫu, split hoặc chốt để làm đẹp số liệu.
- Readiness mô tả cấu trúc, không xác nhận quyền sử dụng/chiều score/accuracy
  hoặc số thử độc lập cho LTT. Mẫu degraded có raw score vẫn không phải đạt.

## Câu hỏi cho nhóm
- Chủ tài khoản cấp quyền nguồn gated hoặc publisher cung cấp license/crosswalk.
  SEA-Spoof hạn chế biometric deployment; SpeechFake VI giữ vai trò test và thiếu
  speaker/source; ViSpoofDB chưa rõ license; VSASV gated/chưa kiểm đủ metadata.
- Khi có đủ dữ liệu, cần triển khai LTT đúng đặc tả và giả định độc lập theo nhóm;
  không lấy Clopper–Pearson riêng lẻ làm thay toàn bộ thủ tục nhiều rủi ro.

## Test đã chạy
- Baseline `test_nes2net_utterance.py`: 19 passed.
- RED bộ readiness: 10 failure do thiếu chức năng, 4,25s; test dùng tín hiệu
  tổng hợp, không WAV/trọng số/người thật hoặc fit.
- GREEN cuối nhóm utterance/readiness: 29 passed, 11,18s ở runtime audio.
- Ruff lint/format sạch; plan_check 0 lỗi/10 cảnh báo đã có; diff check sạch.
- Full Python/collect đang chạy tại checkpoint; không gọi đã đạt khi chưa có log.
