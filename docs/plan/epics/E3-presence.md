# E3 — Chứng minh hiện diện phía server (PRES)

> Mục tiêu epic: từ tín hiệu và video, kết luận "người thật trước camera" / "camera bị thay" / "chưa rõ", kèm bằng chứng cho người duyệt.
> Đọc chung: ADR-0007; proposal §2.7(c), Phụ lục A; `docs/research/github-references.md` §7.2, §8.1, §8.2.

---

### PRES-01 · Spike phân tích độ trễ ChromaPulse (cổng quyết định 17/10)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | **S0** | P0 | CAP-03 |

**Mục tiêu:** dựa trên dữ liệu thật từ CAP-03, quyết định ChromaPulse được giữ làm **cổng chính** hay hạ xuống **tín hiệu phụ**.
**Đầu vào:** các file JSON do CAP-03 xuất.
**Đầu ra:**
- Notebook `notebooks/01-chromapulse-spike-<tên>.ipynb`.
- Kết luận ghi vào `docs/status/STATUS.md` → "Quyết định": giữ / hạ, kèm số liệu.

**Các bước:**
1. Đổi RGB sang tuyến tính, tính log(vùng da) − log(vùng nền) cho từng kênh.
2. Dựng tín hiệu màu đã phát theo thời điểm vẽ; mô hình hóa `y = M·x(t−τ) + b`; quét τ từ 0–300 ms, bước 5 ms; lấy R² lớn nhất và τ tương ứng.
3. So sánh 3 tình huống: người thật, video phát lại, OBS.

**Tiêu chí hoàn thành:**
- [ ] Bảng R² và τ theo máy × tình huống.
- [ ] Kết luận rõ ràng theo luật:
  - người thật đạt R² ≥ 0,5 trên ≥ 2/3 máy → **giữ làm cổng chính**;
  - ngược lại → **hạ xuống tín hiệu phụ**, ghi lý do.
- [ ] Ghi các tham số khởi điểm cho PRES-02: ngưỡng R², khoảng τ của người thật.

**Lưu ý:** nếu trình duyệt không có `captureTime`, dùng `now` của rVFC trừ đi độ trễ ước lượng, và ghi rõ là giới hạn.

---

### PRES-02 · Mô-đun chromapulse.py

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 2 | S1 | P0 | PRES-01, PLAT-03 |

**Mục tiêu:** detector `chromapulse` trả `ModuleResult` với `gate` = pass / fail / unclear, kèm bằng chứng.

**Đầu ra:** `ml/src/vericlue_ml/presence/chromapulse.py`
- **Tính lại phía server:** dùng video (MediaPipe Python) tính màu trung vị 5 vùng da + nền, loại điểm ảnh quá tối (≤ 55) hoặc cháy sáng (≥ 200). So với `region_means` trình duyệt gửi; lệch nhiều → bật cờ `client_server_mismatch`.
- **Khớp chuỗi:** trong miền log, có trừ nền; quét τ; tính R², τ, số ký hiệu màu giải mã đúng (trên 8), biên độ phản chiếu.
- **Quyết định cổng** theo `ml/configs/thresholds.yaml` (mục `chromapulse`):

  | Kết quả | Điều kiện |
  |---|---|
  | `fail` | Không phản chiếu, hoặc τ vượt khoảng người thật |
  | `unclear` | Biên độ thấp |
  | `pass` | Còn lại |

- **Bằng chứng:** chuỗi thời gian "màu đã phát vs phản chiếu đo được", τ (ms), R², số ký hiệu đúng.

**Tiêu chí hoàn thành:**
- [ ] Test với tín hiệu **tổng hợp**: đồng bộ → `pass`; trễ 100 ms → `fail`; không phản chiếu → `fail`; biên độ thấp → `unclear`.
- [ ] Test với JSON thật từ CAP-03 cho kết quả khớp PRES-01.
- [ ] Chạy < 500 ms trên CPU cho video 6 giây.

**Lưu ý (trưởng nhóm 16/10):**
- **Trời quá sáng / nắng chiếu thẳng:** ánh màn hình bị ánh sáng nền lấn át nên biên độ phản chiếu rất thấp. Đây là "không đo được", **không phải** "giả": trả `unclear` (không `fail`, không bao giờ `pass`); router cho chụp lại với chỉ dẫn tránh nắng, quá số lần thì `voice_challenge`/`review`. Cổng web đã có chỉ dẫn "Tránh nắng chiếu thẳng vào mặt" (CAP-02); nếu server cần phát mã gợi ý riêng thì PR `[contract]` thêm mã `retry_hint`.
- Thu thêm vài mẫu "người thật gần cửa sổ có nắng" khi có dịp, để đặt ngưỡng biên độ có số liệu.
- **Tùy chọn, không bắt buộc:** đo thêm phản chiếu trên giác mạc (vùng nhỏ quanh con ngươi, điểm mốc mống mắt của MediaPipe; chỉ lưu con số, không lưu ảnh) làm tín hiệu phụ khi da yếu. Chỉ làm nếu dư thời gian và có số liệu cho thấy có ích.

---

### PRES-03 · Mô-đun camprobe.py

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 0,5 | S1 | P0 | CAP-05, PLAT-03 |

**Mục tiêu:** chấm điểm tín hiệu CamProbe thành `gate`.
**Đầu ra:** `ml/src/vericlue_ml/presence/camprobe.py`.

**Luật:**
- `api_tamper_flags` khác rỗng → `fail`.
- `applyConstraints` phản hồi < 5 ms mà `getSettings()` không đổi, hoặc kích thước khung thật không đổi → `fail`.
- `duplicate_frame_ratio` > ngưỡng → `fail`.
- Tên thiết bị chứa "virtual", "obs", "dummy", "manycam" → **không** fail một mình; chỉ là bằng chứng phụ, vì tên rất dễ giả.

**Bằng chứng:** danh sách cờ kèm nhãn tiếng Việt cho người duyệt.

**Tiêu chí hoàn thành:**
- [ ] Test cho từng luật.
- [ ] Thông số thật hợp lý thì không fail.

---

### PRES-04 · Chạy thử của nhóm và chỉnh ngưỡng (kết quả R5)

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M1 (+M3) | 1 | S2 | P0 | PRES-02, PRES-03, CAP-06, REDT-01 |

**Mục tiêu:** chỉnh ngưỡng ChromaPulse và CamProbe, và đo kết quả R5.
**Đọc trước:** `docs/runbooks/red-team.md`.

**Kịch bản chạy thử** (5 thành viên × ≥ 3 máy × 3 mức ánh sáng):
- người thật;
- video phát lại trên màn hình;
- OBS phát video;
- tiện ích trình duyệt giả camera;
- Deep-Live-Cam có và không bật Poisson.

**Đầu ra:**
- Ngưỡng cập nhật trong `thresholds.yaml` (PR riêng, kèm số liệu).
- Bảng R5 trong `docs/status/results/R5.md`: số lần đạt / không đạt theo tình huống, và phân bố τ của người thật so với ghép mặt.

**Tiêu chí hoàn thành:**
- [ ] Đủ kịch bản.
- [ ] Bảng R5 ghi rõ đây là **kết quả chạy thử**, không phải tuyên bố thống kê.
- [ ] Ngưỡng được đội đồng ý trong buổi họp.
- [ ] Video phát lại trên `data/selftest/` bị xóa sau khi xong.
