# E7 — Bàn duyệt và giám định (REV, FOR)

> Mục tiêu epic: nhân viên xem được hồ sơ bằng chứng và ra quyết định; điều tra viên tải video lên và nhận báo cáo giám định có chữ ký.
> Đọc chung: ADR-0008; proposal §2.7(e), §2.8; `docs/research/github-references.md` §8.5.

---

### REV-01 · API bàn duyệt và nhật ký chuỗi băm

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 1 | S1 | P0 | PLAT-05 |

**Mục tiêu:** API cho danh sách ca, hồ sơ, quyết định; nhật ký không sửa xóa được.

**Đầu ra:** `services/api/src/vericlue_api/routers/review.py`, `services/api/src/vericlue_api/services/audit_log.py`.
- `GET /v1/review/cases`: lọc theo trạng thái, sắp theo ưu tiên rồi thời gian.
- `GET /v1/review/cases/{id}`: hồ sơ gồm ảnh (media), ghi chú chụp, lịch sử quyết định — **không** có `ModuleResult[]`/điểm AI (chống thiên kiến tự động hóa; theo hợp đồng `review.schema.json`). `ModuleResult[]` chỉ ở `GET …/ai`, sau quyết định ban đầu.
- `POST .../decision`: quyết định + mã lý do bắt buộc + ghi chú.
- **Bắt buộc ghi quyết định riêng của nhân viên trước** khi API trả điểm AI. Ví dụ endpoint `.../ai` chỉ mở sau khi đã có `human_initial_decision`.
- `review_events` chỉ ghi thêm (`hash = sha256(prev_hash ‖ json chuẩn hóa)`), kèm hàm `verify_chain()`.

**Tiêu chí hoàn thành:**
- [x] Test: sửa một dòng trong `review_events` → `verify_chain()` báo sai.
- [x] Test: gọi `.../ai` trước khi ghi quyết định ban đầu → 409.
- [x] Mã lý do theo danh sách cố định (`services/review_reasons.py`, danh sách tạm — M2 chỉnh; sai → 422).

---

### REV-02 · Giao diện bàn duyệt và hồ sơ bằng chứng

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 2 | S1–S2 | P0 | REV-01, PLAT-04 |

**Mục tiêu:** nhân viên ra quyết định dựa trên **bằng chứng kiểm chứng được**, không bị điểm AI dẫn dắt.

**Đầu ra:** `apps/web/src/app/review/`
- **Hàng đợi** (cột trái): ưu tiên, thời gian, trạng thái.
- **Bước 1 — bằng chứng, chưa có điểm AI:**
  - ảnh và video;
  - biểu đồ "màu đã phát vs phản chiếu" của ChromaPulse;
  - độ trễ (ms);
  - cờ CamProbe kèm nhãn tiếng Việt;
  - câu đề bài vs câu nhận dạng được (tô khác biệt);
  - khung câu hỏi kiểm chứng ("Da mặt có phản chiếu đúng màu không?"…).

  Nhân viên chọn quyết định ban đầu.
- **Bước 2 — mở ý kiến AI:** xác suất từng bộ phát hiện kèm lời, heatmap SBI có nhãn "chỉ là vùng mô hình chú ý".
- **Bước 3:** quyết định cuối + mã lý do + ghi chú.

**Tiêu chí hoàn thành:**
- [ ] Đi hết một ca với dữ liệu mock và với một phiên thật.
- [ ] Không thể xem điểm AI trước khi chọn quyết định ban đầu.
- [ ] Chụp màn hình bỏ vào PR.

**Ghi chú từ REV-01 (16/10):**
- API bàn duyệt đã có: danh sách/hồ sơ ca, quyết định ban đầu → `.../ai` → quyết định cuối, `GET /v1/review/reason-codes`, `GET .../audit/verify`, `history` trong hồ sơ. Hồ sơ **không** có điểm AI; `ModuleResult[]` chỉ ở `.../ai`.
- **Còn thiếu:** API phục vụ ảnh/video của ca (URL media hiện là chỗ giữ chỗ). REV-02 làm phần này (endpoint có kiểm quyền nhân viên sau PLAT-06, chỉ phục vụ file trong `MEDIA_DIR/<session_id>/`).
- 9 mã lý do hiện là **danh sách tạm**; M2 chốt danh sách cuối khi làm giao diện.

---

### REV-03 · Chặn quyết định duyệt lặp khi SQLite đọc trạng thái cũ

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | REV-01 |

**Mục tiêu:** sửa lỗi đã xuất hiện trong CI PR #62: hai request cùng ghi quyết
định ban đầu và đều trả 200 khi SQLite đọc trạng thái cũ, dù chuỗi hash không
rẽ nhánh. Cùng bảo vệ bước quyết định cuối, không đổi hợp đồng/DB schema.

**Tiêu chí hoàn thành:**
- [x] Test tái hiện có điều khiển: request thua giữ snapshot cũ, request thắng
      commit trước khi request thua ghi; chỉ một 200, bên còn lại 409.
- [x] Quyết định initial/final được chốt bằng điều kiện nguyên tử tại DB,
      không dựa vào khóa Python, không UPDATE/DELETE review_events.
- [x] Trạng thái ca, nhật ký và quyết định phiên cùng transaction; lỗi rollback
      không chiếm lượt, không ghi sự kiện hoặc quyết định phiên thừa.
- [x] Hồi quy SQLite qua; giữ test PostgreSQL để CI kiểm thật, luật xem AI,
      mã lý do và hợp đồng không đổi.
- [x] Lint/plan_check/tài liệu/bàn giao đầy đủ.

---

### FOR-01 · API giám định: tiếp nhận, chia đoạn, chạy bộ não

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1,5 | S2 | P0 | PLAT-05, FACE-02, VOICE-01 |

**Mục tiêu:** nhận file, phân tích theo đoạn, trả kết quả theo thời gian.

**Đầu ra:** `services/api/src/vericlue_api/routers/forensic.py`, `ml/src/vericlue_ml/forensic/segment.py`.
- **Tiếp nhận:** tính **SHA-256 trên byte gốc trước mọi bước chuyển mã**; `ffprobe` lấy codec, độ phân giải, bitrate, thời lượng; ước lượng mức nén.
- **Chia đoạn:** 3 giây, chồng lấn 50%. Mỗi đoạn chạy `face_deepfake`, `voice_spoof`, `lipsync`. Đoạn không có mặt hoặc im lặng → `not_applicable`.
- **Chạy nền:** `BackgroundTasks`; `GET /jobs/{id}` trả tiến độ.
- **Gộp đoạn liền kề vượt ngưỡng** thành khoảng nghi giả, **mở rộng ±1 giây**.

**Tiêu chí hoàn thành:**
- [ ] Video 60 giây xử lý < 2 phút trên GPU. *(Chưa đo GPU; xem bàn giao FOR-01.)*
- [x] Test: hash giữ nguyên dù file bị chuyển mã sau đó. *(`services/api/tests/test_forensic_real.py`: hash trên byte gốc, file lưu nguyên vẹn.)*
- [x] Test gộp khoảng. *(`ml/tests/test_forensic_segment.py`.)*
- [ ] **Hiệu chỉnh riêng cho chế độ giám định:** dùng tập calib có cả bản nén (DATA-05), vì video giám định thường đã bị nén. Lưu calibrator riêng tên `forensic`.

> **Lõi MVP (nhánh `feat/FOR-01-forensic-real-mvp`, ADR-0012):** `ml/src/vericlue_ml/forensic/{segment,media,pipeline}.py` và `services/api/.../forensic_runner.py` chạy nền, chia đoạn 3 s chồng 50%, gọi detector thật từng đoạn, gộp khoảng ±1 s, `GET /jobs/{id}` trả tiến độ. Dùng calibrator identity hiện có (chưa có calibrator `forensic`) và ngưỡng `thresholds.yaml` như eKYC. `face_deepfake` (FACE-02) đã có trên `main` và chạy thật theo đoạn; `lipsync` (VOICE-05) vẫn `unavailable` ở giám định (cần câu đề bài), không giả lập; bước bắt buộc thiếu mô hình thì kết luận `inconclusive`. Hồ sơ `mvp` vẫn bật được vì giám định gọi detector trực tiếp (không qua orchestrator). Chưa đổi trạng thái FOR-01.

---

### FOR-02 · Giao diện giám định

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 1,5 | S2 | P0 | FOR-01 |

**Mục tiêu:** điều tra viên thấy ngay **đoạn nào** nghi bị làm giả.

**Đầu ra:** `apps/web/src/app/forensic/`
- Tải file lên, có thanh tiến độ.
- Trình phát video; **mỗi tín hiệu một dải điểm** (mặt / giọng / khớp môi) dưới trình phát. Bấm vào đoạn để tua tới đó.
- Dạng sóng và phổ âm (wavesurfer.js 8).
- Khoảng nghi giả tô màu, kèm nhãn "0:15–0:24".
- Khối "quét nguồn gốc" (FOR-03).
- Nút xem và tải báo cáo (FOR-04).

**Tiêu chí hoàn thành:**
- [ ] Demo được kịch bản 6 và 7 trong proposal §1.4.
- [ ] Chụp màn hình bỏ vào PR.

---

### FOR-03 · Quét nguồn gốc: thủy vân AI và C2PA

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 | 1 | S2 | P0 | PLAT-03 |

**Mục tiêu:** chỉ ra công cụ AI đã tạo file nếu công cụ đó có gắn thủy vân.
**Đọc trước:** ADR-0008; README của `facebookresearch/audioseal`, `resemble-ai/Perth`, `contentauth/c2pa-python`.

**Đầu ra:** `ml/src/vericlue_ml/forensic/provenance.py` → `ModuleResult(module="provenance")`.
- **AudioSeal:** xác suất thủy vân theo từng mẫu → khoảng có thủy vân trên dòng thời gian.
- **Perth** (Resemble/Chatterbox): có hay không, độ tin cậy.
- **c2pa-python:** đọc manifest nếu có (người ký, khẳng định "do AI tạo", trạng thái hợp lệ).
- **Kết luận một chiều:**
  - có thủy vân → "Phát hiện thủy vân AI của <công cụ>";
  - không có → "Không có tín hiệu nguồn gốc" (**không** được hiểu là thật).

**Tiêu chí hoàn thành:**
- [ ] Tạo 1 file bằng Chatterbox (máy red-team) → Perth phát hiện.
- [ ] Tạo 1 file gắn AudioSeal → phát hiện đúng khoảng. *(Thử tay, chưa có test tái lập; xem bàn giao FOR-01.)*
- [x] File thật → "Không có tín hiệu nguồn gốc". *(Thử tay, ghi trong bàn giao; không phải số liệu.)*

---

### FOR-04 · Báo cáo giám định ENFSI có chữ ký

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (+M5 phần ký) | 1,5 | S2 | P0 | FOR-01, FOR-03, PLAT-06, ROUT-01 |

**Mục tiêu:** báo cáo đúng chuẩn trình bày giám định, không ai sửa được về sau.
**Đọc trước:** ADR-0008; `docs/research/github-references.md` §8.5.

**Đầu ra:** `ml/src/vericlue_ml/forensic/report.py` + template HTML `forensic/templates/report.html`.

**Các mục của báo cáo:**
1. Thông tin báo cáo (mã, thời gian, phiên bản công cụ và mô hình).
2. Vật chứng và chuỗi lưu giữ (tên file, SHA-256, thông số, nhật ký thao tác).
3. Hai giả thuyết Hp/Hd.
4. Phương pháp.
5. Kết quả theo tín hiệu (tỷ số khả năng + **thang lời ENFSI**).
6. Quét nguồn gốc.
7. Các khoảng nghi giả kèm ảnh và phổ.
8. **Giới hạn.**
9. Kết luận dạng tỷ số khả năng (không viết "đây là giả").
10. Chữ ký.

**Cách làm:**
- **Đổi xác suất hiệu chỉnh → tỷ số khả năng:** LR = [p/(1−p)] / [π/(1−π)], với π là tỷ lệ tấn công trong tập calib. Từ LR suy ra thang lời ENFSI.
- **Xuất PDF:** Playwright `page.pdf()` hoặc WeasyPrint.
- **Ký:** Ed25519 trên JSON chuẩn hóa của báo cáo + hash PDF; in dấu vân tay khóa công khai.
- **Trang xác minh** `/forensic/verify`: dán JSON hoặc tải PDF + chữ ký → hợp lệ hay không.

**Tiêu chí hoàn thành:**
- [x] Gói PDF/JSON: sửa byte PDF hoặc JSON → xác minh thất bại, có CLI với key đã pin (test).
- [ ] (Từ REV-01) Neo **hash cuối chuỗi** `review_events` của ca liên quan vào báo cáo đã ký, để phát hiện việc cắt bớt đuôi nhật ký (`verify_chain()` chỉ bắt được sửa/xóa giữa chuỗi).
- [ ] Bảng thang lời được kiểm tra lại với tài liệu ENFSI 2015 trước khi dùng.
- [x] Mục giới hạn luôn có mặt trong HTML/PDF và manifest không được trống (test, PDF tổng hợp đã render kiểm trực quan).

**Lát cắt xuất artifact 26/10 (doing):** Đã có endpoint StaffBearer xuất ZIP
PDF/JSON/signature, Node/Chromium opt-in, protocol domain riêng dùng khóa report
PLAT-06 và CLI kiểm offline. Chỉ done/real, mock không được ký; không thêm LR
hoặc thang lời từ điểm MVP. PDF có nhãn thử nghiệm. Phần này độc lập với các phụ
thuộc hiệu chỉnh chưa xong; không mở chốt mô hình. Còn neo audit/ảnh/phổ/calib/LR/
ENFSI và UI do thành viên khác làm. Xem `docs/architecture/forensic-pdf-bundle.md`.

**Bổ sung ảnh/phổ 26/10 (doing):** HTML/PDF có minh họa opt-in từ snapshot nguồn
khớp SHA-256; tối đa ba khoảng/ba giây mỗi khoảng, frame và phổ Hann/mono 16 kHz,
giới hạn subprocess và format/protocol FFmpeg. Caption ghi giới hạn thời gian,
không gọi là heatmap hay xác suất AI. Thiếu nguồn/runtime ghi rõ bỏ minh họa,
không đổi verdict/chữ ký. Test native dùng test-pattern/sóng sin, chặn playlist
mạng; PDF tổng hợp đã kiểm bố cục. Không đổi schema/UI. Còn neo audit/calib/LR/
ENFSI và nghiệm thu toàn luồng; xem `docs/architecture/forensic-report-evidence.md`.
