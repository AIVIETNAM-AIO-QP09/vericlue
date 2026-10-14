# BẢN ĐỀ XUẤT GIẢI PHÁP — PHIÊN BẢN 3

# VeriClue
### Phát hiện khuôn mặt và giọng nói giả mạo bằng AI cho định danh điện tử tại Việt Nam

**Đội thi:** DS@AInSec4E — Phạm Anh Quốc · Lê Quang · Trần Văn Đức · Lý Anh Quân · Hồ Lê Ngọc Quang
**Cuộc thi:** Data for Life 2026 — Vòng 2 "Phát triển giải pháp" (hạn nộp: trước 06/11/2026)
**Đề bài đăng ký:** **BTL86-16 — Bộ Tư lệnh 86 (Bộ Quốc phòng): "Phát hiện deepfake giọng nói, hình ảnh trong giả mạo định danh"**
**Đề bài liên quan:**
- Đề bài 62 — "Chỉ số tin cậy danh tính số" (Công an xã Hòa An, Cao Bằng)
- DA940-02 — "AI sinh trắc học và chống gian lận danh tính"

**Tài liệu đi kèm:**
- Sơ đồ kiến trúc: `docs/architecture/architecture.html`
- Kế hoạch dữ liệu: `docs/data/data-plan.md`
- Nguồn tham khảo: `docs/research/sources.md`

> **Phạm vi bản thi:** một **bản demo chạy được** (ứng dụng web), xây dựng hoàn toàn từ **dữ liệu và mô hình công khai**. Nhóm **không tổ chức thu dữ liệu sinh trắc học** của người ngoài.

---

## TÓM TẮT

**Vấn đề.** Từ 2024, Việt Nam bắt buộc đối chiếu sinh trắc học cho giao dịch ngân hàng trực tuyến. 175,2 triệu hồ sơ đã được đối chiếu và số người bị lừa đảo giảm 59%. Tội phạm vì thế chuyển sang **dùng AI để làm giả chính khuôn mặt và giọng nói**:
- **Thái Bình 2025:** dựng clip khuôn mặt bằng AI để qua xác thực, rửa hơn 1.000 tỷ đồng.
- **Thanh Hóa 2025–2026:** phần mềm thay luồng camera, hơn 2.000 tài khoản trong hai vụ.
- Lừa đảo bằng **cuộc gọi video giả người thân, giả lãnh đạo** ngày càng phổ biến.

Đề BTL86-16 chỉ ra rằng công cụ phát hiện hiện nay *"chủ yếu tối ưu cho dữ liệu nước ngoài"*, trong khi người dùng Việt Nam có khuôn mặt người Việt, giọng nói ba miền và video bị nén qua mạng xã hội.

**Giải pháp.** VeriClue gồm **một "bộ não" phát hiện giả mạo** được kiểm tra và tinh chỉnh cho dữ liệu Việt Nam, phục vụ **hai chế độ** đúng như đề bài yêu cầu:

| Thành phần | Làm gì |
|---|---|
| **Bộ não phát hiện giả mạo** | Phát hiện ảnh in / quay lại màn hình, khuôn mặt ghép bằng AI, giọng nói giả tiếng Việt, môi không khớp tiếng nói. Kiểm tra trên khuôn mặt người Việt, giọng Bắc / Trung / Nam và video đã nén |
| **Chế độ 1 — Kiểm tra tức thời trong eKYC** | Người dân xác minh trên điện thoại:<br>• màn hình **nháy chuỗi màu ngẫu nhiên** để chắc chắn có người thật trước camera;<br>• **bộ định tuyến có bảo đảm thống kê** quyết định *cho qua / chụp lại / chuyển nhân viên*;<br>• khi chưa chắc, mời người dân **đọc một câu tiếng Việt** |
| **Chế độ 2 — Giám định phục vụ điều tra** | Điều tra viên tải video lên (kể cả file đã nén). Hệ thống phân tích **từng đoạn vài giây** và xuất **báo cáo giám định** chỉ rõ đoạn nào nghi bị làm giả |

**Điểm nổi bật:**
1. **Đo và thu hẹp "khoảng cách dữ liệu Việt Nam".** Nhóm đo mô hình quốc tế giảm hiệu quả bao nhiêu trên khuôn mặt người Việt, giọng ba miền và video nén, rồi cho thấy mức cải thiện sau khi tinh chỉnh.
2. **Quyết định có bảo đảm thống kê.** Ngưỡng không chọn theo cảm tính; tỷ lệ kẻ giả mạo lọt qua tự động được chặn trên với xác suất cho trước. Theo khảo sát của nhóm, đây là lần đầu cách tiếp cận này (Learn-then-Test) được áp dụng cho quyết định chống giả mạo sinh trắc học.
3. **Chống camera ảo ngay trên trình duyệt**, trực tiếp nhắm vào thủ đoạn trong các vụ án ở Thanh Hóa:
   - phát hiện các tiện ích trình duyệt đang được chia sẻ công khai để thay camera trên trang KYC;
   - đo chính xác độ trễ phản chiếu ánh sáng để bắt cả khuôn mặt ghép bằng AI thời gian thực.
4. **Giám định đúng chuẩn và có bằng chứng nguồn gốc.** Báo cáo theo thang mức độ bằng chứng của ENFSI và được ký số. Hệ thống còn tự dò **dấu ẩn AI** (thủy vân) trong file, nên chỉ ra được công cụ đã tạo ra giọng hoặc ảnh giả nếu công cụ đó có gắn thủy vân.

---

## 1. TỔNG QUAN DỰ ÁN

### 1.1 Tên dự án

**VeriClue** = *verify* (xác minh) + *clue* (dấu vết). Thay vì chỉ trả về nhãn "thật/giả", hệ thống chỉ ra **dấu vết cụ thể**: phản chiếu ánh sáng, độ trễ, đoạn video bất thường, đặc điểm giọng nói. Nhờ vậy con người kiểm tra lại được.

### 1.2 Mô tả ngắn

VeriClue là một **module tích hợp qua API**, gồm ba phần:
1. **Bộ não phát hiện giả mạo:** bốn bộ phát hiện (ảnh in/màn hình, khuôn mặt ghép, giọng giả, khớp môi–âm), được tinh chỉnh và đánh giá trên dữ liệu Việt Nam.
2. **Chế độ eKYC:** web xác minh trên điện thoại, kiểm tra chất lượng, thử thách ánh sáng màu, bộ định tuyến TrustRouter, bàn duyệt cho nhân viên.
3. **Chế độ giám định:** cổng tải file cho điều tra viên, phân tích theo đoạn, báo cáo giám định.

Quyết định cuối cùng luôn thuộc về con người. VeriClue không tự động từ chối ai — đúng tinh thần NIST SP 800-63A-4 §3.14 và Điều 14 Luật Trí tuệ nhân tạo 2025.

### 1.3 Đối chiếu với đề BTL86-16

| Đề bài yêu cầu | VeriClue đáp ứng |
|---|---|
| Phát hiện deepfake **hình ảnh** — khuôn mặt người Việt | Bộ não: PAD + deepfake khuôn mặt, đánh giá trên Zalo AI 2022, Face_anti_spoofing (người Việt) và deepfake người Việt tạo từ dữ liệu công khai |
| Phát hiện deepfake **giọng nói** — tiếng Việt các vùng miền | Bộ phát hiện giọng giả tinh chỉnh trên MLAAD-vi và ViMD; báo cáo **theo miền Bắc / Trung / Nam** |
| Video **nén qua mạng xã hội** | Huấn luyện có tăng cường nén; báo cáo kết quả theo từng mức nén |
| **Kiểm tra tức thời** trong eKYC | Chế độ 1, có quyết định trong ≤ 5 giây |
| **Giám định** phục vụ điều tra | Chế độ 2, phân tích theo đoạn và xuất báo cáo |
| **Chuẩn hóa thành module tích hợp** | REST API, định dạng đầu ra thống nhất, Docker |

Ngoài ra, VeriClue đáp ứng thêm:
- **Đề bài 62:** ba mức tin cậy **Cao / Trung bình / Thấp**, tương ứng *cho qua / xác thực bổ sung / chuyển cơ quan chức năng qua người duyệt*.
- **DA940-02:** báo cáo theo ISO/IEC 30107-3; làm chủ công nghệ trong nước.

### 1.4 Kịch bản trình diễn

Khách tham quan quét mã QR và tự trải nghiệm trên điện thoại của mình. Các tấn công trực tiếp dùng **khuôn mặt và giọng nói của chính thành viên nhóm** (có đồng ý).

| # | Tình huống | Kết quả | Bằng chứng hiển thị |
|---|---|---|---|
| 1 | Người thật | **Cho qua** | Da mặt phản chiếu đúng chuỗi màu |
| 2 | Người thật, phòng tối | **Chụp lại** → lần hai cho qua | Hướng dẫn "ra chỗ sáng hơn" |
| 3 | Ảnh in / phát lại video trên màn hình | **Chuyển nhân viên** | Phản chiếu phẳng; bộ phát hiện PAD báo động |
| 4 | **Camera ảo phát video quay sẵn** (mô phỏng thủ đoạn Thanh Hóa), qua OBS hoặc tiện ích trình duyệt giả camera | **Chuyển nhân viên – ưu tiên cao** | Không phản chiếu chuỗi màu; camera phản hồi bất thường; API camera của trình duyệt bị can thiệp |
| 5 | **Ghép mặt thời gian thực** + giọng clone tiếng Việt | **Chuyển nhân viên – ưu tiên cao** | Phản chiếu trễ (đo bằng mili giây); phát hiện khuôn mặt ghép và giọng giả |
| 6 | **Giám định:** tải lên video giả đã nén | Báo cáo giám định có chữ ký | Biểu đồ theo thời gian chỉ ra khoảng nghi giả; mức độ bằng chứng theo thang ENFSI |
| 7 | **Giám định:** tải lên giọng nói tạo bằng công cụ clone có gắn thủy vân (ví dụ Chatterbox) | Báo cáo giám định | "Phát hiện thủy vân AI của công cụ X", kèm vị trí trên dòng thời gian |

---

## 2. VẤN ĐỀ VÀ GIẢI PHÁP

### 2.1 Bối cảnh

| Dữ kiện | Nguồn |
|---|---|
| QĐ 2345/QĐ-NHNN (từ 1/7/2024): xác thực sinh trắc khi chuyển > 10 triệu đồng/lần hoặc > 20 triệu đồng/ngày | NHNN |
| 175,2 triệu hồ sơ đã đối chiếu sinh trắc (2/10/2026); số người bị lừa giảm 59% | NHNN (CafeF, VNBA) |
| Thiệt hại lừa đảo trực tuyến **hơn 6.000 tỷ đồng** trong 11 tháng năm 2025; chỉ 32% nạn nhân trình báo | Bộ Công an / NCA |
| **Thái Bình (5/2025):** clip AI khuôn mặt dựng từ video 25–30 giây để qua xác thực; rửa hơn 1.000 tỷ đồng | Công an Thái Bình |
| **Thanh Hóa (2025–2026):** hai đường dây, 18 bị can, hơn 2.000 tài khoản; phần mềm thay luồng camera bằng ảnh lưu sẵn | VietnamPlus, CafeF |
| Lừa đảo bằng cuộc gọi video deepfake giả người thân | Báo chí, Bộ Công an |

### 2.2 Bốn khoảng trống

**G1 — Công cụ phát hiện tối ưu cho dữ liệu nước ngoài.**
- Deepfake-Eval-2024: bộ phát hiện mã nguồn mở mất khoảng 50% AUC trên deepfake ngoài đời thực.
- Nén video làm độ chính xác trên FF++ giảm từ 98% xuống 61,2%.
- Bộ phát hiện giọng giả suy giảm mạnh với tiếng Việt: EER tăng từ 16,3% lên 33,6% khi giọng giả càng giống thật (VietPrism 2026).

**G2 — Chứng nhận hiện có không bao gồm chèn luồng camera.**
- Thông tư 50/2024 (sửa đổi bởi TT 77/2025) chỉ yêu cầu chứng nhận chống tấn công trình diện vật lý.
- Quốc tế đã yêu cầu kiểm soát chèn luồng: NIST SP 800-63A-4 §3.14; ETSI TS 119 461 v2 yêu cầu kiểm thử theo CEN/TS 18099.

**G3 — Quyết định dựa trên ngưỡng cảm tính.**
- Theo tài liệu công khai, các nhà cung cấp chỉ trả về điểm số hoặc "đạt / không đạt", không có bảo đảm thống kê.
- Người dùng máy rẻ, ánh sáng kém, người cao tuổi dễ bị chặn nhầm.

**G4 — Con người không phân biệt được deepfake bằng mắt.**
- Độ chính xác trung bình chỉ khoảng 55,5% (tổng hợp 56 nghiên cứu, 86.155 người).
- Nhân viên duyệt và điều tra viên vì vậy cần **bằng chứng cụ thể, kiểm tra lại được**, không chỉ một điểm số.

### 2.3 Câu hỏi nghiên cứu

- **RQ1.** Mô hình phát hiện quốc tế giảm hiệu quả bao nhiêu trên khuôn mặt người Việt, giọng ba miền và video nén? Tinh chỉnh bằng dữ liệu công khai thu hẹp khoảng cách đó được đến đâu?
- **RQ2.** Có thể chọn ngưỡng quyết định sao cho tỷ lệ kẻ giả mạo lọt qua **được chặn trên với xác suất cho trước**, đồng thời ít phải chuyển nhân viên nhất?
- **RQ3.** Trên trình duyệt điện thoại, thử thách ánh sáng màu và thăm dò camera phân biệt được người thật với camera ảo và ghép mặt thời gian thực đến đâu?

### 2.4 Mô hình đe dọa

| # | Tấn công | Phát hiện bởi | Kỳ vọng |
|---|---|---|---|
| T1 | Ảnh in, mặt nạ giấy | PAD; ChromaPulse (phản chiếu phẳng) | Chặn tốt |
| T2 | Phát lại video trên màn hình | ChromaPulse; PAD | Chặn tốt |
| T3 | Camera ảo phát video quay sẵn (OBS, v4l2loopback) hoặc **tiện ích trình duyệt thay hàm lấy camera** (đã có mã công khai trên GitHub, nhắm vào trang KYC) | ChromaPulse (không phản chiếu); CamProbe (hàm camera bị can thiệp, phản hồi bất thường, khung lặp) | Chặn phần lớn |
| T4 | Ảnh nạn nhân + giọng clone + lip-sync | Giọng giả; khớp môi–âm; deepfake khuôn mặt | Chặn phần lớn |
| T5 | Hook camera trên điện thoại đã root, kể cả **chèn ở tầng nhân Android** (giữ nguyên dấu thời gian thật, qua mặt mọi kiểm tra JavaScript) | **ChromaPulse là lớp duy nhất còn bắt được** | Tăng chi phí tấn công, **không bảo đảm** |
| T6 | **Ghép mặt thời gian thực có hòa trộn theo ánh sáng thật** (Deep-Live-Cam, chế độ Poisson) | **Độ trễ tuyệt đối** của ChromaPulse; deepfake khuôn mặt (GenD, SBI) | **Khó nhất** — mặt ghép vẫn phản chiếu, chỉ trễ hơn; báo cáo trung thực |
| T7 | Video giả gửi qua mạng xã hội (giám định) | Bộ não, phân tích theo đoạn | Hiệu quả giảm khi nén mạnh — báo cáo theo mức nén |

**Ngoài phạm vi:** kiểm tra toàn vẹn thiết bị ở cấp hệ điều hành, đọc chip CCCD, đối chiếu CSDL căn cước. Đây là phần việc của đơn vị tích hợp.

### 2.5 Kiến trúc

Sơ đồ đầy đủ (bản cho người không chuyên và bản kỹ thuật): `docs/architecture/architecture.html`.

```
   NGƯỜI DÂN (điện thoại)                         ĐIỀU TRA VIÊN
   ảnh rõ? → người thật? (nháy màu, camera)        tải video → chia đoạn
              │                                              │
              ▼                                              ▼
   ┌──────────────── BỘ NÃO PHÁT HIỆN GIẢ MẠO (dữ liệu Việt Nam) ────────────────┐
   │  PAD (ảnh in, màn hình) · Deepfake khuôn mặt · Giọng giả tiếng Việt ·        │
   │  Khớp môi–âm  —  bền với video nén                                           │
   └──────────────┬───────────────────────────────────────────────┬──────────────┘
                  ▼                                               ▼
   TRUSTROUTER (ngưỡng có bảo đảm)                     BÁO CÁO GIÁM ĐỊNH
   → Cho qua / Chụp lại / Chuyển nhân viên             đoạn nào nghi giả, mức độ,
     (chưa chắc → mời đọc câu tiếng Việt)              giới hạn, mã kiểm tra file
                  ▼
   HỒ SƠ BẰNG CHỨNG → BÀN DUYỆT (nhân viên)
```

### 2.6 Trụ cột 1 — Bộ não phát hiện giả mạo cho dữ liệu Việt Nam

| Bộ phát hiện | Mô hình nền | Tinh chỉnh / hiệu chỉnh trên | Kiểm tra trên |
|---|---|---|---|
| **PAD** (ảnh in, màn hình) | face-antispoof-onnx, MiniFASNet (Apache-2.0); DINOv2 + lớp tuyến tính | CelebA-Spoof; phần train của Zalo AI 2022 | Phần giữ lại của Zalo AI 2022; Face_anti_spoofing (người Việt) |
| **Deepfake khuôn mặt** | **GenD** (WACV 2026, MIT) làm chính; **SBI** (CVPR 2022) làm dự phòng và nguồn heatmap | RTFS-10k (ghép mặt kiểu Deep-Live-Cam), có tăng cường nén; chỉ tinh chỉnh LayerNorm và lớp cuối (0,03% tham số) | WildDeepfake; deepfake người Việt tự tạo (mục 5.1); 3 mức nén |
| **Giọng giả tiếng Việt** | **NII AntiDeepfake** (`mms-300m`, đã học hơn 100 ngôn ngữ, 74 nghìn giờ âm thanh) | Giọng thật **ViMD** (63 tỉnh) + giọng giả **MLAAD-vi** (5 hệ TTS tiếng Việt); tăng cường theo công thức wedefense | **ViSpoofDB** (FPT.AI, Viettel, ElevenLabs — chưa từng thấy khi huấn luyện); kết quả theo **Bắc / Trung / Nam** |
| **Khớp môi–âm** | SyncNet (bản `stable_syncnet` của LatentSync) | — (dùng sẵn) | LAV-DF; video lip-sync tiếng Việt tự tạo |
| **Nhận dạng và căn chỉnh câu nói** | PhoWhisper + `ctc-forced-aligner` | — | So khớp hai lớp (có dấu và bỏ dấu), tính đến giọng miền Trung |

**Mẹo kỹ thuật rút ra từ việc đọc mã nguồn các dự án mở:**
- *Khuôn mặt:*
  - Dùng đúng tiền xử lý của từng mô hình: GenD dùng SCRFD + căn chỉnh 5 điểm, tỷ lệ 1,3, 224 px. Lệch tiền xử lý có thể làm AUC tụt hơn 10 điểm.
  - Lấy 32 khung. Điểm video = trung bình **và** trung bình 25% khung nghi nhất, vì mặt ghép thường chỉ lỗi ở vài khung.
- *Giọng nói:*
  - Tăng cường bằng RawBoost, codec (Opus 16–32 kbps như cuộc gọi Zalo, AMR, MP3), lấy mẫu 8 kHz, nhiễu và vang thật (MUSAN, RIR).
  - **Chống "học vẹt":** trong dữ liệu công khai, giọng thật thường là giọng đọc sách còn giọng giả là TTS rất sạch, nên mô hình dễ học nhận ra nguồn dữ liệu thay vì giọng giả. Xử lý bằng cách cắt khoảng lặng ở hai đầu và cân bằng âm lượng.

**Cách đo "khoảng cách dữ liệu Việt Nam"** (trả lời trực tiếp nhận định của đề):
1. Chạy mô hình gốc (huấn luyện trên dữ liệu nước ngoài) trên tập kiểm tra Việt Nam, ghi kết quả.
2. Tinh chỉnh lớp cuối bằng dữ liệu Việt Nam công khai, tăng cường nén.
3. Chạy lại và so sánh. Báo cáo tách theo: khuôn mặt người Việt; giọng Bắc / Trung / Nam; ba mức nén (gốc, nén vừa CRF 28, nén mạnh CRF 40 / 480p).

### 2.7 Trụ cột 2 — Chế độ kiểm tra tức thời trong eKYC

**(a) Thu nhận và ràng buộc phiên**
- Server tạo **mã phiên** và **seed thử thách**. Từng bước thử thách chỉ gửi đúng lúc cần. Mọi lần tải lên gắn token của phiên (hết hạn sau vài phút); mỗi bước chỉ được nhận một lần, và mỗi thử thách chỉ có hiệu lực 120 giây, nên không phát lại được dữ liệu cũ.
- Web gửi vài **ảnh mặt chất lượng cao** chụp tại thời điểm do server chọn, cùng video ngắn.
- Màn hình đồng ý tách riêng, ghi rõ "dữ liệu sinh trắc học là dữ liệu nhạy cảm" (Luật 91/2025; NĐ 356/2025).

**(b) Cổng chất lượng**
- Đo độ sáng, độ nét, góc mặt, kích thước mặt, tiếng ồn.
- Chưa đạt → **Chụp lại** kèm **một chỉ dẫn duy nhất**, tối đa 2 lần, sau đó chuyển nhân viên.
- Thông điệp chỉ nói về chất lượng, không bao giờ nói "nghi giả mạo".

**(c) Cổng chứng minh hiện diện: ChromaPulse và CamProbe**

*ChromaPulse.*
- Màn hình phát 8 màu nhạt ngẫu nhiên trong khoảng 4–6 giây, đổi màu chậm (dưới 2 lần/giây, trong giới hạn 2,5 lần/giây, an toàn cho người nhạy cảm ánh sáng theo WCAG 2.3.1).
- Hệ thống đo da mặt có phản chiếu **đúng chuỗi màu** và **kịp thời** không:
  - Người thật phản chiếu ngay.
  - Video quay sẵn và camera ảo không phản chiếu.
  - Ghép mặt thời gian thực phản chiếu trễ vài nhịp.
- Căn cứ: Gerstner & Farid (CVPRW 2022) — tương quan 0,89 khi không trễ, 0,37 khi trễ 3 khung hình.
- **Phải đo độ trễ tuyệt đối, không chỉ xem có phản chiếu hay không.**
  - Đọc mã nguồn Deep-Live-Cam thấy nó có chế độ hòa trộn Poisson, nhờ đó mặt ghép "mượn" được ánh sáng thật ở viền và vẫn phản chiếu.
  - Nghiên cứu GOTCHA (EuroS&P 2024) ghi nhận mặt giả vẫn "làm theo" thử thách nháy sáng 52–83% số lần.
  - Toàn bộ khung hình bị trễ như nhau, nên so mặt với cổ không làm lộ độ trễ. Phải đo tuyệt đối.
- **Cách đo:**
  1. Ghi thời điểm vẽ từng màu bằng `requestAnimationFrame`, và thời điểm camera chụp từng khung bằng `requestVideoFrameCallback` (`captureTime`). Cả hai cùng đồng hồ `performance.now()`.
  2. **Không dùng MediaRecorder để đo thời gian.** AWS phải chỉnh bằng một hệ số kinh nghiệm vì cách này không chính xác.
  3. Phía server khớp chuỗi màu đo được với chuỗi đã phát (miền log, có trừ nền), quét độ trễ τ từ 0–300 ms. Kết quả: mức độ khớp (R²) và độ trễ τ.
- **Phần phát màu tái sử dụng mã của AWS Amplify Liveness** (Apache-2.0):
  - chuỗi màu và thời gian do server gửi;
  - tô màu toàn màn hình quanh khung oval;
  - **kéo khuôn mặt lại gần** để tăng ánh sáng phản chiếu;
  - giữ yên 1 giây trước khi nháy;
  - ghi sự kiện "màu đang hiển thị" kèm số thứ tự.

  Nhóm giữ bảng màu an toàn của mình (Phụ lục A). Phần phân tích phản chiếu và độ trễ phía server là phần tự xây — AWS không công bố phần này, và nhóm cũng không tìm thấy mã nguồn mở nào làm việc đó.

*CamProbe.*
- **Kiểm tra hàm camera của trình duyệt có bị can thiệp không** (học theo CreepJS, MIT). Các tiện ích giả camera công khai trên GitHub gán đè `getUserMedia` và `enumerateDevices` bằng JavaScript thường. Các phép kiểm tra:
  - mã hàm có còn là `[native code]` không;
  - hàm có thuộc tính lạ không;
  - so với bản gốc lấy từ một `<iframe>` sạch.

  Đây là một lớp có giá trị nhưng **không phải bảo đảm**: kẻ tấn công có thể vá các dấu hiệu này về sau.
- **Thăm dò phản hồi:**
  - Trình duyệt yêu cầu camera đổi độ phân giải và tốc độ khung hình, đo thời gian phản hồi, **và đọc lại `getSettings()` để xem thông số có thật sự đổi không**. Camera thật phản hồi khoảng 90–210 ms; camera ảo phản hồi trong 1–2 ms hoặc báo thay đổi giả (Kurmankhojayev et al. 2025).
  - Thông số camera có thể bị giả trọn bộ, nên luôn đối chiếu thông số với **hành vi thật**.
- **Tín hiệu phụ:**
  - khung hình lặp lại hoặc nhịp khung đều bất thường (camera ảo phát theo đồng hồ phần mềm);
  - tên thiết bị kiểu "OBS Virtual Camera";
  - tốc độ khung hình dưới 15 khung/giây.

*Cách dùng trong quyết định.* Hai thành phần này hoạt động như **cổng kiểm tra** với ba kết quả:

| Kết quả | Điều kiện | Xử lý |
|---|---|---|
| **Đạt** | Phản chiếu đúng và kịp; camera bình thường | Sang bước tiếp theo |
| **Không đạt** | Không phản chiếu, phản chiếu trễ, hoặc camera bất thường | Chuyển nhân viên – ưu tiên cao |
| **Chưa rõ** | Tín hiệu yếu (ánh sáng môi trường mạnh, màn hình tối) | Chụp lại |

Ngưỡng được chỉnh qua **chạy thử của nhóm** trên điện thoại và laptop của thành viên. Vì không có dữ liệu công khai cho phép đo này, cổng **không nằm trong phần bảo đảm thống kê** — báo cáo ghi rõ điều đó.

**(d) TrustRouter — quyết định có bảo đảm thống kê**

*Khuôn mặt (bước 1):*
1. Điểm PAD và deepfake được **hiệu chỉnh** thành xác suất trên dữ liệu kiểm định tách theo người. Dữ liệu kiểm định được chia tiếp theo người thành hai phần không giao nhau: một phần để hiệu chỉnh và học trọng số hợp nhất, một phần **chỉ** để chọn ngưỡng — điều kiện để bảo đảm thống kê bên dưới hợp lệ.
2. **Hợp nhất** bằng hồi quy logistic có tính đến chất lượng ảnh.
3. **Cổng ngoài phạm vi** (nên có): mẫu quá khác dữ liệu đã kiểm thử → chuyển nhân viên.
4. So điểm với hai ngưỡng:
   - rõ là thật → **Cho qua** (tin cậy Cao);
   - rõ là giả → **Chuyển nhân viên** (tin cậy Thấp);
   - ở giữa → **mời đọc một câu tiếng Việt** (tin cậy Trung bình).

*Giọng nói (bước 2, chỉ khi cần):*
- **Câu đề bài:** câu tiếng Việt ngẫu nhiên 8–12 âm tiết, phủ đủ 6 thanh điệu, viết số bằng chữ.
- **Nhận dạng:** PhoWhisper nhận dạng câu đọc. **Không** đưa câu đề bài làm gợi ý cho ASR, vì như vậy ASR sẽ "đoán" ra đúng câu dù người dùng đọc sai.
- **So khớp hai lớp:**
  - lỗi âm tiết có dấu ≤ 0,3;
  - độ giống khi bỏ dấu ≥ 0,9.

  Lớp bỏ dấu giúp không bắt lỗi oan người nói giọng miền Trung, miền Nam. Cho thử lại một lần với câu mới.
- **Căn chỉnh chính câu đề bài theo thời gian** (`ctc-forced-aligner`) để phát hiện dấu hiệu cắt ghép: khoảng lặng giữa câu > 1 giây, âm tiết ngắn bất thường (< 60 ms) hoặc dài bất thường (> 1,2 s).
- **Kiểm tra giọng và môi:** bộ phát hiện giọng giả và SyncNet chỉ chạy trên đoạn đã căn chỉnh, để kiểm tra giọng thật và khớp môi.
- Rõ là thật → **Cho qua**; còn lại → **Chuyển nhân viên**.

*Bảo đảm thống kê bằng Learn-then-Test* (Angelopoulos et al., *Annals of Applied Statistics* 2025):
- Ngưỡng của **từng bước** được chọn trên phần kiểm định dành riêng cho việc chọn ngưỡng sao cho, với **mỗi loại tấn công đã biết** — ảnh in, phát lại, ghép mặt; từng hệ TTS — tỷ lệ bị **tự động cho qua** không vượt α, với xác suất ≥ 1 − δ. Trong các bộ ngưỡng thỏa điều kiện, chọn bộ ít phải chuyển nhân viên nhất.
- Kẻ tấn công chỉ lọt qua tự động khi (được cho qua ở bước 1) hoặc (lọt vào vùng giữa rồi được cho qua ở bước 2). Do đó **tỷ lệ lọt của cả quy trình ≤ α_mặt + α_giọng** (bất đẳng thức hợp).
- **Giới hạn nêu rõ:**
  - Dữ liệu công khai không có phiên nào chứa đồng thời mặt và giọng của cùng một người, nên bảo đảm được tính **cho từng bước**, rồi cộng lại theo bất đẳng thức hợp.
  - Bảo đảm chỉ đúng với các **loại tấn công đã biết** và dữ liệu tương tự dữ liệu kiểm định. Môi trường eKYC thật cần hiệu chỉnh lại trong pha thí điểm.

**(e) Hồ sơ bằng chứng và bàn duyệt**
- Câu hỏi kiểm chứng được thay cho "trông có giả không": "Da mặt có phản chiếu đúng chuỗi màu không?", "Câu nói có khớp đề không?", "Camera có phản hồi bình thường không?"
- **Nhân viên quyết định trước, sau đó mới xem điểm AI**, để tránh bị AI dẫn dắt.
- Bằng chứng vật lý đặt lên trước (biểu đồ phản chiếu màu, độ trễ, so khớp câu nói). Nhân viên phải chọn mã lý do khi kết luận.
- Nhật ký dạng chuỗi băm để phát hiện sửa xóa.

### 2.8 Trụ cột 3 — Chế độ giám định phục vụ điều tra

1. **Tiếp nhận:** điều tra viên tải lên video hoặc âm thanh (MP4, WebM, M4A…), kể cả file đã nén qua Zalo/Facebook. Hệ thống tính **mã kiểm tra (SHA-256) trên đúng các byte gốc, trước mọi bước chuyển mã**.
2. **Đo chất lượng file:** độ phân giải, bitrate, mức nén ước lượng (ffprobe). Thông số này đi vào báo cáo vì ảnh hưởng trực tiếp tới độ tin cậy.
3. **Quét nguồn gốc:**
   - dò thủy vân AI trong âm thanh bằng **AudioSeal** (Meta) và **Perth** (Resemble — công cụ clone giọng Chatterbox gắn thủy vân này vào mọi file nó tạo);
   - đọc chứng nhận nguồn gốc **C2PA** nếu có.

   Đây là **bằng chứng một chiều**: có thủy vân → "do AI tạo, công cụ X"; không có → "không có tín hiệu nguồn gốc", **không** có nghĩa là thật, vì thủy vân dễ bị xóa và nhiều công cụ không gắn.
4. **Chia đoạn:** cắt thành các đoạn 2–3 giây, chồng lấn 50%. Chạy bộ não trên từng đoạn (khuôn mặt, giọng nói, khớp môi–âm). Đoạn không có mặt, có nhiều mặt hoặc im lặng được đánh dấu **"không áp dụng"** thay vì cho điểm thấp.
5. **Biểu đồ theo thời gian:** mỗi tín hiệu một dải điểm. Đoạn nghi giả ghi thành **khoảng thời gian có biên ±1 giây**, vì ngay cả mô hình định vị tốt nhất hiện nay cũng không xác định ranh giới chính xác tới từng khung.
6. **Báo cáo giám định** (HTML và PDF), gồm:
   - **thông tin vật chứng và chuỗi lưu giữ:** tên file, mã kiểm tra, thông số kỹ thuật, nhật ký thao tác;
   - **hai giả thuyết** được so sánh: (Hp) đoạn X bị tạo hoặc chỉnh sửa bằng AI; (Hd) đoạn X là ghi hình thật, có thể đã bị nén lại;
   - **kết quả theo từng tín hiệu**, gồm tỷ số khả năng đã hiệu chỉnh và **mức độ bằng chứng bằng lời theo thang ENFSI** (2015), suy ra từ tỷ số khả năng chứ không từ xác suất thô;
   - kết quả quét nguồn gốc;
   - các khoảng nghi giả, kèm ảnh trích và phổ âm;
   - **giới hạn:** không có thử thách trực tiếp; hiệu quả giảm khi nén mạnh; "không phát hiện không có nghĩa là thật"; chỉ là công cụ hỗ trợ, không thay thế kết luận giám định tư pháp;
   - **chữ ký số Ed25519** trên nội dung báo cáo, kèm dấu vân tay khóa công khai, để phát hiện mọi chỉnh sửa về sau.

### 2.9 Kết quả sẽ trình bày

| # | Kết quả | Dữ liệu | Chỉ số |
|---|---|---|---|
| R1 | PAD trên người Việt: mô hình gốc so với sau tinh chỉnh | Zalo AI 2022 (phần giữ lại), Face_anti_spoofing | APCER, BPCER (ISO/IEC 30107-3) |
| R2 | Deepfake khuôn mặt: "khoảng cách Việt Nam" và ảnh hưởng của nén | RTFS-10k, WildDeepfake, deepfake người Việt tự tạo; 3 mức nén | AUC, EER theo mức nén |
| R3 | Giọng giả tiếng Việt theo vùng miền và trên hệ TTS chưa từng thấy | ViMD + MLAAD-vi; ViSpoofDB | EER theo Bắc / Trung / Nam; mô hình tiếng Anh so với sau tinh chỉnh |
| R4 | TrustRouter so với **một ngưỡng** và **hai ngưỡng có vùng xám**, ở **cùng tỷ lệ chuyển nhân viên** | Tập kiểm tra của R1–R3 | Tỷ lệ lọt, tỷ lệ chặn nhầm, tỷ lệ chuyển nhân viên; kiểm tra bảo đảm giữ trên tập giữ lại |
| R5 | ChromaPulse và CamProbe trong chạy thử | Nhóm tự thử: người thật, OBS phát video, tiện ích trình duyệt giả camera, Deep-Live-Cam (có và không hòa trộn Poisson) | Số lần đạt / không đạt theo tình huống; phân bố độ trễ của người thật so với ghép mặt (kết quả chạy thử, không phải tuyên bố thống kê) |
| R6 | Độ trễ | Toàn hệ thống | Thời gian từ khi quay xong đến khi có quyết định |

Mọi kết quả ghi rõ số mẫu, phiên bản mô hình và cấu hình để chạy lại được, không đặt chỉ tiêu trước (thể lệ Điều 7.3).

### 2.10 Tính mới và định vị trung thực

**Điểm mới nhóm tuyên bố:**
1. **Đo có hệ thống "khoảng cách dữ liệu Việt Nam"** của các bộ phát hiện deepfake khuôn mặt và giọng nói (người Việt, ba miền, ba mức nén) chỉ từ dữ liệu công khai, kèm mức cải thiện sau tinh chỉnh. Đây là câu trả lời định lượng cho nhận định "tối ưu cho dữ liệu nước ngoài" của đề.
2. **Lần đầu (theo khảo sát của nhóm)** áp dụng **Learn-then-Test** để có bảo đảm thống kê cho quyết định chống giả mạo sinh trắc học: bảo đảm theo từng loại tấn công, cho quy trình hai bước nhờ bất đẳng thức hợp. Các công trình gần nhất (CA-FAS 2024; Wang & Yamagishi, ICASSP 2022) chỉ từ chối theo độ tin cậy, không có bảo đảm.
3. **Tách "chụp lại" khỏi "chuyển nhân viên":** lỗi chất lượng không bị coi là dấu hiệu giả mạo.
4. **Một bộ não dùng chung cho cả eKYC tức thời lẫn giám định theo đoạn**, đúng yêu cầu kép của đề. Theo khảo sát khoảng 270 repo trên GitHub, chưa có hệ thống mã nguồn mở nào làm giám định theo đoạn cho video có cả hình lẫn tiếng.
5. **Đo độ trễ phản chiếu ánh sáng ngay trên trình duyệt điện thoại** để phân biệt người thật với ghép mặt thời gian thực. Nhóm không tìm thấy mã nguồn mở nào làm phần phân tích này; AWS cũng không công bố phần đó.

**Đã có người làm trước — nhóm trích dẫn, không nhận là của mình:**
- **Phản chiếu ánh sáng màn hình:** Face Flashing (NDSS 2018); Gerstner & Farid (CVPRW 2022); bằng sáng chế iProov US 9,479,500.
- **Câu ngẫu nhiên + khớp môi + nhận dạng tiếng nói:** bằng sáng chế Rakuten US 12,039,024; Tran et al., ĐH FPT (KSE 2022).
- **Phát hiện camera ảo bằng `applyConstraints`:** Kurmankhojayev et al. (2025).
- **Mã phát chuỗi màu phía trình duyệt:** AWS Amplify Liveness (Apache-2.0) — nhóm tái sử dụng có ghi nguồn.
- **Kỹ thuật phát hiện hàm trình duyệt bị can thiệp:** CreepJS (MIT).
- **Dò thủy vân âm thanh:** AudioSeal (Meta), Perth (Resemble).

---

## 3. CÔNG NGHỆ

### 3.1 Mô hình AI (đều có sẵn, chỉ tinh chỉnh lớp cuối)

| Chức năng | Mô hình | Giấy phép |
|---|---|---|
| Landmark khuôn mặt (trình duyệt) | MediaPipe Face Landmarker | Apache-2.0 |
| PAD | face-antispoof-onnx, MiniFASNet; DINOv2 | Apache-2.0 |
| Deepfake khuôn mặt | **GenD** (`GenD_CLIP_L_14`); SBI (dự phòng, heatmap) | MIT / chỉ nghiên cứu |
| Giọng giả | **NII AntiDeepfake** (`mms-300m-anti-deepfake`); công thức tăng cường của wedefense | Code BSD-3, trọng số CC BY-NC-SA / Apache-2.0 |
| Nhận dạng và căn chỉnh tiếng Việt | PhoWhisper (faster-whisper) + ctc-forced-aligner | BSD-3 / BSD-2 |
| Khớp môi–âm | SyncNet (`stable_syncnet` của LatentSync) | Apache-2.0 |
| Phát màu, khung oval (trình duyệt) | Mã từ AWS Amplify Liveness | Apache-2.0 (giữ NOTICE, ghi nguồn) |
| Phát hiện API bị can thiệp | Kỹ thuật từ CreepJS | MIT |
| Dò thủy vân, chứng nhận nguồn gốc | AudioSeal; Perth; c2pa-python | MIT / MIT / Apache-2.0 |
| Ký báo cáo | `cryptography` (Ed25519) | Apache/BSD |
| Ngưỡng có bảo đảm | **MAPIE** (có sẵn Learn-then-Test với hai ngưỡng) | BSD-3 |

*SBI và trọng số AntiDeepfake chỉ được dùng cho nghiên cứu, phi thương mại — phù hợp bản thi. Khi thương mại hóa: dùng GenD (MIT) cho khuôn mặt, và tự huấn luyện lại phần giọng nói trên mô hình nền có giấy phép mở.*

### 3.2 Hạ tầng (đơn giản cho bản demo)
- **Thành phần:** Next.js (web xác minh, bàn duyệt, cổng giám định) · FastAPI · PostgreSQL · lưu file tạm trên đĩa máy chủ, tự xóa theo hạn · Docker Compose.
- **Máy chạy:** một laptop/máy có GPU tại gian hàng, không phụ thuộc mạng. Huấn luyện trên Kaggle/Colab miễn phí và GPU thuê theo giờ.
- **Độ trễ dự kiến:** khoảng 1–2 giây với GPU, khoảng 3–4,5 giây chỉ với CPU.

### 3.3 Bảo mật và quyền riêng tư
- Người dùng chỉ nhận "đạt / chụp lại / chờ kiểm tra", **không bao giờ thấy điểm số**. Giới hạn số lượt thử.
- Ảnh và video tự xóa sau 24 giờ (ca đạt) hoặc 30 ngày (ca cần duyệt). Cơ sở dữ liệu chỉ giữ điểm số, mã kiểm tra và nhật ký.
- Nhân viên chỉ xem được ca được giao.

| Yêu cầu | Nguồn | Đáp ứng |
|---|---|---|
| Đồng ý rõ ràng; thông báo dữ liệu nhạy cảm | Luật 91/2025; NĐ 356/2025 | Màn hình đồng ý riêng, có lưu bản ghi |
| Lưu đúng mục đích, xóa khi hết mục đích | Luật 91/2025 | Tự xóa theo hạn |
| Con người giám sát; có nhật ký | Luật AI 134/2025, Điều 14 | Nhánh chuyển nhân viên; nhật ký chuỗi băm |
| Kiểm soát chèn luồng; bổ sung duyệt thủ công | NIST SP 800-63A-4 §3.14 | ChromaPulse, CamProbe; bàn duyệt |
| Đo theo ISO/IEC 30107-3 | DA940-02; TT 50/2024 sửa đổi bởi TT 77/2025 | Báo cáo APCER/BPCER |

### 3.4 So sánh với giải pháp hiện có

| Năng lực | iProov / Jumio / FaceTec | eKYC trong nước | VeriClue |
|---|---|---|---|
| Tối ưu và đánh giá cho dữ liệu Việt Nam | Không công bố | Không công bố | **Có, đo theo vùng miền và mức nén** |
| Phát hiện giọng giả tiếng Việt | Không | Không | **Có** |
| Giám định video cho điều tra | Không | Không | **Có** |
| Chống camera ảo | Có (đóng, SDK app) | Chưa thấy công bố | **Trên web, minh bạch** |
| Bảo đảm thống kê cho quyết định | Không công bố | Không công bố | **Có** |
| Tách "chụp lại" và "chuyển nhân viên" | Ngưỡng | Ngưỡng | **Có** |

*So sánh dựa trên tài liệu công khai.*

---

## 4. ĐỐI TƯỢNG SỬ DỤNG

### 4.1 Đơn vị triển khai
- **Ngân hàng, ví điện tử, công ty chứng khoán:** khi mở tài khoản, giao dịch > 10 triệu đồng, đổi thiết bị.
- **Nhà cung cấp eKYC đã có chứng nhận PAD** (VNPT, FPT, Viettel AI…): tích hợp như lớp bổ sung chống deepfake và chèn luồng.
- **Cơ quan điều tra, Bộ Tư lệnh 86:** chế độ giám định.

### 4.2 Người dùng trực tiếp

| Vai trò | Cần gì | VeriClue cung cấp |
|---|---|---|
| Người dân | Nhanh, không bị chặn oan | Dưới 60 giây; chụp lại có hướng dẫn thay vì bị từ chối |
| Nhân viên duyệt | Bằng chứng rõ ràng | Hồ sơ bằng chứng; tự quyết trước rồi mới xem điểm AI |
| Điều tra viên | Biết video có bị làm giả không, đoạn nào | Báo cáo giám định theo đoạn |
| Quản trị rủi ro | Kiểm soát tỷ lệ lọt và tỷ lệ chặn nhầm | Ngưỡng có bảo đảm; báo cáo theo loại tấn công |

### 4.3 Tác động
- **Bảo vệ người dân** trước lừa đảo bằng khuôn mặt và giọng nói giả, kể cả cuộc gọi video giả người thân (thông qua chế độ giám định).
- **Hỗ trợ điều tra** bằng công cụ giám định phù hợp dữ liệu Việt Nam.
- **Không bỏ rơi người dùng yếu thế:** máy rẻ, thiếu sáng, người cao tuổi được hướng dẫn chụp lại thay vì bị từ chối.
- **Làm chủ công nghệ:** mã nguồn tự chủ, triển khai on-premise.

### 4.4 Lộ trình sau cuộc thi

Triển khai qua ba pha; mỗi pha chỉ mở khi đạt chỉ số:
1. **Quan sát:** chạy song song hệ thống thật, không tác động quyết định; hiệu chỉnh lại ngưỡng trên dữ liệu thật.
2. **Hỗ trợ duyệt:** đưa hồ sơ bằng chứng cho nhân viên.
3. **Tự động có điều kiện:** chỉ tự động trong vùng đã được chứng nhận.

---

## 5. TÍNH KHẢ THI

### 5.1 Dữ liệu — chỉ dùng nguồn công khai

Chi tiết từng bộ (đường dẫn, giấy phép, cách tải): `docs/data/data-plan.md`.

| Mục đích | Dữ liệu | Người Việt? | Cách lấy |
|---|---|---|---|
| PAD | Zalo AI 2022 Liveness; Face_anti_spoofing; CelebA-Spoof | Có (2 bộ đầu) | Tải ngay |
| Deepfake khuôn mặt | RTFS-10k; WildDeepfake | Không | Tải ngay |
| Giọng giả | MLAAD `fake/vi`; ViSpoofDB; VSASV | Có | Tải ngay |
| Giọng thật theo vùng miền | ViMD (63 tỉnh); VIVOS | Có | Tải ngay |
| Video người Việt nói / ảnh người Việt | ViCocktail; Vietnamese Celebrity Faces | Có | Tải ngay |
| Khớp môi–âm | LAV-DF | Không | Đồng ý điều khoản trên HF |

**Dữ liệu tự tạo từ nguồn công khai** (lấp khoảng trống chưa có bộ công khai nào):
- **Deepfake khuôn mặt người Việt:** ghép mặt từ bộ ảnh công khai vào video ViCocktail (FaceFusion).
- **Video nghe–nhìn giả tiếng Việt:** lip-sync giọng giả MLAAD-vi lên video ViCocktail (Wav2Lip).
- **Video nén kiểu mạng xã hội:** nén lại bằng ffmpeg (H.264 CRF 28–40, 480p; âm thanh Opus/AMR 8 kHz).

Dữ liệu tự tạo chỉ dùng nội bộ, không phát tán, và được ghi rõ trong báo cáo là dữ liệu tổng hợp.

**Chạy thử của nhóm:** ChromaPulse và CamProbe được chỉnh ngưỡng bằng cách 5 thành viên tự thử trên điện thoại và laptop của mình, khoảng 10–15 phút. Đây là kiểm thử phần mềm, không phải thu dữ liệu.

### 5.2 Kế hoạch (hạn nộp trước 06/11/2026)

> Kế hoạch chi tiết, **là nguồn sự thật**: `docs/plan/roadmap.md` (lịch theo ngày, đường găng, cổng quyết định) và `docs/plan/backlog.md` (56 task). Bảng dưới chỉ là tóm tắt.

| Giai đoạn | Ngày | Việc chính |
|---|---|---|
| **Sprint 0** | 15–17/10 | Dựng khung web + API + mô-đun giả lập chạy đầu–cuối; tải dữ liệu và mô hình; thử nhanh ChromaPulse trên 3 máy thật. **Chốt mức độ dùng ChromaPulse** |
| **Sprint 1** | 18–25/10 | Luồng web eKYC đầy đủ (chất lượng, ChromaPulse, CamProbe, gửi media); PAD + GenD; kết quả gốc R1–R3; TrustRouter (ngưỡng tạm); API bàn duyệt; tạo dữ liệu giả tiếng Việt; bắt đầu tinh chỉnh AntiDeepfake |
| **Sprint 2** | 26/10–01/11 | SBI; tinh chỉnh GenD; bước giọng nói (kiểm tra câu đọc, căn chỉnh, giọng giả, SyncNet); Learn-then-Test (MAPIE); chế độ giám định (chia đoạn, quét nguồn gốc, báo cáo ENFSI có chữ ký); giao diện bàn duyệt và giám định; kiểm thử đầu–cuối; chạy thử ChromaPulse cả nhóm (R5) |
| **Sprint 3** | 02–04/11 | Đóng băng tính năng; R4, R6 (R7 nếu kịp); tập 7 kịch bản demo; quay video; viết báo cáo |
| **Dự phòng** | 05/11 | Kiểm tra trên máy sạch, **nộp** |

**Khối lượng:**
- Khoảng **60 ngày công**, chia thành 56 task (53 bắt buộc).
- Quỹ thời gian: 22 ngày × 5 người × 50–70% ≈ **55–77 ngày công**.
- Tải từng người theo từng sprint được kiểm tra tự động bằng `scripts/plan_check.py`: không ai vượt 70% sức chứa ở bất kỳ sprint nào. Sprint 1 là sprint căng nhất.

**Phân công** (chi tiết: `docs/context/team.md`):

| Thành viên | Phụ trách |
|---|---|
| M1 | Web xác minh: hướng dẫn chụp, cổng chất lượng, ChromaPulse (chép từ AWS Amplify, đo thời điểm) và CamProbe phía trình duyệt; kiểm thử đầu–cuối |
| M2 | Bàn duyệt và cổng giám định (giao diện + API bàn duyệt), báo cáo ENFSI, bảo mật phiên, CI, máy red-team, kịch bản demo, báo cáo nộp |
| M3 | AI khuôn mặt: PAD, GenD, SBI; phân tích phản chiếu và độ trễ ChromaPulse; quét thủy vân |
| M4 | AI giọng nói: tinh chỉnh AntiDeepfake, kiểm tra câu đọc, SyncNet, kết quả theo vùng miền; đánh giá chế độ giám định |
| M5 | API, hạ tầng, TrustRouter + Learn-then-Test (MAPIE), chia đoạn cho giám định, khung đánh giá R1–R6 |

### 5.3 Phạm vi

| Mức | Hạng mục |
|---|---|
| **BẮT BUỘC** | Web eKYC đầu–cuối · cổng chất lượng + chụp lại · ChromaPulse có đo độ trễ tuyệt đối · CamProbe có kiểm tra API bị can thiệp · PAD + GenD/SBI · AntiDeepfake tiếng Việt + kiểm tra câu đọc có căn chỉnh · TrustRouter có Learn-then-Test · bàn duyệt + hồ sơ bằng chứng · chế độ giám định theo đoạn + quét thủy vân + báo cáo ENFSI có chữ ký · kết quả R1–R4, R6 |
| **NÊN CÓ** | Cổng ngoài phạm vi · R5 đầy đủ trên nhiều thiết bị · đọc chứng nhận C2PA · xuất báo cáo PDF (ngoài bản HTML) |

**Tiêu chí hoàn thành:**
1. Đi hết một phiên eKYC trên điện thoại thật, có quyết định trong ≤ 5 giây.
2. Bảy kịch bản demo chạy ổn định.
3. Nhân viên mở được hồ sơ và ghi quyết định kèm mã lý do.
4. Chế độ giám định nhận file nén và xuất báo cáo có biểu đồ theo đoạn.
5. Có báo cáo kết quả R1–R4 và R6, kèm số mẫu và cấu hình để chạy lại.

### 5.4 Ngân sách

| Hạng mục | Ước tính |
|---|---|
| GPU thuê theo giờ | khoảng 40–60 USD |
| Ổ cứng lưu dữ liệu (khoảng 150 GB) | dùng thiết bị sẵn có |
| Huấn luyện | Kaggle / Colab miễn phí |

### 5.5 Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| ChromaPulse yếu trên điện thoại thật | Thử ở Sprint 0. Nếu yếu: hạ thành tín hiệu phụ, CamProbe và deepfake gánh phần chống chèn luồng |
| Bộ phát hiện giọng giả chỉ đạt mức khá trên tiếng Việt | Báo cáo trung thực theo vùng miền và hệ TTS; không dùng giọng nói làm căn cứ duy nhất |
| Dữ liệu công khai khác môi trường eKYC thật | Ghi rõ trong báo cáo; hiệu chỉnh lại ở pha thí điểm |
| Nén mạnh làm giảm hiệu quả giám định | Tăng cường nén khi huấn luyện; báo cáo theo mức nén; nêu giới hạn trong báo cáo giám định |
| Thời gian | Phân mức BẮT BUỘC / NÊN CÓ; tích hợp từ ngày đầu bằng mô-đun giả lập |
| Công cụ giả camera tiến hóa, vá được dấu hiệu bị can thiệp | Coi kiểm tra API chỉ là một lớp; ChromaPulse và thăm dò hành vi camera là các lớp độc lập |
| Mô hình nền chỉ cho dùng phi thương mại (SBI, AntiDeepfake) | Phù hợp bản thi; ghi rõ trong bảng giấy phép; có phương án thay thế khi thương mại hóa (mục 3.1) |
| Sự cố khi demo | Chạy local; có video dự phòng |

### 5.6 Hướng phát triển (ngoài phạm vi bản thi)

Chi tiết trong bản 2 (`docs/proposal/archive/proposal-v2-full.md`):
- **Ring Radar** — phát hiện đường dây tài khoản bằng liên kết chéo giữa các phiên.
- **Bảo đảm thống kê cho cả phiên** khi có dữ liệu eKYC thật (mặt và giọng trong cùng phiên).
- **MotionLock**, kiểm tra khép môi theo âm m/b/p, chọn thử thách thích ứng.
- **SDK cho app native** kèm kiểm tra toàn vẹn thiết bị.
- **Giám sát trôi dữ liệu và học liên tục.**
- **Dịch vụ kiểm tra cuộc gọi nghi giả mạo** cho người dân.
- **Bàn duyệt 3 bước:** duyệt mù → mở kết quả AI → nếu bất đồng thì nêu lý do và chuyển người thứ hai; chèn ca chuẩn để đo chất lượng duyệt.
- **Kiểm tra tỷ lệ phản chiếu giữa các vùng mặt:** mặt thật lồi lõm nên phản chiếu không đều; màn hình phẳng thì đều.
- **Hồ sơ nén Zalo/Messenger:** gửi rồi tải lại video qua các app để ước lượng thông số nén thật, dùng cho tăng cường dữ liệu và đánh giá.
- **Agent hỗ trợ viết báo cáo giám định:** LLM chạy cục bộ chỉ viết diễn giải, mọi nhận định phải trích dẫn kết quả công cụ; không ra quyết định.

### 5.7 Đạo đức và giới hạn
- Không thu dữ liệu sinh trắc học của người ngoài. Tấn công trong demo chỉ dùng khuôn mặt và giọng của thành viên nhóm, có đồng ý.
- Deepfake tự tạo từ dữ liệu công khai chỉ dùng nội bộ, không phát tán, xóa sau dự án.
- Ứng dụng web **không chứng thực được** camera và thiết bị. VeriClue **tăng chi phí tấn công**, không tuyên bố miễn nhiễm.
- Bảo đảm thống kê chỉ đúng với loại tấn công đã biết và dữ liệu tương tự dữ liệu kiểm định.
- Ghép mặt thời gian thực có chỉnh màu (T6) là điểm yếu lớn nhất, sẽ được báo cáo riêng.
- Báo cáo giám định là công cụ hỗ trợ, không thay thế giám định tư pháp.

---

## 6. TÀI LIỆU THAM KHẢO (chọn lọc)

Danh mục đầy đủ có đường dẫn: `docs/research/sources.md`.

**Chuẩn và pháp lý**
1. NIST SP 800-63A-4 (2025), §3.11, §3.14.
2. ETSI TS 119 461 V2.1.1 (2025); CEN/TS 18099:2024.
3. ISO/IEC 30107-3:2023.
4. TT 50/2024/TT-NHNN, sửa đổi bởi TT 77/2025/TT-NHNN; QĐ 2345/QĐ-NHNN.
5. Luật 91/2025/QH15; NĐ 356/2025/NĐ-CP; Luật 134/2025/QH15.

**Phương pháp**

6. Angelopoulos et al. *Learn then Test*. Annals of Applied Statistics, 2025.
7. Tang et al. *Face Flashing*. NDSS 2018.
8. Gerstner & Farid. CVPRW 2022.
9. Kurmankhojayev et al. arXiv 2512.10653, 2025.
10. *GenD* — generalizable deepfake detector. WACV 2026, arXiv 2508.06248. github.com/yermandy/GenD
11. Shiohara & Yamasaki. *Self-Blended Images*. CVPR 2022.
11a. NII Yamagishi Lab. *AntiDeepfake* post-trained SSL models. github.com/nii-yamagishilab/AntiDeepfake
11b. Mittal et al. *GOTCHA*. EuroS&P 2024.
11c. San Roman et al. *AudioSeal*. ICML 2024. Resemble AI, *Perth*.
11d. ENFSI Guideline for Evaluative Reporting in Forensic Science, 2015.
11e. AWS Amplify UI — FaceLivenessDetector (Apache-2.0); CreepJS (MIT); MAPIE (BSD-3).
12. PhoWhisper. arXiv 2406.02555.
13. Chung & Zisserman. *SyncNet*. 2016.

**Bối cảnh dữ liệu và con người**

14. Chandra et al. *Deepfake-Eval-2024*. arXiv 2503.02857.
15. VietPrism. arXiv 2609.30005.
16. Diel et al. CHB Reports, 2024.
17. Tran et al. KSE 2022.

**Dữ liệu**

18. Zalo AI Challenge 2022.
19. RTFS-10k.
20. WildDeepfake.
21. MLAAD.
22. ViSpoofDB.
23. VSASV.
24. ViMD (EMNLP 2024).
25. ViCocktail (arXiv 2506.04635).
26. CelebA-Spoof (ECCV 2020).

---

## PHỤ LỤC A — Đặc tả ChromaPulse

**Trình tự phát màu:**
1. Nền xám #d1d1d1 trong 1 giây.
2. 8 đoạn màu ngẫu nhiên từ {#ffcc73, #73d9ff, #ffb3eb, #80e09e}; hai đoạn liền nhau khác màu; mỗi đoạn giữ màu 400–650 ms rồi chuyển màu mượt trong 150 ms (mỗi bước ≥ 550 ms; tổng khoảng 4,4–6,4 giây).
3. Nền xám trong 0,5 giây.

**An toàn:**
- Chênh độ chói giữa các màu ≤ 0,064.
- Không dùng đỏ bão hòa.
- Tối đa 2,5 lần đổi màu/giây.
- Có cảnh báo trước khi phát và lựa chọn bỏ qua; người chọn bỏ qua chuyển sang bước đọc câu.

**Thiết lập khi chạy:**
- Giữ màn hình sáng (wake lock), nhắc tăng độ sáng.
- Khoảng cách 25–40 cm.

**Dữ liệu đo:**
- Thời điểm vẽ từng màu (`requestAnimationFrame`).
- Thời điểm camera chụp từng khung (`requestVideoFrameCallback` → `captureTime`), cùng đồng hồ `performance.now()`.
- Màu trung vị của 5 vùng da (loại điểm ảnh quá tối hoặc cháy sáng) và vùng nền.
- Server tính lại từ video để đối chiếu với số liệu trình duyệt gửi lên. Không tin hoàn toàn dữ liệu phía client.

**Quyết định** (ngưỡng khởi điểm, chỉnh lại qua chạy thử):

| Kết quả | Điều kiện |
|---|---|
| **Đạt** | Mức khớp R² đủ cao; giải mã đúng ≥ 7/8 màu; độ trễ τ trong phân vị 99 của người thật trên cùng loại điện thoại |
| **Không đạt** | Không phản chiếu, hoặc τ vượt khoảng của người thật (ghép mặt thời gian thực thường trễ thêm ≥ 1–2 khung) |
| **Chưa rõ** | Biên độ phản chiếu quá thấp |

## PHỤ LỤC B — Định dạng đầu ra mô-đun

```json
{
  "module": "voice_spoof",
  "model_version": "1.0.0",
  "session_id": "…",
  "status": "ok | degraded | error",
  "score": 0.12,
  "calibrated_prob_attack": 0.08,
  "quality": {"snr_db": 18.5, "duration_s": 3.9},
  "evidence": [{"type": "timeseries", "name": "segment_scores", "uri": "…"}],
  "latency_ms": 420
}
```

## PHỤ LỤC C — Cỡ mẫu cho bảo đảm thống kê

Khi không có lỗi nào, số mẫu tối thiểu là n_min = ⌈ln δ / ln(1 − α)⌉:

| α \ δ | 0,10 | 0,05 |
|---|---|---|
| 5% | 45 | 59 |
| 1% | 230 | 299 |

Dữ liệu công khai có hàng nghìn mẫu cho mỗi loại tấn công (ví dụ RTFS-10k có 9.772 video ghép mặt; MLAAD-vi có ≥ 1.000 clip cho mỗi hệ TTS). Vì vậy nhóm có thể đặt mục tiêu **α = 1–5%** cho từng loại tấn công.

## PHỤ LỤC D — Việc cần xác minh

1. Danh sách đầu ra phải nộp ở vòng 2 (hỏi BTC).
2. Có được nêu Đề 62 và DA940-02 là đề liên quan không.
3. Điều khoản gốc của Zalo AI 2022 về việc dùng dữ liệu.
4. Văn bản gốc TT 77/2025, Luật 91/2025, NĐ 356/2025.
5. Tra lại Google Scholar cho tuyên bố tính mới số 2 ngay trước khi nộp.
