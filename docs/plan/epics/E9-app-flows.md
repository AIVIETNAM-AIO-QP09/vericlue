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
  - `onboarding`: chỉ đọc câu khi điểm mặt lưng chừng (cập nhật 26/10, ADR-0016); `recovery`: luôn đọc câu; điểm mặt ≥ A thì dừng và chuyển xét duyệt.
  - `reauth`: không có thử thách mặc định; điểm lưng chừng thì leo thang sang đọc câu ngẫu nhiên; nghi rõ thì trả `deny`; khóa thiết bị không hợp lệ thì trả `recovery_required`. Người dùng chỉ thấy "Xác thực không thành công, vui lòng thử lại sau".
- VeriClue là eKYC dùng chung: không có logic riêng của ngành (giao dịch, số tiền, hạn mức) — ADR-0013 §Phạm vi.

**Tiêu chí hoàn thành:**
- [x] Test cho từng `purpose`. Không có đường nào ra `pass` khi module bắt buộc lỗi.
- [x] Hợp đồng, API và type web khớp nhau (`gen_openapi --check`).
- [x] Kết quả Ed25519 opt-in theo quyết định đã commit: phiên/nonce/purpose/bên nhận/hạn gắn server; mock/phiên cũ/thiếu bằng chứng không được ký. Client Android và verifier/CLI đã có; chưa nghiệm thu thật.

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
- [x] Bản sửa review PR #65: từ chối đổi thẻ sau media/signals/chấm mặt trước mọi ghi file;
  lỗi OCR/ghi file/commit DB không đổi ảnh hoặc thông tin đã xác nhận. Quét hoàn thành
  dùng tên file mới và hủy xác nhận cũ, kể cả trả `retry`.

**Cập nhật 25/10 — sửa review PR #65:** giữ cầu nối CCCD–selfie ngoài `reauth` để không
đổi policy FLOW-01; test cả mặt và giọng với runtime bật/tắt. Chưa hoàn thành nhận dạng
theo mẫu đăng ký/SEC-02 hoặc nghiệm thu Android. Chi tiết vận hành tại
[`identity-integration.md`](../../runbooks/identity-integration.md).

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
- [x] Wrapper, mock, registry và hợp đồng; chuẩn hóa RGB/112/[-1,1], so tham chiếu–chính diện; cosine giữa ba góc riêng.
- [x] API opt-in dùng LVFace-B thật qua orchestrator, preload/cache/deadline chung; không gọi AdaFace hoặc dùng ngưỡng cũ.
- [x] API opt-in chọn khung chính diện theo lịch server, kiểm tư thế trên pixel video; không fallback selfie khi thiếu/sai video. Mắt/quay đầu có cổng API riêng, reader dùng chung.
- [x] Thiếu ngưỡng/ảnh, nhiều mặt hoặc artifact sai phiên bản không được đạt; không đưa embedding vào ModuleResult/HTTP.
- [x] Nền lưu mẫu/tài khoản mã hóa, DEK độc lập phiên, unique HMAC CCCD/phiên nguồn, gắn public key đã ký, TTL 24 giờ và cleanup có test tổng hợp.
- [x] `face_continuity` mặt–giọng dùng chung LVFace, ba mẫu theo PTS/offset/WAV thật; protocol/ngưỡng riêng, API opt-in fail-closed, mock/CLI/test tổng hợp. Chưa hiệu chỉnh/đánh giá người thật.
- [x] Worker trích mẫu dùng chung slot/hàng đợi LVFace và lease, hook ghi danh onboarding opt-in cùng transaction quyết định; quá hạn/lỗi rollback, không mở real/mixed.
- [x] Receipt theo bearer phiên, client Android và worker so mẫu đã lưu cho reauth/recovery; protocol/ngưỡng riêng, không mở sinh trắc account-bound mock/real/mixed.
- [ ] Đo VRAM khi chạy cùng bộ mô hình MVP.
- [ ] Số liệu ngưỡng chạy ra từ code trong repo.
- [ ] Nghiệm thu toàn luồng FLOW-03/API và vòng đời mẫu mã hóa/xóa 24 giờ trên thiết bị thật.

**Cập nhật 25/10 (Codex, doing):** API opt-in `IDENTITY_LAB_URL` dùng LVFace-B
thật cho một selfie đầu tiên với ảnh mặt trước CCCD; OCR giữ runtime riêng.
Version `front-reference-v2` tách so CCCD–front khỏi cosine giữa các góc,
chặn artifact/kết quả AdaFace hoặc protocol cũ. `IDENTITY_FACE_FROM_VIDEO` đã
chọn/kiểm chính diện từ video trong API; chưa có ngưỡng thật, mặc định không đạt.
Nền ghi danh `AccountStore` có migration 0005 và contract template nội bộ;
`ACCOUNT_ENROLLMENT` đã nối worker và lời gọi sau pass onboarding, mặc định tắt.
Đã có receipt theo phiên và client; chưa nghiệm thu toàn luồng. Đã có `face_continuity` opt-in kiểm ba mẫu video
giọng với khung chính diện; cần artifact riêng, thiếu thì không được đạt/ghi
danh. Không cho mock/mixed tạo tài khoản. Xem
[`account-enrollment.md`](../../architecture/account-enrollment.md).

**Lát cắt backend 24/10:** diagnostic offline qua `eval.face_match`.
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

### FLOW-06 · Rà workflow mobile và bàn giao tích hợp riêng tư

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 0,5 | S2 | P0 | PLAT-05 |

**Mục tiêu:** theo yêu cầu sau merge PR #105, đối chiếu ba luồng với main,
trình bày phương án giảm thao tác và xác định việc cần nối ở app. Đây là bước
chuẩn bị để nhóm thống nhất workflow, không tự thay UI hoặc mở guard sinh trắc.

**Đầu ra:** `docs/architecture/project-workflow.md` và tài liệu bàn giao app.

- [x] Phân biệt rõ code hiện tại, đề xuất rút gọn và đường thật chưa nghiệm thu.
- [x] Ba luồng nêu việc người dùng/hệ thống làm, tham chiếu danh tính và lúc cần giọng.
- [x] Ghi thứ tự consent/API, rút lại, hết hạn, retry và phạm vi xóa; không tự gán quyền từ checkbox tùy chọn chưa có contract.
- [x] Có danh sách quyết định cần nhóm chốt, điểm nối app và checklist kiểm thử; không sửa UI/schema/ADR/ngưỡng.

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
- [x] Test: hủy khóa thì không đọc lại được dữ liệu; nhật ký không sửa được.

**Cập nhật 25/10 (Codex, review):** Có vault AES-GCM theo phiên, mã hóa snapshot/
media/kết quả/ghi chú, hủy wrapped DEK theo TTL và giữ tombstone. Native đọc qua
file giải mã có lease theo future, không xóa sớm khi HTTP timeout. Cờ opt-in không
tự chuyển kho cũ. Có credential nhân viên riêng, access audit chỉ ghi thêm, API
che CCCD/ngày sinh và thao tác reveal có nhật ký, loại EXIF ảnh; contract/type web
cập nhật, không sửa UI. Test dữ liệu tổng hợp bao gồm sửa tag/sai AAD/khóa, hủy
khóa, URL mã hóa, CORS và job trả muộn. Xem `session-privacy.md`. Chưa nghiệm thu
UI nhân viên, backup/KMS/crash cleanup hay vận hành production; không chứng nhận tuân thủ.

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
- [x] Test: dùng lại nonce, chữ ký sai, media bị đổi sau khi ký.
- [x] L0: khóa đã ghi danh, thử thách mới, claim DB một lần; sai khóa/phiên/hạn/replay không cấp device_verified.
- [x] Service khôi phục kiểm đúng số điện thoại/mẫu mặt đã lưu; thay khóa/thu hồi phiên cũ cùng transaction, test tổng hợp và cạnh tranh PostgreSQL.
- [ ] Nghiệm thu Keystore/account context/khôi phục toàn luồng trên điện thoại thật; kết quả có chữ ký cho bên tích hợp.

**Cập nhật 25/10 (Codex, doing):** Đã có ràng buộc public key P-256 theo phiên,
nonce server theo stage/lượt, ký hash byte/format/offset ở Android LiveFlow và
kiểm trước lưu file, claim nullifier bằng PK DB (migration 0004). Test giả lập
khóa thật: sửa byte, sai khóa/phiên/suffix/offset, replay, refresh/retry; mẫu
canonical/signature chung Python–Kotlin. Cờ mặc định tắt, không sửa UI.
**Bổ sung 26/10:** Đã có L0/receipt, service khôi phục/thu hồi và lớp API/flow
Android; không đổi UI, không cấp device_verified cho khóa tự khai. Chốt sinh
trắc thật/mixed và account-bound mock còn giữ, chưa nghiệm thu Keystore phần
cứng. Xem `media-proof.md` và `account-authentication.md`.

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
- [x] Trau chuốt UI 26/10: giữ Be Vietnam Pro; thang chữ, màu sáng/tối, phản hồi nút/OTP/CCCD/thành công, chuyển màn và rung nhẹ; có chính sách tắt chuyển động trang trí theo cài đặt máy.
- [x] So ảnh Paparazzi cho 10 màn yêu cầu ở cả sáng/tối; test tương phản (kể cả lúc nút chuyển màu), giảm chuyển động và `CitizenCopyTest`.
- [x] Áp hướng A · Tối giản ấm: nền trắng ngà, pill navy, Canvas CCCD, nội dung không đóng hộp, tấm đáy/số tài khoản mẫu; so ảnh sáng/tối và A1–A3 với thiết kế.
- [x] Tạo phiên và nhận kết quả từ API thật trên điện thoại thật. (27/10, Galaxy S24 FE, API mock qua `adb reverse`; bàn giao `2026-10-27-2000-app-01`)
- [x] CI chạy unit test và build Android. Kiểm thêm tại máy với `signedMedia=true`.
- [x] Client lưu receipt cùng alias Keystore; nhận receipt sau finalize không giọng;
  đăng nhập lại mở đúng khóa đã lưu; khôi phục tạo khóa mới và chỉ xóa khóa cũ sau
  ghi bền. Test hồi quy HTTP 409/503, mất khóa, hết hạn và lỗi lưu; chưa nghiệm thu
  tài khoản trên điện thoại thật vì server còn chặn sinh trắc account-bound (FLOW-05/SEC-02).

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
- [x] Đi hết giai đoạn A trên điện thoại thật. (27/10, Galaxy S24 FE, thẻ CCCD gắn chip; bàn giao `2026-10-27-2000-app-01`)

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

**Đồng bộ 28/10 (`review`):** đã gộp Terms/consent demo, bỏ ba route cũ, recovery
bỏ CCCD sau OTP và cập nhật Gallery. Checkbox trên thuộc baseline, không chứng
minh bản đồng bộ đã nghiệm thu. Confirm sau mặt đã chốt chặng 4 (148/148).
Theme ấm đã triển khai; lượt toàn bộ mới 159/159 bài đạt (186 lần thực thi),
Release không ký build được. Sau sửa demo binding/keypad/confirm, **lượt cuối
159/159 (186 lần thực thi) xanh**, 0 bỏ qua; 12 vòng Back Terms → Gallery và
OTP/confirm AX3 đã kiểm. Bundle `/tmp/vericlue-ios-theme-final-20261028.xcresult`.
Lịch sử lỗi vẫn nằm trong bàn giao. Sếp xác nhận iPhone bản mới nhất đạt cả
A/B/C/D: theme/Back/chữ lớn, CCCD, quay/confirm/offline/thứ tự API và dừng/dọn
file. Đây là xác nhận thủ công của sếp, không phải agent tự chạy thiết bị.
Chuyển review, còn PR; task chưa done/đã merge. Xem
[bàn giao theme](../../status/handoffs/2026-10-28-1608-ios-01-l-anh-qu-n-codex.md).

---

### IOS-02 · App iOS: client API, LiveFlow, FlowRules + test

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S2 | P1 | FLOW-01 |

**Mục tiêu:** Gọi đúng API phiên (FLOW-01 dynamic, OTP, CCCD, `/challenge`, `/voice`) như `LiveFlow.kt`.

**Đầu ra:**
- `Models.swift`, `SessionApi.swift` (URLSession async/await, multipart), `LiveFlow.swift`, `FlowRules.swift`.
- Port test `LiveFlowTest`, `LiveFlowRetryTest`, `LiveFlowStageATest`, `FlowRulesTest`; giải mã các ví dụ trong `packages/contracts/examples`.

**Bổ sung 28/10/2026 (`doing`):** chặng 0 đồng bộ Android đã khóa nền IOS-06
`6aef3ac` và nguồn `feat/APP-01-account-flow` tại `f034fa9`, tạo nhánh
`feat/IOS-02-android-alignment`. Receipt làm riêng trước, không ký media/device
proof; recovery bỏ CCCD là mục tiêu chặng sau. Chặng 1 đã nối model/GET/storage
receipt sau pass, thêm 19 hàm test với mock. Build test bundle Simulator và Release
iPhone không ký thành công. Một lượt test: unit/receipt xanh, tổng 123/124 đạt,
UI từng timeout đã kiểm lại riêng 1/1 xanh, không sửa assertion. Sếp xác nhận probe Keychain trên iPhone và giữ thành
công sau GET account 409 đạt; chưa kiểm chứng GET 200 receipt thật.
Xem [bảng đối chiếu và lệch contract/backend](../../../apps/ios/docs/android-alignment.md).
Checkbox test nền cũ bên dưới không chứng minh phần receipt mới đã được làm/test.
Xem [bàn giao receipt](../../status/handoffs/2026-10-28-0413-ios-02-l-anh-qu-n-codex.md).

**Rà cấu trúc 28/10:** chuyển model/client/multipart vào `Data/API`, theme vào
`UI/Theme`; tách `UI/App.swift`, `UI/AppRoutes.swift`, Gallery Debug và
`Flow/CaptureFlows.swift` khỏi navigation. Domain types chung ở `Flow/FlowTypes.swift`.
Nền đối chiếu mới là upstream/main `24895c3`; không merge main, không thay
capture/retry/receipt hay luật recovery/OTP riêng. Đây là refactor cấu trúc,
không phải hoàn tất confirm sau mặt hoặc theme mới. Kết quả build và giới hạn
ghi tại [tài liệu đồng bộ](../../../apps/ios/docs/android-alignment.md).

**Tiêu chí hoàn thành:**
- [x] `xcodebuild test` xanh, không test nào gọi mạng thật.

---

**Account parity theo yêu cầu sếp (cập nhật 29/10, chưa chốt toàn bộ):** đã nối
AccountBindingStore/AccountFlow, Auth/L0 và ký media/voice opt-in theo Android
`54acaad`, `SIGNED_MEDIA=NO` mặc định. Receipt+alias ghi nguyên tử; recovery lưu
bền trước xóa khóa cũ; lỗi metadata giữ pass, response trễ bị revoke. Giữ recovery
bỏ CCCD và tổng OTP sai/phiên. Suite binding 15/15 và protocol đã đạt trong các
lượt regression; lượt sau sửa hash/nút đạt 184/185, còn UI light AX3 Back, đã siết
đồng bộ đúng navigation bar và đang kiểm bản mới. Sếp xác nhận ký mặt/giọng có
biên nhận backend, checkpoint khóa thử qua đóng/mở, native OTP không auto verify
và rung đạt trên iPhone. SMS thật, binding/receipt/account-bound backend còn chờ.
Xem [binding](../../../apps/ios/docs/account-binding.md) và
[bàn giao 29/10](../../status/handoffs/2026-10-29-0134-ios-02-l-anh-qu-n-codex.md).

### IOS-03 · App iOS: OTP, chụp CCCD (nét, lóa, QR bằng Vision), xác nhận thông tin

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S2 | P1 | IOS-01, IOS-02, FLOW-02, FLOW-03 |

**Mục tiêu:** Giai đoạn A chạy với server như app Android.

**Đầu ra:**
- Màn số điện thoại, OTP (SMS mô phỏng), camera sau chụp hai mặt, xem lại, xác nhận/sửa thông tin.

**Tiêu chí hoàn thành:**
- [x] Trên iPhone thật với API mock: OTP sai/đúng đúng câu; server nhận 2 ảnh CCCD và trả thông tin từ QR.

Nghiệm thu thao tác do Lý Anh Quân xác nhận ngày 25/10/2026; Codex kiểm tra thêm hai JPEG và `id_edited` ở server local. Chi tiết, kết quả test và giới hạn nằm trong [bàn giao IOS-03](../../status/handoffs/2026-10-25-1004-ios-03-l-anh-qu-n-codex.md). Chưa commit/push/merge PR; không coi checkbox nghiệm thu là đã tích hợp vào main.

**Đồng bộ 28/10 (`review`):** chặng 2–3 thêm OTP tự điền không tự verify, auto/manual
CCCD có nội dung thẻ, pause, review hai mặt và retake giữ mặt còn lại. Sếp đã
xác nhận 4 ca camera/QR/retake/Home chặng 3 đạt. Chặng 4 đã nối giữ MP4 đã đóng
và binding phiên/challenge, confirm sau mặt rồi mới upload; thêm test thứ tự,
mạng/expiry/rotation/late reply/cleanup. Sếp xác nhận nhóm A/B/C/D; DB xác nhận
tên/ngày sửa, ISO và ID gốc khớp. Sau sửa ba lỗi, lượt toàn bộ cuối đạt 148/148,
0 lỗi/0 bỏ qua (174/174 tính tham số), chốt chặng 4 xanh. Chưa commit/push/merge,
chưa đổi theme và không tuyên bố account-bound auth/receipt thật đã hoàn chỉnh.
Xem [checklist mới](../../../apps/ios/docs/post-face-confirm-device-checklist.md)
và [bàn giao](../../status/handoffs/2026-10-28-1106-ios-03-l-anh-qu-n-codex.md).
Không dùng checkbox/test nền cũ để nghiệm thu code mới.

---

### IOS-04 · App iOS: camera trước, lịch phần mặt một video (màu, chấm, quay đầu), signals, camprobe

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 3 | S2 | P1 | IOS-02, LIVE-01 |

**Mục tiêu:** Phần mặt chạy đúng lịch `challenge.dynamic`, một video liên tục, như `FaceTimeline.kt`.

**Đầu ra:**
- AVCaptureSession + AVAssetWriter (MP4 không lật), Vision dò mặt, khóa AE/AWB, `color_events`, `frame_times`, `camprobe` iOS.

**Bàn giao review (25/10/2026):** đã triển khai 5.1–5.11, gồm full camprobe và năm vùng da + nền. Checkpoint camera/quality/writer được sếp nghiệm thu; yaw thẳng gần 0°, trái −20°, phải +20° trên máy thử, không phải quy ước chung mọi thiết bị. Chi tiết [checkpoints IOS-04](../../../apps/ios/docs/ios04-device-checkpoints.md) và [checklist Cổng 5](../../../apps/ios/docs/ios04-live-checklist.md).

**Nghiệm thu cập nhật:** sếp cung cấp phiên `ses_339f14675babe6e8` có 8 màu,
585 frame, 282 mẫu vùng, app 30 FPS/JPEG 226.288 byte, AE/AWB 1/1;
video 19.501,667ms so với lịch 19.460ms. Sếp xác nhận JPEG/MP4/câu đọc,
low_quality/gián đoạn/mất kết nối đạt. Bản cuối sau sửa stop re-entry đạt 78/78 unit
và 4/4 lượt UI test trên Simulator. Review mã không phát hiện lỗi chặn bàn giao;
chuyển `review`, chưa commit/push/merge PR. Thu giọng thật thuộc IOS-05.

**Tiêu chí hoàn thành:**
- [x] Trên iPhone thật: `genuine` gửi đủ JPEG, MP4 (dài bằng lịch) và signals; `low_quality` ra chụp lại. (Output genuine và xác nhận nghiệm thu của sếp trong chat.)

---

### IOS-05 · App iOS: đọc câu, WAV 16 kHz + MP4, audio_offset_ms

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P1 | IOS-04 |

**Mục tiêu:** Bước đọc câu như app Android (VOICE-05).

**Đầu ra:**
- `WavRecorder.swift` (AVAudioEngine → 16 kHz mono), video cùng lúc, `voice_challenge_id`, `audio_offset_ms`.

**Cập nhật 26/10/2026 (`review`):** đã nối thu WAV/MP4 thật dùng chung camera IOS-04,
chờ frame video đầu rồi bật AVAudioEngine; offset lấy từ host timestamp của mẫu âm
đầu, không lấy lúc bấm nút. Header WAV PCM 44 byte, mono 16 kHz Int16, RMS,
giới hạn 8 giây, chờ đóng cả hai trước `/voice`. Giữ payload khi mất mạng; câu
đọc lại dùng ID mới từ server, tối đa một lần. Một lượt toàn bộ test sau yêu cầu
của sếp: 89/89 unit và 4/4 lượt UI đạt trên Simulator. Đã kiểm file/DB `voice_clone`
ra review; đủ ba lượt WAV 8,000s/MP4 8,200s, offset app 113/107/114ms. Sếp xác
nhận ca lỗi đạt và chấp thuận bỏ qua tiếng WAV nhỏ trong lần bàn giao này
(chưa sửa gain, không coi mock review là chứng minh giọng rõ/ASR thật đạt).
Codex review cuối chưa thấy lỗi chặn bàn giao; chờ commit/PR/merge, chưa ghi done.
Theo [checklist IOS-05](../../../apps/ios/docs/ios05-device-checklist.md) và
[bàn giao IOS-05](../../status/handoffs/2026-10-26-0018-ios-05-l-anh-qu-n-codex.md).

**Tiêu chí hoàn thành:**
- [x] `voice_clone` → đọc câu → chờ duyệt; server lưu WAV và MP4. (Kiểm file/DB local và nghiệm thu của sếp; giới hạn tiếng nhỏ được chấp thuận như trên.)

---

### IOS-06 · App iOS: gián đoạn, thử lại khi mất mạng, xóa file tạm

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P1 | IOS-04 |

**Mục tiêu:** Hành vi khi gián đoạn và mất mạng giống Android (ADR-0017).

**Đầu ra:**
- Xuống nền khi đang quay → "Xác minh bị gián đoạn", lượt sau gọi `/challenge`; thử lại chỉ gửi phần chưa nhận; xóa file tạm.

**Cập nhật 27/10/2026 (`doing`):** triển khai trên nền IOS-05 `58c36fd`, không
gộp luồng/giao diện Android mới. Scene background, lỗi camera/audio và Back
được xử lý có chủ sở hữu; bỏ lượt thu buộc về chuẩn bị mặt và lấy challenge mới.
LiveFlow hủy request/bỏ reply cũ bằng operation UUID; retry mạng giữ ack/payload.
File vào namespace riêng, dọn orphan lúc mở app và không quét rộng tmp.
Cập nhật 28/10/2026: lượt mới nhất sau sửa Gallery/path binding toàn bộ scheme
Passed, 105 test (122 lượt tính tham số), 0 lỗi/0 bỏ qua trên Simulator. Hai lượt
104/105 trước sửa được giữ trong bàn giao. Sếp chấp nhận nghiệm thu mười ca với
giới hạn bằng chứng và phục hồi phiên mới khi đổi quyền, ghi tại
[checklist IOS-06](../../../apps/ios/docs/ios06-device-checklist.md).

**Tiêu chí hoàn thành:**
- [ ] Các mục tương ứng trong checklist mục 13 của `apps/ios/docs/plan-ios.md` đạt.

---

### IOS-07 · App iOS: bản Release HTTPS, đo trên máy thật, README, bàn giao

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P1 | IOS-03, IOS-05, IOS-06 |

**Mục tiêu:** Bản iOS demo được trên iPhone thật.

**Triển khai 28/10 (`doing`):** phạm vi mức 1 theo Android upstream `54acaad`:
Release HTTPS, ẩn debug, README/checklist và số đo. Đã viết guard URL khi build,
plist Release riêng và scheme không attach debugger. Cập nhật 29/10: build Release
không ký/artifact check đạt trên bản có native OTP/rung, không ATS/local-network/
marker Debug. URL .invalid chỉ để compile. Chưa nghiệm thu Release trên iPhone;
sếp xác nhận chưa có domain HTTPS được duyệt, số đo kết nối thật vẫn pending.
Không gộp receipt binding/device proof/media signing (SEC-02). Xem
[checklist IOS-07](../../../apps/ios/docs/ios07-release-device-checklist.md).

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
| M5 | 2,5 | S3 | P1 | PLAT-03 |

**Mục tiêu:** bên tích hợp biết "đã xác minh, trên 18 tuổi" mà không nhận video, ảnh hay số CCCD.

**Cập nhật trưởng nhóm 27/10:** chọn BBS, holder binding và bí danh theo dịch vụ;
SD-JWT+KB đối chứng. ADR-0018 thay lựa chọn zk-STARK/ML-DSA ở ADR-0016 mục 5.
PQC là hướng riêng, không là phụ thuộc của lab này. Không mở cổng sinh trắc thật.

**Đầu ra:** `services/credentials` (Node CLI/library, persona tổng hợp, không UI).
Blind issuance chỉ nhận commitment, holder giữ secret; verifier pin key, nonce/
audience/policy/hạn và dùng lượt một lần. BBS proof không lộ signature/PII;
JWT+PoP và SD-JWT+KB cùng policy để so sánh. `age_over_18` là boolean issuer ký,
không nhận là range proof hoặc W3C VC hoàn chỉnh. Xem README package và ADR-0018.

**Tiêu chí bản thử nghiệm:**
- [x] Cấp/giữ/xuất trình/kiểm proof BBS bằng mật mã thật, trao đổi JSON theo schema.
- [x] Test vector công khai upstream; khóa sai, sửa proof/claim/context, thiếu
      holder secret hoặc minor không qua policy adult; replay/cạnh tranh bị chặn.
- [x] Bí danh ổn định trong dịch vụ và đổi giữa dịch vụ; không đưa stable holder
      public key vào proof. Đối chứng JWT+PoP/SD-JWT+KB; phép đo có từng mẫu.
- [x] Secret chỉ RAM, output không credential/PII, header/claim synthetic-demo;
      luật real/mixed/account-bound mock và UI giữ nguyên. Lint/test vào CI.

**Còn để hoàn tất tính năng tích hợp (giữ doing):**
- [x] API opt-in cấp từ cổng quyết định server đã commit, khóa thiết bị ký consent
      cho commitment, cache mã hóa/unique session/rollback/retry; Node BBS thật và
      holder SDK profile riêng, không thêm tuổi hoặc mở chốt sinh trắc thật.
- [x] SDK ví RAM trình duyệt: kiểm Ed25519/context/pins, consent bắt buộc, đối chiếu
      byte trước ký P-256, kiểm credential và BBS proof theo origin. Chromium thực
      kiểm tương thích Python-signature/Node-issuer/verifier, chưa là HTTP xuyên suốt.
- [x] Điều phối SDK giữ offer/body ký khi thử lại, timeout/abort, hủy phản hồi muộn;
      Chromium–HTTP FastAPI–worker BBS xuyên suốt phần chứng nhận reauth/recovery
      với quyết định/khóa ghi danh tổng hợp phía server, không mở chốt sinh trắc.
- [ ] Màn consent và tích hợp UI/Android với khóa thiết bị đã ghi danh;
      SDK headless không thay được đồng ý hoặc nghiệm thu người dùng/thiết bị thật.
- [x] Đóng gói Node/BBS/schema/holder bundle trong image API; overlay mount khóa
      read-only, CLI preflight không ký verdict/cấp credential hoặc mở DB.
      CI kiểm image non-root, read-only/network none và khóa tạm trong tmpfs.
- [x] HTTP verifier dùng nonce DB qua nhiều worker/restart, origin theo credential
      tích hợp riêng, worker chỉ có public pin; hạn kiểm trước/sau crypto và commit
      trước response. PostgreSQL khóa hàng/advisory quota, SQLite BEGIN IMMEDIATE.
- [x] Registry public issuer key opt-in: staged/active/verify_only/revoked, xoay
      khóa nguyên tử, key cũ tin tối đa 60 giây, thu hồi theo key và CLI operator.
      Không đổi BBS header/proof hoặc thêm định danh thu hồi cá nhân.
- [ ] Nghiệm thu quyết định/thiết bị thật; thu hồi riêng từng credential nếu
      cần phải có thiết kế giữ riêng tư. Không gọi secret RAM là phần cứng hoặc BBS là PQC.

Chi tiết lát cắt API: `docs/architecture/private-credential-issuance.md`.
API kiểm proof: `docs/architecture/private-credential-verifier.md`.
Vòng đời khóa: `docs/architecture/private-credential-keys.md`.
SDK holder không UI: `docs/architecture/private-credential-holder.md`.
Runtime/bàn giao: `docs/runbooks/bbs-demo.md`.
Trao đổi 28/10: nhóm có app iOS/Android; thống nhất/rút gọn workflow trước khi
chỉnh UI. Không coi các mục UI/nguồn thật đã hoàn thành chỉ vì BBS kỹ thuật có test.
Workflow đối chiếu: `docs/architecture/project-workflow.md`.

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
