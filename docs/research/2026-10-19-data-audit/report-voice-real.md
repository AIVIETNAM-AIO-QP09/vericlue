# Rà soát GIỌNG THẬT tiếng Việt cho bước giọng của VeriClue (19/10/2026)

> Agent nghiên cứu không ghi được file này, nên phiên điều phối chép lại từ báo cáo trả về.
> Số đo gốc nằm trong các thư mục `voice_real\<bộ>\` (`measures.jsonl`, `asr*.jsonl`), và trong `voice_real_leak_auc.json` và `voice_real_leak_auc_v2.json` cùng thư mục.
> Script: `scripts\voice_real\`.
> Ổ D còn 62 GB.

## Kết luận
- **Không có bộ công khai nào khớp đủ 4 điều kiện:** micro điện thoại, câu ngắn, nhiều người có ID, có nhãn miền.
- **Lớp thật để dạy**, xếp theo thứ tự ưu tiên:
  1. **Common Voice vi**
     - Giấy phép CC0, kèm điều khoản không tìm cách xác định danh tính người nói.
     - 182 người đã duyệt; một người chiếm 56% số clip.
     - File MP3; câu ngắn khoảng 3,8 giây.
  2. **DNU-ViSpeech**
     - CC BY-NC; cấm xác thực người tham gia ngoài phạm vi đồng ý.
     - 26 người, 75,6 giờ, tự đọc câu.
     - Người 023–026 lẫn kênh.
  3. **Speech-MASSIVE vi**
     - CC BY-NC-SA.
     - Khoảng 65 người, phần lớn là người Việt sống ở nước ngoài.
  4. **FLEURS vi** — CC BY 4.0, không có ID người.
  5. **CROWS-vi** — CC BY-NC; có thể lẫn giọng TTS; phải lọc kỹ.
  6. ≤ 15% **Vietnam-Celeb / VieSpeaker** (CC BY-NC, YouTube) làm mẫu "thật khó".
- **Loại để dạy:**

  | Bộ | Lý do |
  |---|---|
  | ViMD | Giấy phép ND |
  | ViVoice-34 | Lẫn TTS, giấy phép mâu thuẫn |
  | VIVOS | Thu bằng micro chất lượng cao, quá sạch |
  | MSR-86K | Giấy phép ND |
  | DAI-ASR | Cấm dùng để huấn luyện |
  | ViSpeech | Không có giấy phép |
  | VietMed | 8 kHz |
  | SEA-Spoof | Phải được duyệt tay; cấm dùng huấn luyện mô hình thương mại |

- **VLSP2020-100h:** khoảng 20 giờ đọc bằng điện thoại, rất hợp kênh. Nhưng **chưa thấy giấy phép gốc**, nên chờ xác minh.
- **Theo miền:** không có bộ nào đúng kênh. Vietnam-Celeb (Bắc 513 / Trung 40 / Nam 447 người, YouTube) và LSVSC chỉ dùng làm số phụ.
- **Nhân bản giọng:** DNU, Common Voice (76 người có ≥ 5 clip), Speech-MASSIVE.
- **Gói tải đề xuất:** khoảng 20 GB, mất khoảng 4–5 giờ:

  | Bộ | Dung lượng |
  |---|---|
  | Common Voice | 0,43 GB |
  | Speech-MASSIVE | 0,71 GB |
  | FLEURS | 2,4 GB |
  | DNU | 8,7 GB |
  | CROWS (10 shard) | khoảng 8 GB |

## Lộ đề
- **Ở dạng gốc,** chỉ một đặc trưng đơn lẻ đã cho AUC = 1,00: sample rate (22,05 kHz chỉ có ở MLAAD), độ dài (ViSpoofDB luôn đúng 5,00 s), nền −120 dBFS (số 0 tuyệt đối), đuôi im lặng.
- **Sau chuẩn hóa v2** (16 kHz, cắt VAD, RMS −26, cửa sổ 2,5 s, thêm nhiễu SNR 15–30 dB cho cả hai lớp): AUC lớn nhất còn 0,52–0,81.
  - Phần còn sót: nhiễu nền (Vietnam-Celeb 0,81), đuôi im lặng (Common Voice 0,81).
- **Đề xuất khử lộ đề:**
  1. Đưa về 16 kHz, low-pass khoảng 7,6 kHz.
  2. Đệm bằng nhiễu thật, không đệm số 0.
  3. Cắt cửa sổ ngẫu nhiên 2–4 s.
  4. Tăng giảm âm lượng ngẫu nhiên ±10 dB.
  5. Áp cùng codec, RIR và nhiễu cho cả hai lớp.
  6. Sinh giọng giả từ chính văn bản và giọng người của tập thật.
  7. Kiểm bằng bộ phân loại "mù nội dung": AUC phải ≤ 0,6.

## Câu hỏi cho nhóm
- Có chấp nhận dữ liệu NC / NC-SA cho bản demo không?
- Có được nhân bản giọng người trong DNU / Common Voice không? Họ đồng ý cho nghiên cứu ASR, chưa chắc đã đồng ý cho deepfake.
- Có tự thu dữ liệu theo miền không?

## Phát hiện phụ
PhoWhisper bịa thêm chữ ở đoạn im lặng cuối (Common Voice 2/10, Speech-MASSIVE 3/10, DNU 3–4/10 mẫu). Liên quan VOICE-04.

(Bản đầy đủ với giấy phép trích nguyên văn và bảng số đo từng bộ nằm trong lịch sử phiên điều phối ngày 19/10.)
