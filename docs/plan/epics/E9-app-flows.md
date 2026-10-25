# E9 — App Android, ba luồng eKYC, riêng tư và bảo mật (FLOW, SEC, APP)

> **Mục tiêu epic:** người dân dùng **app Android** để đăng ký, đăng nhập lại và khôi phục tài khoản theo ADR-0013. Mọi quyết định do server đưa ra. Dữ liệu cá nhân được bảo vệ theo ADR-0013 mục 7.
> **Đọc chung:** ADR-0012, ADR-0013, ADR-0014, ADR-0015.
> **Không cần thu dữ liệu.** Ngưỡng là hằng số có tên trong code, chờ ROUT-03.

---

### FLOW-01 · Tham số `purpose` và luật quyết định theo luồng

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S1 | P0 | ROUT-02, PLAT-08 |

**Mục tiêu:** API và router phân biệt `onboarding`, `reauth`, `recovery`.

**Đầu ra:**
- Tạo phiên nhận `purpose`, `nonce` và ảnh tham chiếu (tùy chọn). Đây là PR gắn `[contract]`.
- Luật quyết định:
  - `onboarding` và `recovery`: luôn đọc câu; điểm mặt ≥ A thì dừng và chuyển xét duyệt.
  - `reauth`: không có thử thách mặc định; điểm lưng chừng thì leo thang sang đọc câu ngẫu nhiên; nghi rõ thì trả `deny`; khóa thiết bị không hợp lệ thì trả `recovery_required`. Người dùng chỉ thấy "Xác thực không thành công, vui lòng thử lại sau".
- VeriClue là eKYC dùng chung: không có logic riêng của ngành (giao dịch, số tiền, hạn mức) — ADR-0013 §Phạm vi.

**Tiêu chí hoàn thành:**
- [x] Test cho từng `purpose`. Không có đường nào ra `pass` khi module bắt buộc lỗi.
- [x] Hợp đồng, API và type web khớp nhau (`gen_openapi --check`).

**Cập nhật 24/10 — nền backend (`doing`):** Có body opt-in `purpose`/`nonce`/
`reference_image_id`, chính sách theo luồng và mock xuyên suốt. Tham chiếu mới chỉ
là mã nối cho FLOW-03/05; reauth chưa có SEC-02 nên trả `recovery_required`, không
nhận cờ xác minh thiết bị từ client. Real/mixed bị chặn 503 cho luồng mới cho tới
khi có đủ bộ kiểm chứng. ADR-0016 cấp câu đọc trước để client thu âm trong lúc chấm
mặt; backend hiện nhận voice sau finalize. Không đánh dấu hoàn thành toàn bộ luồng.
Chi tiết: `docs/architecture/dynamic-session-api.md`.

---

### FLOW-02 · OTP mô phỏng

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S1 | P0 | PLAT-05 |

**Mục tiêu:** xác minh số điện thoại ở bước A2 (đăng ký) và K1 (khôi phục).

**Đầu ra:**
- Server sinh mã 6 số, hạn 2 phút. Sai 5 lần thì khóa. Lưu mã dạng băm.
- App hiện khung **"SMS mô phỏng"**. Kênh gửi đặt sau một giao diện chung, để sau này cắm nhà cung cấp SMS thật.

**Tiêu chí hoàn thành:**
- [x] Test các trường hợp: hết hạn, sai quá số lần, dùng lại mã (`services/api/tests/test_identity_steps.py`).

---

### FLOW-03 · Chụp CCCD, đọc QR, cắt chân dung, kiểm CCCD đã đăng ký

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S1 | P0 | PLAT-05, FACE-01 |

**Mục tiêu:** làm bước A3–A4 của ADR-0013.

**Đầu ra:**
- App chụp mặt trước và mặt sau bằng camera sau, có khung 4 góc và kiểm độ nét, độ lóa.
- Server:
  - đọc QR (OpenCV hoặc ZXing);
  - kiểm định dạng;
  - cắt ảnh chân dung bằng SCRFD để làm ảnh tham chiếu;
  - **HMAC số CCCD** để kiểm "đã đăng ký chưa".
- Màn hình xác nhận thông tin. Nếu người dùng sửa khác với QR thì gắn cờ cho nhân viên duyệt.

**Tiêu chí hoàn thành:**
- [ ] Test với ảnh thẻ tổng hợp. Không commit ảnh CCCD thật.
- [ ] Phát hiện thẻ giả nằm **ngoài phạm vi**; ghi rõ là giới hạn.

---

### FLOW-04 · Thử thách quay đầu ngẫu nhiên

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 (+M3) | 1 | S1 | P0 | CAP-06 |

**Mục tiêu:** làm bước B3 và ADR-0013 mục 6.

**Đầu ra:**
- Server sinh thứ tự ngẫu nhiên trong {trái, phải, giữa}, hạn khoảng 8 giây.
- App hiện mũi tên hướng dẫn (dùng MediaPipe) và quay video.
- Server tự đo góc, kiểm thứ tự và hạn, kiểm "mặt phẳng hay 3D", rồi đưa các khung nghiêng cho GenD.
- Sai thứ tự hoặc quá hạn thì cho làm lại 1 lần.

**Tiêu chí hoàn thành:**
- [x] Test bằng chuỗi góc tổng hợp: đúng/sai thứ tự, thiếu bước, quá hạn, thiếu dữ liệu và thiếu tư thế trung tính.
- [x] Chọn ba khung từ video theo timestamp server, kiểm lại tư thế trên đúng pixel, so mặt trong RAM; lỗi/thiếu/trùng khung không được đạt.
- [x] Đưa đúng ba khung đã chọn vào GenD trong RAM; trả điểm deepfake riêng, version lấy mẫu riêng, không dùng nhầm calibrator video cũ.
- [x] Tùy chọn FS-VFM-L FAS trên cùng khung RAM; nạp checkpoint gốc có kiểm SHA, điểm PAD thô riêng, không dùng ngưỡng cũ hay thay MiniFASNet của API.
- [ ] Test mặt phẳng (biến đổi homography) và kiểm chứng chiều sâu vật lý.

**Lát cắt backend 24/10 (Codex, doing):** `head_turn` dùng reader MediaPipe,
chỉ kiểm chuyển động/thứ tự/thời gian từ video với lịch server gắn phiên/lượt.
Lịch hiện hành 6 giây theo LIVE-01; các hằng góc/giữ tư thế là thử nghiệm.
Đã có chuỗi offline lấy ảnh chính diện/nghiêng trong RAM cho LVFace và GenD
(bật tùy chọn), và PAD FS-VFM-L FAS FP32. PAD dùng SCRFD thay MTCNN, chưa có
kiểm chứng tương đương/hiệu chỉnh trên dữ liệu thật. Chưa kiểm 3D, chưa nối quyết định API/retry hay sửa UI. Gate pass của module
chỉ nói chuyển động phù hợp, luôn ghi `depth_verified=false`.
CAP-06 còn phụ thuộc cho toàn luồng; diagnostic độc lập không cần UI đó.
Xem [`head-and-match.md`](../../architecture/head-and-match.md).

---

### FLOW-05 · So mặt 1:1 (LVFace-B) và mẫu khuôn mặt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | S1 | P0 | FLOW-03, FACE-01 |

**Mục tiêu:** trả lời câu ⑤ của ADR-0013.

**Đầu ra:**
- Module `face_match` dùng LVFace-B ONNX + SCRFD dùng chung theo lựa chọn mô hình trong phiên làm việc 24/10. Manifest pin revision/SHA và giấy phép trọng số nghiên cứu phi thương mại; không tự chuyển sang mô hình dự phòng.
- So mặt người dùng với ảnh tham chiếu (ảnh CCCD hoặc mẫu đã lưu).
- Mẫu khuôn mặt lưu dạng vector đặc trưng đã mã hóa; bản demo tự xóa sau 24 giờ.
- Ngưỡng chọn trên các cặp vn_celeb, chia theo người.
- So cùng khuôn mặt giữa các bước (ADR-0013 nguyên tắc 4).

**Tiêu chí hoàn thành:**
- [x] Wrapper, mock, registry và hợp đồng; chuẩn hóa RGB/112/[-1,1], so tham chiếu và mọi cặp giữa ba ảnh.
- [x] Thiếu ngưỡng/ảnh, nhiều mặt hoặc artifact sai phiên bản không được đạt; không lưu embedding.
- [ ] Đo VRAM khi chạy cùng bộ mô hình MVP.
- [ ] Số liệu ngưỡng chạy ra từ code trong repo.
- [ ] Nối FLOW-03/API và vòng đời mẫu mã hóa/xóa 24 giờ.

**Lát cắt backend 24/10 (Codex, doing):** diagnostic offline qua `eval.face_match`.
`eval.video_face_match` nối head_turn → chọn khung và kiểm lại tư thế → LVFace,
không nhận nhãn góc/ảnh query từ client trong chuỗi này, không ghi khung ra đĩa.
Ngưỡng không có mặc định: thiếu artifact `calib_ltt` đúng version thì
`degraded/unclear`, dù cosine cao. Embedding chỉ nằm trong RAM. Chưa kiểm chứng
độ chính xác trên người thật hay ảnh CCCD. Tư thế ảnh được kiểm lại bằng ước
lượng MediaPipe, chưa nghiệm thu quy ước góc trên điện thoại hay chiều sâu.
FLOW-03 còn phụ thuộc cho tích hợp toàn luồng; wrapper nhận ảnh
chân dung tham chiếu đã cắt do server quản lý. Xem
[`head-and-match.md`](../../architecture/head-and-match.md).

---

### SEC-01 · Riêng tư: khóa theo phiên, che dữ liệu, nhật ký truy cập

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 1,5 | S1 | P0 | REV-01, PLAT-05 |

**Mục tiêu:** làm A3, A4, A5, A6 của ADR-0013 mục 7.

**Đầu ra:**
- Mỗi phiên mã hóa bằng một khóa riêng; xóa dữ liệu bằng cách hủy khóa.
- HMAC số CCCD với khóa bí mật.
- Bàn duyệt che CCCD và ngày sinh; mỗi lần mở xem đầy đủ đều được ghi.
- Nhật ký "ai đã xem hồ sơ" dùng chuỗi băm.
- Xóa EXIF của ảnh tải lên.

**Tiêu chí hoàn thành:**
- [ ] Test: hủy khóa thì không đọc lại được dữ liệu; nhật ký không sửa được.

---

### SEC-02 ★ · Khóa thiết bị, ký media, mã phiên dùng một lần

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (+M1) | 1 | S2 | P0 | APP-01, PLAT-06 |

**Mục tiêu:** làm B4, B6 của ADR-0013 mục 7 và bước L0 của luồng đăng nhập lại.

**Đầu ra:**
- App tạo khóa trong Android Keystore và gửi khóa công khai lên lúc ghi danh.
- App ký `hash(media) || nonce`.
- Server kiểm chữ ký và đánh dấu nonce đã dùng (nullifier).

**Tiêu chí hoàn thành:**
- [ ] Test: dùng lại nonce, chữ ký sai, media bị đổi sau khi ký.

---

### APP-01 ★ · App Kotlin: khung, API qua HTTPS, điều hướng 3 luồng

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S1 | P0 | PLAT-04 |

**Mục tiêu:** dựng bộ khung app Android native cho bản demo (ADR-0014).

**Đầu ra:**
- `apps/android/` dùng Kotlin, Jetpack Compose, minSdk 29 (Android 10).
- Khung lấy từ eKYC-system (MIT): giữ dòng giấy phép, ghi `third_party/README.md`.
- API client sinh từ `openapi.json`.
- Kết nối HTTPS tới máy demo; có hướng dẫn thiết lập chứng chỉ.
- Điều hướng: đăng ký, đăng nhập lại, khôi phục (ADR-0013).
- Chỉ hiện `pass`, `retry`, `review`, `voice_challenge` và thông báo "Xác thực không thành công, vui lòng thử lại sau" khi `deny`.

**Tiêu chí hoàn thành:**
- [x] Build được APK bằng Gradle trên máy Windows; README có các bước cài Android Studio/SDK.
- [ ] Tạo phiên và nhận kết quả từ API thật trên điện thoại thật.
- [ ] CI không bắt buộc build Android ở bước này; ghi rõ trong PR.

---

### APP-02 ★ · App: chụp mặt, quay 3 giây, quay đầu ngẫu nhiên

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 2 | S1–S2 | P0 | APP-01 |

**Mục tiêu:** làm giai đoạn B của ADR-0013 trên app.

**Đầu ra:**
- CameraX dùng camera trước, căn khung và gợi ý chất lượng bằng ML Kit hoặc MediaPipe.
- Chụp ảnh và quay 3 giây trung tính; tải lên dần.
- Quay đầu theo thứ tự server ra (phần server ở FLOW-04), có mũi tên hướng dẫn.
- Kiểm camera ảo bản native: phát hiện root hoặc hook ở mức cơ bản; gửi tín hiệu lên server.
- Camera không tắt cho tới bước đọc câu.

**Tiêu chí hoàn thành:**
- [ ] Đi hết giai đoạn B trên điện thoại thật; server chấm bằng mô hình thật.

---

### APP-03 · App: ghi âm đọc câu (WAV 16 kHz)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P0 | APP-01 |

**Mục tiêu:** làm giai đoạn C của ADR-0013 và bước leo thang L3.

**Đầu ra:**
- AudioRecord PCM 16-bit, mono, 16 kHz, ghi ra WAV. Tối đa khoảng 8 giây.
- Quay video kèm track âm thanh trong cùng một bản ghi (MediaRecorder) để khớp môi có chung đồng hồ (ADR-0012 mục 6).

**Tiêu chí hoàn thành:**
- [ ] Server đọc được WAV, chấm PhoWhisper và AntiDeepfake trên điện thoại thật.

---

### APP-04 · App: OTP, chụp CCCD, xác nhận thông tin

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (+M1) | 1,5 | S1–S2 | P0 | APP-01 |

**Mục tiêu:** làm giai đoạn A của ADR-0013. Phần server nằm ở FLOW-02 và FLOW-03.

**Đầu ra:**
- Màn hình số điện thoại và OTP, có khung "SMS mô phỏng".
- Chụp CCCD hai mặt bằng camera sau, khung 4 góc. Đọc thử QR trên máy chỉ để báo người dùng chụp lại khi không đọc được.
- Màn hình xác nhận thông tin.

**Tiêu chí hoàn thành:**
- [ ] Đi hết giai đoạn A trên điện thoại thật.

---

## App iOS (bản thêm, ADR-0014 cập nhật 24/10)

Kế hoạch chi tiết từng bước: [`apps/ios/docs/plan-ios.md`](../../../apps/ios/docs/plan-ios.md). App Android (APP-01..04) là đặc tả hành vi và câu chữ.

### IOS-01 · App iOS: khung SwiftUI, theme, toàn bộ màn, điều hướng 3 luồng, chế độ demo

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 2 | S2 | P1 | APP-01 |

**Mục tiêu:** Có đủ màn và điều hướng như app Android, chạy demo không cần server.

**Đầu ra:**
- Project Xcode ở `apps/ios/`, iOS 16+, SwiftUI; theme và font theo Android/Figma.
- Đủ route như Android, thêm `deny`, `recovery_required`; màn "Xem tất cả màn" chỉ ở Debug.

**Tiêu chí hoàn thành:**
- [x] Đi hết luồng demo của 3 `purpose` trên Simulator.

---

### IOS-02 · App iOS: client API, LiveFlow, FlowRules + test

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S2 | P1 | FLOW-01 |

**Mục tiêu:** Gọi đúng API phiên (FLOW-01 dynamic, OTP, CCCD, `/challenge`, `/voice`) như `LiveFlow.kt`.

**Đầu ra:**
- `Models.swift`, `SessionApi.swift` (URLSession async/await, multipart), `LiveFlow.swift`, `FlowRules.swift`.
- Port test `LiveFlowTest`, `LiveFlowRetryTest`, `LiveFlowStageATest`, `FlowRulesTest`; giải mã các ví dụ trong `packages/contracts/examples`.

**Tiêu chí hoàn thành:**
- [ ] `xcodebuild test` xanh, không test nào gọi mạng thật.

---

### IOS-03 · App iOS: OTP, chụp CCCD (nét, lóa, QR bằng Vision), xác nhận thông tin

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S2 | P1 | IOS-01, IOS-02, FLOW-02, FLOW-03 |

**Mục tiêu:** Giai đoạn A chạy với server như app Android.

**Đầu ra:**
- Màn số điện thoại, OTP (SMS mô phỏng), camera sau chụp hai mặt, xem lại, xác nhận/sửa thông tin.

**Tiêu chí hoàn thành:**
- [ ] Trên iPhone thật với API mock: OTP sai/đúng đúng câu; server nhận 2 ảnh CCCD và trả thông tin từ QR.

---

### IOS-04 · App iOS: camera trước, lịch phần mặt một video (màu, chấm, quay đầu), signals, camprobe

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 3 | S2 | P1 | IOS-02, LIVE-01 |

**Mục tiêu:** Phần mặt chạy đúng lịch `challenge.dynamic`, một video liên tục, như `FaceTimeline.kt`.

**Đầu ra:**
- AVCaptureSession + AVAssetWriter (MP4 không lật), Vision dò mặt, khóa AE/AWB, `color_events`, `frame_times`, `camprobe` iOS.

**Tiêu chí hoàn thành:**
- [ ] Trên iPhone thật: `genuine` gửi đủ JPEG, MP4 (dài bằng lịch) và signals; `low_quality` ra chụp lại.

---

### IOS-05 · App iOS: đọc câu, WAV 16 kHz + MP4, audio_offset_ms

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P1 | IOS-04 |

**Mục tiêu:** Bước đọc câu như app Android (VOICE-05).

**Đầu ra:**
- `WavRecorder.swift` (AVAudioEngine → 16 kHz mono), video cùng lúc, `voice_challenge_id`, `audio_offset_ms`.

**Tiêu chí hoàn thành:**
- [ ] `voice_clone` → đọc câu → chờ duyệt; server lưu WAV và MP4.

---

### IOS-06 · App iOS: gián đoạn, thử lại khi mất mạng, xóa file tạm

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P1 | IOS-04 |

**Mục tiêu:** Hành vi khi gián đoạn và mất mạng giống Android (ADR-0017).

**Đầu ra:**
- Xuống nền khi đang quay → "Xác minh bị gián đoạn", lượt sau gọi `/challenge`; thử lại chỉ gửi phần chưa nhận; xóa file tạm.

**Tiêu chí hoàn thành:**
- [ ] Các mục tương ứng trong checklist mục 13 của `apps/ios/docs/plan-ios.md` đạt.

---

### IOS-07 · App iOS: bản Release HTTPS, đo trên máy thật, README, bàn giao

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P1 | IOS-03, IOS-05, IOS-06 |

**Mục tiêu:** Bản iOS demo được trên iPhone thật.

**Đầu ra:**
- Release chỉ HTTPS (cloudflared), ẩn nút debug; `apps/ios/README.md`; số đo thật trong bàn giao.

**Tiêu chí hoàn thành:**
- [ ] Checklist mục 13 của `apps/ios/docs/plan-ios.md` đạt; có bàn giao kèm số đo.

---

## Dynamic Liveness (ADR-0016)

> Server là trọng tài. Điện thoại chỉ quay, ký và gửi. Không tuyên bố "chặn 100 %" hay "đầu tiên". Lớp ① dùng ChromaPulse (CAP-04, PRES-02).

### LIVE-01 · Gói thử thách động theo phiên

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S2 | P0 | FLOW-01 |

**Mục tiêu:** mỗi phiên có một gói thử thách mới, chỉ dùng một lần.

**Đầu ra:**
- Server sinh bằng bộ sinh số ngẫu nhiên mật mã: chuỗi màu, đường chấm sáng (các điểm và thời gian), thứ tự quay đầu, câu đọc. Gói gắn với mã phiên và hết hạn theo ADR-0011.
- Hợp đồng API thêm gói thử thách. PR gắn `[contract]`.
- Router coi lớp nào thiếu hoặc lỗi là không đạt (luật 4).

**Tiêu chí hoàn thành:**
- [x] Test: hai phiên có gói/mã khác nhau; gửi lại cùng bước hoặc mã lượt cũ bị từ chối (409).
- [x] Hợp đồng, API và type web khớp nhau (`gen_openapi --check`).

**Cập nhật 24/10 — nền backend (`doing`):** Gói có 8 màu an toàn dùng chung,
đường chấm sáng 7 giây, thứ tự quay trái/phải rồi về giữa, câu đọc và mã lần đọc;
ràng buộc mã phiên và nonce. Media/signals/finalize/voice kiểm mã lượt hiện hành,
retry đổi gói, reread đổi câu và ID. Chưa có detector ánh mắt/quay đầu/so mặt
và chưa ký byte media; các luồng này chỉ mở mock, không cho chạy thật. Kiểm ID
không chứng minh chống phát lại video được gắn mã mới (LIVE-03/SEC-02).

---

### LIVE-02 · Chấm sáng và đo ánh mắt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 (+M1) | 1,5 | S2 | P0 | LIVE-01 |

**Mục tiêu:** lớp ② của thử thách động.

**Đầu ra:**
- Web hiện chấm sáng chạy theo đường trong gói thử thách, camera trước vẫn quay.
- Server dò mống mắt trên video (MediaPipe hoặc tương đương, giấy phép không GPL), dựng đường đi của mắt, so với đường của chấm (tương quan và độ trễ).
- Ngưỡng là hằng số có tên trong file mô-đun, chờ ROUT-03. Trả `ModuleResult` và có bản mock.

**Tiêu chí hoàn thành:**
- [x] Test bằng chuỗi điểm tổng hợp: khớp, lệch, đứng yên, đường của phiên khác.
- [x] Nối opt-in dò mắt với quay đầu/so mặt/GenD/PAD, cùng task MediaPipe;
  mắt hoặc đầu thiếu/lỗi thì chặn chấm ảnh. Có profile CPU riêng và CLI kiểm runtime.
- [x] Công cụ webcam lab riêng: preview/đo mắt và pose trực tiếp, tham chiếu RAM,
  AI ảnh đơn chạy nền, thử thách mắt/quay đầu cục bộ; không sửa UI sản phẩm.
- Backend diagnostic 24/10: reader MediaPipe/kiểm SHA, mắt tương đối và góc đầu
  ước lượng, đối chiếu hai trục/độ trễ, kiểm độ phủ và lỗi. Có mock + ModuleResult
  gaze_tracking; chưa tham gia router/full/MVP. Đường chấm server được sinh đủ
  biên độ hai trục; không sửa UI. Giữ doing vì chưa đo trên điện thoại thật và
  chưa hoàn tất tích hợp quyết định. Xem ml/src/vericlue_ml/presence/README.md.
- [ ] Đo trên điện thoại thật trong phòng sáng và phòng tối; ghi số mẫu vào bàn giao. Không đưa con số vào báo cáo nếu không chạy ra từ code.

---

### LIVE-03 · Ký media theo phiên trên web, chặn phát lại

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (+M1) | 1 | S2 | P0 | LIVE-01 |

**Mục tiêu:** video cũ hoặc quay lén không dùng lại được.

**Đầu ra:**
- Web tạo passkey (WebAuthn) cho thiết bị, ký `challenge` = băm(mã phiên ‖ gói thử thách ‖ băm media).
- Server kiểm chữ ký, mã phiên và băm media. Sai thì từ chối, ghi lý do cho bàn duyệt; người dân không thấy lý do.
- **Tải lên dần (ADR-0017):** video WebM chia đoạn, gửi trong lúc quay; mỗi đoạn ký, chuỗi chữ ký nối các đoạn với mã phiên. Gửi kèm ảnh tĩnh chất lượng cao cho ba góc mặt. Không nén mạnh tới mức mất chi tiết; đo dung lượng và thời gian tải trên 4G.
- Ghi rõ trong tài liệu: ký số chống phát lại và sửa giữa đường, **không** chống chèn luồng camera (việc của CamProbe và lớp ánh sáng).
- App native dùng SEC-02 (Keystore) cho cùng việc.

**Tiêu chí hoàn thành:**
- [ ] Test: dùng lại media phiên cũ, sửa media sau khi ký, chữ ký sai, mã phiên sai, thiếu hoặc đổi chỗ một đoạn video.

---

### LIVE-04 · Kháng lượng tử: đường truyền và chữ ký kết quả

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 1 | S2 | P0 | FLOW-01 |

**Mục tiêu:** dữ liệu sinh trắc không bị "ghi hôm nay, giải mã sau"; kết quả không bị làm giả kể cả khi có máy lượng tử.

**Đầu ra:**
- Kiểm và ghi lại: đường hầm Cloudflare và trình duyệt điện thoại có dùng trao đổi khóa lai ML-KEM không (ảnh chụp hoặc log làm bằng chứng).
- Kết quả trả cho bên tích hợp ký kép: chữ ký hiện tại và ML-DSA (FIPS 204) bằng liboqs (MIT). Ghi `third_party/README.md`.
- Khi trình bày gọi là "kháng lượng tử", không gọi là "máy tính lượng tử".

**Tiêu chí hoàn thành:**
- [ ] Test: kết quả bị sửa một byte thì kiểm ML-DSA thất bại; khóa sai thì thất bại.

---

### LIVE-05 · Giấy chứng nhận ZKP cho bên tích hợp

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 2,5 | S3 | P1 | LIVE-04 |

**Mục tiêu:** bên tích hợp biết "đã xác minh, trên 18 tuổi" mà không nhận video, ảnh hay số CCCD.

**Đầu ra:**
- VeriClue cấp giấy chứng nhận: từng thuộc tính được cam kết bằng hàm băm, ký ML-DSA.
- Bằng chứng zk-STARK cho câu "trên 18 tuổi" và "đã xác minh". Thư viện Apache/MIT (ví dụ RISC Zero, Winterfell); không dùng circom/snarkjs (GPL). Kiểm giấy phép trước khi chép.
- Tạo bằng chứng trên laptop demo là chấp nhận được; ghi rõ giới hạn.

**Tiêu chí hoàn thành:**
- [ ] Test: bằng chứng đúng thì qua; người dưới 18 tuổi hoặc bằng chứng bị sửa thì không qua.
- [ ] Nếu không kịp: đổi trạng thái `cut`, chuyển phần trình bày vào báo cáo như lộ trình.

---

### LIVE-06 · Gia hạn phiên khi gián đoạn, làm lại riêng phần khuôn mặt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 0,5 | S2 | P0 | LIVE-01 |

**Mục tiêu:** người dùng bị gián đoạn (cuộc gọi, chuyển ứng dụng) không phải làm lại từ đầu, mà không mở khe hở tráo người (ADR-0017 mục 2).

**Đầu ra:**
- Giai đoạn A: tự gia hạn mã truy cập khi quay lại, làm tiếp từ bước đang dở.
- Giai đoạn B, C: giữ kết quả giai đoạn A; phần khuôn mặt và câu đọc làm lại với gói thử thách mới, bỏ dữ liệu khuôn mặt của lần dở.
- Giới hạn tổng thời gian cho cả phiên (đề xuất 15 phút, chốt khi làm). Hợp đồng API đổi: PR gắn `[contract]`.

**Tiêu chí hoàn thành:**
- [ ] Test: gián đoạn ở từng bước A, B, C; quá giới hạn tổng; gói thử thách cũ bị từ chối sau khi làm lại.

---

### LIVE-07 · Thông báo làm lại theo hai loại

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 0,5 | S2 | P0 | LIVE-01 |

**Mục tiêu:** người thật biết chính xác cách sửa, kẻ gian không biết lớp kiểm tra nào đã bắt được họ (ADR-0017 mục 1).

**Đầu ra:**
- Bảng chữ hiển thị cho mọi tình huống làm lại: lỗi chất lượng báo cụ thể kèm cách sửa; lỗi thử thách chỉ hướng dẫn cách làm cho đúng.
- Nhắc chất lượng ngay trong lúc chụp; màn làm lại hiện số lần thử còn lại.

**Tiêu chí hoàn thành:**
- [ ] Không chữ nào chứa điểm số, "giả mạo", hay tên lớp kiểm tra (luật 3). Có test rà chữ hiển thị.
