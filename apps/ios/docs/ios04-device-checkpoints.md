# IOS-04 — checkpoint iPhone, không triển khai toàn bộ trước khi thử

Nhánh `codex/IOS-04-face-timeline`, base IOS-03 `cada332` + working tree.
Máy dự kiến: iPhone 14 Pro/iOS 18.7.8 theo thông tin sếp cung cấp ở IOS-03.

Checkpoint 5.1–5.4 đã được sếp nghiệm thu. Bản tích hợp cuối có 78/78 unit và
4/4 lượt UI test đạt sau sửa stop re-entry; task ở review. Kết quả timeline/API
và giới hạn bằng chứng xem [checklist tích hợp](ios04-live-checklist.md).

## 5.1 — Một pipeline camera trước

**Đã được sếp xác nhận đạt trong chat** trên máy đã nêu: cấu hình/input/output
1/1/1, frame tăng; hai vòng đổi nhãn pha và Home/quay lại giữ ID. Codex không
trực tiếp quan sát; chưa có số kích thước/fps cụ thể được ghi lại.
Các nhãn pha chỉ để kiểm camera không bị tạo lại; chưa có timeline, recording
hoặc upload. Không được diễn giải nút đổi pha thành một lần xác minh mặt.

### Mở nhanh, không cần server hay lặp lại OTP/CCCD

1. Xcode mở `apps/ios/VeriClue.xcodeproj`, scheme VeriClue, Debug, chọn iPhone thật và Run.
2. Ngân hàng → **Xem tất cả màn** → **Kiểm tra camera trước · IOS-04 (5.1–5.4)**.
3. Cho quyền camera nếu hỏi. Preview nhỏ cố định ở góc phải, cùng vị trí dự kiến
   trong lịch mặt. Simulator không có camera thật: báo lỗi là đúng, không dùng ảnh thay thế.
4. Chờ dòng **Đang nhận khung hình**. Chẩn đoán phải có:
   - Cấu hình `1`, input `1`, output `1`.
   - Số frame tăng; kích thước khung dọc (mục tiêu 720×1280), fps đo theo PTS.
   - Dữ liệu dọc `có`, mirror `không`.
5. Bấm **Đổi pha kiểm tra** qua Baseline/Màu/Chấm sáng/Quay đầu ít nhất hai vòng.
   ID Pipeline/Session/Output/Preview không đổi; cấu hình vẫn `1`; frame tiếp tục
   tăng; preview không biến mất hoặc đổi chỗ.
6. Đưa tay trái của mình lên: preview hiển thị kiểu gương. Việc frame/file không
   mirror mới được cấu hình/đối chiếu connection ở bước này; **chưa có MP4 để
   xác nhận bằng QuickTime**, phải làm ở 5.4.
7. Ra Home khoảng 5 giây rồi mở lại: camera dừng khi nền, quay lại nhận frame;
   ID và số lần cấu hình không đổi. Không yêu cầu giữ fps trong thời gian app nền.
8. Đóng checkpoint: camera ngừng; mở lại là một lượt kiểm tra mới, ID được phép
   khác. Từ chối quyền → thông báo, Mở Cài đặt/cấp quyền rồi Thử lại, không crash.

Trong bản tích hợp hiện tại, luồng **API thật** sau OTP/CCCD tới màn quay mặt thật,
không phải checkpoint này. Checkpoint trong gallery chỉ kiểm camera/ghi file độc
lập, không gửi API. Phiên API do `IdentityFlow.liveFlow` giữ tới lúc đóng/reset.

### Bằng chứng cần sếp trả lời trước khi tiếp tục 5.2

Không cần quay hoặc gửi mặt cá nhân. Ghi lại bằng text:

- Model/iOS máy thử.
- Cấu hình/input/output và kích thước/fps sau vài giây.
- Qua hai vòng đổi pha, bốn ID có giữ nguyên không? Frame có tăng không?
- Home/quay lại có tiếp tục nhận frame với ID giữ nguyên không?
- Preview mirror đúng, có màn đen/crash/permission lỗi không?

- [x] 5.1 iPhone được sếp xác nhận đạt.

## 5.2–5.3 — Tracker và căn mặt

**Sếp xác nhận đạt trong chat.** Số đo yaw thô sếp cung cấp: nhìn thẳng gần 0°,
quay về tay trái khoảng −20°, tay phải khoảng +20°. Đây là dấu đo trên cấu hình
camera hiện tại/iPhone đang thử, không phải ngưỡng chung hoặc số đo calibration.
FPS/brightness và hint/hold được sếp xác nhận đã kiểm, không có raw số fps để ghi.

Vẫn mở nút ở trên. Giữ nguyên camera/session/output/preview, thêm:

- Vision revision 3 chạy cách một frame; bbox vẽ trên preview mirror, dữ liệu
  bbox ở tọa độ top-left ảnh dọc không mirror.
- yaw/roll/pitch đổi radian sang độ; API thiếu góc thì hiện **không có**, không
  thay bằng 0. Không tự gán dấu yaw thành trái/phải.
- Luma trung bình toàn khung từ BGRA, thang 0–255. Ngưỡng căn mặt khởi đầu theo
  Android: luma ≥70, width mặt ≥0.32, tâm gần (0.5, 0.45), lệch tối đa 0.18.
  Đây chưa phải calibration trên iPhone; BGRA luma không đảm bảo trùng tuyệt đối
  giá trị Y-plane Android.
- Chỉ một hint chất lượng theo ưu tiên: lỗi tracker → thiếu mặt/nhiều mặt →
  thiếu sáng → đứng xa → lệch tâm → tốt. Không quyết định xác minh danh tính.
- Giữ tốt liên tục 1000ms mới hiện **Đã đủ điều kiện căn mặt**. Lỗi tracker,
  sample gap >250ms, PTS lùi/lặp, Home hoặc frame ngừng đều reset/chặn ready.
  Watchdog stale-frame chỉ kiểm độ mới dữ liệu, không chạy timeline bằng timer.

### Thử thực tế trước 5.4

1. Nhìn thẳng ở nơi sáng: **Số mặt: 1**, bbox bám mặt. Nghiêng/di chuyển nhẹ,
   bbox phải theo đúng mặt, không chạy ngược hoặc lệch vì mirror/crop. Ghi fps
   trước/sau tracker và thời gian Vision (ms) từ Debug; không tự khẳng định đủ fps.
2. Ra khỏi khung → hint thiếu mặt. Nếu có người hỗ trợ, hai mặt trong khung →
   hint chỉ một người, không ready.
3. Với mặt còn được dò: giảm sáng → **Ra chỗ sáng hơn**; lùi xa → **Lại gần hơn**;
   dịch ngang/dọc → **Đưa khuôn mặt vào giữa khung hình**. Chỉ một hint mỗi lúc.
4. Về giữa, đủ sáng → **Tốt, giữ nguyên**; thanh đạt sau khoảng 1 giây. Phá điều
   kiện trước khi đầy → reset về 0. Home/quay lại cũng phải căn lại từ đầu.
5. Đọc yaw thô trong Debug, không gửi ảnh mặt:
   - Nhìn thẳng: yaw khoảng bao nhiêu?
   - Quay về phía **tay trái của sếp**, giữ 1–2 giây: yaw dấu gì, giá trị khoảng?
   - Quay về phía **tay phải của sếp**, giữ 1–2 giây: yaw dấu gì, giá trị khoảng?
   - roll/pitch có số hay **không có**?
6. Bấm đổi pha hai vòng và Home/quay lại, kiểm lại ID 1/1/1 vẫn giữ như 5.1.

Quality gate không tự chạy lịch xác minh. Từ checkpoint 5.4 có nút ghi video thử
riêng sau khi căn mặt đạt. Test dùng bbox/angle/pixel tổng hợp đã chạy đạt trong lượt cuối.

- [x] 5.2 bbox, pose, brightness/fps được kiểm trên iPhone; ghi dấu yaw thật theo sếp.
- [x] 5.3 hint đúng và giữ liên tục 1s/reset được sếp xác nhận.

## 5.4 — Một MP4 liên tục, không mirror (đã đạt)

Chưa tự chạy lịch màu/chấm/quay đầu, không gọi server. Đoạn kiểm tra do sếp chủ
động ghi; chỉ lưu tạm trong sandbox app, không tự lưu Photos hoặc xuất ra Mac.

1. Xcode **⌘R** để cài bản mới. Vào nút checkpoint ở trên.
2. Căn mặt đạt 1 giây → bấm **Ghi video kiểm tra (5.4)**.
3. Quay khoảng 10 giây: nhìn thẳng, giơ tay trái/phải và đưa một tờ giấy có chữ
   mẫu không nhạy cảm vào camera (không dùng CCCD hoặc thông tin cá nhân). Có thể
   bấm đổi nhãn pha vài lần: preview/ID phải giữ nguyên và writer vẫn ghi.
4. Bấm **Dừng và hoàn tất MP4**. Chờ hết **Đang hoàn tất và kiểm tra MP4…**.
   Không xuất/upload trước khi finishWriting trả `.completed` và asset kiểm tra đạt.
5. Phải hiện H.264/không tiếng, kích thước dọc, thời lượng gần đoạn sếp ghi,
   bytes >0, frame đã ghi >0. Debug `media_time đầu` phải là 0; `t0 PTS` phải có
   giá trị. Đây là PTS frame đầu append thành công, không phải giờ bấm nút.
6. Bấm **Xuất MP4 để mở QuickTime** → chọn **AirDrop → Mac của sếp**. Để file ở
   Downloads hoặc thư mục riêng ngoài repo. Nếu AirDrop chưa thấy Mac, có thể
   lưu vào Files rồi tự chuyển sang Mac. Không gửi video mặt vào chat/GitHub.
7. Mac mở file `.mp4` bằng **QuickTime Player**, phát từ đầu đến cuối:
   - Video dọc, hình không xoay/ngược, không có đoạn đen đầu do t0 sai.
   - Chữ trên giấy phải đọc xuôi trong file, dù preview trên điện thoại lật gương.
   - Một đoạn liên tục, chuyển nhãn pha không cắt/khởi động lại recording.
   - Movie Inspector (**Window → Show Movie Inspector**, thường **⌘I**) kiểm
     H.264, kích thước và thời lượng; không có audio track.
8. Quay lại app, **Xóa video tạm** hoặc đóng checkpoint bằng nút ở cuối màn.
   File gốc bị dọn khi xóa/ghi lượt mới/đóng checkpoint; bản đã AirDrop là bản sao
   do sếp quản lý, tự xóa sau nghiệm thu. Nếu app bị kill đột ngột, file tạm có
   thể còn tới khi hệ thống dọn; cleanup bền qua restart thuộc IOS-06.
9. Thử một lượt ghi khác rồi ra Home trước khi dừng: đoạn dở phải bị hủy, không
   cho xuất như video hoàn tất. Foreground phải căn lại và bắt đầu lượt mới.

Writer dùng output camera cũ, không thêm MovieFileOutput/audio input. Mọi frame
camera tới writer trước bước Vision cách một frame. Writer được cấu hình bằng
format camera trước khi chọn frame đầu/t0. Nếu writer chưa sẵn sàng lúc đầu,
bỏ frame có đếm, không giữ lại frame cũ chờ encoder hoặc queue pixel vô hạn.
Session ghi chỉ bắt đầu tại frame thực sự sẵn sàng append. Sau t0, gap giữa hai
frame >100ms (có dung sai làm tròn) hủy file dở và báo ghi lại, không nối thời gian
hay nhân bản frame để che mất dữ liệu. Đây là chốt toàn vẹn capture cục bộ, không
phải ngưỡng mô hình/server. `frame_times` chỉ ghi frame append thành công. Giới hạn an
toàn checkpoint 60 giây; vượt giới hạn là lỗi, không tự coi là hoàn tất lịch.

Trả lời bằng text: kích thước/thời lượng/codec, số frame, chữ có đọc xuôi không,
QuickTime có phát hết không, và thử ra Home có hủy đoạn dở không. Không cần gửi MP4.

- [x] 5.4 iPhone: MP4 mở QuickTime, đúng chiều/không mirror/liên tục, async finish và xử lý đoạn dở đạt.
- [x] File mới sau sửa: H.264, 720×1280, 1 video/0 audio; giải mã toàn bộ
  368 frame, 30 FPS, dài 12,2667 giây. PTS đầu 0, cuối 12,2333 giây,
  gap tối đa 33,33ms, không có gap >100ms hoặc PTS lặp/lùi.
- [x] Sếp xác nhận QuickTime phát hết, hình đúng chiều và chữ đọc xuôi (không mirror).
- [x] Sếp xác nhận ra Home khi đang ghi hủy đoạn dở, không cho xuất.

Chốt 5.4 ngày 25/10/2026: kết hợp kết quả giải mã file mới với xác nhận thử tay
của sếp trong chat. Phần QuickTime/không mirror và Home là người dùng nghiệm thu,
không phải Codex tự thao tác trên iPhone. Không đồng nghĩa toàn bộ IOS-04 đã xong.

Kết quả file mới dựa trên AVFoundation đọc/giải mã MP4 sếp gửi ngày 25/10,
không phải kết quả unit/UI test. Không sao chép video vào repo. Đạt kỹ thuật
trong một lượt ghi không chứng minh mọi lượt ghi hoặc mọi thiết bị đều đạt.

Lượt MP4 sếp gửi ngày 25/10: AVFoundation giải mã đủ 420 frame, H.264,
720×1280, 14,968 giây, 1 video/0 audio, nhưng có gap PTS 1 giây ở đầu.
Không chốt đạt từ file này. Sau sửa đường khởi tạo writer/gap guard, cần ghi
lượt mới khoảng 10–15 giây; nếu xuất được thì kiểm playback và chữ xuôi như trên.
Nếu app báo video gián đoạn, ghi lại thông số FPS/drop để điều tra tiếp, không
coi việc chặn xuất là bằng chứng đã sửa hết nguyên nhân hụt frame.

## Các chặng tiếp theo — code đã nối, chờ nghiệm thu tích hợp

1. **5.2–5.3:** đã được sếp xác nhận đạt, dấu yaw đã ghi ở trên.
2. **5.4:** đã đạt; file mới đạt codec/frame/timestamp và sếp xác nhận hai mục thử tay trên.
3. **5.5–5.8:** đã có baseline/JPEG/AE-AWB, CADisplayLink/targetTimestamp,
   chấm nội suy và quay đầu đủ lịch server, cùng pipeline/preview. Chưa thử timeline mới trên iPhone.
4. **5.9–5.10:** đã có camprobe đầy đủ và năm vùng da + nền; Debug không dùng
   debugger flag. Không bỏ/cắt hai mục này.
5. **5.11:** đã nối media → signals → finalize, retry đúng gói/ack. Cần nghiệm thu
   `genuine`/`low_quality` trên iPhone theo [checklist tích hợp](ios04-live-checklist.md).
   Token xoay ở `/challenge`; finalize retry không có trường token mới theo contract.

Không tự chạy test; build-for-testing chỉ biên dịch test. Không commit/push hoặc
đưa ảnh/MP4/biometric fixture thật vào Git.

## Tài liệu kỹ thuật

- [Apple: sample buffer delegate và serial queue](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutput/setsamplebufferdelegate(_:queue:)).
- [Apple: AVCaptureVideoDataOutput](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutput).
- [Apple: VNDetectFaceRectanglesRequest](https://developer.apple.com/documentation/vision/vndetectfacerectanglesrequest).
- [Apple: VNFaceObservation](https://developer.apple.com/documentation/vision/vnfaceobservation).
- [Apple: AVAssetWriter](https://developer.apple.com/documentation/avfoundation/avassetwriter).
- [Apple: startSession và mapping PTS](https://developer.apple.com/documentation/avfoundation/avassetwriter/startsession(atsourcetime:)).
