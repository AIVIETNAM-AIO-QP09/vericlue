# Bàn giao · SEC-09 · Ngoc Quang+Codex · 2026-10-30 15:20

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Đối chiếu SEC-09, AccountStore, privacy contract và Android: quyền lưu mẫu riêng chưa có; guard chặn ghi danh từ phiên mock/mixed vẫn áp dụng kể cả sau khi thêm consent.
- Viết thiết kế `docs/superpowers/specs/2026-10-30-demo-recording-completion-design.md` để review trước đổi hợp đồng.
- Viết `docs/runbooks/android-recording-rehearsal.md`: kết nối USB, APK, kịch bản quay mô phỏng và tích hợp AI có nhãn/phạm vi rõ.
- Khởi động server hiện có, health `ok`, `failed_modules=[]`; OTP vẫn synthetic. Không đổi khóa, DB, profile hay guard.
- Kiểm SHA256 APK khớp metadata; Android trong APK vẫn commit 94be648, backend tại lúc kiểm a1427ac.

## Đang dở
- Chưa triển khai schema/API/client SEC-09 theo thiết kế mới. Cần review thiết kế và kế hoạch theo skill brainstorming.
- Chưa có dữ liệu/artifact thật đúng protocol, chưa nghiệm thu AI toàn luồng; chưa có thiết bị ADB online. Không báo demo thật đã xong.

## Bước tiếp theo
1. Người dùng review thiết kế; sau duyệt lập kế hoạch triển khai SEC-09 contract-first, rồi test server/client và ảnh màn đồng ý.
2. Khi chuẩn bị dữ liệu đúng protocol, đo/fit/đánh giá độc lập theo runbook calibration; không dùng dữ liệu tổng hợp để hợp thức hóa kết quả thật.
3. Người dùng nối điện thoại và tập quay theo runbook; bản mô phỏng tài khoản hiện chỉ là màn giao diện, chưa có quản lý tài khoản bền.

## Quyết định, lưu ý, bẫy
- Không tự đổi OTP sang thật hoặc mở guard mock/mixed để tạo account. Thêm quyền lưu mẫu không giải quyết các điều kiện biometric còn thiếu.
- Tách hai đoạn quay và ghi chú chế độ rõ, không ghép lỗi API sang pass mô phỏng khiến người xem hiểu là AI đạt.
- Server đang chạy từ runtime `D:/vericlue/tmp/full-demo-setup/server`; dùng launcher VeriClue.cmd để xem trạng thái/dừng, không chạy server thứ hai.
- Không thay đổi code sản phẩm trong phiên chuẩn bị này. Giữ local, không push/PR.

## Câu hỏi cho nhóm
- Cần dữ liệu/lịch/nhãn/nhóm người đúng protocol để hoàn tất hiệu chỉnh; chưa tìm thấy trong các nguồn đã kiểm.
- Thiết kế SEC-09 đang chờ review, không suy diễn yêu cầu quay video thành cho phép nới chốt ghi danh.

## Test đã chạy
- `VeriClue.cmd start`: server sẵn sàng cổng 8421.
- `GET /healthz`: status ok, mock_models true, failed_modules rỗng. Health không chứng minh độ chính xác model.
- `smoke_privacy_api.py`: exit 0, trước consent OTP 409, grant 200, OTP demo 200, withdraw 200/files_deleted, sau withdraw 410. Fixture tổng hợp, không media người thật. processing_cleanup vẫn not_verified; account_data_erased=false.
- `adb devices -l`: không có thiết bị; không cài APK hoặc thử camera/micro.
- SHA256 APK: 17100bd4a076a326e734c37f9cf58ac1920bd0aa12230edc1c4deaf45b2613ec.
- `git diff --check`: qua. Không chạy lại suite sản phẩm vì phiên này chỉ thêm tài liệu; suite 533 test của code backend đã có ở bàn giao FLOW-04 trước.
