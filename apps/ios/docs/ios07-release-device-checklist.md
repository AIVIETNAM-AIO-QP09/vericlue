# IOS-07 — nghiệm thu Release và số đo iPhone

Trạng thái: **chưa nghiệm thu bản IOS-07**. Không tick lại bằng kết quả IOS-06/theme.
Phạm vi mức 1: đóng gói demo, không thêm account binding/device proof/media signing.
Nguồn Android đã đối chiếu: upstream/main `54acaad`; Android cũng chưa có bằng chứng
Release HTTPS trên điện thoại thật trong bàn giao đã đọc.

## A. Ghi môi trường

- [ ] Model / iOS / thời điểm Run:
- [ ] Commit + mô tả dirty diff nếu có:
- [ ] Scheme VeriClue-Release, không debugger, provisioning còn hạn.
- [ ] Domain HTTPS và commit/cấu hình backend (mock hay real); không ghi token/secret.
- [ ] Wi-Fi / nhà mạng và công nghệ dữ liệu thực tế (4G/5G), không gọi 5G là số đo 4G.

## B. Cài và mở Release

- [ ] Làm theo README; domain thật, TLS hợp lệ; không bật ngoại lệ ATS để chữa lỗi mạng.
- [ ] Không có Gallery, chọn scenario, nút chụp/bỏ qua debug.
- [ ] Đăng ký từ màn ngân hàng gọi API thật qua HTTPS (log server đối chiếu phiên).
- [ ] Tạo phiên → OTP → CCCD/review hai mặt → quay → confirm → media → signals → finalize.
- [ ] Pass không đọc câu; voice_challenge mới đọc. Không tự suy status lạ thành success.
- [ ] UI sáng/tối/chữ lớn, quyền camera/mic đúng; không hiển thị điểm hay chữ cấm.
- [ ] Mất mạng lúc gửi/confirm: giữ dữ liệu phù hợp, không success; bật mạng retry đúng ack.
- [ ] Home khi thu: dừng an toàn và lượt mới dùng challenge mới.
- [ ] Back/Dừng: dọn file đúng chính sách. Gallery Debug không tồn tại trên Release;
  kiểm app container bằng Xcode Devices nếu cần, không thêm nút debug vào Release.
- [ ] JPEG/video/WAV server nhận mở được, video đúng chiều/không mirror/đủ lịch.

Low_quality, voice_clone, expiry, permission bị từ chối cần ghi riêng build nào đã thử.
Release không gửi X-Mock-Scenario; không ghi các ca Debug thành bằng chứng Release.
Backend mock mặc định genuine không đủ tạo các ca lỗi này. Phối hợp backend môi
trường thử được duyệt nếu cần nghiệm thu đầy đủ; chưa có thì để pending.

## C. Số đo thật — tối thiểu ba lượt, ghi đúng build/mạng

| Lượt / mạng | Session ID | FPS mặt | MP4 mặt bytes | MP4 giọng bytes | audio_offset_ms | PTS→host ms | Gửi mặt s | Gửi giọng s |
|---|---|---|---|---|---|---|---|---|
| 1 | chưa đo | — | — | — | — | — | — | — |
| 2 | chưa đo | — | — | — | — | — | — | — |
| 3 | chưa đo | — | — | — | — | — | — | — |

- Ghi cả Wi-Fi và dữ liệu di động; nếu lượt pass không cần giọng, ghi N/A có lý do,
  không điền 0 hoặc ép đọc câu. Bổ sung lượt voice_challenge nếu cần đo giọng.
- `fps`, `video_bytes`, `pts_to_host_offset_ms` đã có trong signals.client_quality.
  Đây là số đo client gửi, không phải kiểm chứng độc lập phần cứng đồng bộ.
- Xem chất lượng của đúng phiên trong DB backend, chỉ xuất metadata, không toàn payload:

  ```sql
  SELECT session_id,
    json_extract(payload, '$.signals.client_quality.fps') AS fps,
    json_extract(payload, '$.signals.client_quality.video_bytes') AS video_bytes,
    json_extract(payload, '$.signals.client_quality.pts_to_host_offset_ms') AS pts_to_host_ms,
    json_extract(payload, '$.signals.client_quality.video_duration_ms') AS duration_ms,
    json_extract(payload, '$.signals.client_quality.scheduled_duration_ms') AS schedule_ms
  FROM sessions WHERE session_id = '<SESSION_ID_CUA_LUOT_DO>';
  ```

- Dung lượng file giọng lấy từ đúng file backend/container, không từ file cũ khác phiên.
  Offset giọng lấy từ metadata request/công cụ đo Debug đã có, ghi rõ nguồn. Log HTTP
  mặc định chỉ có status không đủ chứng minh offset hoặc thời lượng.
- Thời gian gửi: có thể dùng screen recording + log server để đo từ bấm xác nhận
  tới kết quả và **ghi nhãn end-to-end gồm confirm/upload/inference**, không gọi là
  thời gian upload thuần. Muốn upload thuần phải đo từng request bằng Instruments/
  công cụ mạng được phép, không ghi payload/Authorization vào bàn giao.
- Yaw: đo lại trên iPhone/bản đang nghiệm thu; nhìn thẳng / quay trái / quay phải,
  ghi đơn vị và chiều theo tay người dùng. Không tự dùng lại số lịch sử làm số mới.

## D. Chốt hồ sơ

- [ ] Test của bản cuối được sếp yêu cầu chạy và xanh; lint/build kiểm đúng bản.
- [ ] README và bàn giao có kết quả thật, nêu các ca pending/N/A và phiên bản backend.
- [ ] Artifact không ATS exception/marker debug, đủ bốn font; không commit dữ liệu riêng.
- [ ] Diff được review và PR/merge theo quy trình (sếp đang tạm hoãn bước này).

Không tick IOS-07 done khi thiếu domain/Release iPhone/số đo. Receipt GET 200 thật
và SEC-02 không tự trở thành tiêu chí hoàn tất của đợt đóng gói này.
