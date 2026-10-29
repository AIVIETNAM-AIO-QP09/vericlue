# Bàn giao · IOS-04 · Lý Anh Quân+Codex · 2026-10-25 17:23

**Nhánh:** `codex/IOS-04-face-timeline`, từ IOS-03 `cada332` (working tree đầu phiên sạch).
**Trạng thái task sau phiên này:** `review` — nghiệm thu genuine/low_quality/gián đoạn/mất kết nối theo xác nhận của sếp; bản cuối sau sửa stop re-entry đạt 78/78 unit test và 4/4 lượt UI test. Review cuối chưa phát hiện lỗi chặn bàn giao. Chưa stage/commit/push/merge PR; không ghi `done`.

## Kết luận cuối — 25/10/2026

- Một lượt toàn bộ scheme sau sửa stop(): `TEST SUCCEEDED`, exit 0, artifact
  `/tmp/vericlue-ios04-final-20261025-04.xcresult`; iPhone 17 Pro Simulator,
  iOS 26.3.1. Console: 78 unit/14 suite và 4 lượt UI đạt. xcresult: 81 định danh
  đạt, 0 lỗi/skip; 94 lượt khi tính cả tham số động. Không cộng lẫn cách đếm.
- Regression test observer gọi stop đồng bộ đã chạy đạt. Không bỏ/nới assertion.
  UI test chỉ kiểm launch/gallery/light-dark; không thay thế nghiệm thu camera thật.
- Build Release SDK iPhone bản cuối (`CODE_SIGNING_ALLOWED=NO`) exit 0; chỉ biên
  dịch, không ký/cài/chạy trên thiết bị. `plan_check.py` exit 0: 0 lỗi/10 cảnh báo
  tải công việc và đường găng chung. `git diff --check` sạch.
- Review source gồm cả file mới chưa track: một camera do root sở hữu; t0/finish,
  lifecycle và re-entry; timeline/server challenge; ack/retry/token; sáu vùng đo,
  camprobe và đường điều hướng không giả thành công. Graph không bao phủ Swift,
  đã đọc source thay thế. Không phát hiện lỗi chặn bàn giao trong phạm vi review.
- Output iPhone/API ở dưới do sếp cung cấp và xác nhận; không phải phép đo do
  Codex tự chạy. Chưa có bằng chứng riêng cho reauth hay debugger Release trên máy thật.
- Quét working tree trong phạm vi IOS-04 không thấy media hoặc token thật theo
  mẫu kiểm tra; không có file staged. Phải kiểm lại staged trước commit. Không sửa
  contracts/backend/thresholds/ADR/STATUS; shared scheme của sếp được giữ nguyên.
- Các mục build-only/chưa nghiệm thu phía dưới là lịch sử từng checkpoint;
  kết luận hiện tại ở mục này thay thế trạng thái cũ.

## Nghiệm thu người dùng mới nhất

- Phiên `ses_339f14675babe6e8`: app/SQL sếp cung cấp cùng có 8 màu, 585 frame,
  282 mẫu vùng; app báo 30 FPS, JPEG 226.288 byte. SQL có đường dẫn ảnh và MP4.
- AE/AWB locked/restored = 1/1. Video 19.501,667ms, lịch 19.460ms, chênh 41,667ms.
- Sau hướng dẫn kiểm JPEG/MP4/câu đọc/low_quality/gián đoạn/mất kết nối, sếp
  trả lời “đúng hết”. Ghi nhận các mục đó đạt theo nghiệm thu người dùng; Codex
  không tự mở MP4 mới hoặc thao tác iPhone. Không bịa số lượt, challenge ID hay RGB từng vùng.
- Test bản stop() mới được xác minh độc lập bằng lượt test cuối ở trên. Không tự commit/push.

## Đã xong
- `Capture/FrontCameraSession.swift`: một session/input camera trước/video output BGRA, preset 1280×720, discards late frames. Queue sở hữu cấu hình/start/stop và sample callbacks; cấu hình một lần, không tạo theo pha; rollback input/output khi cấu hình thất bại.
- Model giữ đúng một preview layer, host UIView có thể được thay mà vẫn gắn lại cùng layer. Preview mirror, connection dữ liệu portrait/unmirrored. Không viết file/retain pixel buffer trong diagnostics.
- Metadata: ID pipeline/session/output/preview, cấu hình/input/output count, frames/drops/kích thước và fps từ PTS; không coi sample PTS ở checkpoint là writer t0.
- `FaceCameraCheckpointScreen`: quan sát camera do root FaceCaptureFlow sở hữu (không tạo session thứ hai cho Debug), preview cố định 96×128, đổi nhãn pha không thay view identity/session/layer. Home/foreground stop/start cùng graph, bỏ telemetry cũ theo generation; 5s không có frame báo lỗi.
- Gallery Debug có nút checkpoint trực tiếp không cần server. Live `.faceReady` nay mở `FaceLiveScreen`/`FaceCaptureFlow`, dùng LiveFlow phiên/token của IOS-03, không đi sang demo/false success.
- Thêm test thuần metadata và giữ identity controller, chỉ build chứ chưa thực thi. Hướng dẫn `apps/ios/docs/ios04-device-checkpoints.md`.
- Theo xác nhận trong chat, 5.1 đạt: 1/1/1, frame tăng; đổi pha hai vòng và Home/quay lại giữ ID. Không có số fps/kích thước cụ thể để ghi như số đo.
- `FaceTracker.swift`: VNDetectFaceRectanglesRequest revision 3 trên cách một frame, bbox top-left/unmirrored; yaw/roll/pitch độ optional; brightness BGRA toàn khung, ghi elapsed ms/lỗi Vision. Không fallback thành mặt giả nếu tracker lỗi.
- `QualityGate.swift`: ngưỡng khởi đầu Android, thêm chặn nhiều mặt và giá trị invalid; giữ good liên tục 1000ms theo PTS, reset khi lỗi/gap >250ms/PTS lùi hoặc lặp. Watchdog main dùng monotonic uptime xóa trạng thái cũ khi frame ngừng, không phục vụ timeline.
- Overlay bbox tính aspect-fill/crop và mirror chỉ ở preview; tắt implicit animation để không trễ hình. Main bỏ snapshot sai generation hoặc frame sequence lùi.
- Test mới cho hint ưu tiên, good hold/reset/gap, optional pose/đổi tọa độ, mirror/crop, BGRA luma; dữ liệu hoàn toàn tổng hợp. Chưa thực thi test.
- Sếp xác nhận 5.2–5.3 đạt; yaw nhìn thẳng gần 0°, trái khoảng −20°, phải khoảng +20° theo người dùng trên máy thử. Đây là số sếp cung cấp, không phải số đo do Codex chạy hoặc ngưỡng quay đầu chung.
- `VideoWriter.swift`: H.264 3Mbps/30fps kỳ vọng, dọc, transform identity, một video input và không audio; từ chính mọi sample của camera output cũ, trước khi skip frame Vision. Writer được cấu hình bằng format camera trước t0; chỉ bắt đầu session tại frame sẵn sàng append, không giữ frame cũ chờ encoder. Gap >100ms hủy đoạn dở/báo ghi lại; không retime hoặc nhân bản frame. Frame_times chỉ chứa sample đã append.
- `finish()` async tuần tự hóa markAsFinished với append trên cùng queue, chỉ trả file sau AVWriter `.completed`. Inspector kiểm isPlayable/duration, H.264, 1 video/no audio, kích thước dọc/transform identity/bytes >0; chỉ sau đó xuất URL qua UI.
- UI checkpoint 5.4 vẫn chủ động ghi/dừng/xuất AirDrop/Files và không upload. UI live mới bắt đầu sau sẵn sàng + quality hold, tự ghi đủ lịch rồi upload. Nền hủy đoạn dở, trả độ sáng/idle timer. Crash có thể để lại file iPhone tmp, cleanup qua restart thuộc IOS-06. Không có media thực được Codex tạo trong repo.
- Thêm test clock t0/frame_times/invalid PTS/epoch/giới hạn 60s, finish thiếu frame và bảo vệ đường dẫn đã tồn tại. Chưa thực thi test. FrameTime chỉ thêm Sendable, không đổi JSON/schema.

## Phạm vi và giới hạn
- File cũ có gap đầu 1 giây đã được thay bằng lượt ghi mới: 368 frame, H.264
  720×1280, 30 FPS, 12,2667 giây, 1 video/0 audio; AVFoundation giải mã đủ,
  PTS đầu 0, cuối 12,2333 giây, gap tối đa 33,33ms, không PTS lặp/lùi.
  File mới đạt kỹ thuật. Sếp đã xác nhận QuickTime phát hết, đúng chiều/chữ đọc xuôi
  (không mirror), và ra Home khi đang ghi hủy đoạn dở/không cho xuất.
- Timeline tích hợp đã được sếp nghiệm thu như mục số đo mới nhất; không có log
  RGB từng vùng hoặc low_quality challenge ID để tuyên bố đã đo độc lập từng mục.
- IOS-02/LIVE-01 trong backlog chưa `done`; đường tích hợp dùng contract/backend hiện hành, không tự đánh dấu các task phụ thuộc done. Thu giọng thật thuộc IOS-05, chưa triển khai ở task này.

## Bước tiếp theo
1. Người duyệt đọc diff và bàn giao; kiểm danh sách staged trước commit, không thêm media/DB/token.
2. Sếp tự commit/push và mở PR. Chỉ chuyển done sau khi được duyệt/merge; không tự thực hiện các thao tác này.
3. IOS-05 tiếp tục thu giọng thật, dùng lại camera và voice prompt/challenge ID từ server. Dấu yaw chỉ để hướng dẫn.

## Quyết định, lưu ý, bẫy
- Mặc định chỉ build theo quy ước của sếp; các lượt unit/UI test ở đây có yêu cầu
  riêng của sếp. Không tự bật camera/quay mặt người dùng, không commit/push.
- Codebase-memory đã kiểm project/graph/coverage; Swift paths `not_tracked`, nên dùng source read fallback cho camera/route/identity. Không dựa vào kết quả graph rỗng để kết luận thiếu code.
- Không sửa contracts/backend/thresholds/ADR/STATUS. Không thêm face media hoặc bí mật. Permission dùng mô tả camera đã có ở IOS-03; chưa cần micro.
- Xcode đã tạo `VeriClue.xcodeproj/xcshareddata/xcschemes/VeriClue.xcscheme` trong lần sếp thử 5.1; giữ nguyên, không tự stage/revert. Đây là shared scheme, không phải `.xcuserdata`.

## Câu hỏi cho nhóm
- Không còn câu hỏi chặn bàn giao IOS-04. Task ở review, chờ duyệt/merge;
  các phụ thuộc trong backlog không được tự đánh dấu done thay nhóm.

## Test đã chạy
Lượt hoàn tất sau sửa định dạng góc: `/tmp/vericlue-ios04-full-tests-20261025-03.xcresult`,
**exit 0, TEST SUCCEEDED**: 77/77 unit test, 4/4 lượt UI test; xcresult tổng hợp
80 định danh đều đạt, 0 lỗi/skip. Đây là bản **trước** sửa stop re-entry bên dưới.

### Sửa stop re-entry sau báo EXC_BAD_ACCESS

- Sếp báo `Thread 1: EXC_BAD_ACCESS (code=2)` tại stop(); chưa có call stack để
  khẳng định mọi chi tiết của crash. Source cho thấy vòng gọi đồng bộ:
  stop phát recordingError → FaceCaptureFlow.captureFailed → stop, trong lúc
  recording/stage vẫn đang active. Đây là lỗi re-entry thực, có thể gây tràn stack.
- FrontCameraSession.stop có guard stopping, vô hiệu run/reset cờ trước phát lỗi,
  không ghi đè lỗi writer cụ thể bằng cancelled. FaceCaptureFlow đổi stage trước
  dừng camera ở captureFailed/cancel, generation loại bỏ tác vụ cũ.
- receive kiểm generation sau callback lỗi để không bật lại receivingFrames của
  lượt vừa bị stop. Thêm regression test subscriber gọi stop đồng bộ, không mở camera.
- Sau đó sếp yêu cầu chốt: regression test và toàn bộ scheme đã chạy đạt như
  kết luận cuối. Nếu thiết bị vẫn crash, cần call stack mới để chẩn đoán, không
  coi test thuần là chứng minh mọi lỗi EXC_BAD_ACCESS đều được xử lý.

### Lượt test cũ trước sửa định dạng góc (giữ lịch sử)
Kết quả lịch sử: unit 76/77 đạt, UI 4/4 lượt chạy đạt trên iPhone 17 Pro Simulator
iOS 26.3.1. Một lỗi do bộ quét bắt ký tự phần trăm trong chuỗi định dạng góc
ở FaceCameraCheckpointScreen. Đã đổi sang Number.FormatStyle giữ dấu và một
chữ số thập phân; không đổi assertion hoặc danh sách chữ cấm. Lượt xanh sau sửa
được ghi riêng ở trên, không dùng artifact lỗi này để kết luận bản cuối.

Artifact: `/tmp/vericlue-ios04-full-tests-20261025-02.xcresult`, xcodebuild exit 65.
Đây là lượt tuần tự hoàn tất; lượt song song trước đó bị dừng do chờ lâu, không
dùng artifact dở của lượt trước để kết luận. xcresult tổng hợp 80 test định danh
(79 đạt/1 lỗi); console Swift Testing có 77 unit test, UI có 4 lượt chạy do launch
test được thực hiện ở cả light/dark. Không cộng hai cách đếm thành số test định danh.

Các lệnh build dưới đây chỉ biên dịch ở các checkpoint trước, không thực thi test:

```
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios04 build-for-testing
```

Kết quả cuối exit 0: app và test bundle biên dịch; không đồng nghĩa test xanh.
Build đầu lỗi cú pháp macro `#expect` với mutating method; đã tách kết quả bool
ra biến trước assertion và build lại thành công, không bỏ assertion.

Hook pre-commit file checkpoint: passed/skip đúng loại; không có SwiftLint riêng.
`plan_check.py`: exit 0, 0 lỗi/10 cảnh báo về tải/đường găng chung của dự án.

Release build SDK iPhone, `-configuration Release -destination 'generic/platform=iOS'
-derivedDataPath /tmp/vericlue-ios04-device CODE_SIGNING_ALLOWED=NO build`: exit 0.
Không ký/cài/chạy iPhone. `git diff --check` sạch. Chưa stage/commit/push.

### Build sau khi thêm 5.2–5.3

- Cùng lệnh Simulator `build-for-testing` và Release SDK iPhone ở trên: **exit 0** cho bản cuối, gồm các test mới. Không thực thi test hay mở camera từ công cụ.
- Build đầu thiếu import CoreGraphics ở QualityGate, đã bổ sung và biên dịch lại thành công. Không bỏ/nới assertion.
- Hook pre-commit file 5.2–5.3: passed/skip đúng loại; diff whitespace sạch. Không gọi đây là kết quả runtime Vision hoặc test xanh.
- Sau phần build này, sếp đã xác nhận 5.2–5.3 đạt và gửi mapping yaw như phần Đã xong; không có raw số fps để ghi.

### Build sau khi thêm 5.4

- Simulator `build-for-testing` và Release SDK iPhone với cùng lệnh/derivedDataPath ở trên: **exit 0** cho bản cuối. Không thực thi test, không tự quay/xuất media.
- Build đầu thiếu import CoreMedia trong màn checkpoint, đã sửa. Cảnh báo actor-isolated init của clock được sửa bằng nonisolated init; capture AVAssetWriter vào Sendable callback được bỏ bằng truy cập writer theo recordingID trên queue sở hữu. Build cuối không báo các cảnh báo này.
- Hook pre-commit 5.4 passed/skip đúng loại; `git diff --check` sạch. File MP4 thực, tính không mirror và playback vẫn phải xác nhận trên iPhone/QuickTime trước 5.5.

### Sửa hụt frame đầu sau khi kiểm file sếp gửi

- Fact: file cũ giải mã đủ nhưng có gap PTS 0→1 giây. Inference: giữ frame đầu
  trong lúc encoder khởi tạo có thể góp phần tạo gap; chưa chứng minh là nguyên nhân duy nhất.
- Chuyển cấu hình input/startWriting sang lúc bấm ghi với format camera hiện tại,
  trước khi chọn t0. Bỏ pending-first; chưa ready thì không chọn session/t0.
- Clock chặn gap >100ms (dung sai 1µs), áp dụng cả đầu và giữa đoạn. Hủy/xóa
  file dở và UI báo ghi lại; không xuất hoặc sửa timestamp cho trông liên tục.
- Thêm hai regression test synthetic PTS cho gap 1 giây và cadence/backpressure
  nhỏ; chưa thực thi. Không đưa file mặt từ Downloads vào repo.
- Lượt ghi mới sau sửa đã được giải mã đầy đủ: 368 frame/30 FPS/12,2667 giây,
  gap tối đa 33,33ms. Không còn hụt frame như file cũ trong lượt này;
  không khái quát thành bảo đảm mọi lượt hoặc mọi thiết bị.
- Kiểm tra bản sửa: Simulator `build-for-testing` **exit 0**, Release SDK iPhone
  `CODE_SIGNING_ALLOWED=NO build` **exit 0**. Chỉ biên dịch, không thực thi test,
  không cài/quay camera. Lượt build sandbox đầu lỗi quyền macro/Simulator;
  chạy lại ngoài sandbox thành công, không sửa code để né lỗi môi trường.
- `git diff --check` sạch; chưa stage/commit/push.

### Lịch sử triển khai 5.5–5.11 trước nghiệm thu thiết bị

- `Capture/FaceTimeline.swift`: validate dynamic/safety/8 màu/8 gaze marks/3 head turns,
  nội suy tuyến tính đúng điểm/thời gian, transition + hold theo server, không mirror.
  Reauth thụ động 3 giây. Thiếu/sai dynamic ở luồng cần dynamic bị chặn.
- `FrontCameraSession.swift` dùng nguyên session/output/preview; nhận timeline,
  tự dừng nhận frame cho writer tại biên cuối lịch; không kết thúc theo yaw.
  Convert PTS từ `synchronizationClock` sang host clock bằng CMSyncConvertTime;
  frame_times và targetTimestamp dùng chung gốc host, không giả định epoch giống nhau.
- `FaceEvidence.swift`: một bản sao pixel độc lập cho JPEG ở gần mốc frontal;
  encoder JPEG 0,9 chạy ngoài camera queue, không giữ buffer của camera pool.
  AE/AWB khóa sau baseline, mở sau màu/finish/hủy; ghi kết quả/thời điểm thực,
  không bịa khóa thành công nếu API/thiết bị không hỗ trợ.
- `FaceTimelineCanvas.swift` + `FaceCaptureFlow.swift`: CADisplayLink vẽ layer trực tiếp,
  painted_at theo targetTimestamp; không dùng timer/SwiftUI animation cho lịch/chấm.
  Giữ một preview cố định; restore brightness/idle state trên mọi đường dừng/hủy.
  Mất nhịp display/frame, thiếu JPEG/sáu vùng/events/thời lượng không khớp thì lỗi,
  không retime/nhân bản frame hoặc tự đi tới kết quả đạt.
- `CamProbe.swift`: simulator, jailbreak path + probe ghi exclusive ở đường dẫn
  unique ngoài sandbox rồi dọn file do mình tạo; Debug bỏ debugger flag/note rõ,
  Release sysctl P_TRACED (lỗi đọc báo unavailable); label model/machine, duplicate
  ratio tối đa 30 cặp thumbnail 24×24. Các probe best-effort, không chứng minh thiết bị sạch.
- `Regions.swift`: đủ forehead/left_cheek/right_cheek/nose/chin + background,
  cùng tỉ lệ bbox và ngưỡng trim tham khảo Android; histogram median RGB (stride 3).
  Background tránh mặt có margin; missing báo null/0. Chỉ gửi khi ít nhất một mẫu
  thực có đủ sáu vùng, không thay vùng trống bằng số giả.
- `FaceLiveScreen.swift` + root-owned `FaceCaptureFlow`: dùng session của IdentityFlow,
  prepareFace thay token từ `/challenge`, media → signals → finalize qua LiveFlow.
  Network retry giữ pending payload/ack và chỉ gửi phần chưa nhận. Finalize retry
  dùng gói mới từ response, hiển thị hint/số lượt thật. Token không xoay ở finalize
  retry vì response không có token; không gọi refresh thừa bỏ gói đó.
- Chặn màn camera/voice/upload/checking demo cho phiên API thật. Handoff
  voice_challenge hiển thị prompt/ID do server cấp, giữ camera controller cho IOS-05;
  không giả ghi âm hoặc giả thành công. Quan sát destination bằng onChange để
  không replay giá trị retry cũ khi màn chuẩn bị xuất hiện lại.
- Rà soát cuối: cả checkpoint Debug cũng nhận camera root bằng injection, không
  tự tạo thêm FrontCameraSession. Source app chỉ có một chỗ khởi tạo controller
  camera trước. Sau thay đổi này, Simulator build-for-testing và Release SDK iPhone
  đều exit 0; chưa stage/commit/push, diff whitespace sạch.
- Thêm 13 test (6 timeline/event log, 5 probe/regions/JPEG synthetic, 2 integration
  payload/rotated token/ack retry/unauthorized/reset destination). Chỉ biên dịch,
  chưa thực thi; không dùng ảnh/QR/audio/video thật trong fixture.
- Build bản cuối: Simulator `build-for-testing` **exit 0** (app + test bundle);
  Release SDK iPhone `CODE_SIGNING_ALLOWED=NO build` **exit 0**, không ký/cài/chạy máy.
  Các lỗi build đầu là import Combine/CoreMedia và biểu thức thumbnail quá lớn,
  đã sửa/tách biểu thức, không nới assertion. Dùng synchronizationClock thay API deprecated.
- Checklist tích hợp: `apps/ios/docs/ios04-live-checklist.md`. Đã bỏ phương án cắt
  full camprobe/regions trong §14 plan theo yêu cầu sếp. Chưa đổi backlog doing
  thành review/done vì còn phép thử thiết bị/test. Không sửa contract/backend/STATUS.
