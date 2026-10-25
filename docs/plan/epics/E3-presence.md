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

**Quyết định trưởng nhóm 17/10 — đóng thẻ, không thu dữ liệu thiết bị:**
- Nhóm quyết định **không thu dữ liệu ChromaPulse trên điện thoại thật** (quá tải). Không có số liệu nên không đạt điều kiện "giữ làm cổng chính".
- Theo đúng luật của thẻ: **ChromaPulse hạ xuống tín hiệu phụ**. Code và trang nháy màu vẫn giữ, vẫn chạy trong luồng và trong demo; quyết định chính dựa vào PAD, GenD, AntiDeepfake và bước đọc câu.
- **Không tuyên bố** trong báo cáo rằng ChromaPulse phát hiện được tấn công (luật 9). Ghi "đã xây dựng, chưa kiểm chứng trên thiết bị thật".
- Nếu sau này có người tự nguyện thu dữ liệu thì mở lại thẻ.

---

### PRES-02 · Mô-đun chromapulse.py

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 2 | S1 | P0 | PRES-01, PLAT-03 |

**Tiến độ 24/10 — doing, chưa nghiệm thu cổng:** đã có đo median 5 vùng da/nền
phía server, trừ nền miền log, khớp affine và quét lag, ModuleResult, factory
diagnostic dùng mock sẵn có và CLI. Xem
[`chromapulse-diagnostic.md`](../../architecture/chromapulse-diagnostic.md).
ADR-0016 đã đưa ChromaPulse về lớp 1, thay quyết định hạ xuống phụ ngày 17/10;
việc bật gate vẫn cần kiểm chứng. Hiện luôn `degraded/unclear`, không sửa ngưỡng
hoặc bật thật trong HTTP. Các tiêu chí cổng/độ trễ bên dưới còn **chưa hoàn thành**.
Chưa có client/server mismatch, số ký hiệu giải mã độc lập, CAP-03 thật hay R5.
Lag từ decoder/lịch dự kiến chỉ là lag biểu kiến; không dùng tiêu chí “100 ms
là fail” khi chưa có đồng hồ và ngưỡng được kiểm chứng.

**Bổ sung webcam 24/10:** nút thử ánh sáng 6–8 giây trong lab nội bộ, dùng
chung task MediaPipe cho mắt/đầu/màu. Chỉ giữ số đo và log yêu cầu vẽ trong RAM;
dừng/hủy bỏ lượt, kết quả luôn unclear. Chưa có mẫu người hoặc kết quả kiểm
thiết bị/tấn công; không đánh dấu xong tiêu chí cổng bằng smoke tổng hợp.

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

**Quyết định trưởng nhóm 17/10:** không tổ chức chạy thử với thành viên nhóm (không thu dữ liệu người thật). R5 bỏ, hoặc thay bằng đánh giá trên dữ liệu tổng hợp (DATA-04) nếu kịp — ghi rõ là dữ liệu tổng hợp.

---

### PRES-05 · Lượt thử mặt liên tục trong lab nội bộ

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | S2 | P0 | PLAT-03 |

**Mục tiêu:** tiếp tục tính năng ngày 25/10: gộp các thành phần diagnostic đã
có của PRES-02/LIVE-02/FLOW-04 vào một lượt thử ánh sáng → mắt → quay đầu,
không đợi nghiệm thu cổng/accuracy của những thẻ đó và không đổi UI sản phẩm.

**Tiêu chí kỹ thuật:**
- [x] Một nút bắt đầu, một camera/reader, lịch và đồng hồ chung; không mở
      thiết bị khi khởi động. Giữ nguyên palette/nhịp màu và thời lượng mắt/đầu.
- [x] Hướng dẫn ba bước, đếm ngược theo lịch thực; thu số đo màu/mắt/đầu
      từ cùng frame, lấy ba ảnh ở đúng vị trí của lịch đã dịch.
- [x] Báo cáo các kết quả riêng gắn cùng mã lượt; lỗi một phần vẫn thấy
      phần khác, không tạo kết luận xác minh/giả mạo chung.
- [x] Dừng/Esc/đóng/mất tiêu điểm/hide hủy lượt, bỏ kết quả cũ, giới hạn và
      dọn pixel RAM; không chồng lượt hoặc chấm ảnh khi motion thiếu/lỗi.
- [x] Test tổng hợp/lifecycle, smoke reader không thiết bị, QA cửa sổ,
      tài liệu/bàn giao/lint/plan_check. Không đổi API/hợp đồng/ngưỡng/ADR.

Phạm vi này chỉ điều phối công cụ thử local. Không chứng minh màu phản chiếu,
chiều sâu, danh tính, chống phát lại hoặc tính đúng của camera timestamp.
