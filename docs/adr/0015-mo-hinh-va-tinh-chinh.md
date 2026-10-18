# ADR-0015: Chọn mô hình và kế hoạch tinh chỉnh trên dữ liệu người Việt

- **Trạng thái:** đã chấp nhận (18/10)
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
