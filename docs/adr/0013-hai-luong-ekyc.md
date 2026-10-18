# ADR-0013: Ba luồng eKYC trên điện thoại — đăng ký, đăng nhập lại, khôi phục

- **Trạng thái:** đã chấp nhận (18/10). Mục "Cần xác nhận" ở cuối là mặc định theo đề xuất của phiên điều phối.
- **Ngày:** 2026-10-18
- **Người quyết định:** Trưởng nhóm (người dùng) cùng phiên điều phối
- **Liên quan:** ADR-0012 (MVP), ADR-0014 (app Android), ADR-0015 (mô hình và tinh chỉnh)

## Bối cảnh
MVP (ADR-0012) chỉ có một luồng: chấm mặt, khi lưng chừng thì cho đọc câu. Thực tế có ba tình huống với rủi ro và yêu cầu trải nghiệm khác nhau:
- mở tài khoản (đăng ký);
- xác thực khi đăng nhập hoặc giao dịch;
- khôi phục tài khoản hoặc đổi thiết bị.

VeriClue không đọc chip CCCD:
- web không làm được việc này;
- xác thực ảnh trong chip cần chứng thư của Bộ Công an;
- proposal §2.4 xếp việc này ngoài phạm vi.

## 1. Sáu câu hỏi — mỗi bước trả lời một câu
| # | Câu hỏi | Bước trả lời |
|---|---|---|
| ① | Bạn có giữ số điện thoại hoặc thiết bị này không? | OTP (đăng ký) · khóa thiết bị (đăng nhập) |
| ② | Bạn tự nhận mình là ai? | Chụp CCCD (đăng ký) · tài khoản đã có (đăng nhập) |
| ③ | Có đủ hình và tiếng tốt để chấm không? | Căn khung, kiểm chất lượng |
| ④ | Có một người thật đang có mặt ngay lúc này không? | Quay đầu, nháy màu, CamProbe, PAD, GenD |
| ⑤ | Người đó có đúng là người trên giấy tờ hoặc chủ tài khoản không? | So mặt 1:1 (`face_match`) |
| ⑥ | Người đó có tự nguyện, chủ động làm việc này không? | Đọc câu ngẫu nhiên, kiểm giọng giả, kiểm cắt ghép |

Thứ tự bắt buộc là ① → ② → ③ → ④ → ⑤ → ⑥. Lý do:
- ② phải có trước ⑤, vì cần mốc để so.
- ④ phải có trước ⑤, vì chỉ so khi đã chắc là người thật.
- ① đi đầu vì rẻ nhất và chưa đụng tới dữ liệu sinh trắc.

## 2. Tám nguyên tắc sắp xếp
1. Bước rẻ làm trước, bước đắt làm sau.
2. Người dùng tự nhận danh tính trước, hệ thống chứng minh sau.
3. Chứng minh "người thật" trước, rồi mới chứng minh "đúng người".
4. **Phiên camera trước liền mạch.** Server so khuôn mặt giữa các bước để biết vẫn là cùng một người, chặn việc đổi người hoặc đổi nguồn giữa chừng.
5. Chỉ đổi camera một lần: chụp CCCD bằng camera sau, sau đó chuyển hẳn sang camera trước.
6. Thử thách do server ra, ngẫu nhiên, có hạn giờ.
7. Server là trọng tài. Số đo trên máy chỉ dùng để hướng dẫn người dùng.
8. Phản hồi về chất lượng ngay lập tức. Không bao giờ nói bước nào bị nghi.

Thêm **tải lên dần**: phần nào chụp xong thì gửi ngay để server chấm trong lúc người dùng làm bước tiếp theo.

## 3. Luồng đăng ký (`purpose=onboarding`)
| Giai đoạn | Bước |
|---|---|
| **A. Danh tính** (không sinh trắc) | A1 đồng ý (tách: xử lý sinh trắc / lưu mẫu / lưu CCCD; nói rõ không dùng để huấn luyện) → A2 số điện thoại + **OTP mô phỏng** → A3 **chụp CCCD** mặt trước và mặt sau bằng camera sau; server đọc QR, kiểm định dạng, cắt ảnh chân dung, kiểm **"CCCD này đã đăng ký chưa"** (HMAC) → A4 hiện thông tin để người dùng xác nhận (nếu sửa khác với QR thì gắn cờ cho nhân viên duyệt) |
| **B. Có mặt và đúng người** (camera trước, không tắt) | B1 căn khung → B2 chụp ảnh thẳng và quay 3 giây trung tính → B3 **quay đầu theo thứ tự ngẫu nhiên** → B4 nháy màu và CamProbe → server chốt phần mặt: chất lượng, CamProbe, PAD, GenD (cả khung nghiêng), kiểm thứ tự quay và mặt 3D, **so mặt với ảnh CCCD** |
| **C. Ý chí** | C1 **đọc câu: luôn luôn**, vẫn trên camera trước; server kiểm cùng khuôn mặt với giai đoạn B |
| **D. Ghi danh** (khi đạt) | Tạo tài khoản → lưu **mẫu khuôn mặt** (đã mã hóa) → tạo **khóa thiết bị** (Android Keystore) → bản demo tự xóa mọi thứ sau 24 giờ |

**Quy tắc quyết định của luồng đăng ký:**
| Tình huống | Kết quả |
|---|---|
| Ảnh xấu | Chụp lại, tối đa 2 lần |
| Quay đầu sai hoặc quá giờ | Làm lại 1 lần với thứ tự mới. Sai lần 2 thì xét duyệt |
| Điểm mặt ≥ A, mặt không khớp CCCD, CamProbe fail, mặt phẳng, hoặc module bắt buộc lỗi | **Dừng, chuyển xét duyệt, không cho đọc câu** |
| Đọc sai câu | Đọc lại 1 lần với câu mới |
| Mọi thứ ổn | **Đạt** |
| Mọi nghi ngờ ở bước giọng | Xét duyệt |

**Luồng đăng ký không tự từ chối.** Ngoại lệ duy nhất là vượt giới hạn số lần thử.

## 4. Luồng đăng nhập lại (`purpose=reauth`)
- **L0.** Thiết bị ký mã phiên bằng khóa thiết bị (người dùng không thấy).
  - Khóa không hợp lệ hoặc thiết bị lạ → chuyển sang luồng khôi phục.
- **Khi có hành động rủi ro** (chuyển trên 10 triệu, đổi hạn mức, thêm người nhận):
  - **L1.** Hiện nội dung giao dịch.
  - **L2.** Chụp ảnh thẳng, quay 3 giây, chạy CamProbe. Server chấm PAD, GenD và **so mặt với mẫu đã lưu**.
    - Rõ ràng là thật → **Đạt**.
    - Lưng chừng → sang L3.
    - Nghi rõ → **Chặn**.
  - **L3.** Leo thang: **đọc câu xác nhận giao dịch** (có số tiền viết bằng chữ, không có tên riêng).
- **Chặn** nghĩa là:
  - không thực hiện giao dịch;
  - báo người dùng "thử lại sau hoặc liên hệ ngân hàng";
  - cảnh báo qua số điện thoại đã đăng ký;
  - nếu lặp lại thì khóa tạm sinh trắc.
- **Không chuyển nhân viên duyệt**, vì giao dịch không chờ được.

## 5. Luồng khôi phục / đổi thiết bị (`purpose=recovery`)
1. OTP tới **số điện thoại đã đăng ký**.
2. Toàn bộ giai đoạn B, **so mặt với mẫu đã lưu**.
3. Đọc câu.
4. Nếu đạt:
   - cấp khóa thiết bị mới;
   - báo thiết bị cũ và gửi SMS;
   - áp **hạn mức thấp trong 24 giờ đầu**.
5. Nếu nghi → xét duyệt.

## 6. Thử thách quay đầu (dùng cho `onboarding` và `recovery`)
- **Mục đích:**
  - người dùng làm theo lệnh ngay lúc đó, nên video quay sẵn không khớp;
  - chứng minh mặt có chiều sâu 3D, vì tờ giấy hay màn hình nghiêng chỉ méo theo một mặt phẳng;
  - lấy thêm khung mặt nghiêng cho GenD.
- Thứ tự ngẫu nhiên do server ra, hạn khoảng 8 giây.
- Server tự đo góc từ video (MediaPipe hoặc SCRFD).
- Không cần dữ liệu. Ngưỡng là hằng số có tên trong code (theo ADR-0012 mục 3).
- Không chặn được mặt nạ 3D tốt. Deepfake thời gian thực tốt vẫn có thể theo kịp ở góc vừa phải.

## 7. Riêng tư và bảo mật (chọn cho bản cuộc thi)
| Mã | Biện pháp |
|---|---|
| A3 | **Mỗi phiên mã hóa bằng một khóa riêng.** Xóa dữ liệu bằng cách hủy khóa (crypto-shredding). |
| A4 | Băm số CCCD bằng **HMAC với khóa bí mật của server**. Không dùng SHA-256 trần, vì số CCCD chỉ có 12 chữ số nên dò ngược được. |
| A5 | Che bớt khi nhân viên xem: CCCD chỉ hiện 3 số cuối, ngày sinh chỉ hiện năm. Mở xem đầy đủ phải được ghi lại. |
| A6 | Nhật ký "ai đã xem hồ sơ của tôi" (mở rộng chuỗi băm của REV-01). |
| B4 | **Điện thoại ký lên hash của media** ngay lúc chụp (khóa thiết bị + mã phiên). |
| B6 | **Mã phiên dùng một lần**, kèm danh sách mã đã dùng (nullifier). |

Các biện pháp làm khi có thời gian hoặc khi có app:
- B3: chứng thực khóa Android;
- B5: dùng ChromaPulse như dấu thời gian bằng ánh sáng;
- B9: certificate pinning;
- A7, A8, A10.

Ý tưởng 1, 2, 3, 4 học từ repo `AIVIETNAM-AIO-QP09/eKYC-system` (MIT). **Chỉ học ý tưởng, không chép code.** Không học theo cách repo đó để điện thoại tự quyết "thật/giả" (kết quả `approval`).

## Cần xác nhận (đang dùng mặc định theo đề xuất)
- Đăng nhập lại: nghi thì **chặn và cảnh báo**, không chuyển duyệt.
- Câu đọc khi giao dịch có số tiền.
- Hạn mức thấp 24 giờ sau khôi phục: **chỉ ghi trong báo cáo** như khuyến nghị cho ngân hàng, không làm trong demo.

## Hệ quả
- **Hợp đồng API:** thêm `purpose`, `nonce`, ảnh tham chiếu, OTP, CCCD, bước quay đầu, kết quả "deny" cho bên tích hợp. PR gắn `[contract]`.
- **Task mới ở epic E9:** FLOW-01 đến FLOW-05, SEC-01, SEC-02, APP-01.
