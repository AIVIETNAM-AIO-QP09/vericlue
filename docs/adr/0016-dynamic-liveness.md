# ADR-0016: Dynamic Liveness — thử thách động do server chấm, video ký theo phiên, kháng lượng tử

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-22
- **Người quyết định:** Trưởng nhóm (người dùng) cùng phiên điều phối
- **Liên quan:** ADR-0007 (ChromaPulse, CamProbe), ADR-0011 (token, thử thách), ADR-0013 (ba luồng eKYC), ADR-0014 (app/web)

## Bối cảnh
- Trưởng nhóm muốn một điểm nổi bật dễ thấy trong **luồng người dân**. Từ 22/10, nhóm chỉ tập trung vào luồng này; chế độ giám định không làm thêm.
- Vụ Thanh Hóa (công bố 8/10/2026): hơn 2.000 tài khoản được mở bằng phần mềm **chèn ảnh có sẵn vào camera** khi app quét mặt. Nguồn: https://cafef.vn/dieu-tra-hon-2000-tai-khoan-ngan-hang-cong-an-bat-18-doi-tuong-188261008083550404.chn
- Một bản ý tưởng "Dynamic Quantum-ZKP Liveness" đề xuất: điện thoại tự phân tích khuôn mặt, chỉ gửi bằng chứng ZKP, không gửi video. Bản này **sai ở gốc**:
  - ZKP chứng minh phép tính đúng nhưng không chứng minh được dữ liệu vào đến từ camera thật. Mã độc chèn deepfake thì bằng chứng vẫn hợp lệ.
  - Không gửi video thì server không chạy được PAD/GenD và mất bàn duyệt.
  - Không có "thử thách lượng tử". Số ngẫu nhiên mật mã thông thường là đủ.
- Các bản ý tưởng tiếp theo cũng không dùng được trong cuộc thi:
  - "Hợp nhất sinh trắc" không làm được vì app không đọc được dữ liệu vân tay.
  - "Luồng camera cô lập trong TEE" không làm được vì app bên thứ ba không chạy được code trong chip bảo mật; nếu đã tin chữ ký của chip thì ZKP cũng thừa.

## Quyết định
1. **Server là trọng tài** (giữ nguyên ADR-0013, nguyên tắc 7). Điện thoại chỉ quay, ký và gửi. Mọi phán quyết do server đưa ra.
2. **Thử thách động 4 lớp, sinh mới cho mỗi phiên, dùng một lần:**

   | Lớp | Người dùng làm | Server kiểm |
   |---|---|---|
   | ① Ánh sáng | Giữ yên khi màn hình đổi màu ngẫu nhiên | Da phản chiếu đúng màu, đúng thời điểm; độ trễ bất thường là dấu hiệu deepfake thời gian thực |
   | ② Ánh mắt | Nhìn theo chấm sáng chạy theo đường ngẫu nhiên | Đường đi của mắt (dò mống mắt trên video) khớp đường đi của chấm |
   | ③ Quay đầu | Quay theo thứ tự ngẫu nhiên | Đúng thứ tự, mặt có chiều sâu 3D (FLOW-04) |
   | ④ Giọng | Đọc câu ngẫu nhiên | Đúng câu, khẩu hình khớp tiếng, không phải giọng AI |

   - Sau 4 lớp vẫn chạy AI như cũ: PAD, GenD, giọng giả.
   - ChromaPulse **trở lại làm lớp ①** của thử thách động. Quyết định 17/10 hạ nó xuống tín hiệu phụ được thay ở điểm này. Ngưỡng là hằng số có tên, chờ ROUT-03. **Chưa có số đo độ chính xác trên dữ liệu lớn; báo cáo phải ghi rõ.**
3. **Video ký theo phiên:**
   - Điện thoại ký mã băm của media cùng mã phiên và thử thách.
   - Trên web dùng WebAuthn (passkey); trên app native dùng Android Keystore (SEC-02).
   - Server từ chối media mang chữ ký sai hoặc mã phiên khác. Video cũ, video quay lén không dùng lại được.
4. **Kháng lượng tử (PQC), không dùng máy tính lượng tử:**
   - Đường truyền dùng trao đổi khóa lai ML-KEM (FIPS 203). Cần kiểm đường hầm Cloudflare và client đã hỗ trợ chưa.
   - Kết quả trả cho bên tích hợp ký kép: chữ ký hiện tại và ML-DSA (FIPS 204), dùng thư viện có sẵn (liboqs, MIT).
   - Chữ ký trên điện thoại vẫn là chữ ký thường, vì chip bảo mật điện thoại chưa hỗ trợ PQC (cần kiểm).
   - Khi trình bày phải gọi là "kháng lượng tử / hậu lượng tử", không gọi là "ứng dụng máy tính lượng tử".
5. **ZKP chỉ dùng ở phía bên tích hợp, và là P1:**
   - Bên tích hợp nhận giấy chứng nhận có dấu VeriClue cùng bằng chứng zk-STARK cho đúng câu hỏi ("đã xác minh", "trên 18 tuổi"). Họ không nhận video, ảnh hay số CCCD.
   - Làm nếu còn thời gian; nếu không thì chỉ trình bày như lộ trình.
   - Không dùng circom/snarkjs (GPL).
6. **Lộ trình, không làm trong cuộc thi:**
   - Chứng thực điện thoại "sạch" (Play Integrity, Key Attestation) nếu làm app native.
   - Camera ký phần cứng (C2PA) kết hợp ZKP để video không cần rời điện thoại.
7. **Không tuyên bố "chặn 100 %" hay "đầu tiên".** Nháy màu đã có ở AWS, iProov, NDSS 2018 (proposal §2.10).

## Phương án đã cân nhắc
- **Bản ZKP chạy trên điện thoại, không gửi video:** loại, vì không chứng minh được nguồn dữ liệu (xem Bối cảnh).
- **Thử thách cố định (quay trái, phải, cười):** yếu trước video quay sẵn và không gây ấn tượng.
- **Chỉ AI, không có thử thách động:** không chặn được phát lại video thật của nạn nhân.

## Hệ quả
- **Chặn được:** ảnh chèn sẵn, video quay sẵn hoặc quay lén, phát lại phiên cũ.
- **Không chặn tuyệt đối:** deepfake thời gian thực tinh vi theo kịp cả 4 thử thách. Lớp ① (độ trễ) và AI là phần đối phó; báo cáo phải ghi giới hạn này.
- **Hợp đồng API** thêm gói thử thách (màu, đường chấm sáng, thứ tự quay, câu) và chữ ký media. PR gắn `[contract]`.
- **Task mới ở E9:** LIVE-01 đến LIVE-05. CAP-04 và PRES-02 (ChromaPulse) trở lại là việc cần làm cho lớp ①.
- **Rủi ro:**
  - dò ánh mắt bằng camera trước điện thoại rẻ có thể kém khi thiếu sáng: phải đo trước khi hứa;
  - nháy màu không dùng được với người nhạy cảm ánh sáng: giữ cảnh báo và cho dừng;
  - thời gian: còn 15 ngày, LIVE đứng sau mô hình giọng và luồng người dân.
