# IOS-05 — Cổng 6: nghiệm thu thu giọng thật

Code đã triển khai; build không thay thế nghiệm thu iPhone hoặc test xanh.
Ngày 26/10: đủ ba lượt đo (offset app 113/107/114ms), file/DB voice_clone → review,
unit/UI xanh; sếp xác nhận ca lỗi và chấp thuận bỏ qua tiếng WAV nhỏ. Giới hạn
âm lượng chưa sửa, không đánh dấu giọng nghe rõ hoặc ASR thật đã đạt. Task review,
chi tiết trong bàn giao IOS-05; chưa merge nên không ghi done.
Không dùng ảnh/giọng/QR thật làm fixture hoặc thêm media vào Git.

## Chuẩn bị và chạy

1. API mock như IOS-03/04; Debug API_BASE_URL đúng IP của Mac, iPhone cùng mạng.
   SQLite không cần Docker. Không đổi secret/khởi động lại API giữa một phiên.
2. Xcode mở VeriClue, Debug, chọn iPhone thật → Run. Máy đã dùng ở IOS-04:
   iPhone 14 Pro / iOS 18.7.8 theo sếp; ghi lại nếu lần này thay đổi.
3. Ngân hàng → Xem tất cả màn → bật **API thật**, scenario **voice_clone**.
   Về ngân hàng, mở phiên mới và đi OTP/CCCD/phần mặt như trước. Đừng mở riêng
   route Đọc câu trong gallery: đó là màn demo, không phải phép thử API.
4. Tới câu đọc từ server: bấm micro, cấp quyền. Giữ mặt trong preview và đọc rõ
   câu, bấm **Đọc xong · Gửi bản ghi**, hoặc đợi tự dừng ở giới hạn 8 giây.
   Trong lúc chuẩn bị/đóng/gửi không có nút tạo bản ghi thứ hai.
5. `voice_clone` phải tới **Hồ sơ đang được xác minh thêm**, không tự success.
   Về ngân hàng → Xem tất cả màn: xem **Ba bản ghi giọng gần nhất · IOS-05**.
   Số đo gồm session ID, WAV/MP4 giây, offset ms, bytes; không có token/media.
   Chỉ giữ ba dòng trong RAM, khởi động lại app sẽ mất.
6. Lặp bằng **ba phiên mới**, ghi ba dòng và kết quả server vào bàn giao.
   Một dòng chẩn đoán chỉ chứng minh đóng bản ghi, không tự chứng minh server đã nhận.

## Kiểm file ở Mac

Chạy ở gốc repo ngay sau từng lượt, trước khi tạo phiên mới:

```bash
sqlite3 -header -column tmp/dev.db "SELECT session_id, status,
 json_extract(payload, '$.audio') AS wav
 FROM sessions ORDER BY created_at DESC LIMIT 1;"
```

DB giữ đường dẫn WAV trong `audio`. Video giọng được server lưu riêng trong
thư mục media phiên; `payload.video` là **video mặt**, không dùng nó để chứng minh
server nhận MP4 giọng. Với MEDIA_DIR mặc định, thay session ID bằng dòng vừa ghi:

```bash
ls -lh tmp/media/<session_id>/voice_audio.wav tmp/media/<session_id>/voice_video.mp4
open tmp/media/<session_id>/voice_audio.wav
open tmp/media/<session_id>/voice_video.mp4
```

Nếu Mac đã cài ffprobe, kiểm định dạng/thời lượng bằng:

```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bits_per_sample:format=duration,size -of json tmp/media/<session_id>/voice_audio.wav
ffprobe -v error -show_entries stream=codec_name,width,height:format=duration,size -of json tmp/media/<session_id>/voice_video.mp4
```

Kỳ vọng WAV `pcm_s16le`, 16000 Hz, 1 channel, 16 bit, có tiếng đọc rõ,
0 < thời lượng ≤ 8 giây. WAV có header chuẩn 44 byte, PCM theo sau.
MP4 H.264 dọc, không mirror, không audio track, mở/phát hết bằng QuickTime.
MP4 bắt đầu trước WAV; `offset / 1000 + wav_seconds` không vượt thời lượng MP4
quá 100ms. Offset thực lấy từ app, **không mặc định một số**.

## Các tình huống cần thử

- [x] `voice_clone` → review; server có cả WAV và MP4, mở được/đúng định dạng.
  WAV nhỏ là giới hạn được sếp chấp thuận, không coi mức âm đã đạt.
- [ ] Ghi đủ 8 giây tự kết thúc; WAV không dài hơn 8 giây. Bấm gửi nhanh hai lần
  không tạo hai tác vụ; không upload trước khi WAV và MP4 đóng xong.
- [x] Bấm micro rồi dừng ngay/không nói → **Chưa thu được giọng nói**, không gửi
  WAV rỗng hoặc âm thanh toàn số 0. RMS là heuristic cục bộ (ít nhất 150ms có
  RMS ≥ 0,005), không phải bộ nhận diện lời nói; tiếng ồn có thể vượt ngưỡng.
- [x] Từ chối quyền micro → báo rõ/có Mở Cài đặt, không crash hoặc quay giả.
- [x] Tắt mạng lúc gửi → báo lỗi tại màn giọng; bật mạng/Gửi lại giữ nguyên
  WAV/MP4/offset/ID, không thu lại hoặc tự success. HTTP 409 không giả là pass.
- [x] Ra Home khi thu → hủy bản ghi dở, không upload; sếp xác nhận trong chat.
- [ ] Đổi input audio/gián đoạn hệ thống khi thu → hủy bản ghi dở, không upload;
  không tự bật micro lại. Bấm lại mới thu một bản mới. Xử lý hồi phục toàn phiên
  và dọn file khi app bị kill thuộc IOS-06.
- [ ] Đọc sai câu khi backend có kiểm nội dung → câu đọc lại/ID **mới**, số lượt
  đúng server. `attempts_left = 0` vẫn cho đọc câu vừa cấp lần cuối; không tạo
  vòng lặp đọc vô hạn. API mock không chắc sinh kịch bản sai câu chỉ từ lời đọc
  thực: nhánh này có MockURLProtocol test, cần backend có ASR để nghiệm thu tay.

## Ba lần đo bắt buộc

Ghi trong bàn giao: model/iOS, commit build (`git rev-parse --short HEAD` cộng
working tree IOS-05 nếu chưa commit), API/IP/scenario; ba session ID, WAV giây,
MP4 giây, offset ms, định dạng và kết quả. Không dump payload DB/token vào chat.

- [x] Ba lần đo thật đã điền vào bàn giao: thời lượng từ file, offset từ ảnh/text app;
  không suy ra từ lịch/timer hoặc fixture tổng hợp.
- [x] Codex self-review và cập nhật bàn giao, không phát hiện lỗi chặn trong phạm vi
  IOS-05; âm lượng nhỏ được sếp chấp thuận bỏ qua. Không tự chạy thêm test.
- [x] Một lượt unit/UI test theo yêu cầu sếp ngày 26/10: 89/89 unit và 4/4 lượt UI
  đạt trên Simulator; `/tmp/vericlue-ios05-tests-20261026-01.xcresult`.
- [ ] Diff được duyệt, staged không có dữ liệu/bí mật; PR được merge mới ghi done.

Tham khảo triển khai:
[Apple AVAudioConverter](https://developer.apple.com/documentation/technotes/tn3136-avaudioconverter-performing-sample-rate-conversions),
[Apple AVAudioTime](https://developer.apple.com/documentation/avfaudio/avaudiotime),
[Apple quyền quản lý audio session của capture](https://developer.apple.com/documentation/avfoundation/avcapturesession/automaticallyconfiguresapplicationaudiosession).
