> **LƯU TRỮ — không dùng để triển khai.** Bản đang dùng: `docs/proposal/proposal.md`. Đường dẫn bên trong file này có thể đã cũ.

# BẢN ĐỀ XUẤT GIẢI PHÁP — PHIÊN BẢN 2

# VeriClue
### Lớp tin cậy cho định danh điện tử: chứng minh hiện diện thật, quyết định có bảo đảm, lần ra đường dây

**Đội thi:** DS@AInSec4E — Phạm Anh Quốc · Lê Quang · Trần Văn Đức · Lý Anh Quân · Hồ Lê Ngọc Quang
**Cuộc thi:** Data for Life 2026 — Vòng 2 "Phát triển giải pháp"
**Bài toán gắn kết (Ngân hàng ý tưởng):**
- **Đề bài 16 – Bộ Tư lệnh 86 (BQP):** "Phát hiện deepfake giọng nói, hình ảnh trong giả mạo định danh" — *bài toán chính*
- **Đề bài 62 – Công an xã Hòa An, Cao Bằng:** "Chỉ số tin cậy danh tính số"
- **DA940-02:** "AI sinh trắc học và chống gian lận danh tính"

> Phiên bản 2 thay thế bản nộp vòng 1 (`VeriClue_Proposal.pdf`). Bản này giữ nguyên tư tưởng gốc: tách *dữ liệu kém*, *bằng chứng giả mạo* và *chưa đủ căn cứ*; không ép kết luận; có người duyệt. Những gì thay đổi:
> - **Mô hình đe dọa** được viết lại theo các vụ án thật tại Việt Nam năm 2025–2026.
> - Bổ sung lớp **chứng minh hiện diện** để chống chèn luồng camera.
> - Bộ điều phối được **toán học hóa**, có **bảo đảm thống kê**.
> - Nhánh giọng nói được **gắn với khuôn mặt** và **huấn luyện cho tiếng Việt**.
> - Thêm **Ring Radar** (phát hiện đường dây) và **chế độ giám định** cho cơ quan điều tra.
>
> Mọi tuyên bố về tính mới đã được đối chiếu với tài liệu đã công bố. Các thành phần đã có người làm trước đều được trích dẫn rõ ở mục 2.8.

---

## TÓM TẮT ĐIỀU HÀNH

**Vấn đề.** Từ 2024, Việt Nam bắt buộc đối chiếu sinh trắc học cho giao dịch ngân hàng trực tuyến. Biện pháp này hiệu quả: 175,2 triệu hồ sơ khách hàng đã được đối chiếu và số người bị lừa giảm 59%. Vì vậy tội phạm **không cầm ảnh trước camera nữa — chúng tấn công chính khâu sinh trắc học**:
- *Thái Bình 2025:* dựng clip AI khuôn mặt từ video nguồn 25–30 giây để qua bước xác thực; rửa hơn 1.000 tỷ đồng.
- *Thanh Hóa 2025–2026:* hai đường dây (18 bị can, mỗi vụ hơn 1.000 tài khoản) dùng phần mềm **thay luồng camera** bằng ảnh chân dung lưu sẵn.
- *Quảng Ninh 2025:* thuê người thật ở tập trung để "quét mặt ngày đêm" cho các tài khoản lừa đảo.

Trong khi đó:
- Chứng nhận PAD mà Thông tư 50/2024 (sửa đổi bởi TT 77/2025) yêu cầu chỉ đo **tấn công trình diện vật lý**, **không kiểm thử chèn luồng hay deepfake**.
- Các bộ phát hiện mã nguồn mở mất khoảng 50% AUC khi gặp deepfake ngoài đời thực.
- Con người chỉ nhận ra deepfake đúng **55,5%** — gần như đoán mò (phân tích tổng hợp 56 nghiên cứu, 86.155 người).

**Giải pháp.** VeriClue là **lớp tin cậy bổ trợ** đặt giữa bước thu nhận và quyết định eKYC. Nó **không thay thế** engine PAD đã được chứng nhận của đơn vị triển khai, mà bổ sung bốn năng lực còn thiếu:

| # | Năng lực | Nội dung | Khoảng trống được lấp |
|---|---|---|---|
| 1 | **Chứng minh hiện diện trên web** — *ChromaPulse · CamProbe · MotionLock* | Màn hình phát chuỗi màu ngẫu nhiên an toàn; đo phản xạ và độ trễ trên da mặt; thăm dò hành vi driver camera; đối chiếu cảm biến chuyển động với chuyển động khung hình | Chèn luồng camera / camera ảo; deepfake phát lại |
| 2 | **Thử thách nghe–nhìn tiếng Việt** — *VoiceGate-VI* | Câu ngẫu nhiên; kiểm nội dung bằng PhoWhisper; chống giả giọng huấn luyện cho tiếng Việt ba miền; kiểm môi khép đúng âm m/b/p | Giọng clone tiếng Việt; tách rời mặt–giọng |
| 3 | **Bộ định tuyến có bảo đảm** — *TrustRouter* | Hiệu chỉnh xác suất → hợp nhất có điều kiện chất lượng → cổng ngoài phân phối và mâu thuẫn → hỏi thêm bằng chứng thích ứng → chọn ngưỡng bằng *Learn-then-Test*: **bảo đảm tỷ lệ lọt theo từng loại tấn công ≤ α với xác suất ≥ 1−δ** | Ngưỡng cảm tính; từ chối nhầm người thật |
| 4 | **Bằng chứng cho con người và cơ quan chức năng** — *Evidence Dossier · Forensic Mode · Ring Radar* | Hồ sơ "người duyệt quyết trước, AI hiện sau"; chế độ giám định file video/âm thanh; liên kết chéo phiên để phát hiện đường dây tài khoản thuê | Duyệt bằng mắt; không thấy đường dây |

**Đầu ra.**
- Ứng dụng web chạy thật, đi trọn luồng thu nhận → quyết định → duyệt → giám định.
- Bộ dữ liệu red-team **ViKYC-Attack**: tấn công theo đúng thủ đoạn tại Việt Nam, có đồng ý của người tham gia.
- Báo cáo đánh giá theo ISO/IEC 30107-3 và CEN/TS 18099, gồm khoảng tin cậy, đối chứng và ablation.
- Mọi số liệu đo thực tế, tái lập được (thể lệ Điều 7.3).

**Tính mới có thể bảo vệ.**
- Theo khảo sát của nhóm, đây là **lần đầu kiểm soát rủi ro phi tham số với bảo đảm mẫu hữu hạn** (conformal / Learn-then-Test) được áp dụng cho quyết định liveness/eKYC.
- Có **nhánh "thu lại" tách riêng**, với ngân sách rủi ro riêng.
- Chọn thử thách **thích ứng theo lượng thông tin**.
- Có **nghiên cứu đo lường** về phản xạ màn hình và chuyển động–video trên **trình duyệt di động phổ thông tại Việt Nam**, trước tấn công camera ảo.

---

## 1. TỔNG QUAN DỰ ÁN

### 1.1 Tên dự án

**VeriClue** = *verify* (xác minh) + *clue* (dấu vết). Hệ thống không trả về một nhãn "thật/giả" trống ngữ cảnh. Nó thu thập **dấu vết vật lý có thể kiểm chứng** — ánh sáng phản xạ, độ trễ, chuyển động, khẩu hình, âm học — rồi đưa ra **quyết định có bảo đảm và truy vết được**.

### 1.2 Mô tả ngắn

VeriClue là dịch vụ tích hợp qua API, gồm năm thành phần:
1. **SDK thu nhận chạy trên trình duyệt.** Hướng dẫn chụp, đo chất lượng, phát thử thách ánh sáng, thu chuyển động và giọng nói.
2. **Các engine bằng chứng phía máy chủ.** PAD thụ động, deepfake, chứng minh hiện diện, giọng nói tiếng Việt, đồng bộ môi–âm.
3. **TrustRouter.** Chọn một trong ba hành động: **TIẾP TỤC / THU LẠI / DUYỆT**. Hành động được ánh xạ sang **mức tin cậy Cao / Trung bình / Thấp** theo đề bài 62.
4. **Bàn duyệt và chế độ giám định** cho chuyên viên và điều tra viên.
5. **Ring Radar.** Liên kết các phiên để phát hiện cụm tài khoản do một đường dây vận hành.

Quyết định cuối cùng thuộc về đơn vị triển khai. VeriClue không tự động từ chối ai mà không có đường duyệt của con người. Đây là yêu cầu của NIST SP 800-63A-4 (§3.14, §3.15) và Luật Trí tuệ nhân tạo 2025 (Điều 14).

### 1.3 Đối chiếu với yêu cầu của các đề bài trong Ngân hàng ý tưởng

| Yêu cầu nêu trong đề bài | Nguồn | Thành phần VeriClue đáp ứng |
|---|---|---|
| Công cụ hiện nay "chủ yếu tối ưu cho dữ liệu nước ngoài" → cần phù hợp **giọng nói tiếng Việt các vùng miền, khuôn mặt người Việt** | Đề 16 (BTL86) | VoiceGate-VI fine-tune trên VSASV, SEA-Spoof-vi và dữ liệu tự thu ba miền; ViKYC-Attack trên khuôn mặt người Việt |
| Phát hiện trên **video nén qua mạng xã hội** | Đề 16 | Huấn luyện có tăng cường nén; Forensic Mode nhận file đã nén; báo cáo kết quả theo mức nén |
| Vừa **kiểm tra tức thời trong eKYC**, vừa **giám định phục vụ điều tra** | Đề 16 | Live Mode (≤ 5 giây) + Forensic Mode (phân tích file, báo cáo tỷ số khả năng) |
| **Chuẩn hóa thành module tích hợp** | Đề 16 | REST API + hợp đồng đầu ra thống nhất (Phụ lục B) + Docker |
| Chỉ số tin cậy **Cao / Trung bình / Thấp** → **cho phép / xác thực bổ sung / cảnh báo, chuyển cơ quan chức năng** | Đề 62 | TrustRouter: TIẾP TỤC / hỏi thêm bằng chứng hoặc THU LẠI / DUYỆT (ưu tiên cao → chuyển cơ quan chức năng *qua người duyệt*) |
| Dựa trên **độ ổn định thiết bị, hành vi, tần suất, thời điểm**; **Graph Analytics**, **Anomaly Detection** | Đề 62 | CamProbe (thiết bị), Ring Radar (đồ thị, tần suất, thời điểm), cổng ngoài phân phối |
| Lớp chống giả mạo/deepfake **huấn luyện liên tục trên mẫu tấn công mới** | DA940-02 | Vòng học liên tục từ nhãn của người duyệt và red-team; phát hiện trôi bằng martingale |
| Đo theo **ISO/IEC 30107**; phân mức bảo đảm theo **NIST SP 800-63-4** | DA940-02 | Báo cáo APCER/BPCER theo ISO/IEC 30107-3; đối chiếu NIST 800-63A-4 (mục 3.4) |
| **Làm chủ công nghệ trong nước**, không phụ thuộc hộp đen nước ngoài | DA940-02 | Mã nguồn tự chủ, triển khai on-premise, bảng giấy phép minh bạch (mục 3.1) |

### 1.4 Kết quả trình diễn (Vòng 3 — triển lãm)

Khách tham quan tự trải nghiệm **7 kịch bản** ngay tại gian hàng. Mỗi kịch bản hiển thị hành động, mức tin cậy và hồ sơ bằng chứng trong vòng 5 giây.

1. **Người thật, điện thoại tầm trung** → TIẾP TỤC. Biểu đồ ánh sáng phản xạ bám sát chuỗi màu.
2. **Người thật, phòng tối, điện thoại giá rẻ** → THU LẠI, kèm hướng dẫn "ra chỗ sáng hơn" → lần hai TIẾP TỤC. Không từ chối nhầm.
3. **Ảnh in / video phát lại trên màn hình** → DUYỆT. Bằng chứng: phản xạ phẳng, sai đặc tính 3D.
4. **Camera ảo (OBS) chèn video lưu sẵn — mô phỏng thủ đoạn Thanh Hóa** → DUYỆT ưu tiên cao. Bằng chứng: không phản xạ chuỗi màu; driver đáp ứng trong khoảng 1 ms thay vì hàng trăm ms.
5. **Face-swap thời gian thực** (Deep-Live-Cam) + giọng clone tiếng Việt → DUYỆT ưu tiên cao. Bằng chứng: phản xạ trễ nhiều khung hình, phát hiện giọng tổng hợp.
6. **Chế độ giám định:** tải lên đoạn video cuộc gọi đã nén qua mạng xã hội → báo cáo giám định có tỷ số khả năng và giới hạn.
7. **Ring Radar:** bản đồ cụm phát hiện 9 "danh tính" mở tài khoản từ cùng một căn phòng, cùng dòng máy, trong 3 giờ.

---

## 2. VẤN ĐỀ VÀ GIẢI PHÁP

### 2.1 Bối cảnh: sinh trắc học thành công, tội phạm tấn công chính khâu sinh trắc học

| Dữ kiện | Nguồn |
|---|---|
| QĐ 2345/QĐ-NHNN (từ 1/7/2024): xác thực sinh trắc khi chuyển > 10 triệu đồng/lần hoặc > 20 triệu đồng/ngày, khi giao dịch lần đầu, khi đổi thiết bị | NHNN |
| 175,2 triệu hồ sơ khách hàng cá nhân đã đối chiếu sinh trắc (2/10/2026); 57 tổ chức tín dụng + 39 trung gian thanh toán triển khai | NHNN, qua CafeF và VNBA |
| Hệ thống SIMO: đến 28/9/2026 đã cảnh báo hơn 5,6 triệu lượt khách hàng; hơn 1,9 triệu giao dịch bị dừng/hủy, trị giá hơn 6.300 tỷ đồng | NHNN, qua CafeF |
| Thiệt hại lừa đảo trực tuyến vẫn **hơn 6.000 tỷ đồng trong 11 tháng 2025**; chỉ 32% nạn nhân trình báo | Bộ Công an / NCA |
| **Thái Bình (5/2025):** thuê người quay video nguồn 25–30 giây, dựng clip AI khuôn mặt để qua xác thực sinh trắc; rửa hơn 1.000 tỷ đồng; 21 bị can, hơn 500 tài khoản bị phong tỏa | Công an Thái Bình, qua VietnamFinance và TTTC-TT |
| **Thanh Hóa (6/2026 và 10/2026):** hai đường dây, 18 bị can, mỗi vụ hơn 1.000 tài khoản; phần mềm chiếm quyền camera, thay khuôn mặt bằng ảnh chân dung lưu sẵn; gỡ bảo mật điện thoại để giả lập luồng dữ liệu camera | VietnamPlus, Tiền Phong, CafeF |
| **Quảng Ninh (10/2025):** thuê người mở tài khoản, cho ở tập trung để quét sinh trắc "ngày đêm"; 256 tỷ đồng; 17 bị can | VOH |
| **Bắc Giang (2025):** "cho thuê khuôn mặt", 71 tài khoản, khoảng 200 tỷ đồng, gần 1.000 nạn nhân | VietnamFinance |
| Deepfake tại Việt Nam tăng 541% (2024) *(số liệu nhà cung cấp)* | Sumsub |

**Nhận định:** cả bốn vụ án đều là **chèn luồng / deepfake số** hoặc **người thật bị thuê** — không phải ảnh in trước ống kính. Đây là hai loại mối đe dọa mà mô hình "kiểm tra sự sống từng phiên" truyền thống không được thiết kế để chặn.

### 2.2 Sáu khoảng trống của các hệ thống hiện có

**G1 — Chứng nhận PAD không bao gồm chèn luồng.**
- TT 50/2024 (sửa đổi bởi TT 77/2025), Điều 11.5: PAD được chứng nhận ISO 30107 mức 2 hoặc FIDO, hiệu lực 1/7/2026. Mức này **chỉ đo tấn công trình diện**.
- CEN/TS 18099:2024 loại trừ PAD khỏi phạm vi và định nghĩa riêng việc kiểm thử chèn luồng. ETSI TS 119 461 v2.1.1 (2025) yêu cầu IAD được kiểm thử theo CEN/TS 18099 trước cuối năm 2026. NIST SP 800-63A-4 §3.14 bắt buộc "kiểm soát kỹ thuật để tăng niềm tin rằng dữ liệu được tạo ra từ cảm biến thật".
- Chứng nhận PAD của các nhà cung cấp Việt Nam (VNPT, Viettel AI, VNPAY, Cake…) đều là PAD. Nhóm **không tìm thấy** chứng nhận CEN/TS 18099 nào của nhà cung cấp trong nước.

**G2 — Bộ phát hiện suy giảm mạnh ngoài phân phối và với dữ liệu tiếng Việt.**
- *Deepfake-Eval-2024:* trên deepfake ngoài đời thực, detector mã nguồn mở mất khoảng 50% AUC (video), 48% (âm thanh), 45% (ảnh) so với benchmark cũ.
- *Nén video:* trên FF++, độ chính xác giảm từ 98% xuống 61,2% ở mức nén c23.
- *Giọng nói tiếng Việt:*
  - SEA-Spoof (Interspeech 2026) ghi nhận suy giảm xuyên ngôn ngữ "nghiêm trọng".
  - VietPrism (2026): EER tăng từ 16,3% lên 33,6% khi giọng giả càng giống người thật.
  - VSASV (VLSP 2025): hệ SASV tốt nhất có EER khoảng 17,8%.
- Chính đề bài 16 nêu: công cụ hiện nay "chủ yếu tối ưu cho dữ liệu nước ngoài".

**G3 — Quyết định bằng ngưỡng cảm tính, không có bảo đảm, dồn rủi ro lên người dùng yếu thế.**
- Theo tài liệu công khai, các nhà cung cấp trả về điểm số hoặc đạt/không đạt với ngưỡng cố định. Nhóm **không tìm thấy** nhà cung cấp hay công bố nào đưa **bảo đảm thống kê** cho quyết định liveness.
- NIST 800-63A-4 yêu cầu hiệu năng mỗi nhóm nhân khẩu học không kém quá 25% so với tổng thể.
- Nghiên cứu của GSA/Clarkson (khoảng 4.000 người, 5 nhà cung cấp) ghi nhận một nhà cung cấp có tỷ lệ từ chối nhầm trên 50%.
- Ở Việt Nam, 9,5% dân số từ 65 tuổi trở lên và 21,5 triệu người chưa dùng Internet (DataReportal 2025). Người dùng máy rẻ, ánh sáng kém, người cao tuổi là nhóm dễ bị chặn nhầm nhất.

**G4 — Con người không phân biệt được deepfake bằng mắt; giải thích kiểu heatmap gây phụ thuộc sai.**
- Độ chính xác của con người là 55,5% (Diel et al. 2024).
- Khuôn mặt tổng hợp còn được đánh giá "đáng tin" hơn mặt thật 7,7% (Nightingale & Farid, PNAS 2022).
- Giải thích trực quan làm tăng niềm tin nhưng **không** cải thiện việc phụ thuộc AI đúng mức (nghiên cứu 381 người, 2026). Saliency map có thể không phản ánh mô hình (Adebayo et al., NeurIPS 2018).

**G5 — Kiểm tra từng phiên đơn lẻ không nhìn thấy đường dây.**
- Người thật được thuê (Quảng Ninh, Bắc Giang) *qua được liveness một cách hợp lệ*.
- Chiến dịch chèn luồng mở hàng nghìn tài khoản (Thanh Hóa) để lại dấu vết **giữa các phiên**: cùng phòng, cùng thiết bị, cùng media nguồn. Dấu vết này không hiện ra trong từng phiên riêng lẻ.
- SIMO hoạt động ở tầng tài khoản/giao dịch, **sau khi** tài khoản đã bị báo cáo.

**G6 — Khuôn mặt và giọng nói là hai sản phẩm tách rời; chưa có chống giả giọng tiếng Việt thương mại.**
- Nhà cung cấp face eKYC không làm voice liveness. Nhà cung cấp voice (Pindrop…) không làm face eKYC.
- Không có nhà cung cấp nào (trong hay ngoài nước) công bố chống giả giọng tiếng Việt.

### 2.3 Câu hỏi nghiên cứu

- **RQ1.** Trên trình duyệt web phổ thông — không có attestation phần cứng — có thể đo được những tín hiệu vật lý nào để **tăng chi phí** cho tấn công chèn luồng và deepfake thời gian thực? Hiệu quả đo được đến đâu?
- **RQ2.** Làm thế nào để **tách "người thật chụp kém" khỏi "tấn công"**, sao cho người thật được hướng dẫn thu lại thay vì bị chặn?
- **RQ3.** Có thể chọn ngưỡng và chính sách hỏi thêm bằng chứng sao cho **tỷ lệ giả mạo lọt qua mỗi loại tấn công đã biết được chặn trên có xác suất**, đồng thời tối thiểu tải duyệt và ma sát?
- **RQ4.** Mô hình chống giả giọng huấn luyện cho tiếng Việt và kiểm tra khẩu hình theo câu đã biết cải thiện được bao nhiêu so với mô hình tiếng Anh?
- **RQ5.** Liên kết chéo phiên có phát hiện được cụm tài khoản do đường dây vận hành với **ngân sách cảnh báo** chấp nhận được, mà không báo nhầm hộ gia đình hay ký túc xá?

### 2.4 Mô hình đe dọa

**Năng lực kẻ tấn công** (theo tinh thần thang "attack potential" của ISO/IEC 30107-3):

| Cấp | Năng lực | Ví dụ |
|---|---|---|
| A1 | Không kỹ thuật | Ảnh in, video phát lại trên màn hình |
| A2 | Công cụ phổ thông | Camera ảo (OBS/ManyCam), video lưu sẵn, TTS clone giọng |
| A3 | Chiếm quyền thiết bị | Android root + module hook camera (kiểu Thanh Hóa); giả lập cảm biến |
| A4 | Thời gian thực, thích ứng | Face-swap trực tiếp có chuyển màu ánh sáng + chuyển giọng thời gian thực; dò hệ thống qua phản hồi |
| A5 | Có tổ chức | Đường dây thuê người thật / vận hành hàng trăm danh tính từ một địa điểm |

**Ma trận tấn công × lớp phòng thủ:**

| # | Tấn công | Cấp | Lớp phát hiện chính | Kỳ vọng (sẽ đo) |
|---|---|---|---|---|
| T1 | Ảnh in, mặt nạ giấy | A1 | PAD thụ động; ChromaPulse (đặc tính 3D); rPPG | Chặn tốt |
| T2 | Video phát lại trên màn hình | A1 | ChromaPulse (không biết trước chuỗi màu); PAD | Chặn tốt |
| T3 | Camera ảo chèn video/ảnh lưu sẵn | A2 | ChromaPulse (không phản xạ); CamProbe (driver đáp ứng bất thường); MotionLock | Chặn phần lớn |
| T4 | Ảnh nạn nhân + TTS + lip-sync offline | A2 | VoiceGate-VI (giọng tổng hợp, khép môi m/b/p); ChromaPulse | Chặn phần lớn |
| T5 | Hook camera trên Android root | A3 | ChromaPulse; CamProbe (hành vi); MotionLock (*có thể bị giả lập*) | Tăng chi phí; **không bảo đảm** |
| T6 | Face-swap trực tiếp có chuyển màu + chuyển giọng thời gian thực | A4 | Độ trễ ChromaPulse; detector face-swap; detector giọng chuyển đổi | **Khó nhất** — báo cáo trung thực tỷ lệ lọt |
| T7 | Dò hệ thống (oracle probing) | A4 | Phản hồi chống oracle; giới hạn lượt; martingale theo dõi mật độ điểm gần ngưỡng | Chuyển duyệt |
| T8 | Đường dây: người thật bị thuê / nhiều danh tính từ một nơi | A5 | Ring Radar | Cảnh báo cụm |

**Ngoài phạm vi (nêu rõ):** bảo đảm toàn vẹn thiết bị ở cấp hệ điều hành (Play Integrity / App Attest trong ứng dụng native — đúng tinh thần TT 50 Điều 8.4); đối chiếu chip CCCD/NFC; đối chiếu CSDL căn cước. Đây là trách nhiệm của đơn vị tích hợp. VeriClue nhận các tín hiệu đó *nếu có* như một nguồn bằng chứng.

### 2.5 Kiến trúc giải pháp

```
┌──────────────────────────── TRÌNH DUYỆT (SDK VeriClue) ─────────────────────────────┐
│ Đồng ý (dữ liệu nhạy cảm) → Hướng dẫn khung mặt → Cổng chất lượng (client)           │
│ ChromaPulse: phát chuỗi màu an toàn  ·  CamProbe: thăm dò driver  ·  MotionLock: IMU  │
│ VoiceGate: hiển thị câu tiếng Việt ngẫu nhiên  ·  Ảnh mặt không nén tại thời điểm     │
│ server chọn  ·  Video nén bitrate cao  ·  Tất cả gắn nonce phiên + chữ ký             │
└───────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │ HTTPS · JWT gắn nonce · hash từng chunk
┌───────────────────────────────────────▼──────────────────────────────────────────────┐
│ L0  API PHIÊN — mã phiên, seed thử thách (server giữ), giới hạn lượt, chống phát lại   │
│ L1  CỔNG CHẤT LƯỢNG — vector chất lượng q (tham chiếu ISO/IEC 29794-5)                 │
│ L2  ENGINE BẰNG CHỨNG (song song, mỗi engine trả LLR đã hiệu chỉnh + q + phiên bản)    │
│     E1 PAD thụ động  E2 Deepfake/face-swap  E3 ChromaPulse  E4 CamProbe  E5 MotionLock │
│     E6 VoiceGate-VI (ASR · chống giả giọng · khẩu hình · nhất quán người nói)          │
│ L3  TRUSTROUTER — hợp nhất có điều kiện chất lượng · cổng OOD · cổng mâu thuẫn ·       │
│     hỏi thêm bằng chứng thích ứng · ngưỡng chứng nhận bằng Learn-then-Test             │
│     → TIẾP TỤC (Cao) / THU LẠI hoặc XÁC THỰC BỔ SUNG (Trung bình) / DUYỆT (Thấp)       │
│ L4  HỒ SƠ BẰNG CHỨNG (ký số, nhật ký chuỗi băm) → BÀN DUYỆT (người quyết trước)        │
│     · FORENSIC MODE (giám định file cho điều tra viên)                                 │
│ L5  RING RADAR — embedding đã che mặt · băm media · thiết bị · giọng · thời gian →     │
│     chỉ mục ANN → đồ thị → cộng đồng (Leiden) → cảnh báo cụm                           │
│ L6  GIÁM SÁT — martingale phát hiện trôi / chiến dịch tấn công · vòng học liên tục     │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.6 Chi tiết các thành phần

#### 2.6.1 L0 — Thu nhận và ràng buộc phiên
- **Seed và nonce:** server sinh `session_id`, nonce 128-bit và **seed thử thách** (chuỗi màu, câu nói, thời điểm chụp ảnh không nén). Seed được giữ phía server; từng bước thử thách được gửi **đúng lúc cần** qua WebSocket.
- **Mỗi chunk tải lên được gắn chữ ký và hash** — JWT chứa `sha256(chunk)`. Token dùng một lần, TTL khoảng 120 giây. Phiên có thời gian bất hợp lý (nhanh quá, hoặc không theo lịch ngẫu nhiên) bị đánh dấu.
- **Hai kênh dữ liệu:**
  - 4–8 **ảnh vùng mặt không nén** (~256×256) chụp tại các thời điểm do server chọn ngẫu nhiên, dành cho PAD và deepfake — tránh sụp đổ độ chính xác do nén.
  - Video 720p, 4–6 Mbps, chia chunk 500 ms, dành cho các phân tích theo thời gian.
- **Đồng ý:** màn hình đồng ý tách riêng, không tích sẵn, nêu rõ "dữ liệu sinh trắc học là dữ liệu nhạy cảm", mục đích và thời hạn lưu (Luật 91/2025; NĐ 356/2025). Bản ghi đồng ý được lưu kèm hash.

#### 2.6.2 L1 — Cổng chất lượng: tách "chụp kém" khỏi "tấn công"
- **Vector chất lượng q:** kích thước mặt / khoảng cách hai mắt, độ nét, phơi sáng, góc đầu (yaw/pitch/roll), che khuất, mắt mở, SNR âm thanh, tốc độ khung hình. Các đo lường lấy cảm hứng từ ISO/IEC 29794-5:2025 và triển khai tham chiếu OFIQ.
- **Phía client:** chỉ đưa **một chỉ dẫn mỗi lần** ("Lại gần hơn", "Thêm ánh sáng").
- **Phía server:** q đi vào cả quyết định THU LẠI **và** phép hợp nhất ở L3. Chất lượng thấp *làm phẳng* bằng chứng thay vì đẩy về "giả mạo".
- **Chống khai thác:** tối đa N = 2 lần thu lại. Lỗi chất lượng lặp lại → DUYỆT. Mọi thông điệp thu lại dùng **cùng một mẫu**, chỉ nói về chất lượng, không bao giờ nói "nghi giả mạo" (nguyên tắc chống oracle).

#### 2.6.3 L2-E1/E2 — Bằng chứng thụ động

**E1 — PAD:**
- MiniFASNet (ONNX, Apache-2.0) chạy trên trình duyệt, **chỉ để phản hồi UX**.
- Điểm chính thức tính phía server: đặc trưng DINOv2 (Apache-2.0) cùng đầu phân loại LoRA hoặc tuyến tính, theo hướng FoundPAD / FLIP. Huấn luyện trên CelebA-Spoof (+ SynthASpoof); hiệu chỉnh trên Zalo AI 2022 Liveness (người Việt) và ViKYC-Attack.

**E2 — Deepfake / face-swap:**
- Linear probe trên đặc trưng CLIP (kiểu UnivFD, MIT; hoặc detector CLIP của Cozzolino, Apache-2.0), tinh chỉnh trên DF40 và FF++ có tăng cường nén.
- Effort (ICML 2025) và DeepfakeBench chỉ dùng làm **đối chứng nghiên cứu** (giấy phép phi thương mại).

#### 2.6.4 L2-E3/E4/E5 — Chứng minh hiện diện trên web

**E3 — ChromaPulse (thử thách ánh sáng màu).**
- *Nguyên lý:* da người là bề mặt 3D phản xạ khuếch tán. Khi màn hình đổi màu, sắc độ trên trán, má, mũi thay đổi **đồng bộ với chuỗi màu** và **gần như tức thì**.
  - Video phát lại không biết trước chuỗi màu.
  - Camera ảo chèn file không phản xạ.
  - Pipeline face-swap thời gian thực phải "xử lý xong rồi mới hiện", nên **trễ thêm vài khung hình**.
- *Bằng chứng thực nghiệm đã có:* Gerstner & Farid (CVPRW 2022) đo tương quan 0,89 khi không trễ, 0,65 khi trễ 2 khung hình, 0,37 khi trễ 3 khung hình, 0,03 khi trễ 4 khung hình. Face Flashing (NDSS 2018) đạt 98,8% với cài đặt ứng dụng native.
- *Thiết kế an toàn* (WCAG 2.3.1; tham chiếu iProov < 2,86 lần đổi/giây):
  - **Bảng màu pastel gần đẳng sáng**: chênh độ chói tương đối tối đa 0,064, không dùng đỏ bão hòa.
  - Chuyển màu mượt 150 ms, **tối đa 2,5 lần đổi màu/giây**.
  - Cảnh báo trước khi chạy, có lựa chọn bỏ qua cho người nhạy cảm ánh sáng (chuyển sang MotionLock + VoiceGate).
- *Xử lý tín hiệu:*
  - Lấy 5 vùng da (trán, hai má, mũi, cằm) bằng MediaPipe, thêm vùng cổ và vùng nền.
  - Đặc trưng log(R/G), log(B/G); **trừ vùng nền** để triệt tiêu tự động phơi sáng và cân bằng trắng.
  - Tương quan chéo với chuỗi phát, ước lượng trễ τ* với nội suy dưới khung hình.
  - Kiểm tra: (i) độ tương quan ρ; (ii) giải mã từng ký hiệu màu (≥ 7/8); (iii) τ* nằm trong phân vị 99 của người thật theo lớp thiết bị; (iv) độ lệch trễ giữa các vùng ≤ 1 khung hình; (v) tỷ lệ đáp ứng giữa các vùng (đặc tính 3D).
- *Đặc tả chi tiết:* Phụ lục A.

**E4 — CamProbe (thăm dò camera ảo).**
- *Kỹ thuật chính:* trình duyệt gửi chuỗi yêu cầu `applyConstraints` (độ phân giải và FPS bất thường) rồi đo **thời gian đáp ứng của driver** và **mức khớp giữa thông số báo cáo và khung hình thật**. Camera thật đáp ứng không đồng đều (khoảng 90–210 ms); camera ảo đáp ứng trong 1–2 ms hoặc báo thay đổi không xảy ra (Kurmankhojayev et al., arXiv 2512.10653).
- *Tín hiệu phụ:*
  - jitter và khung trùng lặp (`requestVideoFrameCallback`);
  - `getCapabilities()` thiếu bất thường;
  - nhãn thiết bị (trọng số thấp vì dễ giả);
  - renderer WebGL của trình giả lập;
  - `navigator.webdriver`.
- *Giới hạn:* đứng riêng thì yếu (BPCER 14,6% tại APCER 10% theo paper gốc), nên chỉ dùng như **một nguồn LLR**.

**E5 — MotionLock (chuyển động điện thoại ↔ chuyển động khung hình, chỉ trên di động).**
- *Cách làm:* người dùng nghiêng nhẹ máy 3 giây. Hệ thống tương quan `DeviceMotionEvent.rotationRate` với dịch chuyển nền (phase correlation, đã che mặt) và vị trí khuôn mặt.
- *Ý nghĩa:* video chèn từ file không thể khớp với dữ liệu IMU *đang diễn ra*.
- *Tài liệu đi trước:* Chen et al. (MobiSys 2014), Li et al. (CCS 2015). Đóng góp của nhóm là **áp dụng trên trình duyệt di động, chống chèn luồng**.
- *Giới hạn:* trên máy root, cảm biến có thể bị giả lập. Ngược lại, một UA "di động" mà không có sự kiện chuyển động thì bản thân đó đã là tín hiệu rủi ro.

**rPPG** (CHROM/POS, khoảng 50 dòng JS): chạy trong pha màn hình trung tính để chặn ảnh in và mặt nạ. **Không** dùng để chống deepfake, vì deepfake chất lượng cao thừa hưởng nhịp tim từ video lái (Seibold et al. 2025).

#### 2.6.5 L2-E6 — VoiceGate-VI (thử thách nghe–nhìn tiếng Việt)

- **Kích hoạt:** chỉ khi bằng chứng mơ hồ (xem 2.6.6), hoặc khi chính sách của đơn vị yêu cầu cho giao dịch giá trị cao. Không kích hoạt ở vùng rủi ro cao, vì kẻ làm được deepfake mặt cũng clone được giọng — bằng chứng thêm vào không đổi được kết luận.
- **Câu thử thách:**
  - 8–12 âm tiết, từ vựng thông dụng, sinh từ ngân hàng từ theo seed.
  - **Cố ý chứa âm khép môi:** phụ âm đầu m/b và âm cuối -m/-p (ví dụ "đẹp", "cơm").
  - Lưu ý ngữ âm: "ph" là /f/, không khép môi.
- **Kiểm nội dung:**
  - PhoWhisper-small (VinAI, BSD-3) chạy faster-whisper int8.
  - So khớp mức âm tiết, có phương án bỏ dấu, ngưỡng dung sai.
  - Lý do: giọng miền Trung có WER cao nhất (PhoWhisper-base: Bắc 15,0%, Trung 24,2%, Nam 17,9% — ViMD, EMNLP 2024). Cho phép thử lại trước khi đánh dấu.
- **Chống giả giọng:**
  - Nền SSL-AASIST (XLS-R + AASIST, MIT) hoặc XLSR-Mamba (MIT).
  - Fine-tune trên VSASV, SEA-Spoof-vi và giọng tự thu ba miền.
  - Mẫu giả do nhóm tự sinh bằng viXTTS, F5-TTS-Vietnamese, VietTTS, RVC; cộng nén codec và thu lại qua loa → mic.
  - Báo cáo trung thực theo giao thức **leave-one-generator-out**.
- **Khẩu hình theo câu đã biết:**
  - Timestamp từ ASR cho biết *khi nào* phải khép môi. Đo khoảng cách môi (landmark MediaPipe) tại các thời điểm đó.
  - Kết hợp điểm đồng bộ SyncNet / AVAD (CVPR 2023, MIT).
  - Đây là kiểm tra **không cần huấn luyện, diễn giải được**, bổ trợ cho hướng lip-reading học sâu đã có trong tiếng Việt (Tran et al., KSE 2022 — LipBERT, VNFaceTalking).
- **Nhất quán người nói:** ECAPA-TDNN (SpeechBrain, Apache-2.0) phát hiện ghép nối hoặc đổi người giữa các đoạn. Không dùng đối khớp mặt–giọng (EER khoảng 24%, quá yếu).
- **Giới hạn nêu thẳng:** với T6 (người điều khiển nói thật + chuyển giọng thời gian thực), môi và tiếng **khớp tự nhiên**. Chỉ detector giọng chuyển đổi và độ trễ ChromaPulse gánh trường hợp này.

#### 2.6.6 L3 — TrustRouter: bộ định tuyến có bảo đảm thống kê

**(a) Hiệu chỉnh.** Mỗi engine m trả điểm s_m. Trên tập hiệu chỉnh tách theo người, một mô hình logistic có điều kiện chất lượng biến điểm thành tỷ số log-khả năng:

  ℓ_m(s_m, q_m) = log [ p(s_m, q_m | tấn công) / p(s_m, q_m | thật) ]

theo tinh thần hợp nhất tỷ số khả năng có chất lượng của Nandakumar et al. (TPAMI 2008) và Poh et al. (TIFS 2009). Báo cáo ECE, Brier và C_llr cho từng engine.

**(b) Hợp nhất.** Λ = Σ_m w_m · ℓ_m. Trọng số w_m học bằng hồi quy logistic có điều chuẩn để chiết khấu tương quan giữa các engine. Engine trạng thái `degraded`/`error` → đóng góp 0 **và** bật cờ "thiếu bằng chứng" — **không bao giờ** được hiểu là đạt.

**(c) Thứ tự định tuyến:**
1. **Toàn vẹn phiên:** nonce/chữ ký sai, thời gian bất hợp lý, tín hiệu thiết bị bị can thiệp → **DUYỆT – ưu tiên cao**.
2. **Cổng chất lượng:** q < τ_q → **THU LẠI**; sau N lần → **DUYỆT**.
3. **Cổng ngoài phân phối:** điểm kNN / energy trên embedding được chuyển thành p-value conformal so với dữ liệu người thật hiệu chỉnh. p < γ → **DUYỆT**. Có bảo đảm: tỷ lệ báo nhầm OOD trên người thật ≤ γ.
4. **Cổng mâu thuẫn:** độ xung đột giữa các engine, đo bằng K = Σ_{i≠j} b_i^(1) · b_j^(2) (Dempster–Shafer, từ "bằng chứng" Dirichlet kiểu Sensoy 2018 / Han 2021). K > κ → hỏi thêm bằng chứng hoặc **DUYỆT**.
5. **Quyết định tuần tự kiểu SPRT** (Wald 1945; Allano 2010; Murakami 2016):
   - Λ ≤ B → **TIẾP TỤC** (tin cậy Cao).
   - Λ ≥ A → **DUYỆT – ưu tiên cao** (tin cậy Thấp; nếu người duyệt xác nhận thì chuyển cơ quan chức năng).
   - B < Λ < A → **hỏi thêm bằng chứng** (tin cậy Trung bình).
6. **Chọn thử thách thích ứng:** chọn thử thách c ∈ {ChromaPulse, MotionLock, VoiceGate} tối đa hóa mức giảm chi phí Bayes kỳ vọng trừ chi phí ma sát:

   c* = argmax_c [ min_a R(a | x) − E_{v_c}[ min_a R(a | x, v_c) ] − C_c ], chỉ hỏi khi giá trị này > 0

   - R(a | ·) là rủi ro Bayes của hành động a, với chi phí do đơn vị triển khai đặt (C_lọt ≫ C_chặn nhầm). Kỳ vọng E_{v_c} tính trên phân phối kết quả thử thách học từ dữ liệu hiệu chỉnh.
   - **Trộn ngẫu nhiên ε** để kẻ tấn công không "lái" được việc chọn thử thách — lỗ hổng đã được chỉ ra bởi Murakami et al. (IEICE 2017).
   - Hết thử thách mà vẫn mơ hồ → **DUYỆT**.

**(d) Chứng nhận ngưỡng bằng Learn-then-Test** (Angelopoulos et al., *Annals of Applied Statistics* 2025).
- Tham số chính sách: θ = (τ_q, γ, κ, B, A, ε).
- Với mỗi θ trên lưới, đặt các giả thuyết không:
  - H₀^(s): APCER_s^auto(θ) > α_s cho **từng loại tấn công đã biết** s;
  - H₀^(bf): BPCER^auto(θ) > β.
- Tính p-value nhị thức / Hoeffding–Bentkus trên tập hiệu chỉnh. Kiểm soát sai số theo họ (fixed-sequence hoặc Bonferroni).
- Trong các θ hợp lệ, chọn:

  θ* = argmin Ĉ(θ) = c_rev · (tỷ lệ duyệt) + c_rec · (tỷ lệ thu lại) + c_ch · (tỷ lệ phải làm thử thách)

- **Bảo đảm:** P( APCER_s^auto ≤ α_s ∀s đã biết **và** BPCER^auto ≤ β ) ≥ 1 − δ, với điều kiện phiên mới có thể hoán đổi với dữ liệu hiệu chỉnh.
- **Hiệu chỉnh cả chính sách tuần tự:** trong dữ liệu hiệu chỉnh, **mọi phiên đều được ghi đủ tất cả thử thách**. Nhờ vậy có thể *phát lại phản thực* (counterfactual replay) toàn bộ chính sách thích ứng với bất kỳ θ nào, và LTT chứng nhận **cả chính sách tuần tự**, không chỉ một ngưỡng.

**(e) Trung thực về giới hạn.**
- Bảo đảm **chỉ đúng cho loại tấn công đã biết** và khi dữ liệu có thể hoán đổi.
- Tấn công chưa từng thấy được xử lý bằng cổng OOD, red-team giữ riêng công cụ, và chế độ "quan sát" khi triển khai.
- **Cỡ mẫu quyết định độ mạnh của bảo đảm** (Phụ lục E). Với 0 lỗi, δ = 0,05:
  - chứng nhận α = 5% cần **59** phiên tấn công mỗi loại;
  - chứng nhận α = 1% cần **299** phiên.
- Trong bản thi, nhóm đặt mục tiêu chứng nhận α = 5% cho mỗi loại tấn công chính, và công bố số mẫu.

#### 2.6.7 L4 — Hồ sơ bằng chứng, bàn duyệt và chế độ giám định

**Nguyên tắc thiết kế** (từ nghiên cứu phối hợp người–AI):
1. **Không hỏi "trông có giả không?"** Hỏi các câu **kiểm chứng được**:
   - Phản xạ có khớp chuỗi màu không?
   - Câu nói có khớp đề bài không?
   - Driver camera có hành vi bình thường không?
2. **Người duyệt quyết trước, AI hiện sau** (Fogliato et al., FAccT 2022): ghi quyết định tạm thời rồi mới mở điểm AI. Hai quyết định đều được lưu để đo mức phụ thuộc đúng (RAIR/RSR).
3. **Hai giả thuyết, tỷ số khả năng kèm thang lời** theo ENFSI 2015. Luôn hiện **cả số lẫn chữ**, tránh "hiệu ứng bằng chứng yếu".
4. **Bằng chứng vật lý trước, heatmap sau.** Heatmap được ghi rõ "vùng mô hình chú ý — không phải bằng chứng". Bằng chứng vật lý gồm:
   - biểu đồ phản xạ màu theo thời gian;
   - độ lệch đồng bộ môi–âm;
   - so khớp transcript với câu đề bài;
   - bảng hành vi camera.
5. **Dòng thời gian phiên:** thử thách, khung nháy màu, đoạn nói, các lần thu lại, siêu dữ liệu — trên một trục có thể tua.
6. **Hàng đợi sắp theo chi phí kỳ vọng**, không theo điểm thô. Chèn "ca chuẩn" (canary) để theo dõi độ chính xác người duyệt. Bắt buộc mã lý do khi kết luận.
7. **Hồ sơ được ký số Ed25519**, nhật ký **chuỗi băm** chỉ-thêm (hash = SHA-256(prev ‖ event)), đầu chuỗi được ký và công bố định kỳ — đáp ứng Luật AI Điều 14(c) và TT 50 Điều 7.7.

**Forensic Mode** (yêu cầu "giám định phục vụ điều tra" của đề 16):
- Điều tra viên tải lên file video/âm thanh — ví dụ cuộc gọi video bị nghi giả mạo người thân, đã nén qua mạng xã hội.
- Hệ thống chạy E2 + E6 (phần thụ động) + đồng bộ môi–âm với mô hình đã tăng cường nén.
- Kết quả là **báo cáo giám định**: tỷ số khả năng theo từng tín hiệu, mức nén và chất lượng đầu vào, giới hạn (không có thử thách chủ động nên độ tin cậy thấp hơn Live Mode), hash file gốc.
- Báo cáo chỉ là **công cụ hỗ trợ giám định, không thay thế kết luận giám định tư pháp**.

#### 2.6.8 L5 — Ring Radar: từ phiên đơn lẻ đến đường dây

**Tín hiệu mỗi phiên** (chỉ lưu dạng dẫn xuất):
- embedding **nền đã che người** (DINOv2) cùng descriptor gần-trùng (SSCD, pHash);
- chữ ký ánh sáng;
- băm khung hình theo thời gian (phát hiện tái sử dụng media chèn);
- embedding giọng và nhiễu nền;
- tín hiệu thiết bị và CamProbe;
- IP/ASN;
- nhịp thời gian (giờ bắt đầu, khoảng cách giữa các phiên).

**Chỉ mục và đồ thị:**
- FAISS-HNSW, mỗi loại tín hiệu một chỉ mục; ngưỡng hiệu chỉnh để tỷ lệ trùng nhầm trên cặp người thật ≈ 10⁻³.
- Đồ thị phiên–thiết bị–IP với cạnh có kiểu, cửa sổ trượt 30 ngày; tìm cộng đồng bằng **Leiden** (Traag et al. 2019).
- Điểm cụm dựa trên: kích thước, mật độ, **số loại cạnh độc lập**, độ dồn dập theo thời gian.

**Chính sách cảnh báo:**
- Chỉ cảnh báo khi **≥ k danh tính** được nối bởi **≥ 2 loại tín hiệu độc lập**.
- Whitelist điểm giao dịch/kiosk.
- Đầu ra là xác thực bổ sung hoặc người duyệt — **không bao giờ tự động từ chối**.
- Thuộc tính rủi ro "nghi liên kết đường dây" có thể làm giàu SIMO **sau khi người duyệt xác nhận**.

**Thẻ giải thích**, ví dụ: "9 danh tính; 7 chung nền (tương đồng ≥ 0,9); 6 mở trong 3 giờ; 4 cùng dòng máy có dấu hiệu hook camera".

**Quyền riêng tư:**
- chỉ embedding/hash, không lưu media thô;
- template khuôn mặt qua phép biến đổi có khóa, hủy được (tinh thần ISO/IEC 24745), khóa riêng theo mục đích;
- thời hạn lưu 90–180 ngày với dữ liệu không cảnh báo;
- phân quyền và kiểm toán mọi truy vấn.

**Căn cứ:** Luật BVDLCN 2025 cho phép xử lý không cần đồng ý để phòng chống tội phạm, kèm các biện pháp bảo vệ — *số điều cần luật sư xác minh*. Báo chí dẫn NĐ 330/2026 Điều 34: bên cung cấp tài khoản phải lưu log thiết bị/IP ≥ 90 ngày và có cơ chế phát hiện bất thường — *cần đối chiếu văn bản gốc*.

**Tài liệu đi trước:** Sumsub ("Similar selfie backgrounds"), AU10TIX Serial Fraud Monitor, Onfido Known Faces — đều đóng, gắn SDK riêng. Đóng góp của nhóm là **module mở, minh bạch, quyền riêng tư theo thiết kế, phù hợp luật Việt Nam và SIMO**, được đánh giá trên kịch bản đường dây thật của Việt Nam.

#### 2.6.9 L6 — Giám sát và học liên tục
- **Martingale hoán đổi** (Fedorova et al. ICML 2012; Vovk et al.) trên p-value conformal của từng phiên.
  - Báo động khi martingale > 100. Theo bất đẳng thức Ville, xác suất báo động nhầm ≤ 1%.
  - Chạy riêng theo lớp thiết bị, theo engine, và theo **mật độ điểm gần ngưỡng** — tín hiệu của việc dò oracle hoặc một chiến dịch tấn công mới.
- **Vòng học liên tục** (DA940-02): nhãn của người duyệt và mẫu red-team mới → huấn luyện lại định kỳ → **hiệu chỉnh lại LTT** → triển khai bóng (shadow) → canary 5–10% → mở rộng; tự động lùi khi martingale báo động hoặc BPCER vượt SLO.

### 2.7 Giả thuyết kiểm chứng và giao thức đánh giá

**Giả thuyết (khóa trước khi mở tập kiểm tra):**

| # | Giả thuyết | Chỉ số chính | Đối chứng |
|---|---|---|---|
| H1 | Ở **cùng tỷ lệ duyệt** (5%, 10%), TrustRouter có BPCER thấp hơn và APCER tự động không cao hơn | BPCER, APCER_max^auto, đường risk–coverage, AURC | (B1) ngưỡng cố định trên PAD; (B2) hợp nhất logistic + 1 ngưỡng; (B3) **hai ngưỡng kiểu Chow**; (B4) split conformal thường; (B5) luôn hỏi VoiceGate |
| H2 | Bảo đảm LTT giữ trên dữ liệu thật | Tần suất vi phạm qua ≥ 200 lần chia lại ngẫu nhiên (phải ≤ δ) | — |
| H3 | Lớp chứng minh hiện diện giảm APCER cho T3/T5/T6 | APCER theo loại tấn công; tỷ lệ tấn công chèn luồng thành công (tinh thần CEN/TS 18099) | PAD + deepfake thụ động |
| H4 | Nhánh THU LẠI giảm từ chối nhầm ở nhóm chất lượng thấp | BPCER theo nhóm chất lượng, lux, lớp thiết bị; tỷ lệ thu lại thành công; số lần thử | Không có cổng chất lượng |
| H5 | Fine-tune tiếng Việt giảm EER trên bộ sinh giọng chưa thấy | EER, minDCF, t-DCF; theo miền Bắc/Trung/Nam | Checkpoint huấn luyện tiếng Anh |
| H6 | Ring Radar phát hiện cụm với ngân sách cảnh báo cố định | Recall cụm @ cảnh báo/1.000 phiên; FPR trên cụm khó (hộ gia đình, ký túc xá, kiosk) | Luật tốc độ đơn lẻ |
| H7 *(khám phá)* | Hồ sơ "người quyết trước" cải thiện phụ thuộc đúng | Độ chính xác cân bằng, RAIR/RSR, thời gian, NASA-TLX | Video + điểm thô |

**Thiết kế đánh giá:**
- *Chia tập:* train / calibration / test **tách theo người, thiết bị và công cụ tấn công**.
- *Tấn công chưa biết:* **giữ riêng công cụ** — hiệu chỉnh trên {OBS phát lại, FaceFusion}, kiểm tra trên {Deep-Live-Cam, LivePortrait}; với giọng, giữ riêng một bộ sinh.
- *Ablation:* bỏ lần lượt hiệu chỉnh, điều kiện chất lượng, cổng OOD, cổng mâu thuẫn, chọn thử thách thích ứng, ChromaPulse, CamProbe, MotionLock, VoiceGate.
- *Thống kê:*
  - bootstrap theo người (cluster) cho khoảng tin cậy 95%;
  - Clopper–Pearson cho APCER thấp;
  - McNemar cho quyết định ghép cặp với baseline;
  - bootstrap ghép cặp cho chênh lệch chi phí và AURC;
  - hiệu chỉnh Holm khi so sánh nhiều cặp;
  - **luôn công bố số mẫu theo từng loại tấn công**.
- *Chỉ số chuẩn:*
  - ISO/IEC 30107-3: APCER theo loài PAI, APCER_max, BPCER, BPCER@APCER 1% và 5%, APNRCR/BPNRCR;
  - ISO/IEC 19795-1: tỷ lệ không thu nhận được (FTA);
  - t-DCF cho giọng nói;
  - IAPAR để đối chiếu ngưỡng tham chiếu của NIST (< 0,07) và FIDO (< 4% tổng).
- *Công bằng:* BPCER theo giới, nhóm tuổi, tông da và lớp thiết bị (NIST: không kém quá 25% so với tổng thể). Nhãn nhân khẩu học **chỉ dùng cho kiểm thử offline**, không suy luận lúc chạy.
- *Độ trễ:* p50/p95 từ lúc kết thúc thu đến lúc có quyết định; mục tiêu ≤ 5 giây.

### 2.8 Đóng góp, tính mới và định vị trung thực

**Tuyên bố tính mới có thể bảo vệ** (đã kiểm chứng qua OpenAlex, arXiv và Google Patents trong giới hạn khảo sát):
1. **Lần đầu (theo hiểu biết của nhóm)** áp dụng kiểm soát rủi ro phi tham số với bảo đảm mẫu hữu hạn (split conformal / Learn-then-Test) cho quyết định liveness/eKYC:
   - bảo đảm BPCER và tỷ lệ thu lại;
   - bảo đảm APCER theo từng loại tấn công đã biết, **cho cả chính sách tuần tự** nhờ phát lại phản thực.
   - Công trình gần nhất chỉ dừng ở từ chối dựa trên độ tin cậy, không có bảo đảm: CA-FAS (2024), Wang & Yamagishi (ICASSP 2022).
2. **Chính sách ba hành động có hiệu chỉnh** tách **thu lại** (bất định giải thích được bằng chất lượng đo được) khỏi **duyệt** (bất định về tấn công), mỗi nhánh có ngân sách rủi ro riêng, trên phép hợp nhất tỷ số khả năng có điều kiện chất lượng của PAD, deepfake, chứng minh hiện diện và giọng nói.
3. **Chọn thử thách dị loại theo lượng thông tin** (ánh sáng / chuyển động / giọng nói) với dừng kiểu SPRT và trộn ngẫu nhiên chống "lái". Đây là mở rộng của hợp nhất sinh trắc tuần tự (Murakami et al. 2016) sang chống giả mạo.
4. **Nghiên cứu đo lường** về độ trễ và tương quan phản xạ màn hình, cùng độ nhất quán chuyển động–video, **trên trình duyệt di động phổ thông tại Việt Nam**, trước tấn công camera ảo.
5. **Bộ dữ liệu ViKYC-Attack** và **ma trận bao phủ mối đe dọa** công bố cả trường hợp hệ thống *không* chặn được.
6. **Kiểm tra khép môi theo câu tiếng Việt đã biết**, không cần huấn luyện, diễn giải được.

**Tài liệu đi trước nhóm trích dẫn và không tuyên bố là của mình:**

| Ý tưởng | Đã có |
|---|---|
| Phản xạ ánh sáng màn hình để kiểm tra sự sống | Face Flashing (NDSS 2018), LiveScreen (INFOCOM 2020), FaceRevelio (MobiCom 2020), Gerstner & Farid (CVPRW 2022); bằng sáng chế iProov US 9,479,500, NEC US 11,954,940, Amazon US 12,333,863 |
| Cảm biến chuyển động cho liveness | Chen et al. (MobiSys 2014), Li et al. (CCS 2015) |
| Câu ngẫu nhiên + đồng bộ môi + ASR | Bằng sáng chế Rakuten US 12,039,024; Agarwal et al. (CVPRW 2020); **Tran et al., FPT University (KSE 2022) — liveness bằng chuỗi từ tiếng Việt ngẫu nhiên + LipBERT** |
| Phát hiện mặt trùng / mạng gian lận | Onfido Known Faces, Sumsub Fraud Network Detection, AU10TIX |
| Dải chấp nhận/duyệt/từ chối; hợp nhất có chất lượng | Thực hành công nghiệp; Nandakumar 2008; Poh & Kittler |

**Sở hữu trí tuệ:** các bằng sáng chế trên là quyền tại Mỹ, châu Âu và Anh. Nguyên mẫu nghiên cứu phi thương mại có rủi ro thấp. **Khi thương mại hóa** sẽ thực hiện rà soát tự do vận hành (FTO), đặc biệt với ChromaPulse (iProov đến khoảng 2033, Amazon đến khoảng 2043) và VoiceGate (Rakuten đến khoảng 2040).

---

## 3. CÔNG NGHỆ DỰ KIẾN SỬ DỤNG

### 3.1 Công nghệ AI và giấy phép

| Thành phần | Lựa chọn | Giấy phép | Ghi chú |
|---|---|---|---|
| Landmark mặt (client) | MediaPipe Face Landmarker | Apache-2.0 | WASM/GPU; mục tiêu ≥ 15 FPS trên máy tầm thấp |
| Phát hiện mặt | YuNet (opencv_zoo) | Apache-2.0 | |
| PAD nhẹ (client, tham khảo) | MiniFASNet ONNX + onnxruntime-web | Apache-2.0 | Không dùng làm điểm chính thức |
| PAD server | DINOv2 ViT-S/B + LoRA hoặc tuyến tính | Apache-2.0 (backbone) | Đối chứng: FoundPAD (CC BY-NC-SA), FLIP |
| Deepfake | CLIP linear probe (UnivFD MIT / Cozzolino Apache-2.0) | MIT / Apache-2.0 | Đối chứng: Effort, DeepfakeBench (CC BY-NC) |
| Chất lượng | Tập con theo OFIQ / ISO/IEC 29794-5 | OFIQ code MIT | |
| ASR tiếng Việt | PhoWhisper-small qua faster-whisper int8 | BSD-3 | |
| Chống giả giọng | SSL-AASIST / XLSR-Mamba | MIT | XLS-R-300M (fairseq, MIT) |
| Đồng bộ môi–âm | SyncNet, AVAD | MIT | Giấy phép SyncNet: [cần kiểm tra] |
| Người nói | ECAPA-TDNN (SpeechBrain) | Apache-2.0 | |
| Ring Radar | DINOv2, SSCD, FAISS, igraph/leidenalg | Apache-2.0 / MIT / GPL (leidenalg) | leidenalg là GPL → tách dịch vụ hoặc thay bằng thư viện khác khi thương mại hóa |
| Hiệu chỉnh / LTT | scikit-learn, `aangelopoulos/ltt` | BSD / MIT | |
| Công cụ red-team (nội bộ) | Deep-Live-Cam (AGPL), FaceFusion, LivePortrait, OBS, viXTTS (CPML, phi thương mại), F5-TTS-VI (CC BY-NC-SA), RVC | — | Chỉ dùng kiểm thử, không phân phối |

**Nguyên tắc:**
- Lõi sản phẩm chỉ dùng thành phần **MIT/Apache/BSD**. Thành phần phi thương mại chỉ dùng cho đối chứng nghiên cứu, ghi rõ trong *model & data card*.
- Mọi mô hình được đóng gói ONNX, lượng tử hóa int8 cho backbone; ghi SHA-256 vào sổ đăng ký mô hình (MLflow).

### 3.2 Hạ tầng và luồng dữ liệu

**Thành phần:**
- **Client:** Next.js/React.
- **API:** FastAPI (session-svc), Redis (giới hạn lượt, hàng đợi Redis Streams/RQ).
- **Worker:** face-gpu, audio, av-sync — ONNX Runtime CUDA/CPU.
- **Lưu trữ:** MinIO/S3 (media tạm, mã hóa theo phiên, vòng đời TTL); PostgreSQL (trạng thái phiên, kết quả, nhật ký chuỗi băm); MLflow (mô hình); Prometheus + Grafana (giám sát); Docker Compose.

**Vì sao không dùng WebRTC:** truyền chunk ngắn qua HTTPS thay cho WebRTC vì WebRTC tự hạ bitrate khi mạng yếu — đúng lúc cần chất lượng nhất — và cần vận hành TURN/SFU.

**Ngân sách độ trễ** (từ khi kết thúc thu đến khi có quyết định; ước lượng, sẽ đo ở tuần đầu):

| Giai đoạn | GPU L4 | Chỉ CPU (8 vCPU, int8) |
|---|---|---|
| Chunk cuối + hoàn tất | 0,3–0,8 s | 0,3–0,8 s |
| Giải mã, cắt mặt, lấy mẫu lại | 0,1–0,2 s | 0,2–0,4 s |
| Nhánh mặt (PAD + deepfake, 8 khung) | 0,1–0,2 s | 1,0–2,0 s |
| Nhánh âm thanh (XLS-R + ECAPA + PhoWhisper-small) | 0,3–0,5 s | 1,2–2,2 s |
| Đồng bộ môi–âm + ChromaPulse + CamProbe | 0,1–0,2 s | 0,4–0,8 s |
| Hợp nhất, ghi DB, ký hồ sơ | < 0,1 s | < 0,1 s |
| **Tổng** (các nhánh song song) | **≈ 1,2–2,0 s** | **≈ 3,0–4,5 s** |

### 3.3 Bảo mật của chính hệ thống
- **Chống oracle:** client chỉ nhận `pass | retry | review`, không bao giờ nhận điểm. Giới hạn lượt theo thiết bị, IP và danh tính (ví dụ 3 lần/giờ, 10 lần/ngày) kèm backoff.
- **OWASP API Top 10:**
  - BOLA: người duyệt chỉ xem ca được giao;
  - giới hạn kích thước và độ dài upload;
  - ffprobe chạy trong sandbox;
  - timeout suy luận.
- **Chống mẫu đối kháng:** ensemble dị loại (CNN/ViT/CLIP/âm thanh/đồng bộ), crop ngẫu nhiên phía server, ngưỡng ẩn. Kết hợp với thử thách vật lý mà nhiễu số thuần túy khó giả. **Nhóm không tuyên bố bền vững đã chứng minh** (Athalye et al. 2018).

### 3.4 Quyền riêng tư theo thiết kế và tuân thủ

| Yêu cầu | Nguồn | Cách VeriClue đáp ứng |
|---|---|---|
| Đồng ý rõ ràng, cụ thể; im lặng không phải đồng ý; báo là dữ liệu nhạy cảm | Luật 91/2025 Điều 9; NĐ 356/2025 | Màn hình đồng ý riêng, không tích sẵn; lưu bản ghi kèm hash |
| Đánh giá tác động xử lý dữ liệu cá nhân (DPIA) | Luật 91/2025; NĐ 356/2025 | Hồ sơ DPIA đi kèm sản phẩm |
| Lưu đúng mục đích; xóa khi hết mục đích | Luật 91/2025 | Media TTL 24 giờ (đạt) / 30 ngày (ca duyệt); crypto-shred bằng khóa theo phiên |
| Thông báo vi phạm 72 giờ | NĐ 356/2025 | Quy trình ứng phó sự cố |
| Giám sát và can thiệp của con người; nhật ký | Luật AI 134/2025 Điều 14 | Nhánh DUYỆT; hồ sơ bằng chứng; nhật ký chuỗi băm |
| PAD theo ISO 30107 mức 2; FRR < 5% tại FAR < 0,01% | TT 50/2024 sửa đổi bởi TT 77/2025, Điều 11.5 | VeriClue **bổ trợ** engine PAD đã chứng nhận; báo cáo theo ISO/IEC 30107-3 |
| Dừng khi phát hiện giả lập, hook, root | TT 50 Điều 8.4 | Nhận tín hiệu toàn vẹn thiết bị từ app native (nếu có); CamProbe trên web |
| Log ≥ 3 tháng trực tuyến, ≥ 1 năm sao lưu | TT 50 Điều 7.7 | Chính sách lưu nhật ký và hồ sơ |
| Chống chèn luồng; phân tích dấu hiệu AI tạo sinh; bổ sung duyệt thủ công | NIST 800-63A-4 §3.14 | ChromaPulse, CamProbe, MotionLock, E2; nhánh DUYỆT |
| IAD kiểm thử theo CEN/TS 18099 | ETSI TS 119 461 v2.1.1 | Giao thức red-team theo ma trận phương thức × công cụ chèn |
| Kiểm thử thiên lệch | NIST §3.11 (≤ 25%); FIDO | Báo cáo BPCER theo nhóm |
| Mức tác động AI | Luật AI 2025 Điều 9–10; NĐ 142/2026 | Hồ sơ tự phân loại, chuẩn bị theo mức rủi ro cao |

Tham chiếu quốc tế: EU AI Act loại xác minh sinh trắc 1:1 khỏi nhóm "rủi ro cao". VeriClue giữ phạm vi 1:1 + PAD/IAD, **không suy luận cảm xúc hay thuộc tính nhân khẩu học** lúc chạy.

### 3.5 So sánh với các giải pháp hiện có

| Năng lực | iProov / Jumio / FaceTec | Nhà cung cấp eKYC trong nước | VeriClue |
|---|---|---|---|
| PAD được chứng nhận | Có | Có (ISO 30107 mức 2: VNPT, Viettel AI, VNPAY…) | Bổ trợ, không thay thế |
| Chống chèn luồng / camera ảo | Có (đóng, SDK native) | Chưa thấy công bố chứng nhận | ChromaPulse + CamProbe + MotionLock, **trên web**, mở và đo được |
| Deepfake tối ưu cho dữ liệu Việt Nam | Không công bố | Không công bố | ViKYC-Attack, tăng cường nén |
| Chống giả giọng tiếng Việt | Không | Không | VoiceGate-VI |
| Bảo đảm thống kê cho quyết định | Không công bố | Không công bố | **Learn-then-Test** |
| Tách thu lại / duyệt | Hướng dẫn chụp + ngưỡng | Ngưỡng | Hai nhánh, mỗi nhánh có ngân sách rủi ro riêng |
| Hồ sơ cho người duyệt | Không công bố (Reality Defender có heatmap ở gói Enterprise) | Không công bố | Bằng chứng vật lý, người quyết trước |
| Giám định cho điều tra | Không | Không | Forensic Mode |
| Phát hiện đường dây | Sumsub, AU10TIX (đóng) | Chưa thấy công bố | Ring Radar, minh bạch, đúng luật Việt Nam |
| Làm chủ trong nước, on-premise | Không | Có | Có |

*So sánh dựa trên tài liệu công khai; việc không công bố không chứng minh là không có.*

---

## 4. ĐỐI TƯỢNG SỬ DỤNG

### 4.1 Đơn vị triển khai
- **Ngân hàng, trung gian thanh toán, công ty chứng khoán, nhà mạng.** Điểm chạm: mở tài khoản, giao dịch > 10 triệu đồng, đổi thiết bị, đổi thông tin định danh.
- **Nhà cung cấp eKYC đã có chứng nhận PAD** (VNPT, FPT, Viettel AI…). Họ tích hợp VeriClue như lớp **chống chèn luồng, deepfake và quyết định**, chuẩn bị cho xu hướng kiểm thử CEN/TS 18099.
- **Trung tâm RAR (C06) / hệ sinh thái VNeID:** eKYC qua mini-app.
- **Cơ quan điều tra (C06, A05), Bộ Tư lệnh 86:** Forensic Mode và tín hiệu Ring Radar.

### 4.2 Người sử dụng trực tiếp

| Vai trò | Nhu cầu | VeriClue cung cấp |
|---|---|---|
| Người dân xác minh | Nhanh, không bị chặn oan, hiểu cần sửa gì | Dưới 60 giây thu; một chỉ dẫn mỗi lần; thu lại thay vì từ chối; phương án thay thế cho người nhạy cảm ánh sáng, khó nói hoặc cao tuổi |
| Chuyên viên duyệt | Đúng ca, đủ bằng chứng, không bị AI dẫn dắt sai | Hàng đợi theo chi phí; hồ sơ bằng chứng vật lý; người quyết trước, AI hiện sau |
| Quản trị rủi ro | Kiểm soát lọt / chặn nhầm / tải duyệt | Ngưỡng có bảo đảm; bảng điều khiển theo loại tấn công, thiết bị, phiên bản; báo động trôi |
| Điều tra viên | Giám định file, lần đường dây | Forensic Mode; cảnh báo cụm Ring Radar có giải thích |

### 4.3 Tác động
- **An toàn tài chính:** đánh vào đúng thủ đoạn của các đường dây đã bị khởi tố (chèn luồng, AI khuôn mặt, thuê người). Phát hiện **trước giao dịch đầu tiên**, bổ sung cho SIMO vốn hoạt động sau khi tài khoản bị báo cáo. Không phụ thuộc việc nạn nhân trình báo — chỉ 32% nạn nhân trình báo.
- **Bao trùm tài chính:** người dùng máy rẻ, ánh sáng kém, người cao tuổi được **hướng dẫn thu lại hoặc chuyển người duyệt** thay vì bị từ chối. BPCER được đo và công bố theo lớp thiết bị và điều kiện thu.
- **Chủ quyền công nghệ:** mã nguồn và mô hình tự chủ, on-premise, minh bạch — đúng yêu cầu "làm chủ trong nước" của DA940-02.
- **Bảo vệ dữ liệu:** tối thiểu hóa, lưu tạm, crypto-shred, ký số — đúng Luật BVDLCN 2025.
- **Bảo vệ người dân trước lừa đảo deepfake người thân:** Forensic Mode là nền tảng cho dịch vụ kiểm tra cuộc gọi nghi giả mạo. Hướng phát triển gắn với đề bài cộng đồng "Lá chắn chống giả mạo giọng nói và video người thân".

### 4.4 Mô hình triển khai và kinh doanh
- **Hình thức:** API theo lượt kiểm tra (phân bậc); phí riêng cho hồ sơ duyệt/giám định; giấy phép on-premise cho ngân hàng và cơ quan nhà nước.
- **Lộ trình thí điểm ba pha**, mỗi pha chỉ mở khi đạt ngưỡng đã khóa:
  1. **Quan sát:** chạy song song, không tác động quyết định thật; thu dữ liệu hiệu chỉnh.
  2. **Hỗ trợ duyệt:** hồ sơ bằng chứng cho chuyên viên.
  3. **Tự động có điều kiện:** chỉ tự động trong vùng đã được LTT chứng nhận; canary và tự động quay lui khi martingale báo động.
- **Lộ trình chứng nhận:** kiểm thử IAD theo CEN/TS 18099 và PAD theo ISO/IEC 30107-3 tại phòng thí nghiệm được công nhận; đề xuất thí điểm với cơ quan nhà nước theo Điều 11.3 thể lệ.

---

## 5. TÍNH KHẢ THI

### 5.1 Dữ liệu

**Tải ngay (không cần duyệt):**
- Khuôn mặt: CelebA-Spoof; **Zalo AI 2022 Liveness (người Việt, Kaggle)**.
- Deepfake: DF40 (một phần), DFDC (1–2 phần).
- Giọng nói: ASVspoof 2019 LA; ASVspoof 2021 DF; ASVspoof 5 (dev); In-the-Wild; CodecFake+; VIVOS; FOSD.

**Đăng ký trong ngày (thường được duyệt trong vài ngày):**
- Giọng nói: **VSASV** (tiếng Việt, CC BY-NC 4.0), **SEA-Spoof** (phần tiếng Việt khoảng 60 giờ), MLAAD, viVoice.
- Nghe–nhìn: FakeAVCeleb (có người Đông Á và Nam Á), LAV-DF.
- Deepfake: FF++, Celeb-DF v2 / Celeb-DF++, Deepfake-Eval-2024.
- Khuôn mặt: SynthASpoof.
- Trọng số: FoundPAD.

**Cần giảng viên ký (1–4 tuần, không đặt vào đường găng):** CASIA-SURF CeFA, **UniAttackData** (có người Đông Á, có tấn công số), OULU-NPU, SiW-Mv2, WFAS.

**ViKYC-Attack — bộ dữ liệu tự thu** (nguồn duy nhất cho người Việt và tấn công chèn luồng; hiện **chưa có bộ dữ liệu công khai** về camera ảo hay chèn luồng):
- **Người tham gia:** 30–40 người Việt tình nguyện, phân tầng Bắc/Trung/Nam, có người ≥ 55 tuổi; 3–5 điện thoại (Android rẻ, tầm trung, iPhone) và laptop; 4 mức ánh sáng (< 50, 150–300, 500–1.000, > 5.000 lux, ngược sáng).
- **Mỗi người:** 3 video selfie với **toàn bộ thử thách** (để phát lại phản thực); 10 câu đọc; 1 phút nói tự do.
- **Tấn công:**
  - T1–T2: in A4 bóng/mờ, cắt mắt, phát lại trên điện thoại / laptop / máy tính bảng;
  - T3: OBS VirtualCam với video/ảnh lưu sẵn;
  - T5: virtual camera trên Android (trình giả lập / máy thử);
  - T6: Deep-Live-Cam / FaceFusion / LivePortrait với người điều khiển ngồi trước màn hình;
  - T4: viXTTS, F5-TTS-VI, VietTTS, RVC + lip-sync (Wav2Lip/LatentSync);
  - T8: kịch bản đường dây — cùng phòng, nhiều "danh tính" bằng khuôn mặt tổng hợp đưa qua camera ảo vào **ứng dụng của nhóm**; cụm khó: cùng hộ gia đình, ký túc xá.
- **Quy mô dự kiến:** khoảng 1.400 clip, khoảng 30 GB; mục tiêu ≥ 60–100 phiên mỗi loại tấn công chính để chứng nhận α = 5%.
- **Đạo đức và pháp lý:**
  - đồng ý bằng văn bản theo NĐ 356/2025, với các ô đồng ý tách riêng: thu thập / tạo mẫu tấn công từ dữ liệu của mình / hiển thị trong báo cáo / chia sẻ nghiên cứu;
  - chỉ người đủ 18 tuổi;
  - mã hóa, ẩn danh bằng mã người tham gia, lưu trong nước;
  - xóa sau dự án + 6 tháng;
  - loại người có tiền sử động kinh khỏi bước nháy màu;
  - **không thử trên hệ thống ngân hàng thật**; không phát tán công cụ hay mẫu tấn công.

### 5.2 Kế hoạch triển khai

Mốc của BTC: vòng 2 kết thúc 25/10 (theo trang chủ; thể lệ ghi 06/11 — đang xác nhận lại với BTC), triển lãm giữa tháng 11.

| Giai đoạn | Thời gian | Đầu ra khóa |
|---|---|---|
| **Sprint 0** | 15–16/10 | Chốt phạm vi; gửi mọi yêu cầu dữ liệu; repo, CI, Docker; mô-đun giả lập trả điểm để **tích hợp từ ngày đầu**; biểu mẫu đồng ý |
| **Sprint 1 — MVP lõi** | 17–25/10 | Luồng web hoàn chỉnh; cổng chất lượng; **ChromaPulse + CamProbe**; PAD + deepfake server; TrustRouter v1 (hiệu chỉnh + hợp nhất + Chow + LTT); bàn duyệt cơ bản; red-team đợt 1 (T1–T3, T6); số liệu đầu tiên |
| **Sprint 2 — Mở rộng** | 26/10–06/11 | VoiceGate-VI (ASR + chống giả giọng fine-tune + khép môi); MotionLock; cổng OOD và mâu thuẫn; chọn thử thách thích ứng; Forensic Mode; Ring Radar v1; thu ViKYC-Attack đầy đủ |
| **Sprint 3 — Đánh giá và triển lãm** | 07/11–triển lãm | Khóa ngưỡng; chạy toàn bộ H1–H6; mini-study người duyệt (H7) và trải nghiệm người dùng (SUS); tối ưu độ trễ; kịch bản demo 7 tình huống; video dự phòng; báo cáo |

Nếu BTC xác nhận hạn vòng 2 là 06/11, Sprint 1 và 2 được giãn tương ứng. Phạm vi MUST không đổi.

**Phân công:**

| Thành viên | Trách nhiệm chính |
|---|---|
| 1 — Frontend thu nhận | SDK trình duyệt: hướng dẫn, chất lượng client, ChromaPulse (phát và đo), CamProbe, MotionLock, đồng ý, trợ năng |
| 2 — Bàn duyệt và sản phẩm | Hồ sơ bằng chứng, dòng thời gian, Forensic Mode UI, bản đồ Ring Radar, kịch bản demo, mini-study |
| 3 — AI khuôn mặt | PAD, deepfake, xử lý tín hiệu ChromaPulse phía server, đồng bộ môi–âm |
| 4 — AI giọng nói | PhoWhisper, chống giả giọng tiếng Việt, sinh mẫu giả, khẩu hình theo câu, ECAPA |
| 5 — Nền tảng và đánh giá | API, hàng đợi, bảo mật, TrustRouter (hiệu chỉnh/LTT/SPRT), Ring Radar backend, pipeline đánh giá, MLOps |

Cả nhóm cùng thu ViKYC-Attack và cùng làm red-team.

### 5.3 Phạm vi và tiêu chí hoàn thành

| Mức | Hạng mục |
|---|---|
| **MUST** (không có thì không có câu chuyện) | Luồng web đầu–cuối · cổng chất lượng + thu lại có giới hạn · ChromaPulse · CamProbe · PAD + deepfake · TrustRouter có hiệu chỉnh + LTT · bàn duyệt với hồ sơ bằng chứng · red-team T1–T3, T6 · báo cáo so sánh với Chow ở **cùng tỷ lệ duyệt** |
| **SHOULD** | VoiceGate-VI · MotionLock · cổng OOD và mâu thuẫn · chọn thử thách thích ứng · Forensic Mode · Ring Radar v1 · martingale |
| **COULD** | Mini-study người duyệt (H7) · BPCER theo nhóm nhân khẩu học đầy đủ · chưng cất mô hình · bản đồ Ring Radar tương tác · C2PA cho gói bằng chứng |

**Tiêu chí hoàn thành bản thi:**
1. Người dùng đi hết một phiên trên điện thoại thật trong ≤ 60 giây thu, có quyết định trong ≤ 5 giây.
2. Bảy kịch bản demo (mục 1.4) chạy ổn định.
3. Chuyên viên mở hồ sơ, ghi quyết định và mã lý do; nhật ký kiểm chứng được.
4. Báo cáo có H1–H5 với khoảng tin cậy, số mẫu, cấu hình và phiên bản mô hình để tái lập.

### 5.4 Ngân sách dự kiến

| Hạng mục | Ước tính |
|---|---|
| GPU L4 thuê theo giờ (demo và đánh giá, khoảng 60–80 giờ) | khoảng 40–60 USD |
| Huấn luyện | Kaggle / Colab (miễn phí) + GPU thuê khi cần |
| Thiết bị kiểm thử (2 điện thoại Android giá rẻ đã qua sử dụng) | khoảng 3–4 triệu đồng |
| Vật liệu tấn công vật lý (in ảnh, mặt nạ giấy) | < 0,5 triệu đồng |
| Quà cảm ơn tình nguyện viên | khoảng 2–3 triệu đồng |

### 5.5 Rủi ro và giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Thời gian vòng 2 ngắn | Cao | MUST/SHOULD/COULD; tích hợp từ ngày đầu bằng mô-đun giả lập; khóa đầu ra theo sprint |
| ChromaPulse yếu dưới ánh sáng mạnh hoặc độ sáng màn hình thấp | Trung bình | Wake lock + nhắc tăng độ sáng; đo biên độ, tín hiệu yếu → THU LẠI chứ không phải ĐẠT; MotionLock làm phương án thay thế |
| iOS không khóa được phơi sáng / cân bằng trắng | Trung bình | Trừ vùng nền để bù; hiệu chỉnh riêng theo lớp thiết bị |
| Detector giọng yếu với tiếng Việt và bộ sinh mới | Cao | Fine-tune trên VSASV/SEA-Spoof/tự sinh; báo cáo leave-one-generator-out; không dùng giọng làm căn cứ duy nhất |
| Thiếu mẫu để chứng nhận α nhỏ | Trung bình | Chứng nhận α = 5% theo bảng cỡ mẫu; công bố số mẫu; nêu rõ α = 1% cần khoảng 300 mẫu |
| Dữ liệu cần ký duyệt đến muộn | Trung bình | Không đặt vào đường găng; dùng Zalo, CelebA-Spoof và ViKYC-Attack |
| Kẻ tấn công thích ứng (T5, T6) | Cao | Công bố trung thực tỷ lệ lọt; nhiều lớp độc lập; kiến nghị app attestation khi triển khai |
| Báo nhầm cụm (hộ gia đình, ký túc xá) | Trung bình | ≥ 2 loại tín hiệu độc lập, ≥ k danh tính, whitelist, chỉ chuyển người duyệt |
| Pháp lý dữ liệu sinh trắc | Trung bình | Đồng ý theo NĐ 356; DPIA; lưu trong nước; xóa theo hạn |
| Nén video làm sụp detector | Trung bình | Kênh ảnh không nén; bitrate cao; huấn luyện tăng cường nén |
| Demo trực tiếp gặp sự cố mạng | Trung bình | Chạy local trên laptop GPU tại gian hàng; video dự phòng |

### 5.6 Giới hạn và cam kết đạo đức
- Ứng dụng web **không thể** chứng thực camera hay thiết bị. Một client đã bị chiếm quyền hoàn toàn có thể vượt qua mọi kiểm tra phía client. VeriClue **tăng chi phí tấn công và đo được mức tăng**, không tuyên bố miễn nhiễm.
- Bảo đảm thống kê **không áp dụng** cho tấn công chưa từng thấy hay kẻ tấn công thích ứng; chỉ cổng OOD, red-team và chế độ quan sát giảm nhẹ được rủi ro này.
- Face-swap thời gian thực có chuyển màu ánh sáng (T6) là **điểm yếu lớn nhất**, và sẽ được báo cáo riêng.
- Forensic Mode là **công cụ hỗ trợ**, không thay thế giám định tư pháp.
- Không suy luận cảm xúc hay nhân khẩu học lúc chạy; không tự động từ chối mà không có đường duyệt của con người.
- Mọi kết quả được đo thực tế, công bố kèm cấu hình và số mẫu, không đặt chỉ tiêu để làm đẹp báo cáo (thể lệ Điều 7.3).

---

## 6. TÀI LIỆU THAM KHẢO (chọn lọc)

**Chuẩn và pháp lý**
1. NIST SP 800-63-4 (2025), SP 800-63A-4 §3.11, §3.14, §3.15; SP 800-63B-4 §3.2.3.
2. ETSI TS 119 461 V2.1.1 (2025-02), Identity proofing of trust service subjects.
3. CEN/TS 18099:2024, Biometric data injection attack detection.
4. ISO/IEC 30107-3:2023; ISO/IEC 19795-1:2021; ISO/IEC 29794-5:2025; ISO/IEC 24745:2022; ISO/IEC 19989.
5. FIDO Alliance, Biometrics Requirements v4.1 (2025) — Face Verification.
6. Thông tư 50/2024/TT-NHNN, sửa đổi bởi Thông tư 77/2025/TT-NHNN (VBHN 25/VBHN-NHNN); QĐ 2345/QĐ-NHNN; Thông tư 17/2024/TT-NHNN.
7. Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15; Nghị định 356/2025/NĐ-CP; Luật Trí tuệ nhân tạo 134/2025/QH15; Nghị định 69/2024/NĐ-CP.

**Quyết định có bảo đảm**

8. Angelopoulos, Bates, Candès, Jordan, Lei. *Learn then Test*. Annals of Applied Statistics 19(2), 2025.
9. Angelopoulos et al. *Conformal Risk Control*. ICLR 2024.
10. Vovk, Gammerman, Shafer. *Algorithmic Learning in a Random World*. Springer, 2005.
11. Chow. On optimum recognition error and reject tradeoff. IEEE T-IT, 1970.
12. Geifman & El-Yaniv. Selective classification for deep neural networks. NeurIPS 2017.
13. Nandakumar, Chen, Dass, Jain. Likelihood ratio-based biometric score fusion. TPAMI 2008.
14. Poh et al. Benchmarking quality-dependent and cost-sensitive score-level multimodal biometric fusion. TIFS 2009.
15. Sensoy et al. Evidential deep learning. NeurIPS 2018. Han et al. Trusted multi-view classification. ICLR 2021.
16. Wald. Sequential tests of statistical hypotheses. 1945. Murakami, Ohki, Takahashi. Information Fusion, 2016. Murakami, Kaga, Takahashi. IEICE, 2017.
17. Liu et al. Energy-based OOD detection. NeurIPS 2020. Sun et al. Deep nearest neighbors OOD. ICML 2022.
18. Fedorova et al. Plug-in martingales for testing exchangeability. ICML 2012.

**Khuôn mặt, chứng minh hiện diện, deepfake**

19. Tang et al. Face Flashing. NDSS 2018.
20. Gerstner & Farid. Detecting real-time deep-fake videos using active illumination. CVPRW 2022.
21. Liu et al. LiveScreen. INFOCOM 2020. Farrukh et al. FaceRevelio. MobiCom 2020.
22. Kurmankhojayev et al. Virtual camera detection. arXiv 2512.10653, 2025.
23. Chen, Pande, Mohapatra. Sensor-assisted facial recognition. MobiSys 2014. Li et al. Seeing your face is not enough. CCS 2015.
24. Ozgur et al. FoundPAD. WACV-W 2025. Srivatsan et al. FLIP. ICCV 2023. CA-FAS, arXiv 2411.01263.
25. Ojha et al. UnivFD. CVPR 2023. Cozzolino et al. CVPR-W 2024. Yan et al. Effort. ICML 2025. DF40. NeurIPS 2024.
26. Chandra et al. Deepfake-Eval-2024. arXiv 2503.02857.
27. Seibold et al. High-quality deepfakes have a heart! Frontiers in Imaging, 2025.
28. W3C WCAG 2.2, SC 2.3.1; ITU-R BT.1702.

**Giọng nói và nghe–nhìn**

29. Jung et al. AASIST. ICASSP 2022. Tak et al. SSL-AASIST. Odyssey 2022.
30. ASVspoof 5. arXiv 2408.08739. Kinnunen et al. t-DCF. TASLP 2020.
31. SEA-Spoof. arXiv 2509.19865. VietPrism. arXiv 2609.30005. VSASV (VLSP 2025).
32. Le et al. PhoWhisper. arXiv 2406.02555. ViMD. EMNLP 2024.
33. Agarwal et al. Phoneme-viseme mismatches. CVPRW 2020. Feng et al. AVAD. CVPR 2023.
34. Tran, Tran, Nguyen, Tran. A liveness detection protocol based on deep visual-linguistic alignment. KSE 2022.
35. Mittal et al. GOTCHA. EuroS&P 2024. Wang & Yamagishi. ICASSP 2022.

**Con người và AI**

36. Diel et al. Human performance in detecting deepfakes: a meta-analysis. CHB Reports, 2024.
37. Nightingale & Farid. PNAS 2022. Groh et al. PNAS 2022.
38. Bansal et al. CHI 2021. Buçinca et al. CSCW 2021. Vasconcelos et al. CSCW 2023. Fogliato et al. FAccT 2022. Schemmer et al. IUI 2023.
39. ENFSI Guideline for Evaluative Reporting in Forensic Science, 2015. Adebayo et al. Sanity checks for saliency maps. NeurIPS 2018.

**Đường dây và dữ liệu**

40. Traag et al. From Louvain to Leiden. Sci. Rep. 2019. Pizzi et al. SSCD. CVPR 2022. Johnson et al. FAISS.

**Bối cảnh Việt Nam:** NHNN; Bộ Công an / NCA; VietnamPlus; Tiền Phong; CafeF; VOH; VietnamFinance; TTTC-TT; SGGP. Liên kết chi tiết: `docs/research/Nguon_nghien_cuu.md`.

---

## PHỤ LỤC A — Đặc tả ChromaPulse

**Thời gian:**

| Pha | Thời lượng | Nội dung |
|---|---|---|
| Nền | 1,0 s | Màn hình trung tính #d1d1d1 |
| Thử thách | khoảng 4,5 s | **8 đoạn**, mỗi đoạn một ký hiệu ∈ {warm #ffcc73, cool #73d9ff, rose #ffb3eb, mint #80e09e}; hai ký hiệu liền kề khác nhau |
| Kết thúc | 0,5 s | Màn hình trung tính |

**Tham số:**
- Mỗi đoạn giữ 400–650 ms (ngẫu nhiên); chuyển màu raised-cosine 150 ms.
- Độ bất định ≥ 16 bit; seed do server sinh, gửi đúng lúc, commit theo phiên.
- Độ chói tương đối các màu: 0,593–0,657 (chênh ≤ 0,064, dưới ngưỡng "flash" của WCAG). Không màu nào có R/(R+G+B) ≥ 0,8. **≤ 2,5 lần đổi màu/giây**.
- Kiểm tra lại bằng PEAT hoặc Harding trên bản ghi màn hình trước khi demo.

**Giao diện:** lớp phủ toàn viewport (`position: fixed`), có lỗ khung mặt; `navigator.wakeLock.request('screen')`; nhắc tăng độ sáng; hướng dẫn khoảng cách 25–40 cm (bề rộng mặt chiếm 35–60% khung). Trên Android, nếu `getCapabilities()` cho phép, khóa `exposureMode` và `whiteBalanceMode` sau 1 giây ổn định.

**Ghi log:**
- thời điểm `requestAnimationFrame` của mỗi lần đổi màu;
- `requestVideoFrameCallback` (`now`, `mediaTime`, `presentedFrames`, `captureTime` nếu có);
- trung bình RGB tuyến tính của 5 vùng da + cổ + nền theo từng khung.

**Đặc trưng quyết định:**
1. ρ tương quan chuẩn hóa cực đại (khởi điểm 0,6; hiệu chỉnh lại).
2. Độ chính xác giải mã ký hiệu (≥ 7/8).
3. τ* trong phân vị 99 của người thật theo lớp thiết bị.
4. Độ lệch τ* giữa các vùng ≤ 1 khung; τ* mặt ≈ τ* cổ.
5. Tỷ lệ đáp ứng trán/cằm và giữa/biên nằm trong dải người thật (đặc tính 3D).
6. Biên độ đáp ứng — quá thấp → THU LẠI, không phải ĐẠT.

**Tín hiệu kỳ vọng theo loại đầu vào:**

| Đầu vào | Đáp ứng kỳ vọng |
|---|---|
| Người thật | Đáp ứng đồng bộ, khác nhau giữa các vùng theo hình học 3D |
| Ảnh in | Có đáp ứng, nhưng **phẳng** (giống nhau mọi vùng) |
| Màn hình phát lại | Đáp ứng yếu / phản xạ gương đồng nhất |
| File chèn qua camera ảo | Không đáp ứng |
| Face-swap thời gian thực | Đáp ứng trễ ≥ 2 khung hoặc không đáp ứng (tùy công cụ) |

## PHỤ LỤC B — Hợp đồng đầu ra mô-đun

```json
{
  "module": "chromapulse", "model_version": "1.0.0", "model_sha256": "…", "config_hash": "…",
  "session_id": "…", "status": "ok | degraded | error", "error_code": null,
  "score": 0.12, "llr": -2.3, "calibration_id": "platt-2026-10-24",
  "quality": {"face_px": 182, "blur": 0.08, "illum": 0.71, "yaw": 4.2, "snr_db": null, "frames_used": 90},
  "evidence": [{"type": "timeseries", "name": "chroma_response", "uri": "…", "ttl_h": 24},
               {"type": "scalar", "name": "lag_ms", "value": 66}],
  "latency_ms": {"queue": 40, "infer": 38},
  "input_hashes": ["sha256:…"], "ts": "2026-10-24T09:00:00Z"
}
```

Mã lỗi: `E_NO_FACE`, `E_MULTI_FACE`, `E_LOW_QUALITY`, `E_TIMEOUT`, `E_DECODE`, `E_CHALLENGE_MISMATCH`, `E_INTEGRITY`.

## PHỤ LỤC C — Kịch bản trình diễn vòng 3

**Thiết lập gian hàng:**
- **Một laptop GPU** chạy toàn bộ hệ thống local (không phụ thuộc mạng).
- **Ba điện thoại:** Android giá rẻ, tầm trung, iPhone.
- **Một màn hình lớn** chiếu bàn duyệt và Ring Radar.
- **Một trạm tấn công:** laptop với OBS và Deep-Live-Cam, ảnh in, máy tính bảng phát lại.

**Mỗi lượt khách (khoảng 3 phút):**
1. Khách tự làm một phiên thật.
2. Khách tự cầm ảnh in hoặc tablet tấn công.
3. Nhóm biểu diễn camera ảo và face-swap.
4. Mở hồ sơ bằng chứng: biểu đồ phản xạ màu "bám" hoặc "phẳng", độ trễ, transcript.
5. Kết thúc bằng Ring Radar và Forensic Mode.

**Video dự phòng:** quay sẵn toàn bộ 7 kịch bản.

## PHỤ LỤC D — Tóm tắt biểu mẫu đồng ý (ViKYC-Attack)

Biểu mẫu nêu rõ:
- dữ liệu sinh trắc học là **dữ liệu nhạy cảm**;
- các loại dữ liệu thu (khuôn mặt, video, giọng nói);
- mục đích (nghiên cứu chống giả mạo; phi thương mại; không dùng xác thực tài khoản thật);
- việc **tạo mẫu tấn công/deepfake từ dữ liệu của người tham gia**;
- thời hạn lưu (kết thúc dự án + 6 tháng);
- người được truy cập;
- quyền rút lại và yêu cầu xóa, kèm đầu mối liên hệ;
- dữ liệu lưu trong nước.

Bốn ô đồng ý tách riêng, không tích sẵn: (a) thu thập; (b) tạo mẫu tấn công; (c) hiển thị trong báo cáo; (d) chia sẻ cho nghiên cứu khác. Sàng lọc tiền sử động kinh trước bước nháy màu.

## PHỤ LỤC E — Cỡ mẫu cho bảo đảm thống kê

Số mẫu tối thiểu (khi không có lỗi nào) để cận trên Clopper–Pearson một phía của tỷ lệ lỗi ≤ α với độ tin cậy 1 − δ:

  n_min = ⌈ ln δ / ln(1 − α) ⌉

| α \ δ | 0,10 | 0,05 |
|---|---|---|
| 10% | 22 | 29 |
| 5% | 45 | 59 |
| 2% | 114 | 149 |
| 1% | 230 | 299 |

Nếu có lỗi, cỡ mẫu cần tăng. Ví dụ với α = 5%, δ = 0,05: có 1 lỗi cần khoảng 93 mẫu; có 2 lỗi cần khoảng 124 mẫu. Áp dụng cho từng loại tấn công (APCER) và cho người thật (BPCER).

## PHỤ LỤC F — Việc cần xác minh trước khi nộp

1. Hạn vòng 2 (25/10 hay 06/11) và danh sách đầu ra — hỏi BTC/mentor.
2. Việc đăng ký/chuyển gắn kết sang đề 16 (BTL86), đề 62 và DA940-02 có được chấp nhận ở vòng này không.
3. Văn bản gốc: TT 77/2025 (điều khoản và hiệu lực), Luật 91/2025 (số điều về sinh trắc học và ngoại lệ phòng chống tội phạm), NĐ 356/2025, NĐ 330/2026 Điều 34.
4. Giấy phép: SyncNet, viVoice, Zalo AI 2022; điều khoản UniAttackData.
5. Tra Google Scholar một lần nữa cho tuyên bố tính mới số 1 (conformal/LTT cho liveness) ngay trước khi nộp.
