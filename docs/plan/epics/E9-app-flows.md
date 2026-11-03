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

**01/11 — chuẩn bị thử điện thoại 02/11 (doing):** source
`7904d7092baaa338f06351688286c1f4dc440ea0` hoàn thiện đường
`MANUAL_FULL_DEMO`: model mặt/continuity nhận policy v2; artifact continuity
cũ không ghi đè policy manual. Giọng dùng raw AntiDeepfake/SyncNet với version,
hash và evidence bắt buộc, không nâng NES diagnostic thành đạt. Chế độ chuẩn
và yêu cầu calibrator giữ nguyên. Gói riêng:
`D:/vericlue/tmp/phone-demo-2026-11-02/`. Smoke native Anti/Qwen/CTC một mẫu
chọn sẵn, SyncNet tensor forward và API/DB0011 đã qua; nghiệm thu ba luồng
trên điện thoại còn chờ. Ngưỡng là
mốc minh họa, chưa có accuracy/kiểm chứng chiều sâu; không đánh dấu toàn task xong.

**31/10 — policy trình diễn thủ công (lịch sử face-only):** opt-in riêng PAD/GenD/identity, model
thật với ngưỡng thử nghiệm, namespace và hash policy riêng; không giả artifact
hiệu chỉnh hoặc probability. API vẫn review, marker riêng cho app hiển thị kết
quả có nhãn demo. Không mở account/proof/credential hoặc đổi thresholds.yaml.
Không là nghiệm thu toàn task. Xem [runbook](../../runbooks/manual-face-demo.md).

**31/10 — sửa góc thoáng qua:** head rules0.2 không phủ quyết video chỉ vì
một mẫu yaw vượt50°. Mẫu đó không cung cấp bằng chứng giữ; vẫn kiểm coverage,
gap/biên, baseline/thứ tự và chốt tilt. API chỉ cho retry chất lượng một lần
khi các chốt khác phù hợp; giữ error hiệu chỉnh và mọi quyết định không đạt.
Test tổng hợp, chưa nghiệm thu toàn luồng; không đổi ngưỡng hay kết luận 3D.

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
- [x] Công cụ đo/fit đúng protocol phiên, kiểm provenance/chia người và giữ mẫu lỗi; adapter nhận calibrator fitted đúng full version, từ chối identity/provisional/sai version. Chỉ test tổng hợp; chưa có artifact thực và chưa mở guard.
- [ ] Test mặt phẳng (biến đổi homography) và kiểm chứng chiều sâu vật lý.

**Lát cắt backend 24/10 (Codex, doing):** `head_turn` dùng reader MediaPipe,
chỉ kiểm chuyển động/thứ tự/thời gian từ video với lịch server gắn phiên/lượt.
Lượt mới dùng lịch v2 tổng12giây từ30/10; Android từ02/11 dành5giây mỗi bên,
2giây nhìn thẳng cuối lượt. Server không chia cứng ba khoảng; vẫn nhận v1 6giây.
Các hằng góc/giữ tư thế là thử nghiệm và không đổi trong lần kéo dài lịch.
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

**02/11 — đang thử S24 FE:** APK0.3.0 đã cài và API/ADB hoạt động. Chưa nghiệm
thu đăng ký: lượt đầu `review` ở gaze; phát hiện và sửa thiếu challenge binding
trong bước trích template enrollment, có regression dùng validator production.
Không nới ngưỡng; tiếp tục thử lại và nghiệm thu ba luồng sau triển khai.

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S1 | P0 | PLAT-04 |

**01/11 — chuẩn bị thử điện thoại 02/11 (doing):** source
`7904d7092baaa338f06351688286c1f4dc440ea0`, gói riêng
`D:/vericlue/tmp/phone-demo-2026-11-02/`. APK 0.3.0 mở API thật mặc định
(`liveByDefault=true`, localhost:8421), ký media bật, trace tắt; dùng cùng
signer debug laptop, không đổi khóa ứng dụng. Mode/hash được lưu cùng receipt,
kiểm lại khi reauth/recovery; lỗi hoặc mismatch giữ tài khoản/khóa cũ. Nhãn demo
được giữ qua màn kết quả/mở tài khoản và khôi phục app; không fallback sang
scripted success. Preload AntiDeepfake/Qwen/CTC/SyncNet đã qua, full Python
4998 passed/100 skipped; smoke native giọng và API/DB0011 đã qua (SyncNet
mới tensor forward, chưa video nói thật). Ba luồng
CCCD/mặt/giọng/Keystore trên máy thật vẫn `not_run`; chưa nghiệm thu HTTPS
hoặc chất lượng AI. Không đánh dấu `done` từ kết quả test phần mềm.

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
  tài khoản trên điện thoại thật; chế độ chuẩn còn chặn sinh trắc account-bound (FLOW-05/SEC-02).

---

**Cập nhật 31/10 — tập và giọng hướng dẫn:** thêm phần tập local tùy chọn trước
chuẩn bị challenge, không ghi hình/API; bỏ qua chỉ bỏ phần tập. Giọng Việt đọc
câu cố định, ưu tiên offline, bíp dự phòng nhỏ và khác nhau giữa quay/giữ/nhìn
thẳng; dừng âm cũ khi đổi trạng thái hoặc ra nền. Oval mảnh, mũi tên chỉ hiện
khi còn cần quay. Không đổi ngưỡng/lịch/guard server; chờ nghiệm thu người thật.
Xem [runbook](../../runbooks/head-turn-coaching.md).

**Phản hồi sáng31/10:** bỏ phần tập khỏi điều hướng theo yêu cầu người dùng.
Giọng TTS thêm trace opt-in và probe phát câu thật; người dùng đang bận điện
thoại nên nghe trực tiếp/chạy lượt mới còn chờ, không ghi đã khắc phục âm thanh.

**Tiếp tục 31/10 — ngưỡng demo:** người dùng duyệt ngưỡng thủ công để quay video,
model thật và yêu cầu tiêu đề “Xác minh thành công”. App chỉ dùng tiêu đề đó ở
route riêng có nhãn “Demo · Ngưỡng chưa hiệu chỉnh”, không lưu tài khoản thật;
mode/hash phải khớp từ tạo phiên tới finalize, camera tắt khi vào kết quả.
Điện thoại đổi sang Samsung A04; chờ lượt nghiệm thu thật trên máy mới.

**Cập nhật 30/10 — hướng dẫn quay đầu:** thêm nhắc nghiêng/cúi/ngẩng từ ML Kit
trước khi báo xanh; oval riêng bước quay đầu rộng hơn, giữ vừa màn chữ lớn.
Âm báo nhỏ/ngắn, bỏ âm cảnh báo và chống rung lặp cùng trạng thái trong đoạn.
Không đổi quyết định server, timeline hoặc điều kiện hoàn thành toàn task;
chờ người dùng nghiệm thu bản APK mới và dữ liệu hiệu chỉnh toàn luồng.


**Rà soát 30/10 tối:** vẫn chưa nghiệm thu mắt/quay đầu; artifact video v2 còn
thiếu. Kế hoạch giao Gemini:
[ổn định presence](../../superpowers/plans/2026-10-30-presence-demo-stabilization-gemini.md).
Đây là kế hoạch sửa và nghiệm thu, không phải xác nhận toàn luồng đã đạt.

**Tiếp tục 30/10, 23:25 — Codex:** trace đã nối và có freshness guard;
182 test Android và4544 test Python qua (80 skip). Lượt thật mới mắt đạt,
đầu không mất mặt nhưng roll16,2° vượt giới hạn15°, chưa hoàn tất xác minh.
Đã sửa cleanup trace qua media ACK sau khi mất trace lượt đầu; chờ paired
trial khi người dùng sẵn sàng. Không đổi ngưỡng hoặc đánh dấu toàn luồng đạt.
Xem [runbook](../../runbooks/presence-phone-diagnostics.md).

### APP-07 · Đồng bộ UI phần mặt giữa Giả lập và API

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 0,5 | S2 | P0 | PLAT-04 |

**Mục tiêu:** dùng bộ UI A mới nhất đã có trên main (FaceScreens tại commit
4417e25), không dựng thiết kế khác cho API thật. Bản sửa độc lập trên nền APK
APP-06; không đổi API, lịch thử thách, ngưỡng hoặc quyết định của server.

**Tiêu chí hoàn thành:**
- [x] Giả lập và API dùng cùng màn trình bày màu, ánh mắt và quay đầu; giữ khung
      oval, chữ/mũi tên và nút dừng theo bộ UI hiện có.
- [x] API vẫn dùng lịch và tọa độ chấm toàn màn hình từ server, tính từ frame
      đầu của một video; preview chỉ có một View, không gắn lại khi đổi pha.
- [x] Có test lịch Giả lập, hình học preview, ảnh UI pha sáng/tối và màn nhỏ;
      unit/build/lint đạt; ghi rõ phần chưa nghiệm thu trên thiết bị thật.
- [x] README, backlog và bàn giao cập nhật; plan_check không có lỗi.

**Kiểm chứng 29/10:** mã 605db48 qua 11 checks CI, report UI có 131 test không lỗi
và 36 ảnh mới; đã xem pha giữ yên/màu/mắt/quay đầu ở màn nhỏ và chữ 200%.
Task giữ review: chưa cài bản sửa, chưa nghiệm thu CameraX/video liên tục trên
điện thoại. APK CI mới khác certificate bản USB hiện cài; không gỡ app hoặc
xóa dữ liệu/Keystore để cài đè. Không suy accuracy từ kiểm tra UI.

---

### APP-08 · Quét CCCD tự động bằng QR và chân dung

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P0 | PLAT-04 |

Theo yêu cầu 29/10: bỏ OCR trong luồng quét CCCD app/server; dùng QR lấy thông
tin, ảnh chân dung làm tham chiếu so mặt. Camera nhận diện liên tục, một gợi ý,
không nút chụp mặc định; tự chụp ảnh tĩnh rõ và gửi, xác nhận thông tin trước mặt.
Mặt sau chỉ cần khi mặt trước chưa có QR. Timeout có hướng dẫn, chụp thủ công
hoặc dừng; không dùng nhân viên/OCR làm fallback. Không thay AI/ngưỡng mặt.
Bổ sung theo yêu cầu: một app/package và một server, bỏ bridge HTTP; một
workflow APK, chữ ký ổn định, một lệnh chạy, lưu trữ launcher cũ và giữ DB/khóa.

- [x] Contract hỗ trợ mặt sau tùy chọn và retry thiếu chân dung, tương thích client cũ.
- [x] Backend QR-only, không dùng trường OCR/client QR để cứu ảnh không đọc được.
- [x] Android không dùng OCR kích hoạt chụp; QR/chân dung được kiểm lại trên ảnh
      tĩnh, không ghép kết quả cũ giữa các thẻ/lượt; chất lượng, timeout và lỗi rõ.
- [x] Tự gửi, xác nhận thông tin trước quay mặt; xử lý retry có giới hạn.
- [x] Bộ đọc trong API dùng chung SCRFD; chỉ một package/workflow APK và lệnh chạy server.
- [x] Kiểm APK ký ổn định tại laptop (khóa không lên CI), source/hash/pin.
- Chuyển bản cài và nghiệm thu camera khi người dùng tiếp tục test; hiện tạm dừng theo yêu cầu.
- [x] Unit/API/contract/build/lint/snapshot đạt, kiểm runtime QR-only; tài liệu,
      bàn giao và plan_check; ghi rõ phạm vi nghiệm thu điện thoại.

---

### APP-10 · Độ nhạy QR và điều kiện tự chụp Android

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P0 | PLAT-04 |

Người dùng báo QR khó bắt trên nubia Neo 2 (29/10). Đã đo stream phân tích
hiện tại 640×480; chưa đo độ chính xác hoặc tốc độ giải mã trên tập thẻ.

- [x] Cấu hình ảnh phân tích riêng khi quét thẻ, có giới hạn/fallback thiết bị;
      giữ cấu hình camera trước và video mặt hiện có.
- [x] Bước QR bỏ tìm khuôn mặt không cần thiết; hỗ trợ QR nhỏ bằng tính năng
      ML Kit có sẵn, zoom giới hạn ở bước QR và reset khi đổi bước.
- [x] Hai lần đọc QR ổn định có khoảng đệm ngắn, chống kết quả cũ/QR đổi;
      giữ phản hồi ngắn hạn nhưng không dùng cache thay QR trong ảnh chụp mới.
- [x] QR thực đọc được không bị chặn bởi lóa/nét toàn khung; ảnh chụp mới và
      server vẫn phải kiểm lại. Không dùng OCR, QR mẫu hay nới chốt xác minh.
- [x] Test trường hợp âm/thời gian/đổi QR/reset; lint/build và kiểm cấu hình
      camera trên thiết bị khi cài cập nhật. Ghi rõ phần chưa được nghiệm thu.
- [x] Tài liệu, backlog, bàn giao và plan_check hoàn tất; một app/server,
      không thay model, ngưỡng ML, contract hoặc khóa ký.

Đã cài cùng package/khóa, stream thực tăng từ 640×480 lên 1600×1200 trên nubia
Neo 2. Có quan sát bộ đọc trả kết quả, nhưng chưa chốt độ nhạy hay toàn luồng:
một số khung decoded=true/qrRead=false, cần tách ROI/format nếu tiếp tục lỗi.
Mốc này là review code/cấu hình; nghiệm thu thẻ thật/camera trước còn chờ.
Phản hồi sau cập nhật: người dùng đánh giá tạm ổn nhưng chưa đủ nhạy, yêu cầu
tạm giữ bản hiện tại. Dừng tối ưu thêm; ghi là hạn chế demo, không đánh dấu đã
giải quyết hoàn toàn hoặc tự đặt số liệu cải thiện.

---

### APP-09 · Tối ưu đăng ký và ngôn từ Android

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1,5 | S2 | P0 | PLAT-04 |

Yêu cầu 29/10: redesign điều khoản/đồng ý, bỏ chữ phụ không giúp thao tác,
chuẩn hóa ngôn từ lịch sự và chính xác. Người dùng chốt một mặt khi đủ QR và
chân dung, chỉ thêm mặt sau khi cần; không OCR. Một app/server như APP-08.
Xuất ảnh Compose thật theo thứ tự đăng ký để người dùng góp ý; dữ liệu giả lập,
không dùng ảnh căn cước/người dùng thật, không cài điện thoại hoặc mở server.

- [x] Điều khoản một vùng cuộn, tóm tắt dữ liệu/mục đích, chi tiết mở khi cần;
      không ép cuộn/giả định đã đọc, không tick sẵn hoặc giả tùy chọn lưu trữ.
- [x] Rà ngôn từ toàn luồng đăng ký; giữ gợi ý hữu ích, quyền người dùng, lỗi và
      dữ kiện cần thiết; bỏ thời hạn/nhân viên/cài đặt chưa được triển khai.
- [x] Thử đọc mặt trước trước khi xin mặt sau; xác nhận thông tin trước khuôn mặt;
      QR/portrait thiếu/lỗi không thành đạt, không QR mẫu/OCR cứu ảnh.
- [x] Test logic điều hướng/đồng ý, build/lint; render ảnh từ code Compose đã sửa
      theo thứ tự; kiểm sáng/tối, màn nhỏ, chữ lớn và ghi rõ phạm vi chưa kiểm.
- [x] Runbook/backlog/handoff cập nhật; plan_check không lỗi. Bản dựa APP-08
      chưa merge, không thay package/model/ngưỡng/contract hoặc khóa.

---

### APP-11 · Hoàn thiện giao diện Android

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P0 | PLAT-04 |

Yêu cầu 02/11: làm đẹp UI/UX app Android. Giữ nhận diện nền ngà/navy và
Be Vietnam Pro; cải thiện phân cấp nội dung, thẻ thông tin, điều khoản và
hướng dẫn trước camera. Không thay hợp đồng, lịch thử thách hoặc luật xác minh.
Task được mở từ yêu cầu trực tiếp; PLAT-04 đã `done`.

- [x] Màn bắt đầu, đồng ý, xác nhận thông tin và chuẩn bị khuôn mặt có phân cấp
      rõ, dùng chung thành phần và màu theo theme.
- [x] Nút/chữ không bị che ở màn nhỏ, chữ lớn; giữ đồng ý chủ động, trạng thái
      lỗi và các cảnh báo cần thiết. Camera không thêm hiệu ứng trang trí.
- [x] Render Compose sáng/tối, 375dp, chữ 200%, ngang; kiểm tra trực quan và
      chạy unit test/lint/build Android.
- [x] README, bàn giao và backlog cập nhật; `plan_check.py` không lỗi.

Kiểm tra 02/11: 154 test đạt, `lintDebug` không lỗi (12 cảnh báo ở mã/tài
nguyên có sẵn), `assembleDebug` thành công. Bộ onboarding có 194 ảnh, gồm
tablet 800dp. Đã xem ảnh đại diện sáng/tối, màn nhỏ, chữ lớn và ngang;
chưa nghiệm thu trên điện thoại thật. Xem bàn giao APP-11 ngày 02/11.

Yêu cầu tiếp 02/11: setup và dùng `wasabeef/awesome-android-ui`. Mở lại
APP-11 trên cùng nhánh/PR theo yêu cầu người dùng. Repo là danh mục tham
khảo; chọn Lottie Compose (Apache-2.0) để thử animation thành công.

- [x] Clone danh mục tham khảo local, ghi commit/nguồn và hướng dẫn setup.
- [x] Ghim Lottie Compose, dùng asset vector tự tạo trong app, có fallback
      tĩnh và tôn trọng giảm chuyển động/vòng đời; không nối vào camera.
- [x] Test parse/render asset thật, reduced motion/fallback, unit/lint/build;
      ghi giấy phép và ảnh xem thử.

Lượt bổ sung: 158 test đạt; lint 0 lỗi/12 cảnh báo/1 thông tin có sẵn;
build APK debug chưa ký thành công. Lottie có 10 ảnh và 2 APNG kiểm
frame cuối, preview local `tmp/app11-ui/lottie/index.html`. Chưa thử
lifecycle/chuyển động trên thiết bị thật; task giữ `review`.

Yêu cầu mở rộng 02/11: khai thác thêm danh mục UI để nâng cấp toàn trải nghiệm.
Tiếp tục trên nhánh/PR APP-11 theo yêu cầu trực tiếp, giữ hợp đồng và lịch camera.

- [x] Màn bắt đầu, tiến trình, nhập số/OTP, chờ/kết quả có bố cục đồng bộ và rõ hơn.
- [x] Trợ giúp theo ngữ cảnh, FAQ mở rộng; dán dữ liệu theo thao tác chủ động,
      phản hồi busy/validation và bộ đếm gửi lại OTP hoạt động nhiều lượt.
- [x] Ghi rõ thư viện dùng trực tiếp và mẫu tham khảo triển khai bằng Compose;
      test logic/render, kiểm 375dp/chữ 200%/ngang/tối, lint/build và preview trước/sau.

Lượt mở rộng: 168 test đạt, lint 0 lỗi/12 cảnh báo/1 thông tin có sẵn,
APK debug chưa ký build thành công. Preview `tmp/app11-ui/upgrade/index.html`
có 194 ảnh hành trình và 42 ảnh form/trợ giúp so với bản `4698f2a`.
Chưa nghiệm thu modal/TalkBack/clipboard trên điện thoại; giữ `review`.

Yêu cầu tiếp 02/11: dùng `mrdoob/three.js` để bổ sung chiều sâu cho giao diện.
Mở lại APP-11 theo yêu cầu trực tiếp, cùng nhánh/PR.

- [x] Three.js ghim phiên bản, giấy phép/nguồn rõ; cảnh tự tạo đóng gói offline.
- [x] Tích hợp vùng minh họa 3D ở màn đầu Compose, giữ CTA native, fallback
      khi giảm chuyển động/WebGL lỗi; tạm dừng/hủy tài nguyên theo vòng đời.
- [x] Kiểm WebGL thật, pause/resume/reduced motion/lỗi/context loss;
      Android test/lint/build và preview; không đưa 3D vào camera hoặc API.

Kết quả: 171 test Android và 4 nhóm WebGL đạt; lint không lỗi (12 cảnh báo,
1 thông tin có sẵn), APK debug chưa ký build được và chứa tài nguyên Three.js.
Preview `tmp/app11-ui/three/index.html`; browser dùng SwiftShader, Paparazzi
dùng hình dự phòng. Chưa nghiệm thu WebView/GPU/lifecycle/cuộn trên điện thoại;
giữ `review`, chi tiết ở bàn giao 17:20.

Yêu cầu mở rộng Three.js: dùng cảnh theo ngữ cảnh ở nhiều màn, có tương tác
chọn nội dung và chuyển cảnh, thay vì chỉ minh họa một thẻ ở màn đầu.

- [x] Màn đầu có các chương thẻ/khuôn mặt/giọng nói; chuẩn bị khuôn mặt có
      các tư thế minh họa chọn bằng nút native; đồng ý/thành công có cảnh riêng.
- [x] Một renderer mỗi vùng, đổi cảnh không nạp lại WebView; giải phóng geometry,
      material/instance khi đổi cảnh; giới hạn chuyển động và giữ fallback có nghĩa.
- [x] Kiểm chuyển cảnh liên tục, dừng/chạy, giảm chuyển động, lỗi WebGL,
      tài nguyên GPU; kiểm native controls, snapshot, lint/build và preview mới.

Lượt mở rộng: 174 test Android đạt; lint 0 lỗi/12 cảnh báo/1 thông tin có sẵn,
APK build được, sáu asset/license Three.js trong APK khớp source. Năm nhóm
WebGL đạt, kiểm bảy cảnh/hai theme và 56 lần chuyển không tăng geometry/texture
GPU; thêm 36 snapshot lựa chọn native. Preview tại `tmp/app11-ui/three/index.html`,
tái tạo bằng script trong repo. Giữ `review` chờ điện thoại, bàn giao 17:52.

Phản hồi test thiết bị: 3D chỉ trang trí, bỏ điều khiển/thuyết minh thừa;
khung mặt bị đổi tỷ lệ qua căn mặt/đổi màu/theo chấm/quay đầu.

- [x] 3D tự chạy ngắn, không có tab/xem lại/dừng trong luồng người dân; rút gọn copy.
- [x] Dùng chung viewport camera và oval cho mọi pha, không scale/crop lại khi chuyển pha;
      giữ tọa độ chấm toàn màn hình, lịch màu, recording và điều kiện xác minh.
- [x] Nêu đúng giới hạn luồng không đổi màu; đăng nhập thụ động không hiện cảnh báo đổi màu.
- [x] Test hình học thực qua các màn, snapshot/chữ lớn, lint/build, cập nhật preview và APK local.

Kết quả: 177 test Android đạt, lint không lỗi (12 cảnh báo/1 thông tin có sẵn),
APK local build thành công. Đo cùng viewport/oval qua chín trạng thái trên ba
cấu hình (27 ảnh); 18 ảnh kiểm không có player và cảnh báo đổi màu ở reauth.
Năm nhóm WebGL đạt. Preview `tmp/app11-ui/refined/index.html` so với `2aa9971`.
Giữ `review` chờ thử lại trên điện thoại; phương thức không đổi màu cho đăng ký/
khôi phục chưa triển khai, câu hỏi và phạm vi backend ở bàn giao 18:36.

Phản hồi tiếp: tăng chất lượng chuyển động, bỏ mô tả thừa ở màn danh tính;
khung mặt cần vừa ở khoảng cách tự nhiên, camera thu gọn lúc theo chấm;
không bắt đầu khi thiếu mặt và không tự chuyển yêu cầu quay đầu khi chưa làm.
Mở lại theo yêu cầu trực tiếp, cùng nhánh/PR; cho phép subagent chia việc.

- [x] Chuyển động native/Three.js rõ, hữu hạn và tôn trọng giảm chuyển động;
      bỏ mô tả dưới ba mục và câu chuẩn bị ở hero, chữ ngắn/chuyên nghiệp.
- [x] Preview mặt giữ đầy đủ ảnh, oval rộng hơn; gaze dùng thumbnail góc và
      chấm có tương phản rõ, giữ tọa độ server và crop nguồn khi chuyển pha.
- [x] Chỉ bắt đầu khi một mặt đầy đủ nằm trong oval, nhìn thẳng, ổn định qua
      các frame mới; không cho tín hiệu cũ/thiếu quyền camera kích hoạt timer demo.
- [x] Kiểm đúng hướng quay/nhìn giữa qua nhiều frame; chưa đạt thì dừng/thử lại
      bằng challenge mới, không tự chuyển tiếp hoặc kéo lệch lịch thu server.
- [x] Test hồi quy thiếu mặt/không làm/sai hướng/tín hiệu cũ/hủy capture, ảnh
      và chuyển động ở chữ lớn/màn nhỏ, lint/build, cập nhật preview/APK.

Kết quả tích hợp: 208 test Android đạt; lint 0 lỗi/12 cảnh báo/3 thông tin,
APK build thành công. Sáu nhóm WebGL đạt; ba APNG native có chuyển động
thực rồi đứng yên. Preview `tmp/app11-ui/polished/index.html` gồm chín cặp
trước/sau và ba APNG. Giữ `review`: cần nghiệm thu khoảng cách, hướng quay
và camera thực tế. Lịch server vẫn cố định; thiếu thao tác thì retry, chưa
chờ thích ứng từng hướng. Chi tiết và giới hạn mock ở bàn giao 20:39.

Phản hồi thử máy tiếp: căn mặt còn khó, cần nhắc sửa tại bước quay đầu thay
vì bắt làm lại toàn lượt. Mở lại APP-11 theo yêu cầu trực tiếp; cập nhật hợp
đồng/API/ML đồng bộ để hỗ trợ lịch quay đầu thích ứng, giữ tương thích bản cũ.

- [x] Căn mặt chấp nhận khoảng cách tự nhiên, dung sai rung nhẹ và gợi ý đúng
      khoảng cách/vị trí; vẫn bắt buộc một mặt đầy đủ, rõ và frame mới.
- [x] Quay sai/chưa quay giữ nguyên yêu cầu và nhắc ngay tại chỗ; chỉ đổi
      hướng khi có đủ frame giữ đúng tư thế, không qua bước theo đồng hồ.
- [x] Server cấp chế độ thích ứng có giới hạn thời gian, tự kiểm động tác
      trên video gốc; phiên/bản cũ giữ lịch cũ, refresh giữ chế độ đã chọn.
- [x] Test Android/API/ML và snapshot, build APK; cập nhật tài liệu và bàn giao,
      giữ nghiệm thu khoảng cách/tư thế trên máy thật ở mức review.

Lượt thích ứng: 229 test Android đạt, lint 0 lỗi/12 cảnh báo/3 thông tin,
APK build thành công. Backend/ML có hai lượt 193 và 122 test đạt (chồng lặp).
39 ảnh gợi ý từ nội dung thật qua ba cấu hình, không nhảy footer/oval hoặc
quá hai dòng ở chữ 200%. Schema/OpenAPI/SDK đồng bộ; mock không chứng minh
liveness thật. Bàn giao 22:10 ghi cách kiểm và giới hạn tổng thu 30 giây.

**02/11 23:31 — tích hợp S24 FE theo yêu cầu:** ghép PR130 `658139f` với
nền PR134 `9291bb5`, giữ các sửa giọng, quyền riêng tư và tài khoản. Review chéo
ba agent bổ sung kiểm sensor clock, giữ Finalize hiện tại, chống lặp lời nhắc,
EOF thật và phiên bản phép đo adaptive riêng; không mượn artifact timed.
Schema/OpenAPI/SDK đồng bộ. Giữ `review`, chưa nghiệm thu máy thật của bản này;
khôi phục vẫn còn chốt nhận dạng câu/lipsync. Kết quả kiểm tra và triển khai ở
[bàn giao tích hợp](../../status/handoffs/2026-11-02-2331-app-11-ngoc-quang-codex.md).

---

### APP-02 ★ · App: chụp mặt, quay 3 giây, quay đầu ngẫu nhiên

**02/11 — doing, thử S24 FE:** lượt mới đã qua CCCD/gaze nhưng quay hướng đầu
vượt vùng nhận, các đoạn giữ không đủ liên tục; server trả `wrong_order`, các
model cần ba tư thế giữ `degraded`. Sửa ổn định lời nhắc để giảm cắt giọng khi
góc dao động, giữ cảnh báo ưu tiên và lịch challenge12s. Sau cập nhật, người
dùng xác nhận dễ theo và hoàn tất; server xác nhận một lượt CCCD/mặt đạt,
bảy module ok/pass và tài khoản/consent receipt đã commit. Chưa nghiệm thu
nhánh giọng hoặc khôi phục. Đăng nhập lại sau đóng/mở app sau đó đã đạt, đúng
khóa/tài khoản và năm module ok/pass (tổng hợp APP-01-s24fe-physical-acceptance).

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 2 | S1–S2 | P0 | APP-01 |

**03/11 chiều — yêu cầu giao diện mới:** oval hiển thị gọn, cùng source guide
ở framing/các thử thách/giọng; text scale không đổi vùng tối đa nhận mặt.
Hướng dẫn lấp đầy ít nhất 65% khi vào/60% khi giữ để tránh mặt quá nhỏ trong
oval. Thiếu tracking metadata sau khi đã có ID dùng correction/grace hiện có,
không coi ngay là đổi người; không cộng hold từ khung đó. Chờ nghiệm thu máy
thật, không công bố khoảng cách cm hoặc mức giảm retry. Xem
[bàn giao](../../status/handoffs/2026-11-03-1300-app-04-ngoc-quang-codex.md).

**02/11 — sửa nhắc lặp:** người dùng xác nhận bị nhắc cùng bên; local hold chưa
hoàn tất có thể nhắc quay ra lại sau khi đã về giữa. Thêm latch hướng dẫn riêng
từng đoạn: một excursion đúng phía rồi về giữa thì chờ hướng tiếp. Không coi
latch là hold đạt/đổi phase/qua gate; giữ các hằng và lịch5/5/2. Cần thử bản mới.

**Mục tiêu:** làm giai đoạn B của ADR-0013 trên app.

**Đầu ra:**
- CameraX dùng camera trước, căn khung và gợi ý chất lượng bằng ML Kit hoặc MediaPipe.
- Chụp ảnh và quay 3 giây trung tính; tải lên dần.
- Quay đầu theo thứ tự server ra (phần server ở FLOW-04), có mũi tên hướng dẫn.
- Kiểm camera ảo bản native: phát hiện root hoặc hook ở mức cơ bản; gửi tín hiệu lên server.
- Camera không tắt cho tới bước đọc câu.

**Tiêu chí hoàn thành:**
- [x] Đi hết giai đoạn B trên điện thoại thật; server chấm bằng mô hình thật.
      (02/11, S24 FE, một lượt đăng ký CCCD/mặt, APK1367c2e/API6f3171e;
      kết quả `APP-02-s24fe-onboarding-2026-11-02.json`, chưa nghiệm thu giọng.)

---

### APP-03 · App: ghi âm đọc câu (WAV 16 kHz)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 1 | S2 | P0 | APP-01 |

**03/11 trưa — tiếp tục sửa, chưa nghiệm thu:** đăng ký và đăng nhập mới đã
đạt trên demo 0.90. Khôi phục 11:15 bị chặn ở lipsync; lượt 11:50 bị chặn trước
giọng ở GenD và ánh mắt. Sửa timestamp CameraX trước hàng đợi main để loại
lỗi trễ callback khỏi mốc video ước lượng, giữ lịch và mọi ngưỡng/chốt.
Không kết luận đã sửa GenD hoặc đồng hồ encoder. Xem
[bàn giao](../../status/handoffs/2026-11-03-1210-app-03-ngoc-quang-codex.md).

**03/11, sau lượt 10:57:** người dùng yêu cầu ngưỡng demo GenD **0.90** sau
khi 0.70 vẫn chặn. Profile riêng đã đổi với policy mới; không coi các lượt
demo dùng để điều chỉnh ngưỡng là đánh giá độc lập. GenD chưa hiệu chỉnh và
khôi phục chưa nghiệm thu; mục 0.70 bên dưới là lịch sử.

**03/11 10:54 — cấu hình demo theo yêu cầu mới:** ngưỡng GenD riêng của máy
demo đổi từ 0.50 sang 0.70, policy có mã mới; server đã xác nhận qua HTTP.
Đây là lựa chọn thủ công chưa hiệu chỉnh, có thể tăng bỏ lọt deepfake, không
phải bằng chứng mô hình đã sửa. Không đổi mặc định repo hoặc chốt error/degraded.
Chưa có lượt điện thoại trên policy mới; xem
[bàn giao](../../status/handoffs/2026-11-03-1042-app-03-ngoc-quang-codex.md).

**03/11 sáng — sửa GenD:** lượt07:39 qua sáu mô-đun mặt nhưng GenD chặn
trước giọng. Đối chứng gốc phát hiện lỗi căn mặt NumPy; sửa và version riêng,
không đổi ngưỡng. Mã gốc cũng từ chối front của lượt này ở cutoff hiện có,
nên chưa coi khôi phục đã sửa xong. Xem
[bàn giao](../../status/handoffs/2026-11-03-0757-app-03-ngoc-quang-codex.md).

**03/11 02:57 — đã triển khai, chưa nghiệm thu:** APIfb8c2bf với Qwen1.7B
manual-only đã preload đủ11 mô-đun và khởi động thực; APKc646868 cài giữ dữ
liệu lênS24 FE. Python5329 đạt, Android445 ca không lỗi, CI10/10 xanh trên
fb8c2bf. Frontend SyncNet mới vẫnoffline; khôi phục/ASR/lipsync cần lượt người
thật. Giữdoing và DraftPR135; xem
[bàn giao cuối](../../status/handoffs/2026-11-03-0257-app-03-ngoc-quang-codex.md).

**03/11 — tiếp tục điều tra:** APK03b4abc đã cài giữ dữ liệu; sửa thời hạn chờ
AI và kiểm phản hồi trước giải phóng bản thu. Đối chứng ASR cố định trên
18 mẫu/18 người DNU calib_fit, không dùng điện thoại/test/VIVOS parity để chọn.
Frontend landmark106 có version và probe file/RAM riêng, chưa bật trong API;
xem [runbook](../../runbooks/syncnet-frontend-probe.md). Khôi phục vẫn chưa đạt
nghiệm thu, không nới chốt hoặc đổi ngưỡng để lấy kết quả pass.

**03/11 — doing, sửa thao tác thu giọng:** cap native 10 giây gồm chuẩn bị;
đếm ngược theo CameraX và bắt buộc bấm “Đọc xong”. Nếu hết giờ, không decode/
gửi, cho ghi lại cùng câu và challenge ID, không dùng lượt đọc lại phía server.
Giữ nguồn MP4/WAV chung, PTS v3, giới hạn decoder 12 giây và chốt AI. Chưa nghiệm
thu ASR/lipsync/khôi phục; xem
[bàn giao](../../status/handoffs/2026-11-03-0001-app-03-ngoc-quang-codex.md).

**02/11 22:50 — doing, đã nhận xác nhận đọc đúng:** người dùng xác nhận đủ câu
và sáu số cả hai lượt. Đối chứng cùng trọng số Qwen với runtime chính thức
cho bản đọc lại có cùng token sinh và vẫn mismatch; VAD không cắt PCM.
Chưa có bằng chứng cho lỗi wrapper còn lại ở bản ghi này. Lipsync còn khác recipe căn mặt,
recovery chưa nghiệm thu; xem
[bàn giao](../../status/handoffs/2026-11-02-2250-app-03-ngoc-quang-codex.md).

**02/11 21:49 — doing, tiếp tục điều tra server:** sửa Qwen theo assistant
language prefill gốc và SyncNet theo resize uint8 gốc, phiên bản riêng cho
từng wrapper. Có regression/control-token guards và review chéo; trọng số,
ngưỡng/câu thử thách/clock không đổi. Đối chứng bản ghi cũ vẫn không đạt nội
dung và lipsync, chưa nghiệm thu recovery. Xem
[bàn giao](../../status/handoffs/2026-11-02-2149-app-03-ngoc-quang-codex.md).

**02/11 21:16 — doing, lượt người thật mới trên v3:** cả bản đọc đầu và bản
đọc lại đã tới AI. Mặt/quay đầu, voice spoof và continuity đạt; nội dung câu
và lipsync không đạt, kết quả `review`, chưa commit liên kết khôi phục, tài khoản
vẫn còn nguyên. Không tái hiện lỗi parser trước gửi ở lượt này; nguyên nhân
gốc của hai chốt AI chưa được xác định. Giữ Draft PR134 và chưa nghiệm thu.

**Lịch sử 02/11 tối — sửa tiếp ca đọc lại:** v2 đã đưa giọng tới API, nhưng ca
đọc lại vẫn bị từ chối bởi bước nhảy timestamp. V3 đã kiểm chứng nội suy WAV
theo timeline presentation và normalizer version riêng; không dùng kết quả AI
để dịch media/chọn ngưỡng.320test và5native replays đạt; chưa nghiệm thu toàn
luồng hoặc clock vật lý.

**Lịch sử 02/11 tối — sửa lỗi micro:** Android đã cấp quyền nhưng decoder từ
chối PTS của file thực; callback báo nhầm thiếu quyền. Policy nguồn mới
`muxed-av-pcm-v2-clock1ms` kiểm sai số tối đa1ms cả theo mốc đầu và đoạn kế cận,
PTS phải tăng, không sửa PCM/offset. Lỗi capture khi đã có quyền chuyển màn
ghi lại; chỉ quyền thực sự bị từ chối mới mở hướng dẫn quyền. Ngưỡng AI/API
vẫn giữ nguyên. Full Android và native decoder replay đã qua; cần thử lại toàn
luồng sau cài.

**02/11 — doing, nguồn ghi chung:** CameraX ghi micro/video vào một MP4 có
cap 8 giây; chuẩn bị chỉ kết thúc khi có video và audio native ACTIVE. Sau
finalize, giải mã chính file sẽ tải lên thành WAV PCM 16-bit, mono, 16 kHz, giữ offset
PTS PCM/video có dấu. Policy nguồn `muxed-av-pcm-v1`, chuẩn hóa
`pcm16-mono16k-sinc-v1`; kiểm PTS trước chuẩn hóa, không dùng VAD hoặc tự dịch
thời gian. Luồng API không thu AudioRecord/WAV riêng; gallery offline giữ cách
cũ. Hủy/lỗi/finalize không hợp lệ chặn gửi, không nhận kết quả đến muộn.
Không đổi mô hình, API, chữ ký media hoặc ngưỡng; chưa xác nhận clock phần cứng.

Lượt khôi phục thực gần nhất trước thay đổi nguồn ghi chỉ còn SyncNet không
đạt. Nguồn chung mới và khôi phục toàn luồng trên S24 FE vẫn chờ nghiệm thu;
không đánh dấu `done` từ mã nguồn hoặc thử nghiệm tổng hợp.

**Lịch sử 02/11 — trước nguồn MP4 chung:** recovery đã chạy thật đến Qwen/
AntiDeepfake/CTC/SyncNet và continuity; lượt đầu chưa đạt nhận dạng câu/khớp môi.
Đã sửa trạng thái chuẩn bị micro, tự dừng 8 giây, mốc offset sau AudioRecord start
và quyền đọc lại bị bỏ qua bởi mã `E_CHALLENGE_MISMATCH` hợp lệ. Mốc offset đó
là ước lượng phần mềm; không phải cách lấy offset PTS của nguồn chung mới.

**Mục tiêu:** làm giai đoạn C của ADR-0013 và bước leo thang L3.

**Đầu ra:**
- Luồng API: CameraX ghi video và track âm thanh trong một MP4, giới hạn 10 giây;
  WAV PCM 16-bit, mono, 16 kHz được giải mã/chuẩn hóa từ chính file đó, cùng offset PTS có dấu.
- Hiện thời gian native còn lại; chỉ gửi khi người dùng bấm “Đọc xong” trước cap.
  Hết cap cho ghi lại tại máy, giữ câu/challenge ID và giới hạn/expiry phía server.
- Chữ ký media ràng buộc WAV, MP4 và offset như hợp đồng hiện có; gallery offline
  giữ AudioRecord. Chung PTS container chưa chứng minh đồng bộ clock phần cứng.

**Tiêu chí hoàn thành:**
- [ ] Server đọc được WAV và chấm nội dung câu/AntiDeepfake/khớp môi theo policy
  hiện có; nghiệm thu khôi phục toàn luồng trên điện thoại thật.

---

### APP-04 · App: OTP, chụp CCCD, xác nhận thông tin

**02/11 — thử lại S24 FE:** bản đang dùng đã có cải thiện QR từ PR115. Có
khung đọc được mã nhưng chưa qua lọc định dạng/ROI; bổ sung log cờ kỹ thuật để
tách hai nguyên nhân, không công khai nội dung mã. Sửa thông báo hết20s tự
chụp để hướng dẫn bấm nút thủ công và giữ lý do chụp lại. Không bỏ chốt QR.

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (+M1) | 1,5 | S1–S2 | P0 | APP-01 |

**Mục tiêu:** làm giai đoạn A của ADR-0013. Phần server nằm ở FLOW-02 và FLOW-03.

**Yêu cầu mới 03/11 — doing:** một màn quét, QR và chân dung cùng ảnh mới;
thiếu thì hướng dẫn chỉnh tại chỗ, bỏ điều hướng QR-only. Sửa crop/đo chất
lượng vùng thẻ, giữ xác nhận thông tin và kiểm server. Yêu cầu tiếp theo:
tự chụp tiếp có khoảng nghỉ, bỏ nút chụp thủ công và giới hạn dừng 20s/ba lần;
thử vùng QR chồng lấp cùng bitmap khi toàn khung chưa đọc được. Không bỏ
kiểm ảnh cuối hoặc quota/TTL của server. Preset đầy đủ `phone-demo-fixed-v1`
chưa bật; sau đó người dùng cho phép reset riêng tài khoản test và chỉ bật
GenD 0.95 (bàn giao 13:47). Xem
[bàn giao](../../status/handoffs/2026-11-03-1300-app-04-ngoc-quang-codex.md).

**Bổ sung 03/11 — độ nhạy quét:** người dùng cho phép tách điều kiện chụp/gửi
phân tích khỏi điều kiện xác nhận. QR/candidate có thể kích hoạt ảnh tĩnh khi
preview bỏ sót chân dung. Ảnh rõ có dấu hiệu QR hoặc chân dung được gửi server
đọc lại, không gửi QR text nếu local chưa đủ cả hai. Server quét một mặt phải
đọc QR hợp lệ và tìm chân dung trên cùng ảnh; offline vẫn chốt đủ bằng chứng
local. Thử crop QR và nắn phối cảnh giới hạn, chưa thay model/trọng số.

**Đầu ra:**
- Màn hình số điện thoại và OTP, có khung "SMS mô phỏng".
- Một màn camera sau tự chụp; ảnh mới có thể gửi để server đọc phần còn thiếu, chỉ sang xác nhận khi đủ QR/chân dung cùng ảnh, thiếu thì hướng dẫn chỉnh tại chỗ, không mở bước QR riêng.
- Màn hình xác nhận thông tin.

**Lịch sử — bộ quét tài liệu đã được yêu cầu bỏ, 03/11 chiều:** người dùng chọn bộ quét tài liệu tự chụp
thay vì tiếp tục căn QR trong camera cũ. Luồng API mặc định mở ML Kit Document
Scanner, một trang JPEG, không nhập thư viện, chế độ BASE. SDK nhận mép/chụp
và có màn kiểm tra ảnh; app gửi JPEG cho server đọc QR/chân dung. Lỗi tải có
retry/camera cũ dự phòng, hủy không mở lại liên tục. Không ghi nhận thành công
từ việc chụp được ảnh, không đổi chốt server. Luồng offline/gallery giữ cũ.

**Yêu cầu tiếp theo 03/11 16h:** quay lại camera trong app, tự detect và đọc
cả QR/chân dung. Giữ chốt cùng ảnh; thử bộ giải mã QR bổ sung, tăng chi tiết
ảnh tĩnh, hiển thị trạng thái preview chính xác. Không kết luận lỗi model
hoặc so ngang Zalo khi chưa đo trên cùng điều kiện.

**Yêu cầu tiếp theo 03/11 — WeChat và ngưỡng demo:** người dùng đã cho phép
thay OpenCV QRCodeDetector bằng WeChat trên server, giữ ZXing-C++ và chốt
QR/chân dung cùng ảnh. Tải trọng số pin revision/SHA-256, preload một lần;
không fallback ngầm khi thiếu/sai model. Cho phép kích hoạt preset hiện có
`phone-demo-fixed-v1` trong manual full demo; đây là ngưỡng thủ công chưa
hiệu chỉnh, không thay artifact chuẩn. Giữ lỗi/degraded/timeout non-pass.
Yêu cầu mới này thay giới hạn chỉ bật GenD 0.95 ở bàn giao 13:47; không cấp
thêm quyền xóa tài khoản. Xem bàn giao `2026-11-03-1656-app-04-codex.md`.

**Sửa CI PR #136 (03/11):** image BBS đã build nhưng export cache GitHub bị
treo, làm job hết 15 phút trước offline smoke. Giới hạn cache import/export
2 phút, chỉ bỏ lỗi export cache; build và smoke vẫn bắt buộc. Xem bàn giao
`2026-11-03-1755-app-04-codex.md`.

**Tiêu chí hoàn thành:**
- [x] Đi hết giai đoạn A trên điện thoại thật. (27/10, Galaxy S24 FE, thẻ CCCD gắn chip; bàn giao `2026-10-27-2000-app-01`)
- [ ] Nghiệm thu lại bước quét một màn theo yêu cầu 03/11 trên S24 FE; test tự động không thay nghiệm thu này.
- [ ] Nghiệm thu camera native sau khi bỏ Document Scanner theo yêu cầu mới: tự nhận QR/chân dung, ảnh tĩnh chi tiết, ZXing bổ sung; kiểm cả chữ lớn và ảnh thiếu một thành phần.
- [x] Tách chụp/gửi khỏi xác nhận; không dùng QR cũ, không chấp nhận QR xung đột hoặc thiếu chân dung phía server cho ảnh một mặt.
- [x] Có smoke giai đoạn A trên API local: hai đồng ý, OTP sai/đúng, đọc QR tổng hợp và từ chối ảnh thiếu chân dung; phát hiện cấu hình thiếu OTP/lệch phiên bản trước giao bản thử.
- [x] Tích hợp WeChat opt-in với pin trọng số; test QR xung đột/thiếu model, giữ kiểm SCRFD và preset demo hiện có.
- [ ] Nghiệm thu lại xác minh đầu cuối trên điện thoại sau khi bật WeChat và preset full demo.

---

### APP-05 · Đóng gói Android test từ xa qua mạng riêng

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

**Mục tiêu:** theo yêu cầu test Android từ xa sau PR105, cho laptop chạy API
test tách biệt và tạo APK từ source hiện có, không cần Android SDK trên laptop.
Không thay UI, contract, guard sinh trắc, ngưỡng hoặc dùng dữ liệu triển khai.

- [x] API test mã hóa, chỉ loopback; Tailscale Serve HTTPS riêng, không Funnel.
- [x] CI nhận URL HTTPS riêng qua cấu hình, bật ký media, chạy unit test và build APK có checksum/metadata nguồn; không nhúng khóa hoặc token mạng riêng vào APK.
- [x] Kiểm HTTP qua HTTPS bằng dữ liệu tổng hợp và chữ ký; artifact trỏ đúng endpoint.
- [x] Có hướng dẫn cài/chọn API, QR mẫu/kịch bản mock, dừng/restart và giới hạn chưa nghiệm thu điện thoại.

Hướng dẫn: [android-remote-test.md](../../runbooks/android-remote-test.md).
Probe HTTPS tổng hợp qua 3 kịch bản; CI run `40725003348` tạo APK, kiểm
BuildConfig/DEX và checksum sau tải khớp. Người test xác nhận Chrome Android
đã mở được HTTPS health. Chưa nghiệm thu camera/micro/luồng app từ xa hoặc AI thật.

**29/10:** người test báo đi hết luồng mock qua APK. Đã chuẩn bị profile AI mặt
từng phần bằng cờ hiện có, DB/khóa riêng, Serve 8421; probe native và HTTP/HTTPS
tổng hợp qua. Chưa có lượt camera Android với profile AI. Qwen thiếu RAM, giọng
chưa bật; không nhận là eKYC thật xuyên suốt. Chi tiết ở mục 6 của runbook và
bàn giao `2026-10-29-0029-app-05-codex.md`. Giữ `review`, không mở guard hoặc sửa ngưỡng.

### APP-06 · Android test server qua USB

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

**Mục tiêu:** theo yêu cầu 29/10, dùng điện thoại Android cắm USB để test API
trên laptop qua ADB reverse; giữ APK Tailscale và dữ liệu app hiện có.

- [x] Debug APK riêng `vn.vericlue.app.usbtest`, tên VeriClue USB, gọi đúng
  `http://localhost:8421/`, bắt buộc ký media; không có release USB.
- [x] CI chạy unit test/build và kiểm APK/manifest/checksum/source metadata.
- [x] Cài ADB chính thức, nhận quyền thiết bị, reverse cổng 8421 và kiểm health
  từ điện thoại; không mở API LAN, Funnel hoặc ADB TCP legacy.
- [x] Cài/khởi động bản USB trên thiết bị được cho phép; không gỡ bản cũ hoặc
  xóa dữ liệu. Có runbook, cách bỏ reverse và giới hạn AI từng phần.

Không đổi UI flow, API/ML/contract/ngưỡng hoặc guard. API mặt thật vẫn là profile
nội bộ từng phần; đổi đường truyền không làm OTP/CCCD hoặc giọng thành thật.

**29/10:** CI 10 checks xanh ở commit `92555d0`; run USB `40796808317` kiểm
package/label/URL/release guard. Artifact tải về khớp SHA-256; đã cài mới và mở
trên Samsung SM-S721B SDK36 ARM64, app cũ giữ nguyên. Chủ máy xác nhận health
trong Chrome qua localhost/USB; chưa nghiệm thu capture và AI từ app mới.

**Bổ sung theo yêu cầu 29/10:** cáp mất kết nối nhiều lần; chuyển sang Wireless
debugging TLS ghép đôi bằng mã, giữ APK. Đã kiểm route Wi-Fi, reverse và mở app;
chủ máy xác nhận health ok sau rút cáp, không còn transport USB. Không dùng cổng
5555 legacy hoặc lưu mã pairing. Hướng dẫn ở cuối runbook; chưa nghiệm thu AI.

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
- [x] Lịch mới v2/12000 ms đồng bộ API–ML–Android, chặn cặp chéo và tách version hiệu chỉnh; giữ v1/6000. Android có đếm ngược/hướng tiếp theo. Chưa nâng cấp iOS hoặc nghiệm thu đạt toàn luồng thật.

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
