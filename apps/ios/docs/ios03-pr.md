# Bản nháp PR — IOS-03

**Tiêu đề:** `feat(ios): add live OTP and ID card capture [IOS-03]`

## Task

IOS-03 — `docs/plan/epics/E9-app-flows.md`.
Nhánh: `feat/IOS-03-otp-id-card`, base `2e043e2`.

## Đã làm gì

- Nối phone/OTP vào API: tạo session trước OTP, khóa request đồng thời, deadline resend 45s, attempts và các lỗi OTP.
- Camera sau, crop 1.586:1, kiểm ảnh rỗng/nét/lóa, đọc QR bằng Vision; fallback Core Image chỉ trên Simulator khi Vision Code 9.
- Gửi hai JPEG/QR, retry về mặt sau và giữ mặt trước; sửa tên/ngày, khóa số CCCD, confirm đúng JSON ISO; giữ draft khi lỗi mạng.
- Luồng API dừng sau giai đoạn A, không mượn success demo; tách preview gallery khỏi API thật.
- Test hồi quy cho đổi số trong cooldown rồi lỗi mạng; tài liệu nghiệm thu/bàn giao và task card cập nhật.

## Cách kiểm tra

Xem kết quả mới nhất trong [bàn giao](../../../docs/status/handoffs/2026-10-25-1004-ios-03-l-anh-qu-n-codex.md).

- Nghiệm thu thủ công: Lý Anh Quân xác nhận iPhone 14 Pro/iOS 18.7.8, API mock `192.168.1.11:8000`, kịch bản genuine.
- Codex kiểm DB/file: đủ hai JPEG 1200×758, ghi nhận `full_name`/`date_of_birth` thay đổi.
- Test hoàn toàn mock bằng MockURLProtocol; không dùng CCCD/QR thật trong fixture.
- Bản cuối sau review: `xcodebuild test` exit 0, **54/54 test cases passed, 0 failed, 0 skipped** trên iPhone 17 Pro Simulator/iOS 26.3.1; artifact `/tmp/vericlue-ios03-final-review-20261025.xcresult`.
- `uv run python scripts/plan_check.py`: 0 lỗi, 10 cảnh báo tải/đường găng toàn dự án.
- Pre-commit hooks và `git diff --check`: sạch; không có SwiftLint riêng trong repo.

## Checklist (Definition of Done)

- [x] Đạt tiêu chí task card theo nghiệm thu thủ công do sếp xác nhận và bằng chứng DB/file.
- [x] Bản sửa cuối test xanh 54/54; hook lint/kiểm tra file passed hoặc skip đúng loại file.
- [x] Khớp hợp đồng; không sửa `packages/contracts/`.
- [x] Diff dự kiến không có dữ liệu thật, ảnh/video/audio, `.env`, token hoặc khóa bí mật; kiểm lại staged diff trước commit.
- [x] Không chép code bên thứ ba cần thêm attribution.
- [x] Tài liệu, task card, backlog (`review`) và bàn giao đã cập nhật.
- [x] `plan_check.py` không báo lỗi.

## Ghi chú cho người review

- Backend chỉ lưu tên trường thay đổi trong `id_edited`, không ghi đè snapshot QR bằng giá trị sửa; không giải quyết backend ngoài IOS-03.
- Ngưỡng sharpness/glare theo Android là ngưỡng khởi đầu, không phải số đo calibration iPhone.
- Chưa có commit IOS-03, chưa push/mở/merge PR. Không tạo artifact từ CCCD cá nhân thật. Simulator xcresult nằm trong `/tmp`, không commit.
- Debug IP đổi từ `.5` sang `.11` là cấu hình local do sếp sửa từ trước.

## Lệnh để sếp tự thực hiện sau khi duyệt

Chạy ở thư mục gốc repo; chỉ stage các file đúng phạm vi:

```bash
git add apps/ios/Config/Debug.xcconfig \
  apps/ios/VeriClue/Capture \
  apps/ios/VeriClue/Flow/DemoFlow.swift \
  apps/ios/VeriClue/Flow/IdentityFlow.swift \
  apps/ios/VeriClue/UI/AppNavigation.swift \
  apps/ios/VeriClue/UI/Screens/RouteScreen.swift \
  apps/ios/VeriClue/UI/Screens/LiveIdentityScreens.swift \
  apps/ios/VeriClueTests/IDCardTests.swift \
  apps/ios/VeriClueTests/IdentityFlowTests.swift \
  apps/ios/docs/plan-ios.md \
  apps/ios/docs/ios03-device-checklist.md \
  apps/ios/docs/ios03-pr.md \
  docs/plan/epics/E9-app-flows.md docs/plan/backlog.md \
  docs/status/handoffs/2026-10-25-1004-ios-03-l-anh-qu-n-codex.md

git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "feat(ios): add live OTP and ID card capture [IOS-03]"
git push -u upstream feat/IOS-03-otp-id-card
```

Không push vào `main`, không dùng `git add -f tmp/`. Nếu hook sửa file khi commit,
review rồi stage lại đúng file đó và commit lại; không bỏ hook.
