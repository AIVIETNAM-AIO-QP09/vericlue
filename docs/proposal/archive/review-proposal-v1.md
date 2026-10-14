> **LƯU TRỮ — không dùng để triển khai.** Bản đang dùng: `docs/proposal/proposal.md`. Đường dẫn bên trong file này có thể đã cũ.

# VeriClue — Đánh giá proposal & Đề xuất nâng cấp

> Tài liệu nội bộ nhóm DS@AInSec4E · Ngày 14/10/2026
> Dựa trên: `docs/proposal/VeriClue_Proposal.pdf` + nghiên cứu tài liệu, paper, báo cáo ngành, văn bản pháp luật (nguồn ở cuối mỗi mục).
> Các thông tin chưa kiểm chứng được tới nguồn gốc được đánh dấu **[cần kiểm tra]**.
>
> **Cập nhật:** đánh giá này đã được hiện thực hóa và mở rộng trong `docs/proposal/VeriClue_Proposal_v2.md`. Hai thay đổi so với nội dung bên dưới:
> - Bài toán gắn kết nên là **Đề bài 16 (BTL86)**, **Đề bài 62** và **DA940-02**, thay vì PB-096.
> - Một số tuyên bố "điểm mới" đã được hạ mức sau khi kiểm chứng tài liệu đi trước (xem mục 2.8 của v2).

---

## 0. Kết luận nhanh (TL;DR)

**Proposal hiện tại: chặt chẽ, trung thực, khả thi — nhưng CHƯA nổi bật.**
Nó viết rất "an toàn": thừa nhận giới hạn, khóa ngưỡng trước, tách tập theo người/thiết bị, có lộ trình thí điểm. Đó là điểm cộng lớn về độ tin cậy. Nhưng chính proposal cũng tự nhận *"điểm nhóm cần chứng minh không nằm ở việc tuyên bố một tính năng chưa từng tồn tại, mà ở cách đóng gói"* — với giám khảo, câu này đọc thành **"đây là bài tích hợp"**. Trong khi đó:

1. **Bộ điều phối — trái tim của đề tài — chưa có phương pháp cụ thể.** "Đánh giá độ chắc chắn", "nhận diện ngoài phạm vi", "kiểm tra mâu thuẫn" đều chưa nêu thuật toán.
2. **Proposal né đúng mối đe dọa thật đang xảy ra ở Việt Nam: tấn công chèn luồng camera.** Các vụ Thanh Hóa (2025–2026, 18 đối tượng, >2.000 tài khoản ngân hàng) dùng phần mềm thay luồng camera để qua mặt sinh trắc học — không phải ảnh in.
3. **Nhánh giọng nói có lỗ hổng logic:** câu thử thách ngẫu nhiên chỉ chặn được *phát lại*; không gắn giọng với khuôn mặt; detector tiếng Anh suy giảm mạnh trên tiếng Việt.
4. **Phép so sánh với "ngưỡng cố định" dễ bị coi là không công bằng** (thêm nhánh "duyệt thủ công" thì đương nhiên ít lỗi hơn).

**Hướng nâng cấp đề xuất** — giữ nguyên khung VeriClue, nhưng biến 3 thứ "mơ hồ" thành 3 điểm nhấn có cơ sở khoa học và có demo "wow":

| Trụ cột | Nội dung | Vì sao nổi bật |
|---|---|---|
| **A. Chứng minh hiện diện (Proof-of-Presence)** | Thử thách ánh sáng màu ngẫu nhiên trên màn hình + đo phản xạ trên mặt + đo độ trễ/đáp ứng camera để phát hiện camera ảo | Đánh thẳng vào kiểu tấn công Thanh Hóa; chạy được trên trình duyệt; demo trực quan |
| **B. Thử thách nghe–nhìn tiếng Việt** | Câu tiếng Việt ngẫu nhiên → kiểm nội dung (PhoWhisper) + chống giả giọng fine-tune tiếng Việt + kiểm khớp môi theo âm vị | Không vendor nào (trong & ngoài nước) có chống giả giọng tiếng Việt hay kiểm chéo mặt–giọng |
| **C. Bộ điều phối có bảo đảm thống kê** | Hiệu chỉnh xác suất → hợp nhất có trọng số chất lượng → cổng mâu thuẫn & ngoài phân phối → leo thang tuần tự (SPRT) → chọn ngưỡng bằng *Learn-then-Test* để **bảo đảm tỷ lệ lọt giả mạo ≤ α với xác suất ≥ 1−δ** | Hai nhánh nghiên cứu độc lập **không tìm thấy paper nào** áp dụng conformal/LTT cho chống giả mạo khuôn mặt → điểm mới thật sự |

Kèm hai đóng góp dữ liệu: **bộ red-team tấn công bối cảnh Việt Nam** và **ma trận bao phủ mối đe dọa trung thực** (cái gì chặn được / không chặn được).

> ⚠️ **Lưu ý thời gian:** theo dataforlife.vn, vòng 2 diễn ra 28/9–25/10 (trang chủ) hoặc 25/9–06/11 (thể lệ Điều 8) — hai nguồn đang lệch nhau. Hôm nay là 14/10 → còn khoảng **11 ngày hoặc ~3 tuần**. Cần hỏi BTC/mentor ngay để chốt deadline và danh sách đầu ra, rồi áp dụng bảng ưu tiên MUST/SHOULD/COULD ở mục 8.

---

## 1. Bối cảnh cuộc thi — giám khảo sẽ nhìn gì

- **Đơn vị chủ trì:** Bộ Công an (C06), phối hợp Bộ KH&CN, Bộ GD&ĐT, ĐH Bách khoa HN, VTV, Block71. Mùa 4 – 2026, chủ đề **"Build Together – Chung tay kiến tạo"**: chuyển từ *thưởng ý tưởng* sang *xây giải pháp triển khai được*.
- **5 tiêu chí chấm (Điều 9 thể lệ, không công bố trọng số):** (1) sát bài toán thực tế; (2) sáng tạo, mới; (3) khả thi kỹ thuật & kiến trúc dữ liệu; (4) tác động xã hội & thị trường; (5) năng lực & cam kết đội.
- **Quy định quan trọng:** bảo vệ dữ liệu được chấp nhận là yếu tố dữ liệu cốt lõi; phải tuân thủ luật BVDLCN; **cấm làm giả kết quả demo, dữ liệu thử, tính năng**.
- **Ngân hàng ý tưởng** có >5.000 bài toán; chọn bài toán trong Idea Bank được cộng điểm ưu tiên. Ví dụ **PB-096** (phát hiện, giám sát tội phạm mạng / đường dây có tổ chức) khá sát → **nên kiểm tra và gắn VeriClue với mã bài toán phù hợp**.
- **Giải đặc biệt:** Sáng tạo nhất, Tác động xã hội, **Công nghệ ấn tượng**, Bình chọn cộng đồng.
- **Xu hướng các đội thắng:** 2024 GoTrust (kiosk y tế dùng CCCD), 2025 Cheppy → sản phẩm *triển khai được*, gắn với dịch vụ công / dữ liệu dân cư.

→ **Hàm ý:** BTC là Bộ Công an — đơn vị đang trực tiếp điều tra các vụ qua mặt sinh trắc học. Một đề tài chống chèn luồng + deepfake cho eKYC **trúng đúng mối quan tâm của người chấm**, miễn là chứng minh được (a) giải quyết loại tấn công thật, (b) có cái mới, (c) chạy được.

Nguồn: dataforlife.vn/the-le · vtcnews.vn (ar1037147) · daibieunhandan.vn (10430369, 10399556, 10353225) · canhsatquanlyhanhchinh.gov.vn (3887)

---

## 2. Điểm mạnh của proposal hiện tại (giữ nguyên)

1. **Tách ba trạng thái** — *dữ liệu kém*, *có bằng chứng giả mạo*, *chưa đủ căn cứ* — là khung tư duy đúng và hiếm thấy. Đây là hạt nhân đáng phát triển.
2. **Tư duy khoa học tốt:** khóa ngưỡng trên tập dev, tách tập theo người/thiết bị/nguồn, báo cáo phân rã theo loại tấn công và điều kiện thu nhận, không đặt chỉ tiêu trước.
3. **Ý thức pháp lý & giấy phép:** nêu rõ CelebA-Spoof phi thương mại, FF++ cần điều khoản riêng; dữ liệu sinh trắc học lưu tạm, có hạn xóa.
4. **Trung thực về giới hạn:** thừa nhận web app không bảo đảm được camera thật (dẫn NIST SP 800-63A-4).
5. **Lộ trình thí điểm 3 pha** (quan sát → hỗ trợ duyệt → tự động có điều kiện) thực tế, giống cách ngân hàng đưa mô hình rủi ro vào vận hành.
6. **Kiến trúc mô-đun + hợp đồng đầu ra thống nhất** — giúp chia việc song song cho 5 người.

---

## 3. Điểm yếu, mâu thuẫn, lỗ hổng (theo mức độ nghiêm trọng)

### 🔴 Nghiêm trọng

**Y1. Tính mới yếu và tự nhận yếu.**
Mục 3.4 thừa nhận Jumio đã có liveness + deepfake + quyết định theo rủi ro, rồi định vị VeriClue là "đóng gói 4 giá trị". Theo khảo sát đối thủ, các thành phần *liveness, chống deepfake, phát hiện chèn luồng, thử thách ngẫu nhiên, hướng dẫn chụp* **đều là "table stakes"** của iProov, Jumio, FaceTec, Incode, Mitek… Nếu chỉ đóng gói lại thì không thắng được các đội mạnh.
→ *Sửa:* định vị lại thành **"lớp quyết định đáng tin cậy, có bảo đảm"** (xem mục 5). Khoảng trống thật ở đây: theo tài liệu công khai, không vendor nào cung cấp độ chắc chắn đã hiệu chỉnh, quyết định 3 hướng thu lại/duyệt, hồ sơ bằng chứng cho chuyên viên, hay chống giả giọng tiếng Việt.

**Y2. Bộ điều phối — phần cốt lõi — chưa có phương pháp.**
Proposal nói "đánh giá mức độ chắc chắn", "nhận diện mẫu ngoài phạm vi", "kiểm tra mâu thuẫn" nhưng không nói *bằng cách nào*. Giám khảo kỹ thuật sẽ hỏi ngay: *"Độ chắc chắn tính bằng gì? Ngưỡng ngoài phạm vi đặt thế nào? Hai mô-đun mâu thuẫn thì đo ra sao?"*
→ *Sửa:* formal hóa bằng lý thuyết quyết định Bayes 3 hành động + calibration + conformal/LTT + đo xung đột Dempster–Shafer + OOD + SPRT (chi tiết ở mục 5.C).

**Y3. Bỏ ngỏ mối đe dọa số 1 ngoài thực tế: chèn luồng (injection).**
- Báo cáo iProov 2025: tấn công camera ảo native tăng 2.665%, face-swap tăng 300%; có ~127 công cụ face-swap, 91 camera ảo *(số liệu của vendor)*.
- **Việt Nam:** vụ Thái Bình 05/2025 (KUBET, rửa >1.000 tỷ, dùng clip AI khuôn mặt chủ tài khoản); **hai vụ Thanh Hóa 2025–2026** (18 bị can, >2.000 tài khoản) dùng phần mềm **thay luồng camera bằng ảnh chân dung lưu sẵn** để qua bước quét khuôn mặt ngân hàng.
- Cả 3 vụ đều là *injection / deepfake số*, **không phải ảnh in hay màn hình phát lại** — trong khi dữ liệu chính của proposal (CelebA-Spoof) chủ yếu là tấn công trình diện vật lý.
- Proposal chỉ ghi nhận đây là giới hạn và đẩy cho "đơn vị tích hợp". Lập luận này đúng về mặt kỹ thuật, nhưng **làm đề tài lệch khỏi bài toán thật**.

→ *Sửa:* Trụ cột A — có những tín hiệu phát hiện chèn luồng làm được ngay trên trình duyệt. Đồng thời vẫn nói thẳng rằng bảo đảm ở cấp thiết bị (attestation) nằm ngoài phạm vi.

Nguồn: thanhnien.vn (185250530180639674) · vtcnews.vn (ar1025879) · kenh14.vn (215261008093659516) · iproov.com/reports/threat-intelligence-report-2025

**Y4. Nhánh giọng nói có lỗ hổng logic.**
1. **Không ràng buộc danh tính:** CCCD/VNeID không có mẫu giọng. Chống giả giọng chỉ chứng minh "có người thật đang nói", **không chứng minh người nói là người trong khung hình**. Kẻ tấn công cho mặt deepfake và để đồng phạm đọc câu là qua.
2. **Câu ngẫu nhiên chỉ chặn được phát lại.** Proposal chưa nói sẽ *kiểm nội dung câu đọc* (cần ASR). Zero-shot TTS (viXTTS, F5-TTS-Vietnamese) sinh câu trong ~1–3 giây; chuyển giọng thời gian thực (RVC ~190 ms trên CPU, LLVC ~20 ms) khiến giới hạn thời gian vô dụng *(con số độ trễ do agent ước lượng/trích từ paper)*.
3. **Logic kích hoạt bị ngược:** proposal chỉ hỏi giọng khi *rủi ro cao*. Nhưng nếu khuôn mặt đã có dấu hiệu giả rõ thì giọng "thật" cũng không nên cứu phiên đó, vì kẻ làm được deepfake mặt cũng clone được giọng. Bằng chứng bổ sung **chỉ có giá trị thông tin ở vùng mơ hồ**, không phải vùng rủi ro cao.
4. **Dữ liệu sai ngôn ngữ:** ASVspoof là tiếng Anh. Các nghiên cứu SEA-Spoof (Interspeech 2026) và VietPrism (2026) cho thấy detector suy giảm mạnh xuyên ngôn ngữ; VietPrism ghi nhận EER tăng từ 16,3% lên 33,6% khi giọng giả càng giống người thật. ASVspoof 5 cũng cho thấy các hệ thống hàng đầu hiệu chỉnh kém (actual DCF ≈ 1).

→ *Sửa:* Trụ cột B: kiểm nội dung bằng ASR, kiểm khớp môi theo câu đã biết, fine-tune trên dữ liệu tiếng Việt, kích hoạt ở vùng mơ hồ.

### 🟠 Quan trọng

**Y5. Phép so sánh với "ngưỡng cố định" không công bằng.**
Hệ 3 đầu ra có thêm "duyệt thủ công" thì đương nhiên ít lỗi tự động hơn hệ 2 đầu ra; cái giá là tải duyệt. Giám khảo có nền ML sẽ chỉ ra ngay.
→ *Sửa:* so sánh **ở cùng ngân sách duyệt** (ví dụ review rate = 5%, 10%), dùng **đường risk–coverage + AURC**. Baseline mạnh hơn gồm: (i) 1 ngưỡng trên điểm PAD; (ii) hợp nhất logistic + 1 ngưỡng; (iii) **hai ngưỡng kiểu Chow** (vùng xám → duyệt) trên điểm hợp nhất; (iv) split conformal thường. VeriClue phải thắng **(iii)** mới có ý nghĩa.

**Y6. Mâu thuẫn giữa chỉ số hứa đo và dữ liệu có sẵn.**
- "Tỷ lệ thu lại thành công", "thời gian hoàn thành phiên" chỉ đo được trên **phiên người thật**. Nhưng mục 5.3 lại nói tập tình nguyện "không được dùng để tuyên bố khả năng khái quát".
- "Tách theo thiết bị": ASVspoof không có metadata thiết bị; CelebA-Spoof có nhưng hạn chế.
- **Không có bộ dữ liệu nào ghép đôi mặt + giọng cùng phiên, kèm tấn công.** CelebA-Spoof (ảnh) và ASVspoof (âm thanh) rời nhau, nên đánh giá hợp nhất / mâu thuẫn chỉ làm được trên **cặp ghép nhân tạo** (chimeric) — cần nói rõ.

→ *Sửa:* tách thành **hai tầng đánh giá**:
- *Tầng mô-đun:* dữ liệu công khai, báo cáo APCER/BPCER chuẩn ISO.
- *Tầng hệ thống:* tập phiên tự thu có đồng ý — ~20–30 người, 3–4 điện thoại, bona fide + red-team. Chỉ số UX và hệ thống tuyên bố **trong phạm vi tập này**, kèm khoảng tin cậy bootstrap.

**Y7. Vòng lặp thu lại có thể bị lợi dụng, và lời giải thích có thể thành "oracle" cho kẻ tấn công.**
- Kẻ tấn công có thể cố tình làm mờ/tối để giấu artifact deepfake, rồi được *thu lại vô hạn* và dò hệ thống.
- Thông điệp như "phát hiện viền màn hình" giúp kẻ tấn công tối ưu hóa.

→ *Sửa:*
- Giới hạn N lần thu lại; lỗi chất lượng lặp lại cũng là tín hiệu rủi ro → chuyển duyệt.
- **Giải thích hai tầng:** người dùng chỉ nhận hướng dẫn *chất lượng* (ánh sáng, vị trí, tiếng ồn); toàn bộ bằng chứng giả mạo chỉ hiện cho chuyên viên.

**Y8. Thiếu mô hình đe dọa tường minh.**
Proposal nhắc tới "mô hình đe dọa" nhưng không trình bày.
→ *Sửa:* thêm bảng kẻ tấn công × kỹ thuật × lớp phòng thủ × kết quả kỳ vọng (mục 6). Bảng này tăng độ chặt chẽ rõ rệt.

**Y9. Thiếu thuật ngữ và chỉ số chuẩn quốc tế.**
Nên dùng đúng chuẩn:
- **ISO/IEC 30107-3:** APCER *theo từng loại tấn công* (PAI species) và APCER_max, BPCER, BPCER@APCER=5% (BPCER20).
- **ISO/IEC 19795-1:** tỷ lệ không thu nhận được (FTA) cho nhánh "thu lại".
- **ISO/IEC 29794-5:2025:** chất lượng ảnh mặt.
- **CEN/TS 18099:2024:** phát hiện chèn luồng.
- **t-DCF:** chỉ số cho nhánh giọng nói.

### 🟡 Nhỏ nhưng nên sửa

- **Y10. Thiếu "từ chối":** mọi ca đáng ngờ đều đi duyệt thủ công nên ở quy mô lớn tải duyệt sẽ phình. Nên có mức **ưu tiên duyệt** (khẩn / thường) hoặc nhánh "chặn tạm + duyệt" cho ca bằng chứng rất mạnh.
- **Y11. Bối cảnh Việt Nam quá mỏng.** Thiếu số liệu và quy định, xem mục 4 để bổ sung.
- **Y12. Công bằng:** proposal có nêu rủi ro "dữ liệu không phải người Việt" nhưng chưa có kế hoạch đo. Nên báo cáo **BPCER theo hạng thiết bị và điều kiện ánh sáng**: chứng nhận iBeta của VNPT chỉ test trên iPhone 12, trong khi người dùng thật có nhiều máy Android giá rẻ.
- **Y13. Văn phong marketing** như "giải pháp tối ưu" (mục 4.1) lệch với giọng khoa học của phần còn lại.
- **Y14. Giấy phép:** phần lớn trọng số mạnh là phi thương mại (FoundPAD CC BY-NC-SA, Effort/DeepfakeBench/DF40 CC BY-NC, SBI, LAA-Net; mô hình InsightFace). Không sao trong bản thi, nhưng phải có **bảng giấy phép** (mục 7) và lộ trình thay bằng thành phần sạch.

---

## 4. Bổ sung bối cảnh Việt Nam (đưa vào phần "Đặt vấn đề")

| Dữ kiện | Nguồn |
|---|---|
| QĐ 2345/QĐ-NHNN (từ 1/7/2024): xác thực sinh trắc khi chuyển >10 triệu/lần hoặc >20 triệu/ngày | vietnamnews.vn (1658627) |
| TT 17/2024/TT-NHNN: đối chiếu sinh trắc với chip CCCD / CSDLQG về dân cư; cá nhân từ 1/1/2025 | div.gov.vn |
| **TT 77/2025/TT-NHNN (hiệu lực 1/3/2026)**: giải pháp **PAD phải được chứng nhận** bởi phòng lab FIDO hoặc **ISO/IEC 30107 mức 2**; app ngân hàng phải dừng khi phát hiện root/jailbreak, **giả lập**, chèn mã, debug **[cần đọc văn bản gốc]** | luatvietnam.vn (883-106480) |
| 132,4 triệu hồ sơ KH cá nhân đã đối chiếu sinh trắc (10/10/2025); số vụ lừa đảo giảm 59% | mekongasean.vn |
| **Nhưng** thiệt hại lừa đảo trực tuyến vẫn **>6.000 tỷ đồng trong 11 tháng 2025** (Bộ Công an); A05 nhận định lừa đảo dùng AI là thủ đoạn phổ biến nhất 2025 | sggp.org.vn · viettimes.vn |
| Vụ Thái Bình 05/2025; hai vụ Thanh Hóa 2025–2026 (chèn luồng camera, >2.000 tài khoản) | thanhnien.vn · vtcnews.vn · kenh14.vn |
| Sumsub: deepfake tại VN tăng 541% (2024) *(số liệu vendor)* | technode.global |
| Luật BVDLCN 91/2025/QH15 (hiệu lực 1/1/2026) + **NĐ 356/2025**: dữ liệu sinh trắc là dữ liệu **nhạy cảm**, cần đồng ý rõ ràng, kiểm chứng được | thuvienphapluat.vn |
| **Luật Trí tuệ nhân tạo 134/2025/QH15** (hiệu lực 1/3/2026): gắn nhãn nội dung AI, cấm dùng deepfake để lừa đảo | daibieunhandan.vn (10399959) |

**Câu chuyện vấn đề nên viết lại:** *"Sau khi sinh trắc học trở thành bắt buộc, tội phạm không còn cầm ảnh trước camera nữa — chúng **thay luồng camera**. Các hệ eKYC Việt Nam hiện được chứng nhận chủ yếu về tấn công trình diện vật lý; chưa thấy vendor nội địa nào công bố chứng nhận chống chèn luồng (CEN/TS 18099) hay chống giả giọng tiếng Việt. VeriClue lấp khoảng trống đó và làm cho mỗi quyết định **có bảo đảm và giải thích được**."*

---

## 5. Thiết kế nâng cấp: VeriClue với 3 trụ cột

Khung 4 lớp (thu nhận → chất lượng → bằng chứng → điều phối) **giữ nguyên**. Ba trụ cột dưới đây là phần lấp nội dung vào khung.

### A. Proof-of-Presence — chứng minh hiện diện thật, ngay trên trình duyệt

**A1. Thử thách ánh sáng màu ngẫu nhiên (kiểu Face Flashing, NDSS 2018; tương tự iProov Flashmark thương mại).**
- Server cấp một **chuỗi màu ngẫu nhiên** (nonce) gắn với mã phiên. Màn hình phát chuỗi này toàn màn hình trong ~2–3 giây.
- Client trích sắc độ trung bình vùng da (trán, má — lấy landmark bằng MediaPipe) theo từng khung hình.
- Server tính **tương quan chéo** giữa chuỗi phát và chuỗi phản xạ, cùng **độ trễ pha**.
- Ba thứ kiểm cùng lúc:
  - (i) có phản xạ đúng chuỗi → chặn ảnh và video phát lại vì không biết trước chuỗi;
  - (ii) phản xạ phù hợp bề mặt 3D da so với màn hình phẳng hay giấy;
  - (iii) **độ trễ** — pipeline face-swap thời gian thực + camera ảo thêm trễ, và có thể không "relight" đúng.
- Paper gốc báo cáo độ chính xác 98,8% *(trên thiết lập của họ)*.
- Hạn chế cần nêu: ánh sáng môi trường mạnh, auto-exposure / auto white balance, màn hình tối.
- Đây là **demo "wow" số 1:** khán giả thấy màn hình nháy màu và biểu đồ tương quan hiện ra theo thời gian thực.

**A2. Thăm dò camera ảo bằng `applyConstraints` (Kurmankhojayev et al., arXiv 2512.10653, 2025).**
- Trình duyệt yêu cầu đổi độ phân giải / FPS rồi đo **độ trễ đáp ứng của driver** và **mức khớp giữa thông số báo cáo và khung hình thật**.
- Camera ảo phản ứng khác cảm biến thật.
- Paper báo cáo ~14,6% BPCER tại 10% APCER — **tín hiệu yếu, chỉ dùng như một lớp**.
- Kết hợp thêm `requestVideoFrameCallback` (jitter, khung trùng lặp) và nhãn thiết bị (rất dễ giả, trọng số thấp).

**A3. Ràng buộc phiên:** nonce, timestamp có chữ ký, chuỗi màu và câu thử thách sinh từ cùng seed phía server. Hồ sơ bằng chứng có hash và chữ ký server (có thể theo định dạng C2PA cho bundle bằng chứng).

**A4. Passive PAD + deepfake (giữ như proposal, chọn mô hình hợp lý):**
- *Trên trình duyệt:* MiniFASNet ONNX (Apache-2.0) để phản hồi nhanh.
- *Trên server:* đặc trưng DINOv2 (Apache-2.0) hoặc CLIP (MIT) + LoRA / linear head, huấn luyện theo hướng FoundPAD / FLIP.
- *Deepfake:* UnivFD (MIT) hoặc detector CLIP của Cozzolino (Apache-2.0).
- *So sánh nghiên cứu:* Effort (ICML 2025) / DeepfakeBench, dùng cho đối chứng (giấy phép phi thương mại).

### B. Thử thách nghe–nhìn tiếng Việt — gắn giọng với khuôn mặt

**B1. Câu tiếng Việt ngẫu nhiên** (≥10 từ, sinh từ ngân hàng từ; *cố ý chứa âm môi m/b/p*) → **PhoWhisper** (VinAI, BSD-3/Apache) kiểm nội dung bằng CER, có phương án so khớp bỏ dấu để không chặn nhầm người thật vì ASR sai thanh điệu.

**B2. Chống giả giọng fine-tune tiếng Việt:**
- *Mô hình nền:* SSL-AASIST (XLS-R + AASIST, MIT) hoặc XLSR-Mamba (MIT).
- *Dữ liệu thật:* **VSASV** (VLSP, CC-BY-4.0), Common Voice VI, giọng tự thu.
- *Dữ liệu giả do nhóm tự sinh:* viXTTS, F5-TTS-Vietnamese, VietTTS, RVC, cộng thêm nén codec và thu lại qua loa → mic điện thoại.
- *Báo cáo trung thực:* **leave-one-generator-out** (ví dụ train không có F5, test trên F5).

**B3. Kiểm khớp môi có điều kiện theo câu đã biết** — điểm mới có thể nhận:
- Vì *biết trước câu* và có *timestamp từ ASR*, hệ thống kiểm tra **môi có khép đúng lúc phát âm m/b/p** (phát triển từ "phoneme–viseme mismatch", Agarwal & Farid, CVPRW 2020).
- Kết hợp điểm đồng bộ SyncNet / AVAD (CVPR 2023, MIT, chỉ huấn luyện trên video thật).
- Chưa tìm thấy công bố nào làm việc này cho tiếng Việt. Chưa có mô hình đọc môi tiếng Việt công khai, nên **không** làm lip-reading đầy đủ.

**B4. Nhất quán người nói trong phiên:** ECAPA-TDNN (SpeechBrain) để phát hiện ghép nối hoặc đổi người giữa các đoạn. **Không** dùng face–voice matching vì EER ~24% là quá yếu.

**B5. Nói thẳng giới hạn:** *face-swap trực tiếp + chuyển giọng thời gian thực* khiến môi và tiếng **khớp tự nhiên** — kiểm khớp môi không chặn được. Chỉ detector giọng giả và detector face-swap (cùng thử thách ánh sáng A1) gánh trường hợp này. Đưa thẳng vào ma trận đe dọa — giám khảo đánh giá cao sự trung thực này.

### C. Bộ điều phối có bảo đảm thống kê (trái tim khoa học)

**Đầu vào:**
- log-likelihood ratio **đã hiệu chỉnh** từ từng mô-đun: ℓ_PAD, ℓ_deepfake, ℓ_light, ℓ_inject, ℓ_voice, ℓ_AVsync;
- vector chất lượng q (lấy cảm hứng từ ISO 29794-5 / OFIQ);
- điểm OOD o;
- độ xung đột K.

**Quy trình định tuyến (theo thứ tự):**
1. **Cổng chất lượng:** q dưới ngưỡng → **THU LẠI**, tối đa N lần, sau đó → **DUYỆT** (chống khai thác vòng lặp).
2. **Cổng ngoài phân phối:** p-value conformal của điểm OOD (energy / kNN trên embedding) < γ → **DUYỆT**. Có bảo đảm: tỷ lệ báo động nhầm OOD trên người thật ≤ γ.
3. **Cổng mâu thuẫn:** độ xung đột Dempster–Shafer giữa các nguồn (học bằng chứng — Evidential DL, Sensoy 2018; Trusted Multi-View, Han ICLR 2021) > κ → **DUYỆT** hoặc xin thêm bằng chứng.
4. **Hợp nhất có trọng số chất lượng** (likelihood-ratio fusion, Nandakumar TPAMI 2008): Λ = Σ ℓ_m(s_m, q_m). Chất lượng thấp *làm phẳng* LLR của mô-đun đó thay vì đẩy về "giả mạo" — đây là cách **toán học hóa** ý tưởng "đừng nhầm ảnh xấu thành giả mạo" của proposal.
5. **Leo thang tuần tự kiểu SPRT** (Wald 1945; Allano 2010 cho đa sinh trắc):
   - Λ ≤ B → **TIẾP TỤC**;
   - Λ ≥ A → **DUYỆT (ưu tiên cao)**;
   - B < Λ < A → yêu cầu thử thách tiếp theo (ánh sáng → câu nói), **chỉ khi giá trị thông tin vượt chi phí trải nghiệm**, rồi cập nhật Λ;
   - hết bằng chứng mà vẫn mơ hồ → **DUYỆT**.
   - Kết quả: *"ma sát thích ứng"* — người thật rõ ràng đi nhanh, chỉ ca mơ hồ mới bị hỏi thêm.
6. **Chọn ngưỡng (B, A, κ, γ) bằng Learn-then-Test** (Angelopoulos et al., Annals of Applied Statistics 2025):
   - kiểm định đa giả thuyết trên tập calibration;
   - bảo đảm **P(APCER_max theo từng loại tấn công ≤ α) ≥ 1−δ** và BPCER ≤ β;
   - trong các bộ ngưỡng hợp lệ, chọn bộ **tối thiểu chi phí kỳ vọng** = C_duyệt × tỷ lệ duyệt + C_UX × (tỷ lệ thu lại + tỷ lệ thử thách).

**Câu chốt cho pitch:**
> *"VeriClue không chỉ nói 'tôi nghĩ phiên này thật'. Nó nói: 'trên các loại tấn công đã kiểm thử, xác suất để tỷ lệ lọt vượt 1% là dưới 5% — và với ca nằm ngoài vùng đã kiểm thử, tôi không tự quyết'."*

**Rủi ro học thuật cần nêu:** bảo đảm conformal giả định dữ liệu *có thể hoán đổi* (exchangeable) — tấn công chưa từng thấy phá giả định này, nên cần cổng OOD và chế độ vận hành pha 1 "quan sát". Với <~100 mẫu tấn công mỗi loại, bảo đảm sẽ yếu; phải báo cáo số mẫu.

### D. Hồ sơ bằng chứng hai tầng

- **Người dùng:** chỉ hướng dẫn sửa lỗi chất lượng ("Bạn vui lòng ra chỗ sáng hơn") — không lộ tín hiệu chống giả mạo.
- **Chuyên viên:** điểm từng mô-đun, heatmap, biểu đồ tương quan ánh sáng, transcript và căn chỉnh môi–âm, tín hiệu camera ảo, **bằng chứng phản bác** và câu "mô hình không chắc vì…", nhãn ưu tiên.
- **Điểm cộng nghiên cứu (nếu kịp):** nghiên cứu năm 2026 (381 người) cho thấy giải thích trực quan tăng niềm tin nhưng **không** giúp phụ thuộc AI đúng mức. Một user study nhỏ — 5–10 người duyệt, có và không có hồ sơ, đo độ chính xác + thời gian + mức độ tin theo AI sai — sẽ là đóng góp thực sự.

---

## 6. Ma trận đe dọa (đưa vào proposal / slide)

| # | Tấn công | Công cụ tiêu biểu | Lớp phát hiện chính | Kỳ vọng |
|---|---|---|---|---|
| T1 | Ảnh in / ảnh trên màn hình | Giấy, điện thoại | PAD passive, thử thách ánh sáng A1 | Chặn tốt |
| T2 | Video phát lại | Màn hình, video cũ | A1 (không biết chuỗi màu), câu ngẫu nhiên + ASR | Chặn tốt |
| T3 | **Chèn ảnh / video lưu sẵn qua camera ảo** (kiểu Thanh Hóa) | OBS, app camera ảo, Android root | A1 (không phản xạ chuỗi), A2 (đáp ứng driver), ràng buộc phiên | Chặn phần lớn; *không bảo đảm nếu kẻ tấn công can thiệp sâu cấp thiết bị* |
| T4 | Ảnh nạn nhân + TTS + lip-sync offline | viXTTS/F5 + MuseTalk/LatentSync | Phát hiện giọng giả, AV sync, khép môi m/b/p, A1 | Chặn phần lớn |
| T5 | **Face-swap trực tiếp + chuyển giọng thời gian thực** | Deep-Live-Cam + RVC + camera ảo | Detector face-swap, A1 (relight + trễ), detector giọng chuyển đổi | **Khó nhất** — môi và tiếng khớp tự nhiên; báo cáo trung thực tỷ lệ lọt |
| T6 | Mẫu chất lượng kém cố ý + dò hệ thống | Làm mờ, tối | Giới hạn N lần thu lại, giải thích hai tầng | Chuyển duyệt |
| — | Ngoài phạm vi | Bảo đảm camera cấp thiết bị, xác thực chip CCCD/NFC, đối chiếu CSDLQG | Đơn vị triển khai (app attestation — đúng tinh thần TT 77/2025 Điều 5) | Nêu rõ |

**Đóng góp dữ liệu:** nhóm tự dựng **bộ red-team VN** — T1–T6 trên khuôn mặt và giọng các thành viên có đồng ý, 3–4 điện thoại, nhiều điều kiện ánh sáng — và báo cáo **APCER theo từng loại tấn công**. Chưa thấy bộ dữ liệu deepfake khuôn mặt tiếng Việt / người Việt nào công khai.

> Lưu ý đạo đức & pháp lý: chỉ dùng khuôn mặt, giọng của thành viên hoặc người tình nguyện có văn bản đồng ý (NĐ 356/2025). Công cụ tấn công chỉ dùng nội bộ để kiểm thử, không phát tán mẫu tấn công.

---

## 7. Stack công nghệ & giấy phép

| Thành phần | Lựa chọn | Giấy phép | Ghi chú |
|---|---|---|---|
| Landmark / face mesh (client) | MediaPipe Face Landmarker | Apache-2.0 | Chạy trên trình duyệt |
| Phát hiện mặt | YuNet (opencv_zoo) | Apache-2.0 | |
| PAD nhẹ (client) | MiniFASNet ONNX + onnxruntime-web | Apache-2.0 | Yếu với replay chất lượng cao |
| PAD server | DINOv2 / CLIP + LoRA tự huấn luyện | Apache / MIT (backbone) | Dữ liệu huấn luyện CelebA-Spoof/OCIM: chỉ nghiên cứu |
| Deepfake | UnivFD / Cozzolino-CLIP | MIT / Apache | Effort, DeepfakeBench, SBI, LAA-Net: **NC**, chỉ đối chứng |
| Chất lượng ảnh | Tập con kiểu OFIQ (blur, pose, sáng, kích thước) | OFIQ code MIT | CR-FIQA / SER-FIQ là NC |
| ASR tiếng Việt | PhoWhisper (small/base) / faster-whisper | BSD-3 / Apache | |
| Chống giả giọng | SSL-AASIST hoặc XLSR-Mamba | MIT | SLS **không có license** |
| AV sync | SyncNet, AVAD | MIT **[cần kiểm tra SyncNet]** | AV-HuBERT: giấy phép riêng của Meta |
| Nhất quán người nói | SpeechBrain ECAPA-TDNN | Apache-2.0 | |
| Công cụ red-team | Deep-Live-Cam (AGPL), viXTTS (CPML, NC), F5-TTS-VI (CC BY-NC-SA), RVC, OBS | — | Chỉ dùng nội bộ |
| Dữ liệu | CelebA-Spoof, VSASV (CC-BY-4.0), ASVspoof 2019/2021/5, UniAttackData **[cần kiểm tra]**, Zalo AI 2022 Liveness **[cần kiểm tra]** | — | |
| Backend / Frontend | FastAPI, PyTorch, ONNX Runtime, Next.js, PostgreSQL, Docker | — | Giữ như proposal |

Đề xuất thêm một mục **"Model & data card"** trong báo cáo: liệt kê thành phần nào dùng thương mại được và thành phần nào chỉ để nghiên cứu.

---

## 8. Ưu tiên triển khai (khớp quỹ thời gian còn lại)

**MUST — không có thì không demo được câu chuyện:**
1. Luồng web: mã phiên → hướng dẫn khuôn mặt → kiểm chất lượng client → gửi server.
2. **A1 – thử thách ánh sáng màu** (demo wow) + PAD MiniFASNet / DINOv2 linear head.
3. **C – bộ điều phối phiên bản 1:** calibration (Platt) → hợp nhất logistic có đặc trưng chất lượng → hai ngưỡng chọn bằng LTT (thư viện `aangelopoulos/ltt`) → 3 hành động + giới hạn thu lại.
4. Cổng duyệt tối giản: danh sách ca + hồ sơ bằng chứng + nút quyết định.
5. **Bộ red-team mini** (T1, T2, T3 bằng OBS, T5 bằng Deep-Live-Cam) + báo cáo so sánh với baseline Chow 2 ngưỡng **ở cùng tỷ lệ duyệt**.

**SHOULD:**

6. B1 + B2: câu tiếng Việt + PhoWhisper + SSL-AASIST fine-tune nhanh trên VSASV + mẫu giả tự sinh.
7. A2: thăm dò `applyConstraints`.
8. Cổng OOD (kNN hoặc energy + conformal p-value), độ xung đột.
9. Leo thang kiểu SPRT (ánh sáng → câu nói chỉ khi mơ hồ).

**COULD:**

10. B3: khép môi m/b/p theo timestamp ASR + SyncNet.
11. Phân rã BPCER theo hạng điện thoại.
12. User study nhỏ cho chuyên viên duyệt.
13. Model card / license audit hoàn chỉnh.

**Phân công gợi ý (5 người):**

| Người | Phụ trách |
|---|---|
| 1 | Frontend thu nhận + thử thách ánh sáng + kiểm chất lượng client (A1, A2) |
| 2 | Cổng duyệt + hồ sơ bằng chứng (D) + giao diện demo |
| 3 | Khuôn mặt: PAD / deepfake server + xử lý tín hiệu phản xạ ánh sáng |
| 4 | Giọng nói: PhoWhisper + anti-spoof tiếng Việt + sinh dữ liệu giả (B) |
| 5 | API / điều phối (C) + calibration / LTT + pipeline đánh giá & red-team |

Nguyên tắc giữ từ proposal: **tích hợp xuyên suốt từ ngày đầu** (mô-đun giả lập trả điểm ngẫu nhiên trước, thay bằng mô hình thật sau).

---

## 9. Giao thức đánh giá chuẩn hóa (thay mục 2.4 và 5.3)

- **Chia tập:** train / calibration / test **tách theo người**. Leave-one-attack-type-out. Giữ riêng một bộ sinh deepfake / TTS cho test.
- **Chỉ số mô-đun:**
  - APCER theo từng loại tấn công, APCER_max, BPCER, BPCER@APCER 1% và 5%, EER;
  - t-DCF cho giọng;
  - ECE, C_llr cho calibration.
- **Chỉ số hệ thống:**
  - tỷ lệ duyệt, tỷ lệ thu lại (FTA), tỷ lệ phải làm thử thách, số lần thử trung bình, thời gian phiên, chi phí kỳ vọng mỗi phiên;
  - **đường risk–coverage + AURC**;
  - **tần suất vi phạm bảo đảm LTT** qua nhiều lần chia lại (phải ≤ δ).
- **Baseline:**
  - (1) ngưỡng cố định trên điểm PAD;
  - (2) hợp nhất + 1 ngưỡng;
  - (3) **Chow 2 ngưỡng ở cùng tỷ lệ duyệt**;
  - (4) split conformal thường;
  - (5) luôn hỏi giọng nói (so ma sát).
- **Ablation:** bỏ lần lượt calibration, trọng số chất lượng, cổng OOD, cổng mâu thuẫn, leo thang SPRT, thử thách ánh sáng.
- **Thống kê:**
  - bootstrap theo người (cluster) cho khoảng tin cậy 95%;
  - Clopper–Pearson cho APCER thấp;
  - McNemar cho quyết định ghép cặp với baseline;
  - hiệu chỉnh Holm khi so nhiều cặp;
  - luôn ghi số mẫu mỗi loại tấn công.

---

## 10. Gợi ý viết lại thông điệp

- **Tagline:** *"VeriClue — Không chỉ phát hiện giả mạo: chứng minh hiện diện, và biết khi nào không nên tự quyết."*
- **Ba câu "tại sao chúng tôi khác":**
  1. **Chống loại tấn công đang thật sự xảy ra ở Việt Nam** — chèn luồng camera và deepfake — bằng thử thách ánh sáng và thăm dò camera chạy ngay trên trình duyệt.
  2. **Bảo đảm thống kê cho từng quyết định tự động** — tỷ lệ lọt bị chặn trên có xác suất — thay vì một ngưỡng chọn cảm tính.
  3. **Gắn giọng nói tiếng Việt với khuôn mặt** bằng câu thử thách: kiểm nội dung, kiểm giọng giả, kiểm khép môi đúng âm.
- **Trả lời trước câu hỏi khó:**
  - *"Vendor lớn làm rồi?"* — Họ làm phát hiện. Chúng tôi làm quyết định có bảo đảm, có giải thích, cho tiếng Việt và cho thiết bị phổ thông. Đó là các khoảng trống không vendor nào công bố.
  - *"Web app thì sao chặn được camera ảo?"* — Không bảo đảm tuyệt đối. Chúng tôi tăng chi phí tấn công bằng các tín hiệu đo được, báo cáo trung thực tỷ lệ lọt, và chỉ rõ phần thuộc về app attestation (đúng yêu cầu TT 77/2025).

---

## 11. Việc cần xác minh ngay

1. Deadline vòng 2 và danh sách đầu ra — hỏi BTC hoặc mentor (hai mốc ngày đang lệch nhau).
2. Mã bài toán Idea Bank phù hợp (PB-096 hay mã nào sát hơn) để được cộng điểm ưu tiên.
3. Văn bản gốc TT 77/2025/TT-NHNN: điều khoản PAD và mốc hiệu lực.
4. Quyền tải UniAttackData, Zalo AI 2022 Liveness, VietPrism, SEA-Spoof; giấy phép SyncNet, viVoice.
5. Kiểm tra lại claim "chưa có paper conformal/LTT cho FAS/deepfake" bằng Google Scholar trước khi viết vào proposal (hai nhánh nghiên cứu độc lập đều không tìm thấy, nhưng chưa tìm trên các cơ sở dữ liệu chuyên sâu).

---

## Phụ lục — Tài liệu tham khảo chính

**Quyết định & thống kê**
- Chow 1970 (reject option)
- Geifman & El-Yaniv NeurIPS 2017 / ICML 2019 (selective classification, SelectiveNet)
- Mozannar & Sontag ICML 2020 (learning to defer)
- Angelopoulos & Bates 2023 (conformal intro)
- Angelopoulos et al., *Conformal Risk Control* ICLR 2024
- Angelopoulos et al., *Learn then Test*, AoAS 2025 — arXiv 2110.01052, github.com/aangelopoulos/ltt
- Tibshirani et al. NeurIPS 2019 (conformal under covariate shift)
- Guo et al. ICML 2017 (calibration)
- Nandakumar et al. TPAMI 2008 (LR fusion)
- Poh et al. TIFS 2009 (quality-dependent fusion)
- Sensoy et al. NeurIPS 2018 (evidential DL)
- Han et al. ICLR 2021 (trusted multi-view)
- Liu et al. NeurIPS 2020 (energy OOD); Sun et al. ICML 2022 (kNN OOD)
- Wald 1945 (SPRT); Allano et al. PRL 2010 (SPRT trong đa sinh trắc)

**Khuôn mặt**
- Tang et al., *Face Flashing*, NDSS 2018 (arXiv 1801.01949)
- Kurmankhojayev et al., *Virtual camera detection*, arXiv 2512.10653
- Ozgur et al., FoundPAD, WACV-W 2025
- Srivatsan et al., FLIP, ICCV 2023
- Ojha et al., UnivFD, CVPR 2023
- Cozzolino et al., CVPR-W 2024
- Effort, ICML 2025
- Seibold et al., *High-quality deepfakes have a heart!*, Frontiers in Imaging 2025
- NIST IR 8491 (FATE PAD); NIST SP 800-63A-4
- ISO/IEC 30107-3, 29794-5:2025, 19795-1; CEN/TS 18099:2024

**Giọng nói & nghe–nhìn**
- Jung et al., AASIST, ICASSP 2022; Tak et al., SSL-AASIST, Odyssey 2022; XLSR-Mamba
- ASVspoof 5 (arXiv 2408.08739)
- SEA-Spoof (arXiv 2509.19865); VietPrism (arXiv 2609.30005); VSASV (VLSP)
- PhoWhisper (arXiv 2406.02555)
- Agarwal et al. CVPRW 2020 (phoneme–viseme)
- Feng et al., AVAD, CVPR 2023
- Haliassos et al., LipForensics, CVPR 2021
- Mittal et al., challenge-response cho deepfake audio (arXiv 2402.18085)

**Thị trường**
- iProov Threat Intelligence Report 2024/2025
- Entrust/Onfido Identity Fraud Report 2025
- Sumsub Identity Fraud Report
- Gartner PR 01/02/2024
- Thư xác nhận iBeta cho VNPT (03/2026), VNPAY (2024)
- Deepfake-Eval-2024 (arXiv 2503.02857)
