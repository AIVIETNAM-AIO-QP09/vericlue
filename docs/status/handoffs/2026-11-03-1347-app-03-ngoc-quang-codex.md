# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-03 13:47

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** doing

## Đã xong
- Người dùng đổi quyết định: chốt GenD 0.95 và cho phép xóa riêng tài khoản
  demo hiện tại để đăng ký lại. Quyết định này thay lựa chọn chờ hết hạn trong
  bàn giao 13:00; không phải cho phép xóa mọi tài khoản hoặc media.
- Đã dùng `AccountStore.destroy_manual_demo_account(account_id=...)` của
  API bất biến `11dfc7e`, đúng một account có expiry đã đối chiếu trước đó.
  Account DEK/payload và chỉ mục CCCD/điện thoại bị hủy theo cơ chế có sẵn;
  giữ tombstone, thêm một access audit. Không chỉnh review_events. Transaction
  kiểm tra các bảng khác giữ nguyên trước commit. Không sao lưu payload đã xóa.
- Chỉ đổi cấu hình riêng `MANUAL_DEMO_GEND_MAX` từ 0.90 lên 0.95; PAD 0.50,
  spoof 0.50, lipsync 0.50, match/consistency 0.30 giữ nguyên. **Không bật**
  `phone-demo-fixed-v1` (preset đó đổi thêm các ngưỡng khác).
- Policy mới `f253400f0f038ab737959a8a7859d257920bb031a9366f096604dab0beedd317`.
  So sánh Settings xác nhận đúng một trường đổi; API/APK/model không đổi.
  Backup chỉ profile/build-info trước activation, giữ riêng ngoài repo.
- APK vẫn `1f0fc60`, đã cài 13:29. Không uninstall/clear app data hoặc mở
  camera tự động. ADB reverse 8421 đã làm mới.

## Đang dở
- Server đã nạp xong mô hình, launcher xác nhận ready và phiên tổng hợp ký
  HMAC khớp policy mới. Nghiệm thu đăng ký/đăng nhập/khôi phục ở policy mới
  chưa thực hiện, không dùng kết quả policy cũ thay thế.

## Bước tiếp theo
1. Người dùng về màn đầu và chọn Đăng ký mới cùng CCCD, đồng ý lưu mẫu lại;
   không tiếp tục phiên cũ hoặc dùng tài khoản đã hủy.
2. Sau khi đăng ký đạt, thử đăng nhập lại rồi khôi phục; ghi kết quả từng lượt.

## Quyết định, lưu ý, bẫy
- Đây là ngưỡng demo do người dùng chọn sau quan sát lượt điện thoại,
  không phải ngưỡng hiệu chỉnh hoặc số đánh giá độc lập. Điểm GenD thô không
  là xác suất đã hiệu chỉnh. Giữ `error/degraded` và chốt khác không thành pass.
- Việc xóa tài khoản và thay ngưỡng là hai thao tác riêng. Biên nhận activation
  nói DB không đổi chỉ áp dụng cho bước đổi profile sau khi reset đã commit.
- Các helper/biên nhận riêng ở scratch phiên và bundle diagnostics
  `gend-demo095-20261103`; không commit cấu hình riêng hoặc dữ liệu người dùng.

## Câu hỏi cho nhóm
- Dữ liệu hiệu chỉnh/đánh giá tách theo người và nghiệm thu thật vẫn còn.

## Test đã chạy
- Pytest ca `test_manual_full_demo_requires_lipsync_in_recovery_and_protects_existing_accounts`
  với PYTHONPATH của API/ML bất biến đang chạy: **1 passed**, một warning
  Starlette/httpx có sẵn. Ca bao gồm reset account demo có phạm vi.
- Reset thực: đúng một account; CCCD được giải phóng, bảng không liên quan
  giữ nguyên, audit append-only. Activation: source/APK/DB/media giữ nguyên;
  candidate hash/settings và binding manifest khớp.
- CI HEAD `219968478e7127ce0cf223a34133270fe0a2529e`: **10/10 SUCCESS**.
  Đây là CI trước commit tài liệu bàn giao này, không tuyên bố CI HEAD sau.
- Kiểm DB chỉ đọc sau reset: 0 account chưa hủy, 0 chỉ mục CCCD còn giữ.
  `plan_check`: 0 lỗi, 10 cảnh báo có sẵn. Start exit 0, preload thành công.
