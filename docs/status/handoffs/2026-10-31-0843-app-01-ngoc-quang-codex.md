# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-10-31 08:43

**Nhánh:** `codex/APP-01-demo-integration`, nền `524136d`
**Trạng thái task sau phiên này:** doing — trình diễn ngưỡng thủ công, chưa nghiệm thu/hiệu chỉnh toàn luồng thật

## Đã xong
- Người dùng duyệt mode ngưỡng thủ công do cần quay video nộp bài. Model mặt
  chạy thật, không giả Calibrator/MatchThreshold hoặc dữ liệu hiệu chỉnh.
- ManualDemoThresholds: PAD/Gendmax0.50, cosine identity/consistencymin0.30,
  hash policy và version suffix riêng. Chỉ tính gate khi inference OK, không
  error; prob_attack=null, calibrated=false. Standard mặc định giữ nguyên.
- Cấu hình chỉ cho synthetic+ekyc+mvp, onboarding, real face/video/card/checks/
  consistency, OTP mock. Từ chối protected/full/account enrollment/credentials/
  signing/voice continuity. Không sửa thresholds.yaml hoặc guard tài khoản.
- API session gắn policy; đổi mode/ngưỡng thì phải bắt đầu phiên mới. API vẫn
  review, chỉ thêm demo_complete khi mọi kiểm tra đạt; không cấp receipt/proof.
- Contract trước: optional evaluation_mode/demo_policy_id/demo_complete,
  allOf/validator không cho manual thành pass. Standard metadata mặc định được
  bỏ khi serialize, giữ response cũ. OpenAPI và type web cùng cập nhật.
- Android kiểm mode/hash và cấm manual pass/marker lạ; route riêng không qua
  AccountFlow.finish. Theo yêu cầu người dùng, tiêu đề “Xác minh thành công”,
  luôn có “Demo · Ngưỡng chưa hiệu chỉnh” và giải thích không dùng mở tài khoản/
  xác minh thực tế. Có notice trước khi ghi hình; camera unbind ở màn kết quả.
- Đã pair/kết nối điện thoại mới Samsung A04, API34/arm64, cài -r Success cùng
  signer822e5e44…, reverse8421. Không thao tác điện thoại cũ đang offline.

## Đang dở
- Chưa có lượt người dùng đầy đủ trên A04; không bảo đảm mọi lượt/model sẽ đạt
  ngưỡng. Test tổng hợp không phải accuracy/chống tấn công hoặc nghiệm thu.
- Chế độ chuẩn còn thiếu artifact, dữ liệu theo người, SEC-09/lưu mẫu/tài khoản,
  continuity/giọng khi cần và nghiệm thu đầu cuối. Mode này không thay thế chúng.

## Bước tiếp theo
1. Theo runbook manual-face-demo.md, bắt đầu phiên đăng ký mới; giữ nhãn demo khi
   quay và nói rõ AI thật/OTP mô phỏng/ngưỡng chưa hiệu chỉnh.
2. Nếu không hoàn tất, đọc kết quả đúng attempt trước khi yêu cầu người thử lặp;
   không nới ngưỡng theo một mẫu hoặc tự ép head/model lỗi thành đạt.
3. Tắt mode và restart/bắt đầu phiên mới khi đã có artifact đúng protocol;
   tiếp tục nghiệm thu luồng chuẩn, không phát hành mode thử nghiệm làm xác minh thật.

## Quyết định, lưu ý, bẫy
- Các ngưỡng là lựa chọn thủ công chưa có số liệu; không tuyên bố FAR/FRR/accuracy.
- API review dù demo_complete=true là chủ ý giữ client cũ không hiểu nhầm auth
  pass; label Android phản ánh kết quả trình diễn. Không tạo ngân hàng/tài khoản thật.
- Helper local configure_manual_face_demo.py --check/--apply/--restore kiểm/cập
  nhật nguyên tử .env, backup chỉ trường cấu hình không bí mật. Không in/lưu
  secret mới, không xóa DB/khóa; runtime helper ở tmp không commit.
- Bằng chứng private: `D:\vericlue\tmp\full-demo-setup\manual-*`.
- Không push/PR, không hẹn tắt máy (người dùng đã hủy yêu cầu đó).

## Câu hỏi cho nhóm
- Nhóm chốt nguồn dữ liệu có quyền dùng/nhãn/split theo người và đánh giá độc lập;
  artifact thật/SEC-09/ghi danh vẫn là công việc còn lại để hoàn tất luồng chuẩn.

## Test đã chạy
```
TDD: manual cutoff/adapters/settings/closure, manual response không thể pass,
Android marker/session và cleanup camera đều có RED→GREEN; standard response
regression được bắt bởi test_dynamic_flows rồi sửa serialize giữ dạng cũ.
Android testDebugUnitTest assembleDebug:198 tests/0failure/error/skip, build OK.
Paparazzi manual screens:8 ảnh sáng/tối/chữ200%, record OK; đã xem notice/kết quả.
Web gen:api và typecheck OK. Ruff toàn repo sạch; OpenAPI --check khớp.
Review không còn P1/P2 sau khi bắt buộc mvp và đóng camera ở route mới.
Lượt full Python đầu bắt lỗi tương thích response; đã sửa và focused GREEN.
Lượt tiếp theo dừng ở test CLI token60s hết hạn khi máy bận/tạm dừng; chạy lại
riêng3case qua. Đã cố định clock TRONG TEST kiểm context/status, không đổi
verifier hoặc expiry production. Full lượt cuối đang được chờ trước commit.
```
