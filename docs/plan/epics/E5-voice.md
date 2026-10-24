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

**Phạm vi PR wrapper (quyết định trưởng nhóm 17/10):** chỉ bước 1; giữ VOICE-01 chưa done.
Runtime Transformers ánh xạ checkpoint Fairseq trong RAM, kiểm SHA và không thiếu khóa.
Fairseq chỉ ở môi trường Linux riêng để kiểm parity logits ≤ 1e-4; parity là điều kiện
bắt buộc trước R3-baseline. Bốn file smoke TTS/thật chỉ kiểm chiều điểm, không phải R3.

**Đầu ra:**
- `ml/src/vericlue_ml/voice/antispoof.py`: nạp `mms-300m-anti-deepfake`, đầu vào 16 kHz mono, cửa sổ 4 giây (file dài thì trượt cửa sổ, bước 1 giây).
- `docs/status/results/R3-baseline.md`:
  - EER trên ViMD + MLAAD-vi, tách Bắc / Trung / Nam;
  - EER trên ViSpoofDB (công cụ chưa từng thấy);
  - EER ở 3 mức nén.

**Tiêu chí hoàn thành:**
- [ ] Bảng có số mẫu theo miền và theo công cụ tạo giọng.
- [x] Im lặng hoặc quá ngắn (< 1 giây) → `status=not_applicable`.

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
| M4 | 2 | S1–S2 | P0 | VOICE-01, VOICE-02, DATA-03, DATA-05, DATA-06 |

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

**Cập nhật trưởng nhóm 18/10 (ADR-0015):**
- Giọng AI dùng để huấn luyện gồm thêm **TTS tiếng Việt tự sinh** (DATA-06). Giọng thật lấy thêm từ **ViMD bản lớn**. Không thu âm tay.
- **Huấn luyện thật chạy trên Colab hoặc Kaggle.** Laptop chỉ dùng để chạy thử nhỏ.
- Bằng chứng từ MVP 18/10: mô hình chưa tinh chỉnh chấm giọng mms-tts-vie lúc 0,84, lúc 0,38, lúc 0,115 tùy câu. Đây là thử tay, không phải R3.

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

**Vá 18/10:** giới hạn số token PhoWhisper theo số âm tiết đề bài, chống lặp 8 token, lỗi nếu chạm trần; không truyền nội dung đề bài vào ASR, không đổi ngưỡng. Wrapper voice04-v2; task đã nghiệm thu vẫn giữ done.

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
- [x] Test: audio ghép từ 2 đoạn → có cờ cắt ghép.
- [ ] Test: video lip-sync giả (DATA-04) có độ tin cậy SyncNet thấp hơn video thật (ghi số).

**MVP đợt 2, 18/10:** đã cắm lõi CTC + stable SyncNet offline, lipsync trở lại
hồ sơ MVP chạy tham khảo (ADR-0012 §6), identity v2 tạm; cờ cắt ghép đi qua evidence của lipsync. Lượt thử tay
chỉ kiểm luồng trên một clip có sẵn, không fit/chia tập hoặc làm kết quả R. Task
vẫn `doing`: chưa nghiệm thu tiêu chí DATA-04/độ chính xác ở trên. Xem
[bàn giao VOICE-05](../../status/handoffs/2026-10-18-1247-voice-05-m4-codex.md).
**Vá demo 18/10:** `LIPSYNC_DEVICE=cpu` tách SyncNet/CTC/SCRFD lipsync khỏi `DEVICE`; nạp lười lần dùng đầu, không chiếm GPU khi khởi động. VOICE-05 vẫn `doing`.
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

---

### VOICE-07 · Qwen3-ASR: backend kiểm câu đọc — diagnostic riêng

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 1 | S2 | P0 | PLAT-03, VOICE-04 |

**Mục tiêu:** dùng checkpoint Qwen3-ASR-0.6B-hf đã chọn/tải để nhận dạng và
đối chiếu câu, không đổi runtime mặt hoặc thay backend PhoWhisper đã nghiệm thu.
Task mở rộng theo yêu cầu tiếp tục triển khai ngày 24/10; không mở lại các số
liệu VOICE-04 và không coi benchmark cũ là nghiệm thu Qwen.

**Đầu ra:** `voice/qwen_asr.py`, config hash, factory/mock, CLI
`eval/qwen_voice.py`, runtime CPU pin riêng và hướng dẫn chạy local.

**Tiêu chí review phần kỹ thuật:**
- [x] Kiểm file/runtime, tải offline một lần, CPU, serialize inference, không remote code.
- [x] Audio có giới hạn; VAD; không đưa đề bài vào model; budget/EOS fail-closed.
- [x] `ModuleResult` và mock; giữ luật so khớp hiện có, không thay ngưỡng/API.
- [x] CLI xuất metadata/hash/nguồn câu, chặn đổi file và ghi đè input/model.
- [x] Unit/hồi quy qua; checkpoint thật chạy generation tổng hợp và chặn im lặng.
- [x] Tài liệu/bàn giao/backlog/lint/plan_check đầy đủ.

**Ngoài nghiệm thu kỹ thuật này:** độ chính xác tiếng Việt, công bằng miền,
đánh giá trên người, so sánh PhoWhisper, tối ưu GPU/ONNX/INT8 và nối API cần
đánh giá riêng trước khi sử dụng. Không tuyên bố đã phát hiện giọng AI/khớp môi.

---

### VOICE-08 · Thử câu đọc bằng microphone trên laptop

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 0,5 | S2 | P0 | VOICE-07 |

**Mục tiêu:** sau khi VOICE-07 được merge, cho nhóm tự thu và đối chiếu câu
trực tiếp trong công cụ nội bộ; dùng runtime Qwen riêng, không sửa UI sản phẩm.

**Tiêu chí hoàn thành:**
- [x] Micro chỉ mở theo nút bấm; dừng/hủy/đóng cửa sổ giải phóng stream, giới hạn 20 giây.
- [x] Audio trong RAM, VAD/ASR và luật khớp dùng chung backend; lỗi/overflow không đạt.
- [x] UI không bị khóa khi nạp/suy luận; không chồng lượt, bỏ kết quả đã hủy.
- [x] Hiện transcript/chỉ số đúng nghĩa; JSON tùy chọn có commit/model/hash/runtime/số mẫu.
- [x] Test không dùng micro/model; QA cửa sổ tổng hợp, lint/plan_check và bàn giao.

Không nghiệm thu accuracy trên người, phát hiện giọng AI, nhịp đọc, khớp môi
hay quyết định eKYC. Câu local không phải thử thách được server xác thực.
