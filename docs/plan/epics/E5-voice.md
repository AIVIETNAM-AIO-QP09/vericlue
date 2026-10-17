# E5 — Giọng nói tiếng Việt (VOICE)

> Mục tiêu epic: phát hiện giọng giả tiếng Việt theo vùng miền (R3) và kiểm tra câu đọc ngẫu nhiên.
> Đọc chung: ADR-0005; proposal §2.6, §2.7(d); `docs/research/github-references.md` §7.4, §8.4.

---

### VOICE-01 · AntiDeepfake: bọc mô hình + kết quả gốc

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 1 | S0–S1 | P0 | PLAT-03, DATA-02, DATA-03, EVAL-01 |

**Mục tiêu:** detector `voice_spoof` chạy thật; có số liệu R3 "trước tinh chỉnh".
**Thứ tự:**
1. S0: viết phần bọc mô hình.
2. Đầu S1: sinh `R3-baseline.md` khi đã có DATA-03 và EVAL-01.

**Đầu ra:**
- `ml/src/vericlue_ml/voice/antispoof.py`: nạp `mms-300m-anti-deepfake`, đầu vào 16 kHz mono, cửa sổ 4 giây (file dài thì trượt cửa sổ, bước 1 giây).
- `docs/status/results/R3-baseline.md`:
  - EER trên ViMD + MLAAD-vi, tách Bắc / Trung / Nam;
  - EER trên ViSpoofDB (công cụ chưa từng thấy);
  - EER ở 3 mức nén.

**Tiêu chí hoàn thành:**
- [ ] Bảng có số mẫu theo miền và theo công cụ tạo giọng.
- [ ] Im lặng hoặc quá ngắn (< 1 giây) → `status=not_applicable`.

---

### VOICE-02 · Tăng cường dữ liệu và chống "học vẹt"

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 1 | S1 | P0 | PLAT-03, DATA-01 |

**Mục tiêu:** pipeline tăng cường dùng khi tinh chỉnh, để mô hình bền với cuộc gọi, nén và tiếng ồn.
**Đọc trước:** `external/wedefense`: `codec_util.py`, `rawboost.py`.

**Đầu ra:** `ml/src/vericlue_ml/voice/augment.py`, mỗi loại dùng ở khoảng 50% mẫu, áp dụng **cho cả giọng thật lẫn giả**:
- RawBoost algo 5;
- codec: MP3, Opus 16/32 kbps, AMR-NB;
- 8 kHz + lọc 300–3400 Hz;
- MUSAN + RIR;
- tăng giảm âm lượng ±6 dB.

Thêm **chống học vẹt**: cắt khoảng lặng hai đầu (Silero VAD), chuẩn hóa độ to.

**Tiêu chí hoàn thành:**
- [ ] Test: mỗi phép biến đổi giữ độ dài và tần số lấy mẫu hợp lệ.
- [ ] Thí nghiệm nhỏ: mô hình chỉ dựa vào độ dài khoảng lặng hoặc độ to **không** đoán được nhãn (AUC ≈ 0,5) sau khi xử lý. Ghi kết quả.

---

### VOICE-03 · Tinh chỉnh AntiDeepfake cho tiếng Việt

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 2 | S1–S2 | P0 | VOICE-01, VOICE-02, DATA-03, DATA-05 |

**Mục tiêu:** giảm EER tiếng Việt; có R3 "sau tinh chỉnh".

**Các bước:**
1. **Dữ liệu:**
   - giọng thật ViMD (đều 3 miền) + VIVOS;
   - giọng giả MLAAD-vi;
   - **giữ riêng 1 hệ TTS** của MLAAD-vi để kiểm tra trên công cụ chưa từng thấy.
2. **Huấn luyện:** lr 1e-6, có tăng cường (VOICE-02), chọn checkpoint trên `calib_fit` theo `0,5·EER sạch + 0,5·EER điều kiện xấu nhất`.
3. **Đánh giá trên tập test một lần** → `R3-final.md`, tách theo miền, theo công cụ (gồm ViSpoofDB), theo mức nén.

**Tiêu chí hoàn thành:**
- [ ] Bảng trước / sau, có số mẫu và khoảng tin cậy.
- [ ] Mô hình lưu ở `models/finetuned/antideepfake-vi/<ngày>/` kèm `card.md`.

**Lưu ý:** trọng số gốc giấy phép CC BY-NC-SA, chỉ dùng phi thương mại.

**Cập nhật trưởng nhóm 17/10:**
- **Không dùng VIVOS để huấn luyện.** DATA-03 xếp VIVOS **chỉ ở test** vì là nguồn giọng thật của ViSpoofDB (huấn luyện trên VIVOS thì test ViSpoofDB gặp lại đúng người). Giọng thật để huấn luyện: **VSASV (train)** + ViMD (train).
- Test MLAAD-vi hiện chỉ có hệ TTS vixTTS (4 hệ còn lại dính một nhóm ở train) — đúng tinh thần "giữ riêng 1 hệ TTS", ghi rõ trong R3.
- **AntiDeepfake (~300 triệu tham số) không vừa RTX 4050 6 GB khi tinh chỉnh cả mô hình:** chạy thử nhỏ trên máy, chạy thật trên **Kaggle**. Cùng luật cloud như FACE-04.
- Dữ liệu small rất nhỏ (ViMD 3 người/tập): trước khi chốt R3 cuối, cân nhắc tải bản lớn hơn của ViMD, VSASV nếu ổ đĩa cho phép.

---

### VOICE-04 · Câu thử thách + nhận dạng + so khớp hai lớp

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 1,5 | S1–S2 | P0 | PLAT-03 |

**Mục tiêu:** sinh câu tiếng Việt ngẫu nhiên và kiểm tra người dùng có đọc đúng không, mà không bắt lỗi oan giọng địa phương.

**Đầu ra:** `ml/src/vericlue_ml/voice/challenge.py`, `asr.py`.
- **Ngân hàng mẫu câu:** 8–12 âm tiết, phủ đủ 6 thanh, từ thông dụng, viết số bằng chữ, tránh tên riêng. Có cặp phụ âm dễ nhầm theo miền (tr/ch, s/x, r/d/gi, n/ng cuối).
- **Nhận dạng:** PhoWhisper qua Transformers CPU và WebRTC VAD riêng (`condition_on_prev_tokens=False`, tương đương yêu cầu không điều kiện theo đoạn trước; trưởng nhóm duyệt 15/10). **Không** đưa câu đề bài làm `initial_prompt` hay hotword.
- **Chuẩn hóa:** NFC, chữ thường, bỏ dấu câu, số thành chữ, thống nhất vị trí dấu thanh (hoà/hòa).
- **So khớp hai lớp:**
  - lỗi âm tiết có dấu (jiwer) ≤ 0,3;
  - **và** độ giống khi bỏ dấu (rapidfuzz) ≥ 0,9.
- Đọc sai → được thử 1 lần nữa với câu mới.

**Tiêu chí hoàn thành:**
- [x] Test với audio TTS đọc đúng và đọc sai.
- [x] Thử với giọng thật của ViMD ở 3 miền: tỷ lệ bị bắt lỗi oan theo miền; ghi kết quả.

**Nghiệm thu 15/10:** TTS MMS đọc đúng/sai 2/2; chạy mọi câu của 12 người ViMD đã
chọn (19 câu, đã đối chiếu đủ qua 130 shard metadata). Kết quả và CP95 theo miền:
[VOICE-04.md](../../status/results/VOICE-04.md). Giữ ngưỡng theo thẻ, không chỉnh
bằng kết quả. Lỗi xử lý tính riêng và không được xem là đạt.

---

### VOICE-05 · Căn chỉnh câu, phát hiện cắt ghép, khớp môi

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 1,5 | S2 | P0 | VOICE-04, DATA-02 |

**Mục tiêu:** phát hiện giọng bị cắt ghép, và kiểm tra người trong khung hình đúng là người đang nói.

**Đầu ra:** `ml/src/vericlue_ml/voice/align.py`, `syncnet.py`.
- **Căn chỉnh câu đề bài** (không phải câu ASR nhận được) bằng `ctc-forced-aligner`. **Cờ cắt ghép:**
  - khoảng lặng giữa câu > 1 giây;
  - âm tiết < 60 ms hoặc > 1,2 giây;
  - token `<star>` chiếm đoạn dài.
- **SyncNet** (`stable_syncnet` của LatentSync) chạy **trên đúng đoạn đã căn chỉnh**, sau khi đã dò mặt: độ lệch hình–tiếng và độ tin cậy.

**Tiêu chí hoàn thành:**
- [ ] Test: audio ghép từ 2 đoạn → có cờ cắt ghép.
- [ ] Test: video lip-sync giả (DATA-04) có độ tin cậy SyncNet thấp hơn video thật (ghi số).

**Ghi chú 17/10:** LAV-DF đang bị bỏ qua ở DATA-01 (chỉ có tar 25,6 GB). Hoặc tải bản đầy đủ khi tới task này (kiểm chỗ trống ổ đĩa), hoặc chỉ dùng video lip-sync tự tạo (DATA-04).

---

### VOICE-06 · Gộp bước giọng nói vào luồng eKYC

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 0,5 | S2 | P0 | VOICE-03, VOICE-04, VOICE-05, ROUT-02 |

**Mục tiêu:** endpoint `/voice` chạy đủ chuỗi và trả `ModuleResult` cho TrustRouter.

**Đầu ra:** 3 kết quả `voice_challenge` (khớp câu + cờ cắt ghép), `voice_spoof`, `lipsync`, gọi từ orchestrator.

**Tiêu chí hoàn thành:**
- [ ] Phiên đầu–cuối với giọng thật → pass.
- [ ] Phiên với giọng clone → review.
- [ ] Chạy < 2 giây trên GPU.
