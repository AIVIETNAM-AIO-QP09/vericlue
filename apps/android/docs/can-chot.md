# Việc cần trưởng nhóm duyệt và chốt (app Android)

- **Ngày:** 24/10/2026. **Người hỏi:** Ngọc Quang (+ Claude).
- **Cách trả lời:** điền vào cột **Trả lời** (ok / sửa / không), sửa thẳng file này trên GitHub hoặc nhắn lại.
- **Sau khi có trả lời:** app làm tiếp theo câu trả lời, và mỗi câu đã chốt sẽ được ghi lại trong file bàn giao.

## A. Duyệt code

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 1 | Duyệt và merge PR giao diện (nhánh `feat/APP-01-android-ui`) | Code chưa vào `main` thì cả nhóm chưa dùng được | Merge trước PR 2 | ok (duyệt miệng 24/10, Quang chuyển lời). Hai nhánh gộp thành PR #46 (`feat/APP-02-camera-mic-scaffold` → `main`), chờ trưởng nhóm merge |
| 2 | Duyệt và merge PR camera/mic/API (nhánh `feat/APP-02-camera-mic-scaffold`) | Đã chạy hết luồng với API mock, 40 test qua, có CI Android | Merge sau PR 1 | ok (duyệt miệng 24/10, Quang chuyển lời). Xem câu 1 |

## B. Đang chặn app

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 3 | **Q3 · Hợp đồng LIVE-01**: đường chấm sáng, thứ tự quay đầu | Chưa có trong `session.schema.json`; app đang tự random trên máy | `Challenge` thêm `turn_order` (ví dụ `["left","right"]`) và `dot_path: [{t_ms, x, y}]` (x, y trong 0–1 theo màn hình). `Signals` thêm `dot_events: [{index, x, y, painted_at}]`, cùng đồng hồ với `color_events`. M5 làm PR `[contract]` | ok (duyệt miệng 24/10, Quang chuyển lời). M5 làm PR `[contract]` LIVE-01; app nối khi PR vào `main` |
| 4 | **Q4 · Endpoint OTP và CCCD** (FLOW-02, FLOW-03) | Chưa có trong `openapi.json`; app chỉ lưu dữ liệu trên máy | OTP: `POST /v1/sessions/{id}/otp` gửi `{phone}`, rồi `POST .../otp/verify` gửi `{code}`; trả `pass`/`retry` + `attempts_left`. CCCD: `POST .../id-card`, multipart `front`, `back`, `qr`; trả các trường đã đọc (họ tên, số CCCD, ngày sinh, giới tính, địa chỉ) | ok (duyệt miệng 24/10, Quang chuyển lời). Server: OTP thuộc FLOW-02 (M2), CCCD thuộc FLOW-03 (M1); làm theo đúng hình đề xuất |
| 5 | **Q5 · Đọc câu luôn hay chỉ khi server yêu cầu** | ADR-0016 (22/10) ghi luôn đọc; API hiện chỉ cho đọc khi `finalize` trả `voice_challenge` | Chốt một cách. App đang theo API; đổi thì app sửa 1 dòng, server phải đổi luồng | ok (duyệt miệng 24/10, Quang chuyển lời). Chốt: giữ như API hiện tại, chỉ đọc câu khi `finalize` trả `voice_challenge` (Quang chốt 24/10). ADR-0016 cần ghi lại cho khớp. **Cập nhật 24/10 chiều:** theo #49 (FLOW-01), luồng `onboarding`/`recovery` luôn đọc câu; luồng cũ không gửi `purpose` mới chỉ đọc khi server yêu cầu. App đã chuyển sang `purpose` nên giờ luôn đọc câu khi đăng ký |

## C. Tài liệu (luật 7: chỉ trưởng nhóm sửa ADR và hợp đồng)

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 6 | **Q1 · Video MP4 hay WebM** | ADR-0017 §3 ghi WebM; app Android quay ra MP4; server đã nhận `.mp4` (`services/api/.../storage.py`) | Sửa ADR-0017: "WebM trên web, MP4 trên app" | ok (duyệt miệng 24/10, Quang chuyển lời). Đã sửa ADR-0017 §3 |
| 7 | **Q2 · ML Kit hay MediaPipe trên app** | ADR-0014 để ngỏ | ML Kit để căn mặt, đo góc quay đầu, đọc QR (mống mắt do server dò, LIVE-02). Ghi vào ADR-0014 | ok (duyệt miệng 24/10, Quang chuyển lời). Đã ghi vào ADR-0014 mục 2, 3 |
| 8 | **Q6 · Mô tả `frame_times`/`painted_at` cho app** | Schema đang mô tả theo web (`performance.now()`, `requestVideoFrameCallback`) | Giữ tên trường; app dùng đồng hồ `elapsedRealtime` (ms), ghi rõ ở `client_quality.clock`. Sửa phần mô tả schema bằng một PR `[contract]` nhỏ | ok (duyệt miệng 24/10, Quang chuyển lời). PR `[contract]` nhỏ, chỉ sửa mô tả: PR #47 |

## D. Cần nhóm thống nhất

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 9 | **CamProbe trên máy ảo** | Server coi mọi cờ trong `api_tamper_flags` là không đạt; app gắn `android:emulator` khi chạy trên máy ảo | Chấp nhận: demo với mô hình thật chạy trên điện thoại thật; máy ảo chỉ dùng với API mock | ok (duyệt miệng 24/10, Quang chuyển lời). Máy ảo chỉ dùng với API mock; demo mô hình thật trên điện thoại thật |
| 10 | **Định nghĩa `region_means`** | App đo vùng da theo tỉ lệ hộp mặt ML Kit; web đo theo điểm mốc MediaPipe | PRES-02 chốt một định nghĩa. Nếu theo web, app chuyển phần đo vùng sang MediaPipe | ok (duyệt miệng 24/10, Quang chuyển lời). PRES-02 (M3) chốt định nghĩa |

## E. Người và máy

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 11 | **Giao APP-02/03/04 cho anh Lý** | Backlog đang ghi "Ngọc Quang+Claude (khung), Lý Anh Quân" | Anh Lý làm tiếp trên khung có sẵn | Không chia: Ngọc Quang+Claude làm tiếp APP-02/03/04 (Quang quyết 24/10) |
| 12 | **Điện thoại thật + cloudflared** | Chưa thử trên máy thật; bản release chỉ gọi HTTPS | Chọn người có máy Android 10+, cài `app-arm64-v8a-release.apk` (22 MB). Cần địa chỉ cloudflared tới máy demo để build | ok (duyệt miệng 24/10, Quang chuyển lời). Còn chờ chọn người có máy và địa chỉ cloudflared |
| 13 | **Khóa ký app** | Bản release đang ký tạm bằng khóa debug | Nộp bài dùng khóa debug là đủ, hay cần tạo khóa riêng? | ok (duyệt miệng 24/10, Quang chuyển lời). Nộp bài dùng khóa debug |

## F. Sau lần duyệt 24/10

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 14 | **Người không xem được màn nháy màu** (nút "Bỏ qua nháy màu") | Trước đây nút này bỏ luôn phần khuôn mặt. Giờ app dừng và hiện màn "Cần xác minh theo cách khác" (mời liên hệ ngân hàng). **Chưa gửi gì lên server**, nên không có hồ sơ nào trong bàn duyệt | Cần endpoint hoặc trạng thái để server mở ca duyệt thủ công (ví dụ `POST .../finalize` kèm `skip_flash: true` → `review`). Tạm thời giữ cách hiện tại | ok (duyệt miệng 24/10, Quang chuyển lời). Tạm giữ màn "Cần xác minh theo cách khác" |
| 15 | **Tiêu chí "Build được APK trên máy Windows"** (E9, APP-01) | Duyệt yêu cầu bỏ tích nếu chưa build thật | Giữ tích: đã build `testDebugUnitTest assembleDebug assembleRelease` trên Windows 11 (JDK 17, Android SDK 35), README có bước cài Android Studio/SDK. Chi tiết trong bàn giao | ok (duyệt miệng 24/10, Quang chuyển lời). Giữ dấu tích |

| 16 | **Độ lệch giữa video và WAV ở `/voice`** (VOICE-05, M4) | App quay MP4 và ghi WAV cùng lúc: WAV chỉ bắt đầu khi video đã có khung hình đầu. Trên máy ảo, video vẫn bắt đầu trước WAV khoảng 0,57–0,72 s (đo 2 lượt), và app chưa có chỗ gửi con số này | Thêm trường multipart `audio_offset_ms` vào `/voice` (thời điểm WAV bắt đầu, tính từ khung hình đầu của video), bằng một PR `[contract]`. Nếu chưa thêm, SyncNet nên dò độ lệch trong khoảng ±1 s | ok (duyệt miệng 24/10, Quang chuyển lời). PR `[contract]` thêm `audio_offset_ms`: PR #47; app đã gửi trường này |
| 17 | **Bàn duyệt chưa xem được media app gửi** (REV, PLAT) | Đã kiểm ca `voice_clone` từ app (24/10, API mock): ca có trong `GET /v1/review/cases`, nhưng (a) `media` thiếu `voice_video`, vì enum `MediaRef.kind` trong `review.schema.json` chưa có; (b) mọi URL `/media/{session}/…` trả 404, vì API chưa có route phát media; (c) web `/review` mới là khung trống | Thêm `voice_video` vào `MediaRef.kind` bằng PR `[contract]` và vào `_open_case` (`session_flow.py`); thêm route media cho nhân viên (có xác thực). Ai làm REV-02 nhận | ok (duyệt miệng 24/10, Quang chuyển lời). Người làm REV-02 (M2) nhận |

## G. Khi làm câu 3 (LIVE-01) và câu 4 (OTP, CCCD), 24/10

Đang làm ở nhánh `feat/APP-contract-clock-voice-offset` (PR #47), chưa commit. Các câu dưới đây cần trưởng nhóm trả lời trước khi đẩy lên. Câu 18–20 quan trọng nhất.

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 18 | **Thêm endpoint cấp thử thách mới** `POST /v1/sessions/{id}/challenge` | OTP và CCCD nằm trong phiên (câu 4), nhưng token chỉ sống 5 phút và thử thách màu 120 giây. Làm xong bước A thì thử thách đã hết hạn | Endpoint trả thử thách mới và gia hạn token, phiên dài tối đa 15 phút (phần gia hạn của LIVE-06, theo ADR-0017 §2). Dữ liệu mặt/giọng của lượt cũ bị bỏ; số lần chụp lại đã dùng vẫn giữ. App gọi khi bắt đầu phần khuôn mặt và khi làm lại sau gián đoạn (thay cho việc tạo phiên mới như hiện nay) | ok (duyệt 24/10, Quang chuyển lời) |
| 19 | **Làm thay task của người khác** | LIVE-01 là của M5, FLOW-02 (OTP) của M2; FLOW-03 (CCCD) là của M1 | Quang+Claude làm phần hợp đồng và server của LIVE-01, FLOW-02, FLOW-03. Nhờ M5 và M2 báo nếu đã bắt đầu, để khỏi làm trùng | ok (duyệt 24/10, Quang chuyển lời) |
| 20 | **Gộp vào PR #47 hay tách PR** | Mỗi PR hợp đồng đều sinh lại `openapi.json`; nhiều PR song song sẽ xung đột | Gộp câu 3, 4, 18 vào #47 rồi duyệt một lần. Nếu muốn merge #47 ngay thì mở PR mới | ok (duyệt 24/10, Quang chuyển lời) |
| 21 | **Thông số thử thách** (M3 làm LIVE-02 cần đồng ý) | Server sinh, app hiện, server chấm theo đúng các con số này | Chấm sáng: 7 điểm, mỗi điểm 1 giây (khoảng 6 giây), cách mép 15%, hai điểm liền nhau cách nhau ít nhất 25% màn hình. Quay đầu: 2 bước, mỗi bên một lần, thứ tự ngẫu nhiên (`["left","right"]` hoặc ngược lại) | ok (duyệt 24/10, Quang chuyển lời) |
| 22 | **OTP mô phỏng trả mã trong phản hồi** (`simulated_sms`) | App cần nội dung để hiện khung "SMS mô phỏng" (FLOW-02) | Chỉ kênh mô phỏng (bản demo) trả trường này; kênh SMS thật không bao giờ trả. Mã lưu dạng băm, hạn 2 phút, sai 5 lần thì khóa, dùng một lần | ok (duyệt 24/10, Quang chuyển lời) |
| 23 | **Phạm vi CCCD đợt này** | Task card FLOW-03 còn ba việc chưa làm | Server dùng chuỗi QR do app gửi (ML Kit), chưa tự đọc QR từ ảnh (OpenCV chỉ là thư viện tùy chọn). Chưa cắt chân dung bằng SCRFD. Chưa kiểm "đã đăng ký", mới lưu HMAC số CCCD. Ba việc này làm sau | ok (duyệt 24/10, Quang chuyển lời) |
| 24 | **Người dùng sửa thông tin khác QR** | Task card FLOW-03: sửa khác QR thì gắn cờ cho nhân viên duyệt. Đề xuất câu 4 chưa có chỗ gửi thông tin đã sửa | Thêm trường tùy chọn `confirmed_fields` khi gửi CCCD (hoặc một endpoint xác nhận riêng); server so với QR, khác thì ghi chú cho ca duyệt | ok (duyệt 24/10, Quang chuyển lời) |
| 25 | **Khóa `ID_HMAC_KEY`** | Dùng để băm số điện thoại và số CCCD | Code có giá trị mặc định chỉ để chạy dev. Máy demo đặt biến môi trường; trưởng nhóm giữ khóa | ok (duyệt 24/10, Quang chuyển lời) |
| 26 | **ADR-0016 lệch với câu 5** | ADR-0016 ghi "luôn đọc câu"; câu 5 đã chốt "chỉ đọc khi server yêu cầu" | Trưởng nhóm sửa ADR-0016 cho khớp (luật 7: chỉ trưởng nhóm sửa ADR) | ok (duyệt 24/10, Quang chuyển lời) |

## H. Luồng eKYC gọn (bản vẽ Figma "Đề xuất · Luồng gọn", 24/10)

Quang đã duyệt phần app tự làm được: gộp điều khoản và đồng ý, bỏ màn Giới thiệu và Xin quyền, CCCD tự chụp 2 mặt (dừng 1 nhịp sau mỗi mặt, 1 màn xem lại cả 2 mặt), OTP tự điền và vẫn gõ tay được, màn xác nhận thông tin dời ra sau phần khuôn mặt. Các câu dưới đây đụng server hoặc chính sách, **app chưa làm**, giữ nguyên hành vi hiện tại tới khi có trả lời.

| # | Câu hỏi | Vì sao cần | Đề xuất | Trả lời |
|---|---|---|---|---|
| 27 | **Bỏ số điện thoại và OTP khi app ngân hàng đã xác minh số** | Người dùng đã đăng nhập app ngân hàng bằng số đó; gõ lại số và OTP là 2 màn thừa | App ngân hàng truyền số đã xác minh khi mở VeriClue; bỏ 2 màn này. Server không bắt OTP trước `finalize` nên không phải sửa code, nhưng đây là chính sách của FLOW-02 (M2) | |
| 28 | **Gộp màn "Chuẩn bị quay mặt" vào màn căn mặt** | Cảnh báo nhạy cảm ánh sáng đang chiếm cả một màn riêng | Cảnh báo thành 1 dòng trên màn căn mặt, người dùng vẫn có nút "Bỏ qua nháy màu" (câu 14). Cần chắc 1 dòng là đủ về mặt an toàn cho người dễ lên cơn động kinh | |
| 29 | **Đọc câu chỉ khi server yêu cầu (cả khi đăng ký)** | Từ #49 (FLOW-01), phiên `onboarding`/`recovery` luôn có câu đọc (`session_flow.py`), khớp ADR-0016. Câu 5 và 26 trước đó chốt ngược lại | Vẫn mở. Nếu chốt "chỉ khi cần" thì server đổi luồng `onboarding` và ADR-0016 phải sửa; app chỉ đổi vài dòng. Tạm giữ như #49: đăng ký luôn đọc câu | |
| 30 | **Màn xác nhận thông tin dời ra sau phần khuôn mặt** | Người dùng làm phần mặt liền sau phần CCCD; thông tin chỉ đọc lại một lần trước khi gửi | **Đã đổi 25/10 (Quang chốt):** app giữ video trên máy, người dùng bấm "Thông tin đúng" xong mới gửi media → signals → `finalize`. Không gửi video song song nữa, vì server nhánh `feat/FLOW-05-identity-lab` (runbook `docs/runbooks/identity-integration.md`) trả 409 `step_not_allowed` cho `id-card/confirm` và cho ảnh CCCD mới khi phiên đã nhận media. Quá 120 giây (thử thách màu hết hạn) thì app cho làm lại riêng phần mặt với thử thách mới (đã thử trên máy ảo 25/10). Báo để người làm FLOW-03/FLOW-05 biết thứ tự mới | |

Chi tiết kỹ thuật: [`plan-camera-mic.md`](plan-camera-mic.md) (mục 9 và 11), [`../README.md`](../README.md).
