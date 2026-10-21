# Dữ liệu deepfake mặt (GenD) và so mặt 1:1 (AdaFace) — 19/10/2026

> Agent không ghi được file này, nên phiên điều phối chép lại.
> Số đo và ảnh ghép: `deepfake_facematch\` (`vlr\`, `openforensics\`, `fas_vn_pairs*\`, `rtfs_leak.csv`). Script: `scripts\`.
> Phiên điều phối đã tự xem `vlr\sheet_vlr_p1_p4.jpg`: người Việt, không khẩu trang, mặt chính diện; nhiều clip trùng người.
> Phiên điều phối đã tự gọi Zenodo API cho record 19705466: license `cc-by-4.0`, `access: open`, 7 part (9–11 GB mỗi part).

## (A) GenD — bộ deepfake có sẵn
- **Không có** bộ deepfake mặt người Việt hay Đông Nam Á công khai.
- Các bộ châu Á:
  - KoDF: người Hàn, phải điền form, chỉ mở theo đợt.
  - DeeperForensics: 40% diễn viên châu Á, nhưng chỉ có phương pháp DF-VAE năm 2020.
- **Gần mối đe dọa nhất:** DeepSpeak v1/v2. Quay bằng webcam; thật và giả cắt từ cùng một bản ghi; công cụ gồm FaceFusion Live, LatentSync, SimSwap. Phải điền form, chỉ cấp cho đơn vị học thuật; bản v2 nặng 134 GB.
- **DF40:** 40 phương pháp, CC BY-NC, phải điền form, cần thêm FF++. **Celeb-DF++:** 22 phương pháp, CC BY-NC, phải điền form; hợp làm TEST.
- Không có bộ công khai nào về ghép mặt thời gian thực qua camera ảo trên selfie điện thoại.
- **RTFS-10k lộ đề qua bitrate:** video thật 1.258 kbps, video giả khoảng 430 kbps (AUC 0,88–0,89); độ nét cho AUC 0,79–0,84. Phải nén lại cả hai lớp theo cùng cấu hình trước khi dùng.
- **OpenForensics:** chỉ có ảnh tĩnh, gần như toàn người da trắng, giấy phép ghi mâu thuẫn. Loại.

## (A) Tạo DATA-04
- **Nguồn THẬT: VLR**
  - Zenodo 19705466, CC BY 4.0, truy cập mở, khoảng 116 nghìn clip YouTube tiếng Việt, mặt chính diện, 320×320.
  - **Đã bỏ âm thanh**, không có nhãn người nói.
  - SCRFD dò được mặt ở 100% trong 100 clip mẫu.
  - Part 4 đa dạng nhất; part 7 gần như chỉ có 1 người, nên bỏ.
- **Công cụ để DẠY** (chạy trong FaceFusion):

  | Công cụ | Loại | Giấy phép |
  |---|---|---|
  | hyperswap_1a_256 | Ghép mặt (2025) | "ResearchRAIL" — chưa tìm được toàn văn |
  | ghost_2_256 | Ghép mặt | Apache-2.0 |
  | MuseTalk 1.5 | Lip-sync | Code MIT; trọng số ghi "any purpose"; chạy được trên GPU 4 GB |

- **Công cụ GIỮ RIÊNG để TEST:** blendswap_256 (NC) và LatentSync 1.5 (cần 8 GB, chạy trên Kaggle T4). Thêm RTFS (inswapper, uniface) làm test ngoài.
- **Không dạy bằng họ inswapper** (Deep-Live-Cam là AGPL; roop; Rope).
- **Quy mô:**
  - ≥ 60 người nói × ≤ 10 clip 3 giây ≈ 600 clip thật, chia theo người 60/20/20.
  - Giả và thật cắt từ **cùng một clip**.
  - Mọi clip đi qua cùng một lần mã hóa lại.
  - Chỉ dạy khi AUC lộ đề nằm trong khoảng 0,4–0,6.
  - Chạy thử 20 clip trước để đo VRAM và tốc độ.

## (B) AdaFace — dữ liệu chọn ngưỡng so mặt
- Không có bộ CCCD–selfie người Việt công khai.
  - Public-IvS: trang không mở được.
  - IJB: đã ngừng phát hành.
  - RFW: phải gửi email bằng địa chỉ cơ quan.
- **VN-Celeb gốc:** 1.020 người, 23 nghìn ảnh web. Không có giấy phép, chỉ ghi "cho học tập và nghiên cứu".
- **FAS-VN có ảnh lặp người:** 546 cụm (cos ≥ 0,6), 12/12 cặp đã xem là cùng người ở các phiên chụp khác nhau. Dải cos 0,45–0,6 lẫn lộn, cần người duyệt tay.
- **Đề xuất:**
  - Chọn ngưỡng trên VN-Celeb đã làm sạch, cộng các cụm FAS-VN đã được duyệt tay.
  - Biến đổi ảnh phía "ID" cho giống ảnh CCCD: nền xanh hoặc trắng, cắt 3×4, làm mờ, nén JPEG 40–70, méo phối cảnh.
  - Mục tiêu FAR 1e-3.
  - TEST trên người không trùng với tập chọn ngưỡng, cộng RFW-Asian nếu được duyệt.

## Pháp lý
Theo nguồn thứ cấp: Luật 91/2025/QH15 và Nghị định 356/2025 có hiệu lực từ 01/01/2026, thay thế Nghị định 13/2023. **Cần kiểm lại văn bản gốc.**
