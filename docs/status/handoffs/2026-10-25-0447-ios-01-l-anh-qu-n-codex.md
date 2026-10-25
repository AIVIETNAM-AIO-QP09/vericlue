# Bàn giao · IOS-01 · Lý Anh Quân+Codex · 2026-10-25 04:47

**Nhánh:** `feat/IOS-01-swiftui-scaffold`
**Trạng thái task sau phiên này:** `doing` — phần kỹ thuật đã đạt, chờ commit phần test/bàn giao, mở PR và merge.

## Đã xong
- Tạo theme sáng/tối theo Android, đóng gói đủ Be Vietnam Pro Regular/Medium/Semibold/Bold và kiểm tra font được đăng ký thật.
- Port component SwiftUI và toàn bộ màn IOS-01; đủ 47 route, gồm `deny` và `recovery_required`.
- Thêm `NavigationStack`, chống push trùng route trên đỉnh, Back hệ thống và `toBank()`.
- Thêm demo flow cho `onboarding`, `reauth`, `recovery`; Debug Gallery mở độc lập từng màn và bị loại khỏi Release bằng `#if DEBUG`.
- Sửa race condition khiến timer tự động gọi điều hướng lần hai sau khi bấm `Chụp ngay (debug)`, `Bỏ qua (debug)` hoặc `Dừng`.
- Sếp đã đi thủ công ba demo flow trên Simulator và xác nhận phần còn lại đạt.
- Unit/UI test kiểm tra route, ba purpose, font, tương phản, chữ cấm, màn ngân hàng, Debug Gallery và launch Light/Dark.
- Snapshot `IOS-01 Debug Gallery` và `IOS-01 Launch` được lưu trong kết quả XCTest.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Chưa mở PR và chưa merge; chỉ chuyển backlog sang `review` sau khi PR đã được mở.
- Release vẫn có `NSAllowsLocalNetworking`; kế hoạch giao việc loại bỏ ở IOS-07, không thuộc tiêu chí IOS-01.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Commit phần ổn định UI test, task card/backlog và bàn giao này.
2. Push `feat/IOS-01-swiftui-scaffold`, mở PR theo `.github/PULL_REQUEST_TEMPLATE.md` và chuyển IOS-01 từ `doing` sang `review`.
3. Sau khi PR được duyệt và merge, chuyển IOS-01 sang `done`; không sửa `docs/status/STATUS.md`.

## Quyết định, lưu ý, bẫy
- IOS-01 chỉ là demo UI, chưa gọi server và chưa dùng camera/micro thật; các phần đó thuộc IOS-02..05.
- Gallery chỉ có ở Debug. Launch test chỉ kiểm tra/chụp màn khởi đầu Light/Dark; test `testDebugGalleryOpens` chịu trách nhiệm kiểm tra điều hướng gallery để tránh lặp thao tác gây flaky.
- Không dùng nút Debug và timer tự động gọi trực tiếp cùng callback nếu chưa có cờ one-shot; nếu không route có thể bị push lại sau khi đã sang màn kết quả.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Không có.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
xcodebuild -project apps/ios/VeriClue.xcodeproj \
  -scheme VeriClue \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -parallel-testing-enabled NO \
  -derivedDataPath /tmp/vericlue-ios-final-test \
  test

Kết quả cuối: TEST SUCCEEDED.
- Swift Testing: 7/7 đạt.
- XCTest UI/launch: 4/4 đạt, gồm launch Light và Dark.
- xcresult: /tmp/vericlue-ios-final-test/Logs/Test/Test-VeriClue-2026.10.25_08-21-34-+0700.xcresult
```
