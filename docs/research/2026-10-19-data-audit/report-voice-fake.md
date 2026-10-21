# Rà soát GIỌNG GIẢ tiếng Việt cho VeriClue (19/10/2026)

> Agent không ghi được file này, nên phiên điều phối chép lại.
> Số đo: `results\` (`local_files.csv`, `leak_table.md`, `shortcut_auc_{raw,norm,normcrop}.txt`, `asr_*.json`).
> Script: `scripts\`.
> Mẫu tải về: `voice_fake\`. Môi trường riêng: `envs\` (gồm `vieneu`, `tools`, `f5` cài dở).

## Các nguồn

| Nguồn | Giấy phép | Nội dung tiếng Việt | Lộ đề | Vai trò | Rủi ro |
|---|---|---|---|---|---|
| ViSpoofDB | Không có LICENSE; README chỉ ghi MIT cho code | edgetts, elevenlabs, fptai, gtts, mmstts, zaloai (khoảng 1.200 câu mỗi hệ; câu do LLM sinh) | Code ép file về 16 kHz, cắt lặng, **đệm số 0 tới đúng 5,000 s** | Test "TTS thương mại chưa từng thấy", sau khi bỏ đệm và ghép với giọng thật của mình | Giọng thật 24 kHz, **không phải VIVOS**; chưa rõ nguồn |
| SEA-Spoof | Phải được duyệt tay; chỉ nghiên cứu; **cấm voice cloning và triển khai sinh trắc học** | 81.020 câu tiếng Việt: VITS-MMS, FastSpeech2, F5, HeyGen, ElevenLabs, MiniMax, GPT-4o-mini-TTS | Chưa đo | Chỉ làm benchmark ngoài, nếu được duyệt | Điều khoản có thể cấm hệ sinh trắc học |
| MLAAD-vi | CC BY-NC | 5 hệ mã nguồn mở; 4 giọng mẫu là người đọc tiếng Anh; câu dài 3–15 s | 22,05 kHz | Dạy (4 hệ); hiệu chỉnh (vixTTS) | Lệch miền |
| VSASV | CC BY-NC, gated | Replay; khoảng 61 nghìn câu voice conversion (RVC); không có TTS | 52/150 file replay bị clip | Có thể dùng phần voice conversion | Trước đây đã loại phần này vì không xác minh được người nguồn |
| VietPrism | Chưa có | — | — | Theo dõi | — |
| SpeechFake | CC BY 4.0 | Phần tiếng Việt chỉ có Edge-TTS, nằm trong zip 115 GB | — | Bỏ | — |
| vietkemmai | Chỉ nghiên cứu | 120 câu nhân bản giọng (không rõ hệ) | Định dạng giả và thật khác nhau | Test nhỏ "ngoài đời" | — |

## Các hệ tự sinh (giấy phép code / trọng số)

| Hệ | Code | Trọng số | Ghi chú |
|---|---|---|---|
| VieNeu-TTS v3 Turbo | Apache | Apache | Nhân bản từ 3–8 s, chạy được trên CPU |
| F5-TTS-vi | MIT | CC BY-NC-SA | Có bản zalopay với trọng số CC BY 4.0 |
| ZipVoice-vi | Apache | CC BY-NC-SA | — |
| viXTTS | MPL | CPML | Kém với câu dưới 10 từ |
| OmniVoice | Apache | CC BY-NC | — |
| VoxCPM2 | Apache | Apache | Cần khoảng 8 GB VRAM → chạy trên Kaggle |
| LEMAS | CC BY | CC BY | — |
| VietTTS | Apache | CC BY-NC | — |
| OpenVoice V2 | MIT | MIT | Voice conversion |
| RVC | MIT | — | Voice conversion |
| Seed-VC | GPL-3.0 | — | Chỉ chạy tách rời, không đưa vào repo |

Không hỗ trợ tiếng Việt: CosyVoice, Fish-Speech, Chatterbox, Qwen3-TTS, Spark-TTS.

## Đã chạy thử
- **VieNeu v3 Turbo** (CPU): nhân bản 3 giọng VIVOS và 1 giọng VSASV, sinh 15 câu 8–12 âm tiết, mỗi câu 2–5 s.
  - **PhoWhisper nghe đúng 12/15 câu** (tỉ lệ lỗi âm tiết 0,022). Nghĩa là **bước đọc câu thử thách không chặn được giọng nhân bản**; phải dựa vào bộ phát hiện giọng giả.
- **F5-TTS-vi**: dừng giữa chừng vì không tải hết trọng số.

## Lộ đề
- **Dữ liệu gốc:** chỉ cần 10 đặc trưng thô của file, một bộ phân loại đơn giản đã tách thật/giả với **AUC 0,90–1,00 ở cả 39 cặp** nguồn thật × nguồn giả.
- **Sau chuẩn hóa** (16 kHz, cắt lặng, cân độ to): AUC vẫn 0,86–1,00.
- **Cắt 2 s giữa vùng tiếng nói + thêm nhiễu 30 dB:** AUC còn 0,53–0,99. gTTS, ElevenLabs và Edge vẫn cao.
- **Quy trình đề xuất:**
  1. Đưa về 16 kHz mono, bỏ đoạn số 0 ở hai đầu, không bao giờ đệm 0.
  2. Cắt bằng VAD giống đường chạy thật, lấy cửa sổ tiếng nói cố định.
  3. Cân RMS, lọc thấp khoảng 7 kHz.
  4. Cùng một bộ tăng cường cho cả hai lớp: nhiễu, tiếng vang, codec. Với lớp giả, thêm phát lại rồi thu lại.
  5. **Chạy lại `shortcut_auc.py`; mục tiêu AUC ≤ 0,65.**

## Phân vai đề xuất
- **Dạy:** tự sinh bằng cách **nhân bản người trong tập dạy**, dùng VieNeu v3, F5-vi (zalopay) và OmniVoice/VoxCPM2; thêm OpenVoice (voice conversion); cộng 4 hệ của MLAAD-vi.
- **Chọn / hiệu chỉnh:** viXTTS và ZipVoice-vi, nhân bản người ở tập hiệu chỉnh.
- **Test hệ chưa từng thấy:** ViSpoofDB (đã chuẩn hóa, ghép với giọng thật test của mình); thêm khoảng 200 câu mỗi API thương mại (FPT, Viettel, Google; trong hạn mức miễn phí); thêm vietkemmai. Không hệ nào ở test có mặt ở dạy hoặc hiệu chỉnh.
- **Quy mô:** khoảng 60 người × 3 hệ × 15 câu ≈ 2.700 câu giả để dạy, chia người 70/15/15. Lọc giữ các câu có tỉ lệ lỗi âm tiết ≤ 0,2. Dùng kho câu riêng, không dùng `phrases.py` của demo.

## Câu hỏi cho nhóm
- Sửa `vispoofdb/SOURCE.md` (nguồn giọng thật không phải VIVOS).
- Có xin quyền SEA-Spoof không, khi điều khoản cấm triển khai sinh trắc học?
- Đọc điều khoản dịch vụ của các API TTS thương mại trước khi gọi.
- Dọn các thư mục: `m\f5vi` (1,7 GB), `hfc`, `h`, `voice_fake\_normprobe*` (540 MB).
