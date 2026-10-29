# IOS-04 — nghiệm thu phần mặt thật, Cổng 5

Code 5.5–5.10 và đường gửi/nhận 5.11 đã được triển khai. Sếp đã gửi số đo timeline
genuine và xác nhận các mục JPEG/MP4 đúng chiều/không mirror/liên tục, tới câu đọc,
low_quality, gián đoạn và mất kết nối đều đạt trong chat. Đây là nghiệm thu người
dùng, không phải Codex tự chạy iPhone. Bản cuối sau sửa stop() đạt **78/78 unit
và 4/4 lượt UI test**, artifact `/tmp/vericlue-ios04-final-20261025-04.xcresult`.
Task chuyển `review`, chưa merge nên không ghi `done`.

## Số đo genuine đã nhận

Ngày 25/10/2026, phiên `ses_339f14675babe6e8`, theo output app/SQLite sếp cung cấp:

- 8 color_events, 585 frame_times, 282 region_means; app báo 30 FPS.
- JPEG 226.288 byte theo app; DB có đường dẫn face_image.jpg và face_video.mp4.
- AE/AWB khóa và trả tự động đều 1.
- MP4 19.501,667ms so với lịch 19.460ms, chênh khoảng 41,667ms.
- Sếp xác nhận phát file đúng chiều/chữ xuôi/liên tục, tới câu đọc;
  low_quality/gián đoạn/mất kết nối đạt. Chưa có log chi tiết số lượt/challenge ID
  cho low_quality hoặc giá trị RGB từng vùng để ghi như số đo độc lập.

## Chuẩn bị

1. Chạy API mock như IOS-03, đúng `API_BASE_URL`/IP trong Debug. Không đổi
   `SESSION_SIGNING_SECRET` trong lúc thử một phiên. Không cần Docker nếu dùng SQLite.
2. Xcode chọn iPhone thật, Debug, **⌘R**. Máy đã nghiệm thu trước: iPhone 14 Pro,
   iOS 18.7.8 theo sếp; ghi lại nếu lần này đổi máy/hệ điều hành.
3. Ngân hàng → **Xem tất cả màn** → chọn **API thật**, scenario **genuine**.
   Back về ngân hàng, mở luồng bình thường. Không mở từng màn từ gallery vì
   thao tác đó bật preview/demo và không phải phép thử API thật.
4. Đi OTP/CCCD đến chuẩn bị quay mặt. Nút checkpoint **5.1–5.4** trong gallery
   vẫn chỉ là kiểm camera riêng, không chạy timeline/gọi API của Cổng 5.

## Lượt genuine

- [ ] Bấm **Tôi đã sẵn sàng**, kiểm một hint chất lượng tại một thời điểm.
  Giữ đạt liên tục một giây thì tự ghi; không có nút bỏ qua quality cho phiên thật.
- [ ] Nền xám trước; JPEG chính diện được lấy gần `frontal_capture_at_ms`,
  trong baseline. Ảnh có dữ liệu, dọc, không mirror.
- [ ] Tám màu theo challenge; chuyển trong `transition_ms`, giữ trong `hold_ms`.
  Độ sáng màn hình lên tối đa, trả về mức cũ sau khi ghi xong hoặc hủy.
- [ ] Preview nằm nguyên góc phải suốt baseline/màu/chấm/quay đầu. Không thêm
  camera session/output/layer giữa các pha.
- [ ] Chấm đi thẳng, đều, theo tọa độ server trên vùng màn hình trừ safe area;
  không lật tọa độ theo preview. Không có animation nội suy riêng của SwiftUI.
- [ ] Quay theo đúng thứ tự server; trái/phải theo người dùng. Thanh yaw chỉ là
  hướng dẫn (trái âm/phải dương theo phép thử trước), không kết thúc pha sớm.
- [ ] Hết lịch mới hoàn tất MP4, chờ finish/inspector rồi gửi media → signals
  → finalize. Không gửi file đang ghi, không tự ra success từ timer.
- [x] Finalize `voice_challenge` đưa tới câu đọc **từ server**. Bản Debug có
  số frame/màu/mẫu vùng, dung lượng JPEG và kết quả AE/AWB đã khóa hay chưa.
  Thu âm/WAV/video giọng là **IOS-05**, chưa có nút giả gửi giọng hoặc giả thành công.
- [x] Mở MP4 server nhận bằng QuickTime: một track H.264 dọc, không audio,
  hình đúng chiều/chữ xuôi, liên tục từ đầu đến cuối, thời lượng theo lịch server.
  File có thể dài hơn mốc kết thúc tối đa khoảng vài frame do biên camera/khung cuối;
  app chặn sai khác lastPTS−t0 lớn hơn 100ms. Không dùng “khoảng 19 giây” như giá trị cố định.

Với SQLite, chạy ở gốc repo sau `genuine`, trước khi bắt đầu phiên mới:

```bash
sqlite3 tmp/dev.db "SELECT session_id, status,
 json_array_length(payload, '$.images'),
 json_extract(payload, '$.video'),
 json_array_length(payload, '$.signals.color_events'),
 json_array_length(payload, '$.signals.frame_times'),
 json_array_length(payload, '$.signals.region_means'),
 json_extract(payload, '$.signals.client_quality.ae_awb_locked'),
 json_extract(payload, '$.signals.client_quality.ae_awb_restored'),
 json_extract(payload, '$.signals.client_quality.video_duration_ms'),
 json_extract(payload, '$.signals.client_quality.scheduled_duration_ms')
 FROM sessions ORDER BY created_at DESC LIMIT 1;"
```

Kỳ vọng: một ảnh chính diện trong `images`, `video` có đường dẫn MP4 tồn tại,
8 color events, frame_times và region_means không rỗng. Kiểm JSON các vùng có
forehead/left_cheek/right_cheek/nose/chin/background và thống kê RGB/pixels thật.
Background chồng mặt bị loại; vùng không lấy được báo null/0, không bịa RGB.
App chỉ gửi khi có ít nhất một mẫu đo đủ sáu vùng.

Ghi lại trong bàn giao: codec/kích thước/thời lượng/bytes/fps, số sự kiện màu,
số frame/mẫu vùng, `ae_awb_locked`, `ae_awb_restored`, thời điểm khóa/mở và
`first_pts_seconds`, `first_receipt_host_seconds`, `pts_to_host_offset_ms`.
Đây là chẩn đoán, không phải kết luận xác minh của client. Không in token hoặc
toàn bộ payload DB vào chat/log/commit. Media server vẫn ở thư mục local ignore,
không thêm vào Git và xóa thủ công khi hết nhu cầu nghiệm thu.

## Lượt low_quality và token

1. Về ngân hàng, vào gallery chọn **low_quality**, rồi bắt đầu **phiên mới**.
   Header scenario chỉ được gửi lúc tạo phiên, đổi picker không đổi phiên đang có.
2. Quay đủ lịch. Màn **Chụp lại** phải có hint từ `retry_hint`, số lượt từ
   `attempts_left`, không gán mặc định thành công cho lượt sau.
3. Debug hiện **Lượt vừa gửi** và **Lượt tiếp theo**: hai challenge ID phải khác.
   Bấm quay lại chuẩn bị → ghi lại theo gói mới. Không tái dùng JPEG/MP4/signals cũ.
4. Contract hiện hành: `POST /challenge` trả token mới và app thay token cũ;
   `finalize: retry` chỉ trả challenge mới, **không có token mới**. Vì vậy dùng
   challenge retry trực tiếp với token hiện tại, không refresh thừa rồi bỏ gói
   server vừa cấp. Sau gián đoạn/khởi động lại phần mặt, `/challenge` mới xoay token.
5. Backend xóa `signals`/accepted_steps của lượt cũ khi finalize retry, nên query
   DB ngay sau low_quality có thể thấy signals rỗng — không tự kết luận upload
   thất bại từ đó. Dùng phản hồi/hint/challenge mới và thông tin request để đối chiếu.

## Mất mạng, gián đoạn, reauth

- [x] Tắt mạng khi gửi: lỗi tại màn phần mặt, **Thử lại** chỉ gửi phần chưa ack.
  Bật mạng rồi thử lại đi theo phản hồi server, không tự success. Chỉ
  `step_already_received` được coi là ack; 409 lạ không được bỏ qua.
- [x] Ra Home lúc đang ghi: đoạn dở bị hủy, độ sáng/idle timer được trả lại;
  về app phải chuẩn bị lại và lấy challenge/token mới.
- [ ] Reauth: quay thụ động 3 giây, không màu/chấm/quay đầu; gửi xong điều hướng
  theo server, hiện tại mock trả `recovery_required`, không giả thành công.
- [ ] Simulator có cờ `ios:simulator`; Release có probe debugger `P_TRACED`.
  Debug bỏ debugger flag, có note `skipped_debug_build`. Jailbreak indicators là
  kiểm best-effort, không phải chứng minh thiết bị sạch; Simulator không thử ghi
  probe lên filesystem host. Duplicate ratio từ tối đa 30 cặp thumbnail thật.

## Điều kiện chốt

- [x] Genuine/low_quality/gián đoạn/mất mạng được sếp nghiệm thu; output genuine
  có media/signals như mục số đo. Các mục chi tiết chưa có log riêng vẫn để trống,
  không suy ra đã đo Release probe hoặc reauth trên iPhone.
- [x] Unit/UI test xanh trên bản code mới, gồm regression test stop re-entry;
  không nới assertion. UI test kiểm launch/gallery/light-dark, không thay thế quay thật.
- [x] Codex review diff: chưa phát hiện lỗi chặn bàn giao; quét file thay đổi không
  thấy media/token thật theo mẫu kiểm tra. Chưa có file staged.
- [ ] Người duyệt chấp thuận diff/bàn giao và PR được merge; kiểm staged trước commit.

Không commit/push tự động. IOS-04 ở `review`, chưa tuyên bố đã tích hợp main.

Nguồn API dùng cho đồng hồ/vẽ: [Apple synchronizationClock](https://developer.apple.com/documentation/avfoundation/avcapturesession/synchronizationclock),
[Apple CADisplayLink targetTimestamp](https://developer.apple.com/documentation/quartzcore/cadisplaylink/targettimestamp).
