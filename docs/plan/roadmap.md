# Roadmap triển khai VeriClue — Vòng 2 (15/10 → 05/11/2026)

> **Hạn chót nộp:** trước **06/11/2026**. Hôm nay: 14/10 (thứ Tư).
> **Bảng task:** `backlog.md`. **Chi tiết task:** `epics/`.
> **Số liệu tải và đường găng** do `uv run python scripts/plan_check.py` tính từ backlog. Mỗi khi backlog thay đổi, chạy lại lệnh này (CI cũng tự chạy).

## 1. Mốc và tiêu chí đạt mốc

| Mốc | Ngày | Phải đạt (kiểm tra ở buổi demo nội bộ cuối sprint) |
|---|---|---|
| **M0 — Khung chạy được** | Thứ Bảy 17/10 | • `setup` chạy được trên máy mọi thành viên<br>• web → API → mock → kết quả đi hết luồng<br>• CI xanh<br>• dữ liệu và mô hình tải được<br>• **cổng quyết định ChromaPulse đã chốt** (PRES-01) |
| **M1 — Hình ảnh chạy thật** | Chủ Nhật 25/10 | • phiên eKYC trên điện thoại thật với PAD + GenD + ChromaPulse + CamProbe thật<br>• TrustRouter (ngưỡng tạm)<br>• API và giao diện bàn duyệt cơ bản<br>• có R1, R2, R3 "trước tinh chỉnh" |
| **M2 — Đủ tính năng** | Chủ Nhật 01/11 | • bước giọng nói chạy<br>• SBI + heatmap<br>• chế độ giám định có báo cáo ký số và quét thủy vân<br>• ngưỡng Learn-then-Test đã khóa<br>• R1–R3 "sau tinh chỉnh"<br>• R5<br>• kiểm thử đầu–cuối trong CI |
| **M3 — Đóng băng** | Thứ Tư 04/11 | • không thêm tính năng<br>• R4, R6 (R7 nếu kịp) xong<br>• video demo xong<br>• báo cáo nộp xong bản nháp<br>• tập dượt 2 lần |
| **Nộp** | Thứ Năm 05/11 | Kiểm tra trên máy sạch, gắn tag `v1.0-vong2`, gửi bài |

## 2. Đường găng

Kết quả `plan_check.py` ngày 14/10 — các chuỗi dài nhất (đơn vị: ngày công):

| Chuỗi | Độ dài | Ý nghĩa |
|---|---|---|
| PLAT-01 → PLAT-03 → PLAT-04 → CAP-01 → CAP-02 → CAP-05 → CAP-06 → PLAT-09 → DEMO-01 → DEMO-02 → DEMO-04 | **10** | Web thu nhận là chuỗi dài nhất. **M1 không được trễ** |
| PLAT-01 → PLAT-03 → PLAT-04 → PLAT-05 → PLAT-08 → ROUT-02 → ROUT-03 → ROUT-05 → DEMO-03 | 9,5 | Nền tảng → TrustRouter → đánh giá |
| PLAT-01 → … → CAP-06 → CAP-07 → CAP-08 | 8,5 | Web thu nhận đến màn hình đọc câu |

**Hệ quả quản lý:**
1. **Dự án có 3 chuỗi gần găng chạy song song.** Trễ ở chuỗi nào cũng nguy hiểm.
2. **PLAT-03 và PLAT-04 nằm ở đầu cả 3 chuỗi.** M5 phải xong trước tối 16/10 và 17/10.
3. **Các task mô hình** (FACE-04, VOICE-03) không nằm trên đường găng theo ngày công, nhưng **rủi ro kỹ thuật cao nhất**. ROUT-03 chạy trước trên điểm của mô hình gốc để không bị chặn.

## 3. Lịch theo ngày và vai trò

Tải ở mức 70% thời gian (số liệu từ `plan_check.py`):

| Vai trò | S0 (≤ 2,1) | S1 (≤ 5,6) | S2 (≤ 4,9) | S3 (≤ 2,1) | Tổng |
|---|---|---|---|---|---|
| M1 | 2,0 | 5,5 | 3,0 | 1,0 | 11,5 |
| M2 | 1,0 | 5,5 | 4,0 | 2,0 | 12,5 |
| M3 | 2,0 | 5,0 | 4,5 | 0 | 11,5 |
| M4 | 1,0 | 4,2 | 3,8 | 1,0 | 10,0 |
| M5 | 2,0 | 5,5 | 4,0 | 1,5 (+0,5 DP) | 13,5 |

**S1 là sprint căng nhất:** 4/5 người ở mức 5–5,5 trên sức chứa 5,6.

### S0 — Nền móng (Thứ Năm 15/10 → Thứ Bảy 17/10)

| Ngày | M1 Web | M2 Duyệt / bảo mật | M3 Khuôn mặt | M4 Giọng nói | M5 Nền tảng |
|---|---|---|---|---|---|
| **15/10** | PLAT-02 | Tạo repo GitHub, gửi yêu cầu dữ liệu cần duyệt, hỏi BTC (Q1, Q2); DATA-02 | DATA-01 (ảnh) | DATA-01 (âm thanh) | **PLAT-03** |
| **16/10** | CAP-03 (trang thử) | PLAT-07 (CI, CODEOWNERS, ghim repo phụ) | DATA-01; đọc code GenD; FACE-01 phần bọc mô hình | VOICE-01 phần bọc mô hình | **PLAT-04** |
| **17/10** | CAP-03 thu dữ liệu 3 máy; CAP-01 | Chuẩn bị máy red-team | **PRES-01** (chốt ChromaPulse) | VOICE-01 | PLAT-04 xong; **demo M0** |

### S1 — Hình ảnh chạy thật (Chủ Nhật 18/10 → Chủ Nhật 25/10)

| Vai trò | Việc theo thứ tự |
|---|---|
| M1 | CAP-01 → CAP-02 → CAP-04 → CAP-05 → CAP-06 |
| M2 | REDT-01 → DATA-04 → PLAT-06 → REV-01 → REV-02 (bắt đầu) |
| M3 | DATA-03 (ảnh) → FACE-01 (sinh R1 gốc) → FACE-02 → PRES-02 → PRES-03 |
| M4 | DATA-03 (âm thanh) → VOICE-01 (sinh R3 gốc) → DATA-05 → VOICE-02 → VOICE-04 → VOICE-03 (bắt đầu) |
| M5 | **EVAL-01 (ngày 18–19, vì R1/R2/R3 gốc cần)** → PLAT-05 → PLAT-08 → ROUT-01 → ROUT-02 |

- **21/10:** buổi tích hợp lần 1 (web thật + API thật + PAD/GenD thật).
- **25/10:** demo M1.

### S2 — Đủ tính năng (Thứ Hai 26/10 → Chủ Nhật 01/11)

| Vai trò | Việc theo thứ tự |
|---|---|
| M1 | CAP-07 → PLAT-09 → PRES-04 (chạy thử cả nhóm) |
| M2 | REV-02 → FOR-02 → FOR-04 |
| M3 | FACE-03 → FACE-04 → FOR-03 → FACE-05 (P1) |
| M4 | VOICE-03 → VOICE-04 (xong) → VOICE-05 → VOICE-06 |
| M5 | ROUT-03 (chạy trước trên điểm gốc) → FOR-01 → ROUT-04 (P1) → ROUT-03 chạy lại với mô hình đã tinh chỉnh |

- **29/10:** buổi tích hợp lần 2.
- **01/11:** demo M2.

### S3 — Đóng băng và hoàn thiện (Thứ Hai 02/11 → Thứ Tư 04/11)

| Vai trò | Việc |
|---|---|
| M1 | CAP-08 (P1), DEMO-02 (video) |
| M2 | DEMO-01, chủ trì DEMO-03 |
| M3 | Viết phần khuôn mặt cho DEMO-03 |
| M4 | EVAL-03 (P1, R7); viết phần giọng nói và giám định |
| M5 | ROUT-05 (R4), EVAL-02 (R6); viết phần TrustRouter |

- **02/11:** từ hôm nay **chỉ sửa lỗi**.
- **04/11:** tập dượt 2 lần.

### Dự phòng — Thứ Năm 05/11

DEMO-04, nộp bài. Không làm việc mới.

## 4. Cổng quyết định (đi tiếp hay đổi hướng)

| Ngày | Câu hỏi | Nếu KHÔNG đạt |
|---|---|---|
| 17/10 (PRES-01) | Người thật có R² ≥ 0,5 trên ≥ 2/3 máy? | ChromaPulse hạ xuống tín hiệu phụ; CamProbe và deepfake gánh phần chống chèn luồng. Sửa proposal §2.7(c) |
| 21/10 | Web + API + mô hình thật chạy cùng nhau? | Dồn M2, M5 vào sửa tích hợp; lùi REV-02 |
| 25/10 | GenD trên deepfake người Việt có AUC ≥ 0,7? | Dùng SBI làm chính; ghi kết quả thật vào báo cáo |
| 29/10 | Bước giọng nói chạy đầu–cuối? | Giữ giọng nói ở chế độ giám định, tạm bỏ khỏi luồng eKYC |
| 01/11 | Đủ mẫu cho Learn-then-Test với α = 5%? | Báo cáo α thực tế đạt được |

## 5. Nếu bị trễ: thứ tự cắt bớt

Cắt từ trên xuống. Đổi trạng thái thành `cut`, ghi lý do vào STATUS.md, chạy lại `plan_check.py`.

1. EVAL-03 (R7) — chỉ trình bày giám định bằng demo
2. ROUT-04 (cổng ngoài phạm vi)
3. FACE-05 (tối ưu tốc độ) — chấp nhận chạy chậm hơn trên máy demo
4. CAP-08 (thử nhiều máy) — chỉ thử 2 máy
5. FOR-04: bỏ xuất PDF, chỉ giữ HTML có chữ ký
6. FOR-03: chỉ giữ Perth, bỏ C2PA
7. FACE-03: SBI không có heatmap
8. VOICE-05: bỏ SyncNet, giữ căn chỉnh câu
9. PLAT-09: chỉ giữ kiểm thử mức API, bỏ Playwright

**Không bao giờ cắt:**
- luồng eKYC hình ảnh;
- ChromaPulse/CamProbe ở mức tối thiểu;
- GenD;
- bộ phát hiện giọng giả;
- TrustRouter;
- chế độ giám định theo đoạn;
- kết quả R1–R4.

## 6. Nghi thức nhóm

Chi tiết: `docs/context/team.md` §3–§4.

| Khi nào | Việc | Thời lượng |
|---|---|---|
| Mỗi ngày, 21:00 | **Họp nhanh:** hôm qua / hôm nay / vướng gì. Trưởng nhóm cập nhật `STATUS.md` | 15 phút |
| 21/10, 29/10 | **Buổi tích hợp:** ghép code mọi người, sửa lỗi ghép nối | 2 giờ |
| 17/10, 25/10, 01/11 | **Demo nội bộ cuối sprint** theo tiêu chí mốc; ghi `docs/status/sprints/` | 1 giờ |
| Mỗi PR | Ít nhất 1 người khác duyệt trong vòng 12 giờ | — |
| Cuối mỗi phiên làm việc | Tạo file bàn giao (`scripts/new_handoff.py`) | 5 phút |

## 7. Rủi ro chính và người theo dõi

| Rủi ro | Dấu hiệu sớm | Người theo dõi | Ứng phó |
|---|---|---|---|
| ChromaPulse yếu trên điện thoại | R² thấp ở PRES-01 | M3 | Cổng quyết định 17/10 |
| PLAT-03/04 trễ → chặn cả 3 chuỗi găng | Chưa có `/healthz` tối 15/10 | Trưởng nhóm | Ưu tiên tuyệt đối; M1 hỗ trợ phần sinh type |
| Tích hợp vỡ muộn | Buổi 21/10 không chạy được | M5 | Mock từ đầu; kiểm thử đầu–cuối PLAT-09 |
| S1 căng (4/5 người gần 100% sức chứa) | Trễ > 1 ngày ở giữa sprint | Trưởng nhóm | Cắt theo §5; mượn người từ vai trò còn sức (M4 ở S1) |
| GPU không đủ để tinh chỉnh | Kaggle/Colab hết quota | M3, M4 | Thuê GPU theo giờ (40–60 USD); giảm kích thước dữ liệu |
| Bộ dữ liệu chờ duyệt không về kịp | Chưa có phản hồi sau 3 ngày | M2 | Kế hoạch không phụ thuộc chúng |
| AI làm sai thiết kế | PR lệch kiến trúc hoặc hợp đồng | Người review | AGENTS.md, task card, `/review-pr`, CI |
