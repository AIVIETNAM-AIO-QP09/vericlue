# Bàn giao · IOS-02 · Lý Anh Quân+Codex · 2026-10-25 09:19

**Nhánh:** `feat/IOS-02-api-flow` (từ IOS-01 tại `4af9109`)
**Trạng thái task sau phiên này:** `doing` — sếp đã chốt phần kỹ thuật và phương án timeout; chờ commit/push, PR/review/merge.

## Đã xong

- Thêm Codable models cho session/challenge/dynamic, OTP, CCCD, signals/ack, finalize, voice và lỗi; snake_case dùng codec chung.
- Thêm 10 endpoint async `Result` qua URLSession; multipart binary, Bearer, mock header chỉ Debug, mã HTTP và 409 được giữ để xử lý đúng ngữ cảnh.
- Thêm LiveFlow: token rotation cùng challenge/hạn; giữ payload khi mất mạng; bỏ qua đúng các bước đã acknowledgment; finalize retry thay challenge và xóa dữ liệu lượt cũ.
- Receipt 200 phải đúng step + received true; chỉ `step_already_received` của media/signals được coi như receipt. Finalize/voice conflict không bao giờ được coi là thành công.
- Trạng thái lạ, JSON thiếu trường bắt buộc, thiếu challenge retry hoặc prompt/voice ID cần thiết đều trả lỗi.
- Port các nhóm LiveFlow/Retry/StageA/FlowRules; thêm MockURLProtocol cô lập từng host `.invalid`, test HTTP/multipart/nonce/token/offset, decode + round-trip toàn bộ 18 ví dụ và đối chiếu trường required của schema.
- Giữ nguyên toàn bộ `packages/contracts/`; 19 fixture JSON là bản sao nguyên byte từ schema/ví dụ trong repo.
- Thêm `apps/ios/docs/api-client.md` với cách dùng, phạm vi và giới hạn timeout.

## Đang dở

<!-- file:dòng, việc gì còn dang dở -->
- Chưa nối LiveFlow vào UI hoặc camera/micro; thuộc IOS-03..06. Demo IOS-01 giữ nguyên.
- Chưa commit/push/mở PR. Thay đổi IP `Config/Debug.xcconfig` có trước phiên, thuộc sếp; không đưa vào commit IOS-02 mặc định.
- Chưa ngắt mạng vật lý của Mac để chạy lại test; tính độc lập mạng được kiểm bằng URLProtocol nhận mọi request, fixture bundle và host `.invalid`, không dùng server thật.

## Bước tiếp theo

<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Sếp tự commit/push nhánh `feat/IOS-02-api-flow`; không stage thay đổi IP có trước trong `Config/Debug.xcconfig`.
2. Mở PR theo mẫu của repo. Chuyển `review` sau khi PR tồn tại, `done` sau merge.
3. IOS-03 nối OTP/CCCD UI với LiveFlow; IOS-04/05 cung cấp media thật. Không đưa kết quả demo vào luồng live.

## Quyết định, lưu ý, bẫy

- Contract hiện yêu cầu `ColorStep.transition_ms`; comment/default trong Android đã lỗi thời. Swift bắt buộc decode trường này; không làm theo optional/default cũ để che phản hồi thiếu.
- Lần test đầu bắt lỗi model optional này và hai assertion test ghi cứng nhầm session ID. Đã sửa model theo schema và test lấy ID từ response; không bỏ assertion.
- URLSession không có ba timeout connect/read/write độc lập: dùng idle request 15s và resource tổng 60s. Đây là phương án có giới hạn khác connect 15s + read/write 60s của OkHttp, đã ghi rõ trong tài liệu.
- Sếp đã yêu cầu chốt IOS-02 sau khi được báo giới hạn timeout; ghi nhận chấp nhận phương án trên cho phạm vi demo. Không coi đây là thay đổi timeout của Android hay thay đổi contract.
- Payload ảnh/video/signals/voice được giữ cho retry mạng; không gọi drop/reset khi chỉ muốn gửi lại phần chưa nhận. Mỗi LiveFlow chặn submit đồng thời bằng cờ busy.
- Không sửa `docs/status/STATUS.md`, ADR, thresholds hoặc hợp đồng.

## Câu hỏi cho nhóm

<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Không còn câu hỏi chặn chốt kỹ thuật IOS-02. Việc đo thời gian upload trên iPhone thật thực hiện khi tích hợp media.

## Test đã chạy

<!-- lệnh + kết quả thật -->
```
xcodebuild -project apps/ios/VeriClue.xcodeproj \
  -scheme VeriClue \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -parallel-testing-enabled NO \
  -derivedDataPath /tmp/vericlue-ios02 \
  test

Lần đầu: TEST FAILED, 3 test lỗi (assertion ID x2, transition_ms required x1).
Lần cuối sau sửa: TEST SUCCEEDED (exit code 0).
- Swift Testing: 40 test trong 6 suite đều đạt, gồm các bảng tham số và ma trận lỗi mạng.
- XCTest UI/launch: 4 lượt chạy đều đạt (gallery, ngân hàng, Light/Dark).
- Kết quả: /tmp/vericlue-ios02/Logs/Test/Test-VeriClue-2026.10.25_09-25-04-+0700.xcresult
- Tất cả request test API do MockURLProtocol xử lý; lỗi mạng -1005/-1008 trong log là do mock chủ động trả về.
- Fixture so bằng cmp với packages/contracts: nguyên byte; không sửa contracts.
- git diff --check: đạt.
- uv run python scripts/plan_check.py: exit 0, 0 lỗi và 10 cảnh báo kế hoạch chung.
```
