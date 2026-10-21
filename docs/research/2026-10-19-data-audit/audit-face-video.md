# Kiểm toán dữ liệu mặt dạng video: Zalo 2022, RTFS-10k, WildDeepfake, ViCocktail (+ LAV-DF)

Ngày: 19/10/2026. Chỉ đọc: không sửa repo, không sửa hay xóa file trong `D:\Projects\vericlue-store`. Archive được đọc thẳng trong bộ nhớ.
Tìm mặt bằng SCRFD `det_10g` rev `bfcc7d48` (`vericlue_ml.face.pad.ScrfdFaceFinder`, CUDA, ngưỡng 0,5, tiền xử lý FACE-01).
Mọi số liệu dưới đây lấy từ script trong thư mục này (thư mục audit):

| Script | Đầu ra |
|---|---|
| `audit_common.py` | Hàm dùng chung: lấy 3 khung ở 10/50/90 % video, Laplacian, độ sáng, SCRFD, đoán khẩu trang thô, AUC đơn biến |
| `audit_zalo.py`, `zalo_rot.py` | `zalo_metrics.json`, `zalo_rot.json`, `zalo_real.jpg`, `zalo_fake.jpg`, `zalo_rotated.jpg` |
| `audit_rtfs.py` | `rtfs_metrics.json`, `rtfs_real.jpg`, `rtfs_inswapper.jpg`, `rtfs_uniface.jpg`, `rtfs_pairs.jpg` |
| `audit_wild.py` | `wild_metrics.json`, `wild_real.jpg`, `wild_fake.jpg` |
| `audit_vicocktail.py` | `vicocktail_metrics.json`, `vicocktail_sheet.jpg` |
| `analyze_facevideo.py` | `analyze_facevideo.log`: bảng phân bố và AUC |

**Cách đọc AUC:** "AUC" là AUC đơn biến giữa nhãn giả và nhãn thật. "sep" = max(AUC, 1 − AUC). Từ 0,7 trở lên coi là lộ đề đáng lo.

---

## 1. Zalo AI 2022 Liveness (`zalo2022`)

**Cấu trúc thực tế**
- Có `train/train/label.csv` và 1.168 file mp4. Nhãn `liveness_score`: 598 thật (1), 570 giả (0).
- Có thêm `.cache/liveness-detection-zalo-2022.zip` (2,8 GB). Trong zip có `public_test` (350), `public_test_2` (486) và `private_test` (1.253 video). Các phần này **không có nhãn**.
- Không có subject_id.
- Loại tấn công: trang Kaggle ghi tiêu đề phụ "Replay-attack Video Anti-Spoofing Dataset". Mô tả: video selfie hoặc chân dung 1–5 giây, dùng cho eKYC.
- Công cụ giả: không có (đây là PAD, không phải deepfake).
- Âm thanh: 8/598 video thật có track âm thanh, **0/570 video giả có**.

**Xem bằng mắt.** Đã xem 32 thật + 32 giả, chọn ngẫu nhiên seed 42, khung giữa (`zalo_real.jpg`, `zalo_fake.jpg`). Đã xem thêm 48 video bị SCRFD đánh dấu là xoay (`zalo_rotated.jpg`).
- **Khẩu trang:** 32/32 thật đeo khẩu trang y tế hoặc KF94. Phần giả: 31/32 đeo khẩu trang; ô còn lại (`1868.mp4`) là khung không có mặt, chỉ có 3 chấm đen.
  - Bộ đoán khẩu trang thô theo màu da chỉ báo 58–67 %, tức là **đánh giá thấp**. Không dùng số đó, dùng số đếm bằng mắt.
- **Người trong ảnh:** người Việt trẻ, khoảng 18–30 tuổi (sinh viên, áo đồng phục), trong nhà, camera trước điện thoại, khung dọc, nửa thân trên, mặt chiếm khoảng 50 % cạnh ngắn.
- **Video giả:** quay lại màn hình. Thấy moiré, lóa, viền màn hình, màu bệt, ảnh nghiêng. Một vài video giả rất giống thật (`1803.mp4`). Logo "Zalo AI" xuất hiện trên áo ở `175.mp4` (giả).
- **Lộn ngược:** khoảng 30 video **thật** bị quay lộn ngược 180°. Trong sheet đã xem 32 video thật bị gắn rot180; 29 video thật sự lộn ngược, 3 video đứng thẳng (báo nhầm). Không thấy video giả nào lộn ngược: 5 video giả bị gắn rot180 đều đứng thẳng khi xem.

**Đo định lượng** (1.168 video, mỗi video 3 khung)
- **Độ phân giải:**
  - Thật: 303 video 1080×1920, 91 video 720×1280, 111 video khoảng 480×852, 27 video 4K.
  - Giả: 290 video khoảng 480×852, 192 video 1080×1920, 73 video 720×1280, 0 video 4K.
- **fps:** khoảng 30. fps 32: 102 video thật so với 270 video giả.
- **Thời lượng:** khoảng 5 giây.
- **Metadata xoay:** OpenCV đọc được 0 ở mọi video. Phần lộn ngược nằm sẵn trong điểm ảnh, không ghi trong metadata.
- **SCRFD:** không thấy mặt ở 9 video thật và 11 video giả. Thấy mặt ở một phần số khung: 24 video thật và 35 video giả.
  - Kiểm tra 4 hướng (`zalo_rot.py`): SCRFD chọn khung xoay 180° ở 33 video thật và 5 video giả. Theo xem bằng mắt, 5 video giả này là báo nhầm.
- **Cỡ mặt:** cạnh ngắn của mặt chiếm trung vị 0,49 (thật) và 0,54 (giả) cạnh ngắn của khung.

**Lộ đề (shortcut)**
- **Thời lượng: sep = 0,80.** 417/598 video thật dài hơn 5,03 giây; chỉ 49/570 video giả như vậy. Video giả gần như đúng 5,00 giây.
- Bitrate: sep 0,66. Kích thước file: 0,66. Độ phân giải: 0,64. fps: 0,66. Diện tích mặt: 0,61. Laplacian và độ sáng: khoảng 0,53.
- Đặc trưng nhị phân tách nhãn hoàn toàn trong phần nhỏ dữ liệu:
  - 4K: 27 thật, 0 giả.
  - Có âm thanh: 8 thật, 0 giả.
  - Lộn ngược: khoảng 30 thật, khoảng 0 giả.

**Giấy phép:** bản mirror Kaggle ghi MIT. Điều khoản gốc của Zalo AI Challenge chưa rõ.

**Đối chiếu SOURCE.md:** khớp phần "replay, selfie eKYC". SOURCE.md **không nhắc** khẩu trang, không nhắc chuyện chỉ có replay (không có ảnh in), không nhắc video lộn ngược.

**Kết luận vai trò**
- **Không nên dùng làm nguồn chính để dạy PAD** cho người dùng không đeo khẩu trang. Nếu vẫn dùng thì chỉ để tinh chỉnh hoặc chọn mô hình, kèm các biện pháp sau:
  - (a) Chuẩn hóa thời lượng, fps và độ phân giải, bỏ âm thanh, rồi mới cắt mặt.
  - (b) Xoay thẳng bằng landmark, hoặc lọc bỏ video lộn ngược.
  - (c) Chỉ đưa vào mô hình **vùng mặt đã cắt**, không đưa cả khung.
  - (d) Đánh giá thêm trên dữ liệu không khẩu trang (FAS-VN, dữ liệu tự quay).
- **Rủi ro:**
  - Mô hình học "khẩu trang = bình thường". Với mặt không khẩu trang, phân phối lệch, ngưỡng tính trên Zalo sẽ không đúng.
  - Nếu dùng nguyên khung, mô hình có thể học thời lượng, độ phân giải hoặc hướng xoay thay vì dấu hiệu màn hình.
  - Chỉ có tấn công replay; không có ảnh in hay mặt nạ.
- Có thể dùng hợp lý làm **tập kiểm tra phụ "replay màn hình, người Việt"**: ghi rõ "đều đeo khẩu trang", không dùng để chọn ngưỡng cho demo.

---

## 2. RTFS-10k (`rtfs10k`)

**Cấu trúc thực tế**
- `original_videos/` có 168 clip thật (148 YouTube ID).
- `inswapper/` có 500 clip giả, `uniface/` có 503 clip giả (mỗi clip kèm `.verified.json`).
- CSV: `videos.csv` (1.636 dòng), `inswapper.csv` (4.875), `uniface.csv` (4.897), `photos.csv` (2.000).
- **Không tải ảnh donor.**
- Mỗi clip thật có khoảng 3 bản ghép, mỗi bản dùng một donor khác nhau. 404/1.003 bản giả có thêm `faceenchancer`.

**Âm thanh:** 0/1.171 video có track âm thanh, kể cả clip thật.

**Xem bằng mắt.** Đã xem 32 thật + 32 inswapper + 32 uniface + 8 cặp (thật kèm 3 bản ghép) (`rtfs_*.jpg`).
- Nguồn là YouTube CC: người nói chuyện kiểu webinar hoặc vlog, ngồi trước camera, khung ngang 16:9, mặt nhỏ (cạnh ngắn chiếm trung vị 0,30 khung).
- Người trong video: chủ yếu châu Âu, Mỹ, Mỹ Latinh và châu Phi, khoảng 25–70 tuổi. **Gần như không có người Đông Nam Á** trong video đích (thấy 1 người châu Á ở `uBBif-yksxg`).
- Donor có nhiều khuôn mặt châu Á. Bản ghép thấy rõ mặt châu Á gắn lên thân người da trắng (cặp `zG3QV9_U77g`, `3qMFK-kPtc8`, `mGS5P7beBOU`).
- Có logo kênh, chữ hoặc banner ở góc (UVED, sbam, zoom), có ở **cả** thật lẫn giả.
- Không khẩu trang. Mask_guess ≥ 0,5: 3/168 thật và 8/1.003 giả, mức nhiễu của bộ đoán thô.
- Không có video xoay.

**Đo định lượng**
- Độ phân giải, fps, thời lượng của bản giả trùng 100 % với clip gốc tương ứng: 1080p 65 %, 720p 31 %; fps 24, 25, 30, 50, 60; thời lượng trung vị 17 giây.
- SCRFD thấy mặt ở 100 % video thật; chỉ 1 video giả có khung không thấy mặt.

**Lộ đề**
- **Bitrate: sep 0,89. Kích thước file: sep 0,85.**
  - So từng cặp: bản giả có bitrate trung vị bằng **0,35 lần** clip gốc. Bản giả bị mã hóa lại nhẹ hơn.
  - Laplacian của bản giả bằng 0,83 lần clip gốc (mờ hơn), sep 0,56.
- Độ phân giải, fps, thời lượng, cỡ mặt, độ sáng: sep khoảng 0,50, không lộ đề.
- Vì vậy nếu huấn luyện hay đánh giá trên RTFS mà không nén lại cả hai lớp như nhau, mô hình có thể học "nén nhiều = giả".

**Giấy phép:** theo Kaggle API là CC BY-SA 4.0. Tiêu đề phụ: "Dataset for Video Deepfake Detection in Video-Call Scenarios". Mô tả gốc có 1.636 clip đích, 2.000 ảnh nguồn, 9.772 video giả, dùng inswapper và uniface. SOURCE.md khớp và ghi đúng là bản nhỏ.

**Kết luận vai trò**
- **Chỉ test** cho GenD, đúng như quyết định hiện có. Đây là mối đe dọa kiểu Deep-Live-Cam (inswapper chính là lõi của Deep-Live-Cam).
- Không có âm thanh, nên không dùng được cho kiểm tra đa phương thức hay đồng bộ môi.
- Trước khi đo, **nén lại cả clip thật và clip giả về cùng codec và bitrate**, nếu không AUC sẽ bị thổi phồng bởi khác biệt bitrate.
- Chỉ đo được "mặt Á trên thân người Tây", không đại diện cho selfie dọc trên điện thoại.

---

## 3. WildDeepfake (`wilddeepfake`)

**Cấu trúc thực tế**
- 23 archive `tar.gz` (11 fake_train, 12 real_train) chứa 15.227 PNG: 8.044 khung thật, 7.183 khung giả. Gom theo video được 132 video (79 thật, 53 giả).
- Thư mục `extracted/` (15.227 PNG) là bản giải nén do DATA-03 tạo, dùng cho các file split.
- Không có video, không có âm thanh, không ghi công cụ tạo giả.

**Xem bằng mắt.** Đã xem 32 video thật + 32 video giả, mỗi video 1 khung (`wild_real.jpg`, `wild_fake.jpg`).
- Ảnh **cắt sát mặt 224×224** (100 % mẫu). Lấy từ phim hoặc phim truyền hình Trung Quốc và phim Hollywood, chất lượng nén thấp, nhiều khung mờ.
- Người trong ảnh: khoảng một nửa Đông Á (diễn viên Trung Quốc), nửa còn lại châu Âu, Mỹ và châu Phi; 20–60 tuổi.
- **Cùng diễn viên xuất hiện ở cả lớp thật và giả**, ví dụ nam diễn viên tóc dài râu rậm ở `51/real/23` và `541/fake/68`.
- Lớp giả trông mịn, sáng, môi đỏ rõ. Có chữ Hán watermark ở `174/fake/112`.
- Không khẩu trang, không xoay.

**SCRFD**
- Ảnh gốc 224 px: **0/792 khung thấy mặt.**
- Thêm viền xám 50 % mỗi phía: 98,7 % (thật) và 100 % (giả) thấy mặt. Viền 100 %: 98,9 % và 100 %.
- Kết luận: phải thêm viền (hoặc bỏ bước dò mặt và đưa thẳng ảnh vào GenD, vì ảnh đã là ảnh cắt mặt).

**Lộ đề** (792 khung, 6 khung mỗi video)
- Kích thước PNG: sep 0,69. Laplacian (lớp giả nét hơn): 0,68. Độ tương phản: 0,68. Độ sáng (lớp giả sáng hơn): 0,66.
- Gần ngưỡng 0,7, và nhãn trùng hoàn toàn với archive (mỗi archive chỉ chứa một lớp).

**Split hiện có** (`data/splits/wilddeepfake`)
- calib_fit: 1.620 khung, 14 video (7 thật, 7 giả).
- calib_ltt: 1.773 khung, 14 video (7 thật, 7 giả).
- test: 11.834 khung, 104 video.
- **14 video cho calib_fit là quá ít.** Các khung trong một video tương quan rất mạnh, nên số mẫu độc lập thực tế khoảng 14. Ngoài ra không chứng minh được hai tập độc lập về người: cùng diễn viên có ở cả thật lẫn giả và ở nhiều video.

**Giấy phép:** HF ghi Apache-2.0, README trống. Bài báo gốc (WildDeepfake, ACM MM 2020) thường yêu cầu dùng cho nghiên cứu. Nội dung là phim có bản quyền: không phân phối lại, đúng như SOURCE.md đã ghi.

**Kết luận vai trò**
- **Chỉ test (giám định "ngoài đời, nén").** Không nên dùng làm nguồn chính để hiệu chỉnh ngưỡng `face_deepfake` cho eKYC:
  - miền khác hẳn: cảnh phim, mặt cắt sát, độ phân giải 224;
  - khung đã cắt sẵn, nên khi đưa qua SCRFD phải thêm viền nhân tạo;
  - calib_fit chỉ 14 video.
- Nếu buộc phải dùng để hiệu chỉnh, ghi rõ đây là hiệu chỉnh tạm thời, có độ bất định lớn.

---

## 4. ViCocktail (`vicocktail`)

**Cấu trúc thực tế**
- 2 shard webdataset (`avvn-train-000072.tar`, `-000098.tar`) chứa 2.105 clip, đến từ 35 YouTube ID.
- Mỗi clip gồm `.video` (mp4), `.label` (transcript tiếng Việt), `.length` và `.sample_id`.
- Có âm thanh: 2.105/2.105.

**Xem bằng mắt.** Đã xem 48 clip (seed 42), `vicocktail_sheet.jpg`.
- **Video chỉ là vùng miệng cắt sát 96×96**, từ mũi xuống cằm. Không có mắt, không có cả khuôn mặt.
- Người Việt, nhiều tuổi khác nhau, nguồn YouTube (talkshow, phỏng vấn).

**Đo định lượng** (300 clip ngẫu nhiên): 100 % 96×96, 25 fps, trung vị 4,96 giây. **SCRFD: 0 % khung thấy mặt.**

**Giấy phép:** HF không ghi giấy phép. Bài báo arXiv 2506.04635 mô tả bộ này dùng cho AVSR tiếng Việt. SOURCE.md đã ghi "giấy phép chưa rõ".

**Kết luận vai trò**
- **Không dùng được cho mặt** (PAD, GenD, DATA-04). Tài liệu hiện tại đang dự định dùng sai:
  - `E4-face.md` dòng 102: "video thật ViCocktail" để tinh chỉnh GenD;
  - handoff DATA-03: ViCocktail ∪ vn_celeb làm nhóm nguồn cho DATA-04.
- Chỉ có thể dùng cho **kiểm tra đồng bộ môi và âm thanh** (SyncNet, presence) hoặc làm dữ liệu giọng nói và ASR.

---

## 5. LAV-DF (`lavdf`), chưa tải

- SOURCE.md ghi trạng thái `skipped`: chỉ có tar 25,6 GB.
- Trang HF ghi CC BY-NC 4.0, có **cổng điều kiện** (phải đăng nhập và chấp nhận điều khoản trên GitHub). Kích thước 25,6 GB.
- Là deepfake nghe nhìn để khoanh vùng thời điểm bị sửa (thay từ trong lời nói kèm khẩu hình). Trang không ghi độ phân giải hay nguồn.
- Theo bài báo gốc (Cai và cộng sự, DICTA 2022), dữ liệu xây trên VoxCeleb2: người nổi tiếng nói tiếng Anh, mặt cắt từ phỏng vấn. Điểm này chưa xác minh trên file, cần kiểm tra lại nếu tải.
- Vai trò nếu tải: chỉ test cho chế độ giám định. Phi thương mại. Không phải người Việt, không phải selfie.

---

## 6. Tóm tắt rủi ro chung cho VeriClue

1. **Không bộ video nào ở đây là "selfie dọc, người Việt, không khẩu trang" có cả thật lẫn giả.**
   - Zalo gần đúng miền nhưng có khẩu trang.
   - RTFS là webinar ngang, người phương Tây.
   - WildDeepfake là phim, cắt sát.
   - ViCocktail chỉ có miệng.
2. Lộ đề cần xử lý trước khi huấn luyện hay đánh giá:
   - Zalo: thời lượng (0,80), 4K, âm thanh, lộn ngược.
   - RTFS: bitrate (0,89).
   - WildDeepfake: độ nét và độ sáng (khoảng 0,68), cộng với nhãn trùng archive.
3. Số liệu khẩu trang của Zalo là đếm bằng mắt (63/64 khung đã xem). Bộ đoán tự động thô không đáng tin.
