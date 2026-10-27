# API client và luật luồng — IOS-02

## Phạm vi

`Data/Models.swift` dùng Codable và codec `SessionJSON` để giữ tên JSON snake_case.
`Data/SessionApi.swift` cung cấp 10 endpoint phiên. `Flow/LiveFlow.swift` giữ trạng
thái một phiên; `Flow/FlowRules.swift` quyết định route/câu nhắc từ kết quả server.
Chưa nối vào màn live hoặc camera/micro: các bước này thuộc IOS-03..06. Demo IOS-01
vẫn chạy độc lập.

## Cách dùng

Khởi tạo `SessionApi(baseURL:)` bằng URL máy chủ đã cấu hình, rồi
`LiveFlow(api:)` trên main actor. Các API trả `Result<Value, ApiError>`, không trả
chuỗi lỗi server trực tiếp cho người dân.

1. `sendOtp(phone:purpose:scenario:)` tạo phiên nếu cần và giữ SMS mô phỏng.
2. `verifyOtp(code:)` trả `pass`, `wrong(attemptsLeft)` hoặc `fail`.
3. `sendIdCard(front:back:qr:)` giữ fields trả về; `confirmIdCard(fields:)` chỉ
   chấp nhận khi server xác nhận `received: true`.
4. `prepareFace()` tạo phiên nếu chưa có; nếu đã có phiên thì gọi `/challenge`
   và thay đồng thời token, hạn và challenge. Sau finalize retry, dùng ngay
   challenge trong response, không gọi refresh thừa.
5. Gán `frontalJpeg`, `colorEvents`, rồi gọi `submitFace(video:frameTimes:clientQuality:)`.
   Truyền video dạng `Data`; bộ thu thật sẽ cung cấp dữ liệu ở IOS-04.
6. Khi kết quả yêu cầu đọc câu, dùng `voicePrompt`, `voiceChallengeId` và gọi
   `submitVoice(wav:video:audioOffsetMs:)`.

Media/signals nhận HTTP 200 phải có đúng `step` và `received: true`. Chỉ 409
`step_already_received` ở hai bước này mới thay thế acknowledgment; không áp dụng
cho finalize hoặc voice. Mọi mã 409 khác giữ nguyên error code để caller xử lý.
OTP có ngoại lệ riêng theo contract: `otp_already_verified` nghĩa là đã qua OTP.

Lỗi mạng không tự retry. Gọi lại submit sẽ chỉ gửi phần chưa được xác nhận;
payload video/signals/voice của lần gửi lỗi được giữ tới khi server nhận.
`retry` từ finalize phải kèm challenge mới; trạng thái lạ, JSON thiếu trường,
receipt sai hoặc thiếu prompt/voice ID bắt buộc đều trả lỗi.

`reset()` xóa phiên; `dropFaceAttempt()` giữ OTP/CCCD nhưng xóa dữ liệu lượt mặt,
giọng, offset và acknowledgment. Không gọi drop khi chỉ retry mạng vì sẽ mất
thông tin bước đã nhận.

IOS-06: `abandonFaceAttempt()` dành cho gián đoạn/Back/rời luồng, hủy request đang
chờ, loại phản hồi trễ bằng operation UUID, xóa payload/ack và buộc `/challenge`
trước upload mới. `reset()` cũng hủy request; defer của request cũ không được
mở khóa operation mới. `cancelPendingRequests()` phục vụ Back giai đoạn OTP/CCCD,
không tự xóa bản sửa. Retry mạng thông thường không gọi các hàm abandon/reset.

Không thể biết chắc server đã xử lý finalize/voice nếu mất response. Nếu gửi lại
nhận 409, app báo lỗi theo contract; không tự coi 409 là pass. Không đổi backend
hoặc giả lập idempotency mới trong IOS-06.

## Timeout

URLSession không cung cấp ba timeout connect/read/write riêng như OkHttp.
Client đặt `timeoutIntervalForRequest = 15` (thời gian không có dữ liệu),
`timeoutIntervalForResource = 60` (tổng thời gian request) và không chờ kết nối
vô hạn. Đây không tương đương hoàn toàn với connect 15s + read/write 60s: một
request im lặng 15s có thể timeout trước 60s. Không dùng API riêng của hệ thống
để giả lập một bảo đảm URLSession không cung cấp.

Phương án này đã được sếp chấp nhận khi chốt IOS-02 cho bản demo. Thời gian
upload thực tế sẽ được đo khi tích hợp media trên iPhone thật.

## Kiểm thử cục bộ

```bash
xcodebuild \
  -project apps/ios/VeriClue.xcodeproj \
  -scheme VeriClue \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -parallel-testing-enabled NO \
  test
```

Mọi test API tạo session ephemeral riêng với `MockURLProtocol`, host `.invalid`
riêng cho mỗi test. Protocol nhận mọi request; URL/kịch bản không đăng ký trả lỗi
ngay trong mock, không đi xuống DNS hoặc socket. Không gọi `URLSession.shared`.
Các test không cần server, token thật, mạng Internet hay thư viện ngoài.

`VeriClueTests/Fixtures/` chứa bản sao nguyên byte của 18 ví dụ `session.*.json`
và JSON Schema từ `packages/contracts/`. Chúng được đóng gói vào test bundle.
Khi hợp đồng thay đổi ở task được phép, copy lại fixture, không chỉnh fixture
để bỏ qua lỗi decode. ContractTests kiểm đủ danh sách ví dụ, round-trip, tên
trường, và việc bỏ từng trường bắt buộc phải làm decode thất bại.

Các nhóm test bao phủ luồng cơ bản, retry media/signals/finalize/voice, token
rotation, OTP/CCCD, mã HTTP/409, multipart binary/offset, trạng thái lạ, thiếu
trường, luật điều hướng, ngày/thông tin sửa và chữ cấm.
