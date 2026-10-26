# Bàn giao · IOS-05 · Lý Anh Quân+Codex · 2026-10-26 00:18

**Nhánh:** `feat/IOS-05-voice-capture`, base IOS-04 `c779e93`.
**Trạng thái task sau phiên này:** `review` — test xanh, đủ ba lần đo thật và xác
nhận ca lỗi; sếp chấp thuận bỏ qua tiếng WAV nhỏ trong lần nghiệm thu này.
Codex review diff cuối chưa thấy lỗi chặn bàn giao. Chưa stage/commit/push/merge.

## Review cuối và chấp thuận giới hạn — 26/10/2026

- Sếp yêu cầu “WAW bỏ qua, Review diff cuối và duyệt bàn giao, soạn lệnh”. Ghi
  nhận chấp thuận tiếng WAV nhỏ là giới hạn demo, **không** ghi đã sửa hoặc giọng
  nghe rõ. Không đổi gain/normalize PCM, không bỏ ghi WAV hay bỏ hợp đồng audio.
- Review gồm tracked diff và toàn bộ file Swift/test mới: clock/UUID lượt video,
  WAV format/resample/flush/8s/RMS; một camera root; dừng/hủy/đóng hai payload;
  submit/retry giữ byte/offset/ID, cap đọc lại và điều hướng fail-closed. Không
  phát hiện lỗi chặn bàn giao trong phạm vi IOS-05. Đây là self-review, không
  thay review độc lập hoặc tuyên bố mọi nhánh thiết bị đã được tự động kiểm.
- codebase-memory không bao phủ Swift; đã kiểm coverage và đọc source trực tiếp.
- Artifact test cũ được đọc lại: Passed, 92 định danh/0 lỗi/0 skip; console có
  89 unit và 4 lượt UI do launch light/dark. Không chạy thêm test và không sửa
  Swift sau lượt xanh. Test tham số làm tổng lượt thực thi là 105, không cộng lẫn.
- Diff whitespace sạch; không sửa contracts/backend/thresholds/ADR/STATUS.
  Danh sách file mới chỉ Swift/Markdown; quét mẫu bí mật không có hit. DB và
  media thật trong tmp được Git ignore. Chưa có file staged, phải kiểm lại staged
  trước commit; kiểm tra này không chứng minh tuyệt đối không có bí mật.
- `apps/ios/Config/Debug.xcconfig` có thay đổi IP local do sếp dùng thử. Giữ nguyên
  working tree, **loại khỏi lệnh stage IOS-05**; không tự revert hoặc commit IP đó.
- Bàn giao đủ để chuyển review với giới hạn đã chấp thuận. PR vẫn cần người duyệt
  và merge; Codex không tự ký duyệt thay trưởng nhóm hoặc đánh dấu done.

## Nghiệm thu thiết bị cập nhật — 26/10/2026

- Codex đọc bốn cặp WAV/MP4 trong tmp và đối chiếu DB: cả bốn scenario
  voice_clone, status review; server có cả hai file. Không thu thêm dữ liệu.
- WAV cả bốn: PCM 16 kHz mono 16-bit, 128.000 sample/8 giây, 256.044 byte,
  có tín hiệu và không có sample clipping. MP4 cả bốn: H.264 720×1280, 30 FPS,
  8,2 giây, một video/không audio, transform identity. AVFoundation giải mã đủ
  246 frame/file, không PTS lặp/lùi; gap lớn nhất khoảng 33,33ms.
- Ba offset trong bảng lấy từ ảnh/text app do sếp cung cấp, không suy từ độ dài
  file. DB không lưu audio_offset_ms; pts_to_host_offset_ms của phần mặt không
  thay được audio_offset_ms. Chưa có số offset phiên ses_fb5eb1b7c04605ec,
  không cần dùng phiên đó vì đã đủ ba phiên bên dưới.
- Sếp xác nhận các tình huống còn thiếu bằng chứng (rỗng, mất mạng/gửi lại,
  ra Home, từ chối quyền micro) đều đạt. Đây là nghiệm thu người dùng, không
  phải thao tác iPhone do Codex thực hiện.
- Sếp báo WAV nhỏ ngay cả nghe tai nghe max, sau đó chấp thuận bỏ qua trong lần
  bàn giao này. Không đánh đồng tín hiệu khác 0/đúng format với giọng rõ. Chưa
  chỉnh input gain hoặc khuếch đại số, không sửa WAV gốc gửi server.

## Test cập nhật — 26/10/2026

- Sếp yêu cầu chạy test: đã chạy **một lượt** toàn bộ scheme VeriClue, không sửa
  code/nới assertion hoặc chạy lại. `xcodebuild` exit 0, **TEST SUCCEEDED**.
- iPhone 17 Pro Simulator iOS 26.3.1: **89/89 unit test trong 16 suite**, gồm 11
  test IOS-05; **4/4 lượt UI test** (gallery/bank launch/light-dark). WAV tổng hợp
  được AVAudioFile giải mã đạt; converter/8s/silence/clock/offset/retry/ID đều đạt.
- Artifact: `/tmp/vericlue-ios05-tests-20261026-01.xcresult`. UI test không kiểm
  thu camera/micro thật hoặc lưu media server thật; kết quả thiết bị được ghi
  riêng trong mục nghiệm thu cập nhật, không suy từ test Simulator.
- Lệnh: `xcodebuild -project apps/ios/VeriClue.xcodeproj -scheme VeriClue
  -destination 'platform=iOS Simulator,id=184BFA1A-7DB0-4CE7-A9BB-1DA25FB36F80'
  -derivedDataPath /tmp/vericlue-ios05
  -resultBundlePath /tmp/vericlue-ios05-tests-20261026-01.xcresult
  -parallel-testing-enabled NO -maximum-concurrent-test-simulator-destinations 1
  -test-timeouts-enabled YES -default-test-execution-time-allowance 120
  -maximum-test-execution-time-allowance 180 test`.
- Các ghi chú build-only bên dưới là lịch sử trước yêu cầu chạy test này.

## Đã xong

- `Capture/WavRecorder.swift`: AVAudioSession `.playAndRecord`/`.measurement`,
  chọn micro tích hợp, AVAudioEngine tap → AVAudioConverter mono 16 kHz Int16,
  resample có flush cuối, header RIFF/WAVE PCM 44 byte/little-endian; tối đa
  128.000 sample (8 giây), RMS cho sóng âm. WAV giữ trong RAM, không ghi file
  tạm vào repo. Stop/remove tap/khóa collector xong mới đóng WAV và trả payload.
- `Flow/VoiceCaptureFlow.swift`: dùng đúng camera IOS-04 qua root `CaptureFlows`,
  một MP4 mới cho mỗi lần đọc; không tạo AVCaptureSession/video output thứ hai.
  Chuẩn bị audio session trước, ghi video/chờ frame đã append của đúng UUID
  lượt mới rồi mới bật engine. Offset = hostTime mẫu PCM đầu trừ hostTime PTS
  frame video đầu, làm tròn ms; không lấy thời gian bấm nút hoặc epoch khác nhau.
- WAV và MP4 phải hoàn tất/inspector đạt, audio được video bao phủ (dung sai biên
  100ms), rồi mới gọi LiveFlow.submitVoice: audio/video/offset/voice_challenge_id.
  Khóa thao tác khi preparing/finishing/uploading; lỗi capture không chuyển success.
- Mất mạng giữ cùng payload để gửi lại; chỉ phản hồi hợp lệ mới giải phóng media.
  HTTP 409 của voice không giả thành acknowledgment hoặc pass. Không có token
  trong UI/log thêm mới. MP4 chỉ xóa bằng camera owner sau ack/hủy.
- `LiveFlow.swift`: câu đọc lại phải có ID mới (phiên purpose), tối đa một lần;
  `attempts_left = 0` vẫn cho đọc câu vừa cấp vì server đã trừ lượt trước trả về.
  Response lạ/thiếu ID/reused ID/âm số lượt không thành success.
- `VoiceLiveScreen.swift`: prompt server, micro, RMS, tự dừng tối đa 8 giây, lỗi
  rỗng/quyền/gián đoạn/mất mạng, nút gửi lại; không dùng màn demo cho phiên thật.
  Cờ lifecycle/screen lease ngăn callback view cũ hủy lượt mới khi đổi câu.
- Debug gallery giữ ba số đo gần nhất trong RAM (session ID, thời lượng WAV/MP4,
  offset và bytes), giúp sếp lấy số đo sau màn kết quả. Không giữ media trong bảng.
- Thêm 11 test mới: header/AVAudioFile decode WAV tổng hợp; converter stereo48k
  → mono16k/8s; silence/empty/clock/offset; multipart retry giữ payload rồi review;
  ID/cap đọc lại/409/rỗng/root dùng chung camera/lease view cũ. MockURLProtocol
  không gọi mạng thật; không dùng dữ liệu cá nhân trong fixture. Đã chạy đạt
  trong lượt toàn bộ test ở mục cập nhật.
- Thêm `apps/ios/docs/ios05-device-checklist.md`, cập nhật task card/backlog review.

## Đang dở

- Tiếng nhỏ chưa sửa, được sếp chấp thuận là giới hạn demo. Chưa chứng minh
  hiệu quả ASR/nhận diện giọng thật bằng kết quả scenario mock voice_clone.
- Máy tham chiếu trước đây: iPhone 14 Pro/iOS 18.7.8. Commit base c779e93 cộng
  working tree IOS-05; chưa biết chính xác revision build/IP cho từng lượt quay,
  không lấy IP cấu hình hiện tại gán ngược cho các lần trước.
- IOS-04 vẫn review trong backlog; nhánh dựa đúng commit đã chốt, nhưng chưa
  kiểm chứng PR đã merge trên remote và không tự đánh dấu phụ thuộc done.

### Số đo ba lần thử — file/DB và số app sếp cung cấp

| Lượt | Session/model/iOS/commit/API | WAV giây | MP4 giây | audio_offset_ms | File mở được/server lưu/kết quả |
|---|---|---|---|---|---|
| 1 | ses_bbcb77ff2f1733a2 | 8,000 | 8,200 | 113 (ảnh app) | WAV đọc được, MP4 giải mã đủ; server voice_clone → review |
| 2 | ses_e43e34c944da5476 | 8,000 | 8,200 | 107 (ảnh app) | WAV đọc được, MP4 giải mã đủ; server voice_clone → review |
| 3 | ses_7264b715d004ba5e | 8,000 | 8,200 | 114 (text app) | WAV đọc được, MP4 giải mã đủ; server voice_clone → review |

WAV/MP4 bytes lần lượt: lượt 1 = 256.044/2.976.325; lượt 2 =
256.044/3.181.028; lượt 3 = 256.044/3.130.466. RMS toàn bản WAV lần lượt
−39,0/−30,8/−36,3 dBFS; đây không phải kết luận nội dung lời đọc nghe rõ.

## Bước tiếp theo

1. Sếp stage đúng file IOS-05 (không stage Debug.xcconfig/tmp), kiểm staged,
   commit và push lên upstream/feat/IOS-05-voice-capture, không push main.
2. Mở PR, nêu giới hạn tiếng WAV nhỏ, test và số đo thật. Chỉ ghi done sau duyệt/
   merge. Nếu sửa Swift sau này cần kiểm lại bản mới; không tự commit/push.

## Quyết định, lưu ý, bẫy

- AVAudioConverter primeMethod `.none`; dùng AVAudioTime hostTime của input tap,
  camera PTS chuyển sang host clock. Chờ đúng recording UUID để không lấy t0 của
  đoạn mặt trước. Từ chối offset âm/>3s hoặc clock nhảy/gap thay vì giả offset0.
- WAV cần ≥150ms RMS ≥0,005 để tránh silence/toàn0. Đây chỉ là heuristic chất
  lượng cục bộ, không chứng minh có lời nói; nhiễu phòng có thể vượt ngưỡng.
  Server quyết định khớp câu và kết quả; không chỉnh thresholds/backend/contracts.
- Khi background/route change/audio interruption trong lúc ghi: hủy bản ghi dở,
  không tự resume micro hoặc upload. Hồi phục toàn phiên khi app bị kill/cleanup
  crash xuyên phiên còn thuộc IOS-06; không tuyên bố đã hoàn thành Cổng 7.
- WAV được đóng thành Data trong RAM, không có WAV file handle treo. MP4 vẫn
  AVAssetWriter/finish async/inspector hiện có. Audio không nhét vào MP4.
- Có tra tài liệu Apple, dùng codebase-memory graph trước; Swift chưa được index
  nên đọc source fallback. Android WavRecorder làm tham chiếu định dạng, không
  sửa code Android. Không sửa STATUS hoặc vùng cấm; không thêm dữ liệu/bí mật.
- Tham khảo Apple:
  [sample-rate conversion](https://developer.apple.com/documentation/technotes/tn3136-avaudioconverter-performing-sample-rate-conversions),
  [host time](https://developer.apple.com/documentation/avfaudio/avaudiotime),
  [capture audio session](https://developer.apple.com/documentation/avfoundation/avcapturesession/automaticallyconfiguresapplicationaudiosession).

## Câu hỏi cho nhóm

- Đã đủ ba số đo; tiếng nhỏ được sếp chấp thuận bỏ qua, không còn câu hỏi chặn bàn giao.
- Mock scenario voice_clone quyết định theo scenario, không bảo đảm đổi lời đọc
  thật sinh re-read. Nhánh response đọc lại có test mock; nghiệm thu nội dung thật
  cần backend/ASR tương ứng, không sửa backend để ép test qua trong IOS-05.

## Build/kiểm tra — không thực thi test

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios05 build-for-testing

xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios05-device CODE_SIGNING_ALLOWED=NO build
```

- Build cuối Simulator/test bundle và Release SDK iPhone: **exit 0**, không báo
  warning/error mới. Chỉ biên dịch, không ký/cài/chạy thiết bị và không chạy test.
  Cảnh báo buffer/weak self Sendable ban đầu
  đã xử lý bằng input wrapper đồng bộ trong converter và explicit weak capture.
- Chưa chạy unit/UI test theo quy ước build-only. Không lấy kết quả IOS-04 làm
  kết quả test IOS-05.
- `uv run python scripts/plan_check.py`: exit 0, **0 lỗi/10 cảnh báo** về tải và
  đường găng chung. `git diff --check` sạch; quét cả file mới không thấy trailing
  whitespace. Quét mẫu private-key/token trong file mới không có hit; không có
  file WAV/MP4/ảnh/DB/.env mới chưa ignore. Đây không phải chứng minh tuyệt đối
  không có bí mật; cần kiểm lại staged trước commit. Chưa stage/commit/push.
