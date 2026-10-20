# ADR-0015: Chọn mô hình và kế hoạch tinh chỉnh trên dữ liệu người Việt

- **Trạng thái:** đã chấp nhận (18/10). **Phần dữ liệu được thay bởi mục "Cập nhật 19–20/10" ở cuối.**
- **Ngày:** 2026-10-18
- **Người quyết định:** Trưởng nhóm cùng phiên điều phối
- **Căn cứ:** hai báo cáo tra cứu ngày 18/10, gồm "mô hình SOTA ở server" và "mô hình chạy trên điện thoại". Số liệu đã kiểm ở nguồn có ghi link trong báo cáo. Hai báo cáo này lưu trong bàn giao LEAD.

## Bối cảnh
Trưởng nhóm muốn dùng mô hình tốt nhất hiện nay. Mọi mô hình quyết định chạy ở server (ADR-0014). Server demo là một GPU RTX 4050 6 GB. Mô hình phải thỏa đủ các điều kiện:
- có trọng số công khai;
- giấy phép không thuộc GPL/AGPL/LGPL và repo phải có LICENSE;
- vừa VRAM cùng các mô hình khác;
- mỗi bước chạy dưới 4 giây;
- kịp tích hợp trước 06/11.

## Quyết định — chọn mô hình
| Module | Quyết định | Ghi chú |
|---|---|---|
| Deepfake mặt | **Giữ GenD CLIP-L/14** | AUROC trung bình trên 14 bộ là 91,2, so với Effort 88,5. Các bản mới hơn chỉ hơn ≤ 0,4 điểm. |
| Giọng giả | **Giữ AntiDeepfake MMS-300M, bắt buộc tinh chỉnh tiếng Việt** | Bản 1B tốt hơn một chút nhưng không vừa 6 GB. |
| PAD | **Giữ MiniFASNet, thêm tầng 2 DINOv2-reg ViT-B/14** | DINOv2-reg dẫn đầu trong 15 mô hình nền ở bài khảo sát FAS. Chưa có bản FAS công khai nên phải tự tinh chỉnh. Giữ phương án nào thắng trên `calib_fit`. |
| So mặt 1:1 (mới) | **Thêm AdaFace IR101 (CVLFace)** | Dự phòng có giấy phép sạch: **SFace** (Apache-2.0). Trọng số AdaFace coi là phi thương mại. |
| ASR, khớp môi, dò mặt, căn câu, thủy vân | **Giữ** PhoWhisper, SyncNet, SCRFD, CTC aligner, AudioSeal | Không có ứng viên vừa tốt hơn rõ rệt vừa dùng được. **Kiểm lại giấy phép PhoWhisper**: manifest ghi BSD-3, nhưng một nguồn ghi Apache-2.0. |
| Trên điện thoại | MediaPipe Face Landmarker, OpenCV, thư viện đọc QR | Chỉ dùng để hướng dẫn người dùng. |

**Nguyên tắc đổi mô hình:** chỉ đổi khi ứng viên **thắng rõ trên `calib_fit` tiếng Việt**. Không đổi chỉ vì bảng xếp hạng.

## Quyết định — tinh chỉnh
- **Toàn bộ việc tinh chỉnh chạy trên Colab hoặc Kaggle**, kể cả PAD. Laptop chỉ dùng để chạy demo và thử nhỏ.
- Mỗi notebook:
  - kéo repo đúng commit;
  - dữ liệu để Private;
  - token đặt trong Secrets;
  - chọn checkpoint chỉ trên `calib_fit`.
  
  Trọng số mang về `MODELS_DIR/finetuned/<tên>/<ngày>/`, kèm SHA-256 và `card.md`. Không commit trọng số.
- **Không thu dữ liệu bằng tay** (quyết định 17/10). Nguồn dữ liệu gồm:
  - bộ công khai, có tải thêm bản lớn của ViMD;
  - **dữ liệu do máy tự sinh**: giọng TTS tiếng Việt (DATA-06) và deepfake người nổi tiếng công khai chạy theo lô (DATA-04).

| Thứ tự | Mô hình | Phần được dạy | Dữ liệu |
|---|---|---|---|
| 1 | AntiDeepfake MMS-300M | Toàn bộ, lr ~1e-6, có tăng cường (VOICE-02) | **Thật:** VSASV (bỏ replay), ViMD bản lớn. **Giả:** MLAAD-vi, TTS tự sinh. **Test:** ViSpoofDB. |
| 2 | MiniFASNet và DINOv2-reg | MiniFASNet: toàn bộ. DINOv2: lớp cuối và vài khối cuối | Zalo 2022 train, CelebA-Spoof (chỉ dùng nghiên cứu). **Test:** FAS-VN. |
| 3 | GenD | LayerNorm và lớp cuối (theo bài báo) | **Thật:** video selfie Zalo, vn_celeb. **Giả:** DATA-04. **Test:** RTFS-10k, WildDeepfake. |
| — | AdaFace | Không tinh chỉnh | Chọn ngưỡng trên các cặp vn_celeb, chia theo người. |

Sau khi tinh chỉnh:
- ROUT-01 fit calibrator thật trên `calib_fit`, thay calibrator identity (ADR-0012);
- ROUT-03 chọn ngưỡng bằng LTT trên `calib_ltt`, **riêng cho từng `purpose`**;
- ROUT-05 làm R4.

Tập test chỉ chạy **một lần**, sau khi đã chốt mô hình.

## Rủi ro
- **Giấy phép:** phần lớn trọng số tốt nhất là phi thương mại: SCRFD, AdaFace, AntiDeepfake, MMS aligner, CelebA-Spoof. Dùng cho cuộc thi được, nhưng phải ghi trong `third_party/README.md`. Báo cáo cần có mục lộ trình thương mại hóa với bộ thay thế sạch: SFace, YuNet, MiniFASNet, PhoWhisper, GenD, AudioSeal.
- **VRAM:** thêm AdaFace và DINOv2 sẽ lên khoảng 5/6 GB. Phải đo thực tế. Nếu thiếu, chuyển các mô hình nhỏ sang CPU.
- **Dữ liệu:** SEA-Spoof chưa chắc tải được. Phương án chắc chắn là TTS tự sinh.

## Cập nhật 19–20/10 — dữ liệu (thay bảng dữ liệu ở trên)
Căn cứ:
- rà soát 13 bộ dữ liệu, có xem ảnh, nghe và đo đạc: `scratchpad/audit`;
- nghiên cứu 4 mảng dữ liệu: `scratchpad/dsresearch`.

Trong cả hai, phiên điều phối đã tự xem lại ảnh ghép và tự đo lại các điểm then chốt.

**Phát hiện buộc phải đổi kế hoạch:**
- Zalo 2022: 63/64 khung đeo khẩu trang.
- FAS-VN lộ đề qua chiều rộng ảnh và EXIF (AUC 0,99); có ảnh trùng mang hai nhãn; cặp ảnh gốc/chụp lại bị tách sang hai tập.
- ViSpoofDB: giọng giả luôn dài đúng 5,000 s, 16 kHz, trong khi giọng thật 24 kHz; giọng thật không phải VIVOS.
- mms-tts-vie chỉ có 1 giọng.
- ViCocktail chỉ có vùng miệng.
- WildDeepfake là mặt cắt sát từ phim.

| Mô hình | Dạy | Chọn / hiệu chỉnh | Test |
|---|---|---|---|
| **AntiDeepfake** | Giọng thật: Common Voice vi, DNU-ViSpeech, Speech-MASSIVE vi, FLEURS vi. Giọng giả: **nhân bản chính những người thật trong tập dạy** (VieNeu v3, F5-TTS-vi, OmniVoice, OpenVoice), cộng 4 hệ của MLAAD-vi | Người khác trong cùng các bộ; giọng giả tạo bằng hệ khác (viXTTS, ZipVoice) | ViSpoofDB (sau khi khử lộ đề), MLAAD vixTTS, vietkemmai. Đo theo miền: Vietnam-Celeb |
| **PAD** (MiniFASNet + DINOv2) | **FAS-VN đã làm sạch và chia lại theo người** | FAS-VN (calib_fit/calib_ltt của cách chia mới) | FAS-VN (phần test của cách chia mới). Test phụ: Axon (theo từng loại tấn công), UniData Asian, Zalo (khẩu trang) |
| **GenD** | **Không tinh chỉnh** | **Chỉ hiệu chỉnh**: thật = FAS-VN live + video gốc RTFS; giả = RTFS (nén lại đồng nhất) | Phần test của RTFS theo cách chia mới; WildDeepfake (phụ) |
| **AdaFace** | — | VN-Celeb gốc đã làm sạch, cộng các cụm FAS-VN | Phần người không trùng |

**Kết hợp PAD:**
- Mỗi mô hình hiệu chỉnh riêng.
- Điểm PAD = max(p_MiniFASNet, p_DINOv2), giống fusion của TrustRouter.
- Chỉ dùng cả hai nếu kết hợp thắng mô hình đơn tốt nhất trên calib_fit ở BPCER ≤ 1%.
- Nếu dùng cả hai, thêm DINOv2 làm một mô-đun mặt ở server.

**Không dùng:**

| Bộ | Lý do |
|---|---|
| CelebA-Spoof | 77 GB, không đủ chỗ → thiếu mẫu ảnh in, ghi là giới hạn |
| ViCocktail, vn_celeb bản HF, ViMD (để dạy), VIVOS (để dạy), ViVoice-34, CROWS, SEA-Spoof | Xem lý do trong báo cáo rà soát |
| **ForgeryNet** | Phần dạy cần tài khoản OpenDataLab hoặc 115 |
| **DFDC** | Luật cuộc thi chỉ cho dùng trong cuộc thi; điều khoản Meta §6G cấm dùng cho sinh trắc học |
| Bản sao FF++ trên Kaggle | Phân phối lại trái điều khoản |

**Không tự tạo deepfake người thật (DATA-04 cũ bị hủy).** Người trong VLR hay người nổi tiếng đều không đồng ý; hệ thống an toàn của AI đã chặn đúng việc này. Thay bằng:
- dữ liệu nghiên cứu có sẵn;
- gửi đơn DeepSpeak / Celeb-DF++ nếu có email trường.

**Cách chia tập chuẩn (luật 8):**
- `splits.csv` do notebook PAD (FAS-VN) và notebook hiệu chỉnh GenD (RTFS, FAS-VN live) tạo ra, có in SHA-256, là **cách chia chuẩn duy nhất** cho mọi phép đo sau trên các bộ này (R1, R2, đánh giá PAD).
- Cách chia gốc của bộ và cách chia DATA-03 cũ **không được dùng** cho FAS-VN và RTFS.
- Ảnh đã dùng để dạy hoặc hiệu chỉnh không bao giờ được vào tập đo.
- Hai notebook phải dùng **cùng** một cách chia FAS-VN. Nếu không cùng, ghi rõ và tách bộ đo.

**Quy tắc chung:**
- Thật và giả đi qua cùng một đường xử lý.
- Kiểm lộ đề bằng mô hình chỉ dùng siêu dữ liệu (AUC ≈ 0,5–0,65) trước khi dạy.
- Chia theo người và theo công cụ / hệ TTS.
- Dữ liệu chỉ lấy trên Kaggle/Colab (notebook tự lấy); không thu dữ liệu tay.
