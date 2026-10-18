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
  - `reauth`: không có thử thách mặc định; điểm lưng chừng thì leo thang sang đọc câu; nghi rõ thì trả `deny` cho bên tích hợp. Người dân chỉ thấy "thử lại sau hoặc liên hệ ngân hàng".
- Câu đọc ở `reauth` có số tiền viết bằng chữ.

**Tiêu chí hoàn thành:**
- [ ] Test cho từng `purpose`. Không có đường nào ra `pass` khi module bắt buộc lỗi.
- [ ] Hợp đồng, API và type web khớp nhau (`gen_openapi --check`).

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
- [ ] Test các trường hợp: hết hạn, sai quá số lần, dùng lại mã.

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
- [ ] Test bằng chuỗi góc tổng hợp: đúng thứ tự, sai thứ tự, quá hạn, mặt phẳng (biến đổi homography).

---

### FLOW-05 · So mặt 1:1 (AdaFace) và mẫu khuôn mặt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | S1 | P0 | FLOW-03, FACE-01 |

**Mục tiêu:** trả lời câu ⑤ của ADR-0013.

**Đầu ra:**
- Module `face_match` dùng AdaFace IR101 (CVLFace), có dự phòng SFace. Thêm cả hai vào manifest, ghi rõ giấy phép.
- So mặt người dùng với ảnh tham chiếu (ảnh CCCD hoặc mẫu đã lưu).
- Mẫu khuôn mặt lưu dạng vector đặc trưng đã mã hóa; bản demo tự xóa sau 24 giờ.
- Ngưỡng chọn trên các cặp vn_celeb, chia theo người.
- So cùng khuôn mặt giữa các bước (ADR-0013 nguyên tắc 4).

**Tiêu chí hoàn thành:**
- [ ] Đo VRAM khi chạy cùng bộ mô hình MVP.
- [ ] Số liệu ngưỡng chạy ra từ code trong repo.

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

### APP-01 ★ · App Android cho luồng người dân

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 | 2 | S1–S2 | P0 | CAP-06 |

**Mục tiêu:** bản demo nộp cuộc thi là app Android (ADR-0014).

**Đầu ra:**
- APK cho Android 10 trở lên, gọi API VeriClue qua **HTTPS** tới máy demo.
- Cách làm (bọc web bằng Capacitor hoặc viết Kotlin native) **chốt trước khi bắt đầu** (ADR-0014 mục 2).
- Có ba luồng của ADR-0013.

**Tiêu chí hoàn thành:**
- [ ] Đi hết luồng đăng ký trên điện thoại thật với mô hình thật (`ROUTER_PROFILE=mvp`).
- [ ] Người dân không thấy điểm số (AGENTS §6 luật 3).
