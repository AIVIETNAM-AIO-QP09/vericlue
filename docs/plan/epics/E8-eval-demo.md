# E8 — Red-team, đánh giá, demo và nộp bài (REDT, EVAL, DEMO)

> Mục tiêu epic: có số liệu thật, trung thực, chạy lại được (R1–R6), một buổi demo trơn tru và gói nộp đầy đủ trước 06/11.

---

### REDT-01 · Dựng máy red-team và bộ kịch bản tấn công

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (+M3, M4) | 1 | S1 | P0 | — |

**Mục tiêu:** một máy riêng có đủ công cụ tấn công, dùng để tạo dữ liệu tổng hợp và thử hệ thống của nhóm.
**Đọc trước:** `docs/runbooks/red-team.md`, AGENTS.md §6 luật 11.

**Đầu ra:**
- Máy red-team cài:
  - **camera ảo:** OBS + Virtual Camera;
  - **ghép mặt:** Deep-Live-Cam, FaceFusion;
  - **clone giọng tiếng Việt:** VieNeu-TTS;
  - **tạo giọng có thủy vân:** Chatterbox;
  - **lip-sync:** Wav2Lip;
  - một tiện ích Chrome giả camera (cài thủ công, chỉ trên máy này).
- `docs/runbooks/red-team.md` ghi cách chạy từng kịch bản và các tham số đã dùng.

**Tiêu chí hoàn thành:**
- [ ] Chạy được đủ 7 kịch bản trong proposal §1.4.
- [ ] Không có file của công cụ nào trong repo.

---

### EVAL-01 · Khung đánh giá chung

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S1 | P0 | PLAT-03 |

**Mục tiêu:** mọi người tính chỉ số theo **cùng một cách**.
**Làm vào đầu S1**, vì các kết quả gốc (FACE-01, FACE-02, VOICE-01) cần dùng.

**Đầu ra:** `ml/src/vericlue_ml/eval/metrics.py`, `report.py`.
- **Chỉ số:**
  - APCER theo từng loại tấn công, APCER max, BPCER, BPCER@APCER 5% (ISO/IEC 30107-3);
  - EER, AUC;
  - ECE.
- **Khoảng tin cậy 95%:** bootstrap theo người.
- **Clopper–Pearson** cho tỷ lệ nhỏ.
- **Bảng Markdown** tự sinh, kèm commit, phiên bản mô hình, bộ dữ liệu, số mẫu.

**Tiêu chí hoàn thành:**
- [ ] Test với dữ liệu tổng hợp có đáp án biết trước.
- [ ] R1–R4 đều được sinh bằng khung này.

---

### EVAL-02 · Đo độ trễ (R6)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 0,5 | S3 | P0 | PLAT-08, VOICE-06 |

**Đầu ra:** `docs/status/results/R6.md` — p50, p95 của từng bước và tổng thời gian từ lúc quay xong tới khi có quyết định, trên máy demo (GPU) và CPU.

**Tiêu chí hoàn thành:**
- [ ] Đo ≥ 30 phiên.
- [ ] Tổng p95 ≤ 5 giây trên máy demo. Nếu không đạt, ghi lý do và cách giảm.

---

### EVAL-03 · Đánh giá chế độ giám định theo đoạn (R7)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 1 | S3 | P1 | FOR-01, DATA-04, EVAL-01 |

**Mục tiêu:** có số liệu cho **nửa "giám định"** của đề BTL86-16. Kế hoạch R1–R6 trước đây chưa đo chế độ này.

**Đầu ra:**
- **Bộ thử "giả một phần":** ghép đoạn deepfake người Việt (DATA-04) vào giữa video thật, biết trước vị trí; làm ở 3 mức nén (DATA-05).
- **Chỉ số:**
  - tỷ lệ phát hiện đúng video có chứa đoạn giả;
  - độ trùng (IoU) giữa khoảng hệ thống báo và khoảng giả thật, có tính biên ±1 giây;
  - tỷ lệ báo nhầm trên video thật hoàn toàn.
- Lưu ở `docs/status/results/R7.md`.

**Tiêu chí hoàn thành:**
- [ ] ≥ 50 video thử, có số mẫu và khoảng tin cậy.
- [ ] Thêm dòng R7 vào proposal §2.9 (qua DEMO-03).

---

### DEMO-01 · Kịch bản demo 7 tình huống

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 1 | S3 | P0 | PLAT-09, CAP-07, REV-02, FOR-02, FOR-04, VOICE-06, PRES-04 |

**Đầu ra:** `docs/runbooks/demo-day.md`:
- lời thoại từng tình huống;
- ai làm gì;
- thiết bị cần mang;
- dữ liệu mẫu nạp sẵn;
- checklist trước giờ demo;
- phương án khi lỗi (chuyển sang video dự phòng).

**Tiêu chí hoàn thành:**
- [ ] Tập dượt trọn 2 lần.
- [ ] Mỗi tình huống ≤ 3 phút.
- [ ] Chạy hoàn toàn offline trên máy demo.

---

### DEMO-02 · Video demo và video dự phòng

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 (+cả nhóm) | 0,5 | S3 | P0 | DEMO-01 |

**Tiêu chí hoàn thành:**
- [ ] Video 3–5 phút đi qua 7 tình huống, có phụ đề tiếng Việt.
- [ ] Bản dự phòng cho từng tình huống.
- [ ] Không có khuôn mặt người ngoài nhóm.

---

### DEMO-03 · Báo cáo nộp vòng 2

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (+cả nhóm) | 1 | S3 | P0 | ROUT-05, EVAL-02, FACE-04, VOICE-03, PRES-04 |

**Phân công viết:**

| Người | Phần |
|---|---|
| M3 | Khuôn mặt và hiện diện |
| M4 | Giọng nói và giám định |
| M5 | TrustRouter và độ trễ |
| M1 | Trải nghiệm người dùng |
| M2 | Ghép, biên tập, kiểm tra số liệu |

**Mục tiêu:** tài liệu nộp ban tổ chức, theo danh sách đầu ra BTC yêu cầu (**cần hỏi BTC — câu hỏi mở**).

**Đầu ra:**
- Cập nhật `docs/proposal/proposal.md` bằng **số liệu thật** từ R1–R6.
- Mục giới hạn và giấy phép.
- Slide nếu cần.

**Tiêu chí hoàn thành:**
- [ ] Mọi con số đều trỏ được về file kết quả có commit.
- [ ] Không còn chữ "sẽ đo" ở chỗ đã đo xong.
- [ ] Không tuyên bố vượt quá §2.10.

---

### DEMO-04 · Kiểm tra cuối và đóng gói nộp

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 0,5 | DP (05/11) | P0 | DEMO-02, DEMO-03 |

**Tiêu chí hoàn thành:**
- [ ] Clone repo sạch về một máy khác → làm theo README → `docker compose up` → demo chạy.
- [ ] Gắn tag `v1.0-vong2`.
- [ ] Gói nộp (báo cáo, video, link repo nếu BTC cần) gửi trước 06/11.
