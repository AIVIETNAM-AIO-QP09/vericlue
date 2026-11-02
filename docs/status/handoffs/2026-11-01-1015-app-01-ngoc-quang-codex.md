# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-11-01 10:15

**Nhánh:** `codex/APP-01-demo-integration`, nền `c7613cc`
**Trạng thái task sau phiên này:** doing — tiếp quản phần Anti hết quota; chưa nghiệm thu đủ ba luồng mô hình thật.

## Đã xong
- Rà soát toàn bộ diff kế thừa ở bàn giao `2026-11-01-0953-app-01-ngoc-quang-codex.md`: SEC-09 bổ sung biên nhận lưu mẫu riêng trước trích xuất/ghi tài khoản, migration 0011 append-only, hợp đồng/API/Android; marker `manual_full_demo` gắn policy ở tạo phiên/finalize/voice và nhãn thử nghiệm ở kết quả.
- Review độc lập tìm được lỗi reauth khi khởi động server không bật quét CCCD: readiness cho phép nhưng Orchestrator không chọn/nạp/chạy FACE_MATCH. Sửa đủ ba vị trí theo opt-in `identity_face_from_video`; hai test khởi động/factory thực sự tái hiện RED trước sửa rồi GREEN.
- Thực thi parity với audio thật phát hiện `parity_nes2net.py` gọi hàm không tồn tại `nes2net._read_pcm`. Đổi sang bộ đọc native mono16k `Nes2NetDetector._read_file`, thêm test WAV PCM thật xác nhận mẫu đầu vào giữ nguyên. Smoke tổng hợp trước đó chưa đi qua đường lỗi này.
- Record TermsScreen và kết quả `manual_full_demo`, sáng/tối và font200%; kiểm tra ảnh thường/large. Thêm `TermsSnapshotTest` để tái lập. Ở chữ lớn nội dung cuộn, CTA vẫn cố định; checkbox không tích sẵn. Ảnh trước/sau giữ ngoài Git tại `D:/vericlue/tmp/finish-2026-11-01/`.
- Web typecheck và 1319 tests đạt (10 skipped); Android build/debug và 202 test hiện có đạt; snapshot bổ sung chạy riêng. Ruff/plan_check và kết quả cuối được cập nhật bên dưới sau khi hoàn tất các lượt đang chạy.
- Tải XLS-R gốc từ `https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt`: 3808868242 bytes, SHA256 `b08927597f2c9eb2ebd7dcc3ac78ee4b5f6021cbac4b3a6c5a9deec445d80ed9`, lưu riêng trong `D:/vericlue/models/selected-2026-10-24/`. Hash là giá trị đo của file tải từ nguồn gốc, không phải công bố đối chiếu độc lập của tác giả.
- Tải VIVOS bằng downloader repo từ publisher `AILAB-VNUHCM/vivos` (CC-BY-NC-SA4); chọn 32 cửa sổ PCM không trùng từ 9 speaker cho **đối chiếu số học**, không fit ngưỡng/model. VIVOS vẫn test-only theo chính sách chia dữ liệu của repo.
- Bổ sung môi trường HF Python3.12 `/home/ngocquang/nes2net-hf-parity` trong WSL; không thể chạy package `vericlue_ml` bằng Python3.10 của Fairseq vì `StrEnum`. Fairseq worker tiếp tục Python3.10 `/home/ngocquang/nes2net-fairseq-ref`. README cập nhật đúng hai interpreter và pin scipy1.15.3/numpy1.26.4 để tránh lỗi phụ thuộc.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Full Python suite đã chạy lại đạt **4661 passed,81 skipped,0 failed** (425.50s).
  Lượt đầu có một test cũ đòi timestamp13200/15200 trong khi bộ chọn góc tốt nhất
  chọn12500/14500. Đã tái hiện riêng, sửa kỳ vọng và đối chiếu với evidence server;
  105 test liên quan đạt trước lượt đầy đủ cuối. Không đổi lịch/chốt quay đầu.
- Parity thật trên32 WAV đã thực thi cả HF torch2.8 và Fairseq torch2.2.2:
  sign agreement1.0, max logit diff `9.441375732421875e-05`, max margin diff
  `0.00017642974853515625` > mức đặt sẵn1e-4 → **FAIL**, không tăng tolerance.
  Báo cáo local `nes2net-parity-vivos.json`. Đang đối chiếu thêm với torch2.2.2
  cùng phiên bản để phân biệt ảnh hưởng backend; chưa khẳng định parity đạt.
- Còn thiếu dữ liệu hiệu chỉnh/đánh giá đúng protocol video12s và giọng, chia theo người. Không dùng VIVOS hoặc lượt thử cá nhân để chọn ngưỡng. Không tạo calibrator giả hay đổi trạng thái diagnostic để mở guard.
- Chưa chạy nghiệm thu người dùng trên điện thoại; không tự đổi server, xóa tài khoản hoặc thu dữ liệu.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Sau khi có báo cáo parity số học, ghi kết quả và giới hạn. Nếu lệch phải sửa/kiểm chứng mapping; nếu đạt vẫn cần quy tắc gộp điểm/hiệu chỉnh hợp lệ trước quyết định chống giả giọng.
2. Thu/nhận dữ liệu có quyền sử dụng cho PAD/GenD/match/continuity/lipsync/voice, chia `calib_fit`/`calib_ltt`/test theo người và giữ protocol/version; chạy công cụ đo/fit đã có, không lấy dữ liệu test để chọn ngưỡng.
3. Nghiệm thu cả ca đạt/từ chối trên điện thoại trước khi gọi xong toàn luồng. OTP vẫn mô phỏng `synthetic` + `SIMULATED_OTP=true`.

## Quyết định, lưu ý, bẫy
- Không push/PR; không tắt máy. Không commit media/trọng số/nguồn dữ liệu hay bí mật. Giữ cơ chế từ chối thiếu bằng chứng.
- Cập nhật task card/backlog chỉ ở mức code/test; APP-01/SEC-09 vẫn doing vì chưa nghiệm thu thiết bị và xóa/rút đồng ý toàn phạm vi.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Cần dữ liệu phiên đúng protocol có quyền sử dụng để hiệu chỉnh thật. Các dữ liệu công khai/ảnh tĩnh không tự thay thế tập challenge mắt/quay đầu của app.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
Logs: D:/vericlue/tmp/finish-2026-11-01/
reauth-startup-red.log: 2 failed, đúng lỗi cần sửa.
reauth-startup-green.log: 90 passed (orchestrator/video identity/dynamic flows).
parity-wav-red.log: AttributeError đúng đường WAV native.
nes2net-final.log: 42 passed (môi trường audio; không cần trọng số).
python-final.log/xml: 4661 passed,81 skipped,0 failed,2 warnings in425.50s.
final-affected.log: 311 passed (API/account/consent/contract).
video-identity-green.log:105 passed (video/head/session attack).
android.log: testDebugUnitTest assembleDebug BUILD SUCCESSFUL; JUnit lưu android-unit/: 202 tests,0 failures/errors/skips.
terms-record.log / terms-extra-record.log: recordPaparazziDebug thành công.
web-typecheck.log exit0; web-test.log: 1319 passed,10 skipped.
plan.log: 0 lỗi,10 cảnh báo tải kế hoạch hiện có.
```
