# Bàn giao · IOS-07 · Lý Anh Quân+Codex · 2026-10-28 23:05

**Nhánh:** feat/IOS-07-release-handoff
**Trạng thái task sau phiên này:** doing — code đóng gói, chờ domain/iPhone

## Đã xong
- Guard URL Release ở build phase; plist Release riêng không ngoại lệ ATS/LAN.
- Scheme VeriClue-Release không attach debugger; README/checklist và override local.
- Policy URL runtime và test cấu hình mới; giữ Debug IP/cổng local của sếp.
- Release build không ký exit 0, artifact check đạt với https://build-check.invalid/
  chỉ để compile. Debug build-for-testing exit 0, chưa chạy test.
- Build với placeholder mặc định bị chặn exit 65 đúng guard.

## Đang dở
- Domain HTTPS thật, cài Release/số đo iPhone, test bản mới và review/PR.
- Sếp mở rộng yêu cầu toàn app; phần đó theo bàn giao IOS-02 23:16 và bảng parity,
  không tự biến các phần SEC-02 thành tiêu chí đã xong của IOS-07.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Xin URL HTTPS được duyệt, không tự công khai backend hoặc bỏ kiểm TLS.
2. Chạy test khi sếp yêu cầu, rồi nghiệm thu checklist IOS-07 trên iPhone.

## Quyết định, lưu ý, bẫy
- 159/159 trước đây không chứng minh code mới. Android nguồn 54acaad cũng chưa
  có nghiệm thu đầy đủ Release HTTPS thật; không bịa số đo hoặc dùng .invalid.

## Câu hỏi cho nhóm
- Domain HTTPS/backend demo dùng chung? Sếp hỏi domain là gì, chưa cung cấp URL.

## Test đã chạy
Chưa chạy test. Build và kiểm artifact:
- /tmp/vericlue-ios07-release.log: Release unsigned build exit 0.
- /tmp/vericlue-ios07-debug.log: build-for-testing Debug exit 0.
- /tmp/vericlue-ios07-release-unconfigured.log: exit 65, guard placeholder hoạt động.
- check_ios_release.py --app .../Release-iphoneos/VeriClue.app: đạt checks tĩnh,
  không phải DNS/TLS/API hay iPhone acceptance. Source sau đó thêm nền Security,
  hai build mới exit 0 được ghi trong bàn giao IOS-02 23:16.
