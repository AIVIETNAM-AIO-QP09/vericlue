# E6 — TrustRouter: quyết định có bảo đảm (ROUT)

> Mục tiêu epic: biến kết quả của các bộ phát hiện thành quyết định *cho qua / chụp lại / đọc câu / chuyển nhân viên*, với ngưỡng có bảo đảm thống kê (R4).
> Đọc chung: ADR-0006; proposal §2.7(d), Phụ lục C; `docs/research/github-references.md` §2 (MAPIE).

---

### ROUT-01 · Hiệu chỉnh xác suất

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S1 | P0 | PLAT-03 |

**Mục tiêu:** điểm thô của mọi bộ phát hiện → `prob_attack` đáng tin.

**Đầu ra:** `ml/src/vericlue_ml/common/calibration.py`
- Platt (logistic) và isotonic; chọn bằng log-loss OOF của GroupKFold theo subject (~5 phần) trên **calib_fit**, rồi fit lại trên toàn calib_fit. Isotonic chỉ được chọn khi mỗi lớp ≥ 100 mẫu và log-loss thấp hơn Platt ≥ 2% tương đối.
- Lưu và nạp calibrator theo `model_version` (`ml/configs/calibrators/<module>/<version>.json`).
- ECE, Brier và bảng reliability (dữ liệu + Markdown) trong `common/calibration.py`; PNG tùy chọn với matplotlib (extra `eval`, import lười).
- Artifact JSON ghi epsilon = 1e-4, số mẫu mỗi lớp, tham số, chỉ số trước/sau OOF, ngày và commit. Không dùng calib_ltt/test để fit hay chọn phương pháp.

**Tiêu chí hoàn thành:**
- [x] Test với dữ liệu tổng hợp: ECE giảm sau hiệu chỉnh.
- [x] Detector nào chưa có calibrator thì báo lỗi rõ ràng (không âm thầm dùng điểm thô). Mock `mock@` và module chỉ trả gate/nguồn gốc được miễn theo phạm vi đã chốt.

**Bổ sung MVP được duyệt theo ADR-0012 (18/10):**
- [x] Hồ sơ full mặc định giữ nguyên; MVP chỉ CamProbe, PAD/deepfake, quality, challenge/spoof; orchestrator chỉ preload/chạy module trong hồ sơ.
- [x] Test full/MVP, mock MVP, module thiếu/error/degraded và calibrator thiếu đều không cho pass ở bước bắt buộc.
- [x] Script fit chạy detector thật từ registry, chỉ đọc calib_fit, loại replay khỏi voice; lưu version thật, provisional, số mẫu, commit và hash manifest.
- [x] Commit calibrator voice_spoof thật (Platt, 23 dương/109 âm; 80 replay + 7 no-score loại có thống kê) và ghi lệnh/commit/kết quả trong bàn giao.
- [x] Hỗ trợ identity minh bạch theo ADR-0012 mục 2 sửa ngày 18/10: cắt score, provisional + ghi chú không dùng báo cáo; không bịa mẫu/metrics, giữ Platt voice.
- [x] Commit identity PAD đúng runtime version minifasnet-v2@bfcc7d48+scrfd-10g@bfcc7d48; có CLI sinh GenD khi wrapper chốt version. Không chạy công việc dữ liệu trong cập nhật này.
- [ ] Thêm JSON identity GenD khi FACE-02 commit/xác nhận runtime version (không phải phụ thuộc dữ liệu).

---
### ROUT-02 · Bộ chính sách quyết định

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1,5 | S1 | P0 | ROUT-01, PLAT-08 |

**Mục tiêu:** thay luật tạm của PLAT-04 bằng chính sách đầy đủ, đọc ngưỡng từ `thresholds.yaml`.

**Đầu ra:** `ml/src/vericlue_ml/router/policy.py`, `fusion.py`, và `ml/configs/thresholds.yaml` (giá trị tạm, ghi rõ `provisional: true`).

**Thứ tự cổng:**
1. **Phiên hợp lệ?** Token, thời gian. Không → `review` ưu tiên cao.
2. **Chất lượng đạt?** Không → `retry` + gợi ý. Quá 2 lần → `review`.
3. **Cổng hiện diện** (chromapulse, camprobe):
   - `fail` → `review` ưu tiên cao;
   - `unclear` → `retry` (`BRIGHTNESS_UP` hoặc `MORE_LIGHT`);
   - gate rỗng/không xác định dù status ok → `review`.
4. **Cổng ngoài phạm vi** (nếu có ROUT-04) → `review`.
5. **Bước khuôn mặt:** hợp nhất logistic (`prob_attack` của PAD, GenD, SBI + đặc trưng chất lượng) → Λ. Trọng số hợp nhất học trên **`calib_fit`** (ADR-0010).
   - Λ ≤ B → `pass`;
   - Λ ≥ A → `review`;
   - ở giữa → `voice_challenge`.
6. **Bước giọng nói:** khớp câu sai → cho đọc lại 1 lần. Hợp nhất `voice_spoof` + `lipsync` + cờ cắt ghép:
   - ≤ ngưỡng → `pass`;
   - còn lại → `review`.
7. Bất kỳ `ModuleResult` nào có `status` = `error` hoặc `degraded` ở bước bắt buộc → `review`.

Lưu `decisions` kèm ngưỡng đã dùng và phiên bản cấu hình.

**Chốt nghiệm thu trưởng nhóm 16/10:** chất lượng xét trước trạng thái module mặt;
quality fail → retry, retry, review; quality error/degraded → review.
Face Λ ≤ B pass, Λ ≥ A review; voice dùng spoof_threshold riêng (≤ pass).
Nguồn số duy nhất thresholds.yaml, provisional:true; fusion hiện max(prob_attack)
đã hiệu chỉnh. Logistic chỉ chuẩn bị API học trên calib_fit sau DATA-03; không học
trọng số giả, không dùng calib_ltt/test. WER chỉ là gate; splice dương review ưu tiên cao; splice sai kiểu/không hữu hạn review,
không có splice giữ absent/chờ VOICE-05. Metadata dùng cột JSON/hash hiện có,
không migration mới và không sửa hai file review của REV-01.

**Tiêu chí hoàn thành:**
- [x] Test cho **từng nhánh** (≥ 12 test), gồm "lỗi thì không bao giờ pass" và "quá số lần chụp lại thì review".
- [x] Mock theo kịch bản `genuine`, `print`, `replay`, `virtual_cam`, `faceswap`, `voice_clone`, `low_quality` cho kết quả đúng mong đợi.

---

### ROUT-03 · Chọn ngưỡng bằng Learn-then-Test (MAPIE)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1,5 | S2 | P0 | ROUT-02, FACE-04, VOICE-03 |

**Cách làm để không bị chặn:**
- Ngay khi ROUT-02 xong, viết và chạy thử toàn bộ pipeline trên điểm của mô hình **gốc** (FACE-02, VOICE-01).
- Khi FACE-04 và VOICE-03 xong, chỉ cần chạy lại `fit_thresholds.py`.

**Mục tiêu:** ngưỡng B, A (bước mặt) và ngưỡng bước giọng có bảo đảm: tỷ lệ tự động cho qua của **mỗi loại tấn công đã biết** ≤ α với xác suất ≥ 1 − δ.
**Đọc trước:** MAPIE `mapie/risk_control/`, ví dụ `plot_risk_control_multi_parameter_binary_classification.py`.

**Đầu ra:** `ml/src/vericlue_ml/router/ltt.py` + `scripts/fit_thresholds.py`.
- **Bước mặt:** lưới (B, A).
  - Rủi ro thứ k = P(cho qua | tấn công loại k), với k ∈ {print, replay, faceswap, deepfake VN…}.
  - Thêm rủi ro BPCER ≤ β nếu cần.
  - `BinaryClassificationController`, p-value Hoeffding–Bentkus, Holm.
  - Trong các bộ hợp lệ, chọn bộ có **tỷ lệ chuyển nhân viên thấp nhất**.
- **Bước giọng:** tương tự, mỗi hệ TTS là một loại tấn công.
- **Ghi `thresholds.yaml`:** giá trị, α, δ, số mẫu từng loại, `provisional: false`, commit, ngày.
- **Ghi báo cáo** vào `docs/status/results/R4-thresholds.md`: p-value, các bộ hợp lệ, bộ đã chọn.

**Tiêu chí hoàn thành:**
- [ ] Chọn ngưỡng **chỉ bằng `calib_ltt`** — dữ liệu chưa từng dùng để huấn luyện, hiệu chỉnh hay học trọng số hợp nhất (ADR-0010). Không dùng tập test.
- [ ] Nếu không đạt α = 5% do thiếu mẫu thì ghi rõ α thực tế đạt được (xem Phụ lục C).
- [ ] Bất đẳng thức hợp: báo cáo tỷ lệ lọt cả quy trình ≤ α_mặt + α_giọng.

---

### ROUT-04 · Cổng ngoài phạm vi

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S2 | P1 | FACE-02 |

**Mục tiêu:** mẫu quá khác dữ liệu đã kiểm thử → không tự quyết, chuyển nhân viên.

**Đầu ra:** `router/ood.py`.
- Embedding CLIP (lấy từ GenD).
- Khoảng cách kNN (k = 10) tới tập tham chiếu là người thật trong `calib_fit`.
- p-value conformal tính từ điểm của người thật trong `calib_ltt`: p < γ → `review`.

**Tiêu chí hoàn thành:**
- [ ] Trên người thật của tập test, tỷ lệ báo nhầm ≈ γ (kiểm tra).
- [ ] Ảnh hoạt hình hoặc ảnh không phải mặt người bị chặn.

---

### ROUT-05 · Đánh giá R4

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S3 | P0 | ROUT-03 |

**Mục tiêu:** chứng minh giá trị của TrustRouter một cách công bằng.

**Các bước:**
1. **So sánh trên tập test, ở cùng tỷ lệ chuyển nhân viên** (5% và 10%), với:
   - B1: một ngưỡng trên PAD;
   - B2: hợp nhất + một ngưỡng;
   - B3: hai ngưỡng có vùng xám chọn theo cảm tính.
2. **Kiểm tra bảo đảm giữ được:** chia lại `calib_ltt`/test ngẫu nhiên ≥ 200 lần, giữ nguyên các thành phần đã học trên `calib_fit`; tần suất vi phạm phải ≤ δ.

**Đầu ra:** `docs/status/results/R4-final.md` + biểu đồ risk–coverage.

**Tiêu chí hoàn thành:**
- [ ] Bảng so sánh có số mẫu và khoảng tin cậy.
- [ ] Báo cáo trung thực, kể cả khi TrustRouter không thắng.
