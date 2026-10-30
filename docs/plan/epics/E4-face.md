# E4 — Khuôn mặt: PAD và deepfake (FACE)

> Mục tiêu epic: bộ phát hiện khuôn mặt chạy được, đo được "khoảng cách dữ liệu Việt Nam" trước và sau tinh chỉnh (R1, R2).
> Đọc chung: ADR-0004; proposal §2.6; `docs/research/github-references.md` §8.3.

---

### FACE-01 · PAD bằng MiniFASNet + kết quả gốc trên người Việt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | S0–S1 | P0 | PLAT-03, DATA-03, EVAL-01 |

**Mục tiêu:** detector `face_pad` chạy thật; có số liệu R1 "trước tinh chỉnh".
**Thứ tự:**
1. S0: viết và test phần bọc mô hình (chưa cần DATA-03).
2. Đầu S1: sinh `R1-baseline.md` khi đã có DATA-03 và EVAL-01.

**Đầu ra:**
- `ml/src/vericlue_ml/face/pad.py`: MiniFASNet → `ModuleResult`. Không có mặt → `status=not_applicable`. (Đã làm: chạy `onnxruntime` trực tiếp, tiền xử lý chép từ `uniface` MIT, bộ tìm mặt SCRFD `det_10g`.)
- Chạy trên Zalo 2022 (phần calib_fit/test) và Face_anti_spoofing → `docs/status/results/R1-baseline.md`: APCER, BPCER, EER, số mẫu.

**Tiêu chí hoàn thành:**
- [x] Test với ảnh mẫu tổng hợp. (bước 1 — bọc mô hình)
- [ ] Kết quả gốc có số mẫu và commit.
- [ ] So sánh FP32 với INT8 nếu dùng bản lượng tử hóa (bài học từ verilens: INT8 có thể làm hỏng khả năng phân biệt).

---

### FACE-02 · GenD: bọc mô hình đúng tiền xử lý + kết quả gốc

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1,5 | S1 | P0 | PLAT-03, DATA-02, DATA-03, EVAL-01 |

**Mục tiêu:** detector `face_deepfake` dùng GenD cho video.
**Đọc trước:** `external/GenD`: `detector.py`, `align_face`, `app/run.py`.

**Đầu ra:** `ml/src/vericlue_ml/face/gend.py` và `aggregate.py`.
- **Tiền xử lý — giữ đúng như repo gốc:** SCRFD `det_10g` → căn chỉnh 5 điểm, tỷ lệ 1,3 → 224 px, mean/std của CLIP.
- **Lấy mẫu:** 32 khung đều nhau; nhiều mặt thì chọn mặt lớn nhất.
- **Điểm video:** `mean` và `top25_mean`. Trả cả hai vào `evidence`, `score` = `max(mean, top25_mean)` (sẽ hiệu chỉnh ở ROUT-01).
- **Bằng chứng:** điểm theo khung (chuỗi thời gian), ảnh mặt của 3 khung nghi nhất.
- **Kết quả R2 "trước tinh chỉnh":**
  - RTFS-10k (test);
  - WildDeepfake (một phần);
  - deepfake người Việt (DATA-04) ở 3 mức nén (DATA-05).

  Ghi vào `docs/status/results/R2-baseline.md`.

**Tiêu chí hoàn thành:**
- [ ] Chạy lại benchmark gốc của GenD trên 50 clip, AUC gần với số repo công bố. Nếu lệch > 5 điểm thì kiểm tra lại tiền xử lý.
- [ ] Bảng AUC/EER theo bộ × mức nén, có số mẫu.
- [ ] Chạy trên CPU được (chậm cũng được); trên GPU < 1 giây cho 32 khung.

**Tiến độ 18/10 (MVP, ADR-0012):** wrapper `gend.py` + `quality.py` thật đã xong, chạy được trên CPU và GPU (đo thử tay bằng `ml/scripts/bench_mvp_latency.py`, không phải R6). Ba tiêu chí trên CHƯA đạt (R2, 50 clip, đo GPU chính thức) — chi tiết ở `docs/status/handoffs/2026-10-18-1205-face-02-m3-claude.md`. Chưa làm: `aggregate.py`, ảnh 3 khung nghi nhất.

---

### FACE-03 · SBI + heatmap cho người duyệt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | S2 | P0 | FACE-02 |

**Mục tiêu:** mô hình thứ hai chuyên bắt đường hòa trộn, kèm heatmap.

**Đầu ra:** `ml/src/vericlue_ml/face/sbi.py`.
- **Tiền xử lý — giữ đúng như repo SBI:** RetinaFace + lề 1/4, 380 px, chia 255.
- **Heatmap:** Grad-CAM (`pytorch-grad-cam`) trên 3 khung nghi nhất, lưu ảnh vào `evidence`.
- **Nhãn hiển thị:** "vùng mô hình chú ý — không phải bằng chứng".

**Tiêu chí hoàn thành:**
- [ ] Kết quả SBI có trong R2-baseline.
- [ ] Heatmap hiển thị được trong hồ sơ (REV-02).

---

### FACE-04 · Tinh chỉnh GenD và PAD trên dữ liệu Việt Nam

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 2 | S2 | P0 | FACE-01, FACE-02, DATA-04, DATA-05 |

**Mục tiêu:** thu hẹp "khoảng cách Việt Nam"; có số liệu R1, R2 "sau tinh chỉnh".

**Các bước:**
1. **GenD:** chỉ huấn luyện LayerNorm và lớp cuối (như bài báo gốc).
   - Dữ liệu: RTFS-10k train + deepfake VN train + video thật người Việt (ViCocktail).
   - Tăng cường: JPEG chất lượng 30–95, làm mờ, thu nhỏ 64–224, nhiễu, H.264 CRF 23–40.
   - Chạy trên Kaggle hoặc Colab.
2. **PAD:** lớp tuyến tính trên đặc trưng DINOv2, huấn luyện trên Zalo train + CelebA-Spoof (một phần). So sánh với MiniFASNet; giữ cái tốt hơn trên tập calib.
3. **Lưu mô hình:** `models/finetuned/<tên>/<ngày>/` kèm `card.md`.
4. **Đánh giá trên tập test** (chỉ chạy **một lần** khi đã chốt mô hình) → `R1-final.md`, `R2-final.md`.

**Tiêu chí hoàn thành:**
- [ ] Bảng "trước / sau" cho R1, R2, có số mẫu, khoảng tin cậy bootstrap, commit.
- [ ] Chọn mô hình **chỉ dựa trên `calib_fit`**, không nhìn `calib_ltt` hay tập test.
- [ ] `ml/configs/models.yaml` trỏ tới mô hình đã chọn.

**Cập nhật trưởng nhóm 17/10 (thay một phần các bước trên):**
- **GenD:** tinh chỉnh trên **deepfake người Việt tự tạo (DATA-04, phần train)** + video thật **ViCocktail** (phần train). **RTFS-10k và WildDeepfake chỉ làm test** (DATA-03: gộp theo người cho mặt thì RTFS dính thành một khối, không chia sạch được). R2 "sau" đo trên RTFS test + phần test của DATA-04.
- **PAD:** tinh chỉnh **chỉ trên Zalo 2022 (train)**. **FAS-VN chỉ làm test** (trùng byte giữa train/test gốc, không có mã người). CelebA-Spoof đang bị bỏ qua — không bắt buộc.
- **DINOv2 chưa có** trong `models/manifest.yaml`: bổ sung (ghim revision, SHA-256, kiểm giấy phép) trước khi làm PAD mới; nếu không kịp thì giữ MiniFASNet.
- **Hai bước:** viết script trong repo, **chạy thử nhỏ trên máy** (RTX 4050 6 GB đủ cho PAD và chạy thử GenD), rồi chạy thật trên **Kaggle** (dự phòng: Colab, thuê GPU). Cùng một script, chỉ khác tham số.
- **Luật khi chạy cloud:** notebook kéo repo đúng commit và ghi commit; dữ liệu tải lên để **Private**; token để trong Secrets; chọn checkpoint chỉ trên `calib_fit`; trọng số mang về `MODELS_DIR/finetuned/<tên>/<ngày>/` kèm SHA-256 và `card.md`, không commit.

**Cập nhật 19/10 (PAD, nhánh `feat/FACE-04-pad-kaggle`):** dữ liệu dạy/chọn/test của PAD đổi thành **FAS-VN chia lại theo nhóm người** (lọc trùng, khử lộ đề); Zalo 2022, Axon, UniData chỉ làm test phụ; không dùng CelebA-Spoof. Hai notebook `ml/notebooks/finetune_pad_minifasnet.ipynb` / `finetune_pad_dinov2.ipynb` (2 người chạy song song, gộp bằng `ml/notebooks/combine_pad.py`; sinh bằng `scripts/build_pad_notebook.py`, hướng dẫn `ml/notebooks/README-pad.md`) nhúng code repo thay vì kéo repo (repo private). Thiếu ảnh in giấy/mặt nạ trong dữ liệu dạy — ghi ở `card.md` xuất ra.

---

**Cập nhật trưởng nhóm 18/10 (ADR-0015):**
- **PAD:** thử cả hai cách rồi giữ cách thắng trên `calib_fit`: (a) tinh chỉnh **MiniFASNet**; (b) **DINOv2-reg ViT-B/14** chỉ dạy lớp cuối và vài khối cuối, trên Zalo train và CelebA-Spoof. Thêm DINOv2 vào manifest, ghi rõ giấy phép.
- **GenD:** mặt thật lấy thêm khung từ **video selfie thật của Zalo 2022** (quay bằng điện thoại, người Việt, đúng miền dữ liệu của app) và vn_celeb.
- **Mọi lần huấn luyện thật chạy trên Colab hoặc Kaggle**, kể cả PAD. Không thu dữ liệu tay.

---


**Cập nhật trưởng nhóm 20/10 (ADR-0015 mục "Cập nhật 19–20/10") — thay các ghi chú dữ liệu ở trên:**
- **PAD:** dạy, hiệu chỉnh và test đều trên **FAS-VN đã làm sạch và chia lại theo người**. Có 2 notebook Kaggle (MiniFASNet, DINOv2; PR #38). Kết hợp = max của hai xác suất đã hiệu chỉnh, chỉ dùng nếu thắng mô hình đơn.
- **GenD:** **không tinh chỉnh; chỉ hiệu chỉnh** (PR #39). Lớp thật = FAS-VN live + video gốc RTFS; lớp giả = RTFS. RTFS **không còn chỉ là test** — phần test là phần test trong `splits.csv` của notebook.
- **`splits.csv` do notebook sinh là cách chia chuẩn** cho mọi phép đo R1/R2 sau này trên FAS-VN và RTFS.
- Không tự tạo deepfake người thật.

---

### FACE-05 · Tối ưu tốc độ

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 0,5 | S2 | P1 | FACE-04 |

**Mục tiêu:** bước khuôn mặt chạy < 1 giây trên GPU demo.

**Đầu ra:**
- fp16 hoặc ONNX cho GenD, SBI.
- Nạp sẵn khi khởi động.
- Gom các khung thành một lô.

**Tiêu chí hoàn thành:**
- [ ] Đo p50 và p95 trên GPU và CPU; ghi vào R6.
- [ ] Kết quả sau tối ưu lệch < 0,5 điểm AUC so với bản gốc.

---

### FACE-06 · Xuất ONNX FP32 và đối chiếu FS-VFM-L/GenD-L

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | S2 | P0 | PLAT-03 |

Yêu cầu người dùng 30/10: xuất hai model gốc đã tải, giữ FP32 trước khi thử
giảm độ chính xác. Đây là kiểm chứng chuyển đổi, không thay kết quả AUC/R6 hoặc
nghiệm thu bảo mật của FACE-05. Không đổi API, ngưỡng, tiền xử lý hay server.

- [x] Có CLI xuất đúng loader gốc, metadata và checksum; giữ bản gốc.
- [x] Đối chiếu logits/xác suất/nhãn giả trên cùng dữ liệu tổng hợp, có test âm.
- [x] Xuất thực hai model, ghi kết quả số học và p50/p95, RAM; ghi rõ khả năng
      đo GPU và phạm vi phép đo, không gọi kết quả tổng hợp là APCER/BPCER/AUC.
- [x] Lint/test/kế hoạch, tài liệu tái lập và bàn giao; không commit trọng số.

Kết quả/giới hạn: `docs/research/2026-10-30-onnx-fp32.md` và JSON kèm theo.
CPU cả hai đạt đối chiếu; GPU GenD đạt nhưng chậm hơn, FS-VFM chưa đạt so
nhánh Torch CUDA mặc định. Không phê duyệt triển khai chỉ từ tensor tổng hợp.
