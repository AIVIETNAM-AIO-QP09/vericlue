# ADR-0005: Giọng giả tiếng Việt bằng NII AntiDeepfake; kiểm tra câu đọc 8 bước

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Quyết định

- **Mô hình nền:** `nii-yamagishilab/mms-300m-anti-deepfake`.
  - Đã học hơn 100 ngôn ngữ, 74 nghìn giờ âm thanh.
  - Trọng số CC BY-NC-SA.
- **Tinh chỉnh:** trên giọng thật ViMD (lấy đều ba miền) và giọng giả MLAAD `fake/vi`.
- **Kiểm tra trên công cụ chưa từng thấy:** ViSpoofDB (FPT.AI, Viettel, ElevenLabs).
- **Tăng cường dữ liệu** theo công thức wedefense: RawBoost; codec Opus 16–32 kbps, AMR, MP3; lấy mẫu 8 kHz; MUSAN và RIR.
- **Chống "học vẹt":** cắt khoảng lặng hai đầu, cân bằng âm lượng.
- **Kiểm tra câu đọc:**
  1. Câu đề bài phủ đủ 6 thanh.
  2. PhoWhisper nhận dạng, **không** đưa câu đề bài làm gợi ý cho ASR.
  3. So khớp hai lớp: lỗi âm tiết có dấu ≤ 0,3 **và** độ giống khi bỏ dấu ≥ 0,9.
  4. `ctc-forced-aligner` căn chỉnh chính câu đề bài để phát hiện cắt ghép.
  5. SyncNet (`stable_syncnet`) kiểm tra khớp môi trên đúng đoạn đã căn chỉnh.

## Hệ quả

- Báo cáo EER tách theo Bắc / Trung / Nam và theo từng công cụ tạo giọng.
- Trọng số chỉ dùng phi thương mại → ghi rõ trong báo cáo.
