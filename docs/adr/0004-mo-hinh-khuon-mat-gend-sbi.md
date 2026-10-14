# ADR-0004: Phát hiện deepfake khuôn mặt bằng GenD (chính) + SBI (dự phòng)

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Bối cảnh

Cần mô hình có trọng số sẵn, khái quát tốt trên dữ liệu lạ, có giấy phép rõ ràng, và bắt được ghép mặt kiểu Deep-Live-Cam.

## Quyết định

- **GenD** (`yermandy/GenD_CLIP_L_14`, WACV 2026, giấy phép MIT) là mô hình chính:
  - trung bình AUC trên 14 bộ dữ liệu cao nhất trong các mô hình đã khảo sát;
  - chỉ cần tinh chỉnh LayerNorm và lớp cuối.
- **SBI** (`FFc23`, chỉ dùng cho nghiên cứu) làm dự phòng và nguồn heatmap. Mô hình này chuyên bắt đường hòa trộn khi dán mặt.
- **PAD:** MiniFASNet (qua `uniface`, MIT).
- **Điểm video:** trung bình 32 khung **và** trung bình 25% khung nghi nhất.

## Phương án đã cân nhắc

- **Effort** (ICML 2025): tốt nhưng giấy phép chỉ dùng phi thương mại → giữ làm đối chứng.
- **DeepfakeBench:** nặng, chỉ dùng phi thương mại.
- **Các bộ phát hiện ảnh AI chung** (UnivFD…): yếu với ghép mặt.

## Hệ quả

- Phải dùng đúng tiền xử lý của GenD (SCRFD, căn chỉnh 5 điểm, tỷ lệ 1,3, 224 px).
- SCRFD (insightface) và SBI chỉ dùng phi thương mại → ghi trong bảng giấy phép.
