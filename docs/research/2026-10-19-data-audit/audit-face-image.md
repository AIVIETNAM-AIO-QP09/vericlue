# Kiểm toán dữ liệu MẶT DẠNG ẢNH — fas_vn, vn_celeb_faces, celeba_spoof

Ngày: 2026-10-19. Chỉ đọc: không sửa repo, không xóa hay đổi file trong `D:\Projects\vericlue-store`.
Python: `uv run --no-sync python -I -X utf8` (env dự án; riêng parquet thì thêm `--with pyarrow` tạm thời).
Mô hình: SCRFD `det_10g` qua `vericlue_ml.face.pad.ScrfdFaceFinder` (kiểm SHA theo manifest), ArcFace `arcface-mnet` (căn 5 điểm theo mẫu chuẩn insightface 112×112).
Thư mục: `AUD = C:\Users\aqdev\AppData\Local\Temp\claude\d--Projects-Data4Life\691c4873-d6f8-4b9a-a482-f3728a8f0aba\scratchpad\audit`
Script: `fas_scan.py`, `fas_common.py`, `fas_an1.py`, `fas_an2.py`, `fas_dup.py`, `fas_face.py`, `fas_id.py`, `fas_padtest.py`, `fas_sheet.py`, `fas_dupsheet.py`, `celeb_scan.py`, `celeb_an.py`, `celeb_dh.py`, `celeb_sheet.py`. Số liệu thô: `fas_scan.jsonl` (11.376 dòng), `fas_face.jsonl` + `fas_emb.npy` (1.905 mẫu), `celeb_scan.jsonl` + `celeb_emb.npy` (8.557).

---

## 1. FAS-VN (`fas_vn/face-anti-spoofing.zip`, 8.392.841.360 byte)

### 1.1 Cấu trúc thực tế (đọc toàn bộ zip bằng `zipfile`)

| Thư mục | Số ảnh | Dung lượng giải nén |
|---|---:|---:|
| `Image/train_photo/live` | 6.759 | 2,79 GB |
| `Image/train_photo/not_live` | 2.499 | 3,59 GB |
| `Image/test_photo/live` | 782 | 0,39 GB |
| `Image/test_photo/not_live` | 1.336 | 2,13 GB |
| **Tổng** | **11.376** | 8,9 GB |

- Mọi file đuôi `.jpg`, nhưng thực chất có **2.331 PNG** và 1 GIF (PNG: train live 1.140, train not_live 976, test live 214, test not_live 1). 5 ảnh OpenCV không giải mã được (PIL đọc được), nên các phép đo ảnh dùng 11.371 ảnh.
- **Hai nguồn trộn lẫn**, nhận ra qua tên file:
  - **Nguồn A — `<UUIDv1>_face_image_live_<UUIDv1>.jpg`**: 5.512 ảnh. Có 3.770 ở train/live, **1.064 ở train/not_live** (tên file vẫn ghi "live") và 678 ở test/live. UUID v1 cho thấy mọi ảnh đều tạo trong **19→23/02/2023**, trên cùng một nút MAC `b42e9920aa06/05`. Như vậy chúng đến từ **một hệ thống eKYC đang chạy thật**. Nhiều khả năng hệ thống đó đã cho 1.064 ảnh chụp lại màn hình đi qua là "live", rồi người làm dữ liệu gán lại thành not_live. Đây chỉ là suy luận, chưa được xác nhận.
  - **Nguồn B — `real_N_train0.jpg / real_N_val.jpg / spoof_N_…`**: 5.863 ảnh. Có 2.989 ở train/live, 1.434 ở train/not_live, 104 ở test/live và **toàn bộ 1.336 ảnh test/not_live**. Có 64 mã (loại, N) xuất hiện ở cả train lẫn test.
  - Còn 1 file không theo mẫu nào, nằm ở train/not_live.
- **Test/not_live 100% là nguồn B.** Test/live gồm 87% nguồn A.

### 1.2 Xem bằng mắt (8 ảnh ghép, mỗi nhóm 32 ảnh, seed 42; tên file ghi ở `fas_sheets_files.txt`)

| Nhóm | Ảnh ghép | Quan sát |
|---|---|---|
| train/live/A | `AUD\fas_sheet_train_live_A_uuid.jpg` | Người Việt, đủ lứa tuổi 18–70, chụp **nửa người tại quầy cửa hàng điện thoại** (thấy biển mobifone, Viettel, phụ kiện). Camera sau, do nhân viên chụp, không phải selfie. Nhiều ảnh có **dấu ngày giờ in lên ảnh** (21/02/2023…). Mặt rõ, chính diện, đủ sáng. 2/32 ảnh có khẩu trang **kéo xuống cằm**, không ảnh nào che mặt. |
| train/not_live/A | `AUD\fas_sheet_train_not_live_A_uuid.jpg` | **Chụp lại màn hình**: điện thoại hoặc máy tính bảng cầm tay chiếm khung, có thấy viền và vùng đen. Có ảnh màn hình máy tính (thấy cửa sổ Paint, taskbar Windows) và ảnh cắt sát màn hình nhiều màu lệch. Phần lớn 562×1000. Không thấy ảnh in giấy rõ ràng. |
| train/live/B | `AUD\fas_sheet_train_live_B_numbered.jpg` | Selfie bằng **camera trước**, cắt vuông 900×900, mặt chiếm gần hết khung. Một số ảnh nhóm hoặc ảnh văn phòng mobifone 1024×576, 1 ảnh khẩu trang ở cằm. |
| train/not_live/B | `AUD\fas_sheet_train_not_live_B_numbered.jpg` | Chụp lại ảnh live trên **màn hình** bằng máy độ phân giải cao (2448², 3088², 3120×4160), có **vân moiré** thấy rõ. Có loại để màn hình/tablet đứng trên giá (thấy viền), điện thoại cầm tay. 1/32 ảnh có thể là ảnh in. |
| test/live/A | `AUD\fas_sheet_test_live_A_uuid.jpg` | Giống train/live/A (quầy cửa hàng, dấu thời gian). |
| test/live/B | `AUD\fas_sheet_test_live_B_numbered.jpg` | Giống train/live/B. |
| test/not_live/B | `AUD\fas_sheet_test_not_live_B_numbered.jpg` | **Toàn bộ là chụp lại màn hình cắt sát**, có moiré, 2448×2448 hoặc 3264×2448. Không thấy tablet đặt trên giá, không thấy ảnh in. |
| SCRFD trượt | `AUD\fas_sheet_scrfd_fail.jpg` | Mặt chiếm cả khung, mất trán và cằm. Nguyên nhân là **khung cắt quá sát**, không phải không có mặt. |
| Trùng khác nhãn | `AUD\fas_sheet_crosslabel_dups.jpg` (+ `.txt`) | 16 cụm đã xem. **Ảnh not_live là ảnh live của chính người đó, hiển thị lên màn hình rồi chụp lại** (thiết kế theo cặp). Có cặp nằm ở train/live và test/not_live. Cụm 0 và 1 là **cùng một ảnh gắn cả 2 nhãn** (lỗi nhãn). |

Tóm tắt nội dung: dữ liệu là người Việt, mặt lộ rõ, không đeo khẩu trang, cỡ khoảng 260 ảnh đã xem. Loại tấn công gần như **chỉ có phát lại trên màn hình** (điện thoại, tablet, màn máy tính). **Gần như không có ảnh in giấy**, không có mặt nạ.

### 1.3 Định lượng (11.371 ảnh)

| Nhóm | Cỡ file KB (p5/trung vị/p95) | Rộng px trung vị | Độ sáng trung vị | Độ nét Laplacian@256 trung vị | Có EXIF |
|---|---|---|---|---|---|
| train/live | 30 / 200 / 1.213 | 900 | 131 | 417 | 3.596 / 6.757 |
| train/not_live | 84 / 1.047 / 3.379 | 2.448 | 121 | 184 | 1.748 / 2.498 |
| test/live | 43 / 300 / 1.273 | 720 | 130 | 498 | 386 / 780 |
| test/not_live | 748 / 946 / 3.745 | **2.448** | 118 | 250 | **1.336 / 1.336** |

- EXIF Make ở test/not_live: **Apple 1.079, OPPO 256** (1.335/1.336). Ở test/live chỉ 37/782 ảnh có Make. Orientation=6 có ở 1.079/1.336 ảnh test/not_live, so với 10/780 ảnh test/live.
- SCRFD trên mẫu phân tầng 1.905 ảnh (300 mỗi nhóm, nhóm test/live/B lấy đủ 104):
  - Tỉ lệ dò được mặt ở nguồn A là 0,977–0,993; ở nguồn B chỉ **0,557–0,747**.
  - 369 ảnh trượt được chạy lại sau khi đệm viền 33%: **368/369 dò được**. Vậy ảnh B cắt quá sát. App thật cũng sẽ trượt nếu người dùng đưa mặt quá gần.
  - Cỡ mặt (căn bậc hai tỉ lệ diện tích) trung vị: A live 0,29–0,33; B 0,41–0,49.

### 1.4 Trùng lặp

- **SHA-256**: 200 nhóm trùng, thừa 274 bản sao. Trong đó 142 nhóm cùng nhãn và cùng split; **50 nhóm vắt qua train↔test**; **8 nhóm là cùng một file mang cả nhãn live lẫn not_live**.
- **dHash 64-bit, khoảng cách ≤ 4**: 1.075 cặp. Gần trùng nhưng không trùng byte: 101 cặp khác nhãn, 66 cặp khác split. Gom liên thông được 366 cụm (824 ảnh, 458 ảnh thừa); **107 cụm chứa cả live và not_live, 114 cụm vắt train↔test** (danh sách ở `fas_dupclusters.json`). Đã xem 16 cụm khác nhãn: thấy đúng cặp "ảnh gốc / ảnh chụp lại từ màn hình". Hai ảnh lệch màu và moiré nhưng vẫn lọt ngưỡng dHash.

### 1.5 "Lộ đề": AUC đơn biến, tính max(AUC, 1−AUC), not_live là lớp dương

| Tập | Đặc trưng > 0,7 |
|---|---|
| **test** (2.116) | Số thẻ EXIF **0,991**; chiều rộng **0,989**; megapixel **0,984**; có Make 0,976; chiều cao 0,945; orientation=6 0,897; độ nét gốc 0,890; cỡ file 0,868; tỉ lệ khung 0,812; byte/px 0,712. Độ sáng chỉ 0,659. |
| train (9.255) | Cỡ file 0,850; độ nét gốc 0,832; chiều cao 0,786; độ nét@256 0,758; jpeg q0 0,706; có Make 0,700 |
| train, chỉ nguồn A | Độ nét@256 0,851; jpeg q0 0,809; là PNG 0,808; byte/px 0,798; tỉ lệ khung 0,742; chiều rộng 0,739; cỡ file 0,745 |
| train, chỉ nguồn B | Chiều rộng 0,968; megapixel 0,940; chiều cao 0,932; cỡ file 0,928; độ nét gốc 0,876; có Make 0,821; orientation=6 0,814 |

**Kết luận phần này:** chỉ cần một ngưỡng trên **chiều rộng ảnh** hoặc **số thẻ EXIF** là đã tách được tập test gần như hoàn hảo, không cần nhìn mặt. Vì vậy mọi con số đo trên `test_photo` gốc **không có giá trị**.

### 1.6 Danh tính (ArcFace trên 1.536 ảnh dò được mặt trong mẫu 1.905)

| Ngưỡng cos | Cặp cùng người (không phải ảnh gần trùng, dHash > 10) | Cặp khác nhãn | Cặp khác split | Cụm ≥ 2 ảnh | Cụm có cả live và not_live | Cụm vắt train↔test |
|---|---:|---:|---:|---:|---:|---:|
| 0,4 | 269 | 116 | 113 | 149 | 70 | 82 |
| 0,5 | 153 | 75 | 60 | 97 | 51 | 46 |
| 0,6 | 145 | 74 | 59 | 94 | 50 | 45 |

- Mức nền của cặp ngẫu nhiên: cos p99 = 0,27, p99,9 = 0,346. Ngưỡng 0,5 vì vậy khá chặt.
- Chỉ riêng trong mẫu (khoảng 1/6 dữ liệu), **9,0% ảnh test đã có ảnh train cùng người** mà không phải ảnh gần trùng. Trên toàn bộ dữ liệu, tỉ lệ này chắc chắn cao hơn; con số 9,0% chỉ là cận dưới.
- Mỗi người xuất hiện cả ở live lẫn not_live. Đây là thiết kế theo cặp, tốt cho học PAD, nhưng **bắt buộc chia theo người**.
- **Chưa làm:** gom cụm ArcFace trên toàn bộ 11.371 ảnh (cần đệm viền trước khi dò mặt) để ước số người thật.

### 1.7 Đối chiếu SOURCE.md và trang gốc

Trang gốc (Kaggle API `maihongtng/face-anti-spoofing`): giấy phép **CC BY 4.0**, 8.904.892.791 byte, cập nhật 2025-06-04. Mô tả ghi "ảnh người Việt, live = selfie camera, not_live = chụp màn hình phone/tablet/monitor, thu thập thủ công".

- **Khớp:** đúng là người Việt; tấn công đúng là chụp lại màn hình.
- **Không khớp:**
  1. Phần lớn ảnh live nguồn A **không phải selfie** mà là ảnh nhân viên chụp khách tại cửa hàng. Ảnh có dấu thời gian và đến từ một hệ thống chạy thật trong 5 ngày.
  2. Có 2 nguồn trộn lẫn; các cặp gốc / chụp lại bị tách qua cả train và test.
  3. Đuôi `.jpg` nhưng 2.331 ảnh là PNG.
- **Giấy phép đáng ngờ:** ảnh khách hàng thật lấy từ hệ thống eKYC mà lại gắn CC BY 4.0. Nên giữ ghi chú của SOURCE.md: "chỉ nghiên cứu, không phân phối lại", và **không đưa mặt người lên báo cáo hay demo công khai**.
- SOURCE.md ghi "Giữ nguyên ZIP, không giải nén". Thực tế **đang có `fas_vn/extracted/` 8,4 GB** (11.360 file, ít hơn zip 16 file), tạo lúc 2026-10-18 10:30. Lead cần biết thư mục này do ai tạo. Tôi không động vào.
- SOURCE.md ghi đúng điểm "chưa có subject_id".

### 1.8 Vai trò đề xuất: **dạy PAD (fine-tune) và chọn/hiệu chỉnh** cho kiểu tấn công phát lại màn hình — có điều kiện

Đây là bộ sát mục tiêu nhất trong cả ba: người Việt, camera điện thoại, chụp lại màn hình. Điều kiện bắt buộc:

1. **Bỏ hẳn chia `train_photo/test_photo` gốc.** Gộp lại rồi chia mới theo **cụm người** (ArcFace trên toàn bộ, chạy SCRFD có đệm viền). Mỗi cặp gốc / chụp lại phải nằm cùng một phía.
2. Lọc 274 bản trùng byte. Bỏ 8 nhóm mang hai nhãn. Gom các cụm dHash vào cùng phía.
3. **Khử lối tắt:** bỏ EXIF, cắt theo hộp mặt rồi đưa về một cỡ cố định, mã hóa lại JPEG cùng chất lượng, bỏ hoặc che dấu ngày giờ. Sau đó chạy **mô hình chuẩn chỉ dùng siêu dữ liệu** (cỡ, EXIF, độ nét); AUC phải xấp xỉ 0,5 thì mới tin được kết quả PAD.
4. Không có tấn công in giấy hay mặt nạ, nên **phải bổ sung bằng bộ khác** (CelebA-Spoof) hoặc tự chụp.
5. Không dùng để chọn ngưỡng so mặt, vì không có nhãn người.

---

## 2. vn_celeb_faces (`data/train-…parquet`, 80.630.170 byte)

### 2.1 Cấu trúc thực tế

- **8.557 ảnh**, đều JPEG RGB **160×160**, 4–15 KB (trung vị 9), không có EXIF.
- **224 nhãn**: 106 ca sĩ, 107 diễn viên, 11 hoa hậu. Số ảnh mỗi người: ít nhất 2, trung vị 40, nhiều nhất 48; 6 người có dưới 20 ảnh.
- **Không thuần người Việt.** Đọc danh sách tên bằng mắt, ước khoảng 60 nhãn là sao Hoa ngữ (ví dụ Từ Tranh, Đặng Luân, Lý Thấm, Chu Nhất Long, Vương Bảo Cường…), cùng Enrique Iglesias, Shahrukh Khan, Lana Condor, Catriona Gray, Georgina Rodriguez, Rinrada Thurapan. Con số này chưa xác minh từng người.

### 2.2 Xem bằng mắt

| Ảnh ghép | Quan sát |
|---|---|
| `AUD\celeb_sheet_random48.jpg` (48 ảnh, seed 42, chỉ số ở `.txt`) | **Ảnh mặt cắt sát** (mặt rộng trung vị 95% khung) từ ảnh báo chí, sân khấu, ảnh quảng cáo. Trang điểm đậm, filter làm đẹp, góc nghiêng và cúi nhiều, có micro che miệng, vài ảnh vỡ hạt vì bị phóng to. 0/48 đeo khẩu trang. Châu Á là chính, tuổi khoảng 18–55. **Không giống selfie eKYC hay ảnh CCCD.** |
| `AUD\celeb_sheet_person_SiThanh.jpg` (40 ảnh nhãn "ca sĩ Sĩ Thanh") | Ca sĩ nữ, nhưng **ít nhất 7/40 ảnh là đàn ông**; các khuôn mặt nữ cũng không đồng nhất. Nhiều khả năng do cào web, trùng tên. |
| `AUD\celeb_sheet_person_TuTranh.jpg`, `AUD\celeb_sheet_person_MyTam.jpg` | Dùng để xem đối chứng. |
| `AUD\celeb_sheet_outliers32.jpg` | 32 ảnh có độ giống với tâm cụm của chính người đó thấp (< 0,25): nhiều ảnh khác người, ảnh mờ, mặt nghiêng hẳn. |
| `AUD\celeb_sheet_crossperson_dups.jpg` | Ảnh trùng byte nằm ở hai nhãn khác nhau. |

### 2.3 Định lượng

- Độ sáng trung vị 138 (p5 = 97). Độ nét Laplacian trung vị 256 (p5 = 80).
- SCRFD trên ảnh 160 px gốc: **0,1%** dò được mặt. Sau khi đệm viền 50%: **99,87%** (đo trên đủ 8.557 ảnh).

### 2.4 Trùng lặp và nhãn sai

- SHA-256: 67 nhóm trùng, **cả 67 đều nằm ở hai người khác nhau**. Trong đó 61 nhóm thuộc **3 cặp nhãn thực chất là một người**:
  - "Soobin" / "Soobin Hoàng Sơn": 25 nhóm, cos giữa hai tâm cụm 0,985;
  - "Cát Tường" / "Vũ Cát Tường": 22 nhóm, cos 0,971;
  - "Leg" / "Vanh Leg": 14 nhóm, cos 0,96.
  
  6 nhóm còn lại là lỗi nhãn lẻ (ví dụ Ngọc Châu / Nguyễn Thị Ánh Ngọc, Bigdaddy / Rhymastic).
- dHash ≤ 4 cho 449 cặp khác người. 382 cặp nằm ngoài 3 cặp nhãn trên và **phần lớn có lẽ là báo nhầm** (mặt cắt sát nên dHash ít phân biệt). Chưa xem từng cặp.
- ArcFace, so mỗi ảnh với tâm cụm của chính người đó (không tính ảnh đang xét): trung vị 0,634. **355 ảnh (4,2%) < 0,25**; 454 ảnh gần tâm cụm của người khác hơn của chính mình (chênh > 0,05).
- Phân bố điểm so mặt (arcface-mnet trên ảnh đệm viền):
  - Cặp cùng người (165.329 cặp): trung vị 0,396, p5 = 0,097.
  - Cặp khác người (199.037 cặp): p99 = 0,262, p99,9 = 0,336.
  - Hai phân bố chồng nhau nhiều, do nhiễu nhãn cộng với ảnh cắt sát.

### 2.5 Đối chiếu nguồn

- Trang HF (fptudsc): Apache-2.0, 8.557 dòng, 224 lớp, 160×160, nguồn ghi "nguoinoitieng.tv". Thẻ dữ liệu viết dở. **Khớp về số lượng.**
- Mô tả "người nổi tiếng Việt Nam" **không khớp**: khoảng 1/4 số nhãn là người nước ngoài.
- Giấy phép gốc chưa rõ, vì ảnh báo chí cào về không thể thật sự là Apache. SOURCE.md đã ghi đúng điều này.

### 2.6 Vai trò đề xuất: **không dùng để chọn ngưỡng so mặt cho sản phẩm; không dùng cho PAD**

- Không có ảnh giả. Ảnh là ảnh báo chí cắt sát, không phải cặp selfie–CCCD. Có nhãn trùng người và nhãn sai.
- Nếu muốn dùng, chỉ nên làm **kiểm tra nhanh nội bộ** cho mô hình so mặt trên mặt châu Á (phân bố cặp khác người), sau khi đã:
  - gộp 3 cặp nhãn;
  - bỏ khoảng 355 ảnh ngoại lai;
  - lọc nhãn nước ngoài.
- Không đưa con số đo trên bộ này vào báo cáo như hiệu năng eKYC.

---

## 3. CelebA-Spoof (chưa tải, chỉ tra tài liệu)

| Mục | Thông tin (nguồn) |
|---|---|
| Quy mô | 625.537 ảnh, 10.177 người; tỉ lệ live:spoof = 1:3 (GitHub ZhangYuanhan-AI/CelebA-Spoof; bài ECCV 2020) |
| Ảnh live | Toàn bộ lấy từ **CelebA**, tức ảnh web của người nổi tiếng. Bài báo **không công bố tỉ lệ chủng tộc**; CelebA vốn nghiêng về người phương Tây. Không phải selfie điện thoại, không có người Việt. |
| Tấn công | 11 loại nhỏ: Photo, Poster, **A4 (in)**, Face Mask, Upper-Body Mask, Paper Cut, Region Mask, **PC, Pad, Phone (phát lại)**, 3D Mask. Chụp bằng hơn 10 thiết bị (phone/pad/PC), 8 phiên (2 môi trường × 4 điều kiện sáng). |
| Chia tập | train/val/test = 8:1:1, **không trùng người** (bài báo nói rõ) |
| Nhãn | 43 thuộc tính (40 thuộc tính CelebA, loại spoof, ánh sáng, môi trường, live/spoof). README không nhắc file bbox; bản mirror HF Ar4ikov có cột `Bbox`. |
| Giấy phép | "available for **non-commercial research purposes** only"; mã nguồn "non-commercial research and educational purposes". SOURCE.md ghi "cấm phân phối lại", khớp. |
| Dung lượng / bản tải | Trang chính thức không ghi dung lượng; tải qua Google Drive hoặc Baidu (mật khẩu 61fd), dạng zip chia mảnh (theo SOURCE.md). |
| Bản mirror HF (không chính thức, không ghi giấy phép) | `Ar4ikov/celebA_spoof`: 525.864 dòng, **72 GB**, train/valid/test 420k/46,7k/59,2k, có Bbox.<br>`nguyenkhoa/celeba-spoof-for-face-antispoofing-test`: 67.170 dòng, **4,95 GB**, cột `cropped_image`, nhãn 0 = live / 1 = spoof.<br>`Camilotabares1/celebA_spoof_sample(_split)`: 46,7k và 18k dòng.<br>Kaggle: không tìm thấy bản mirror qua tìm kiếm web (trang Kaggle không đọc được nội dung). |

**Vai trò đề xuất:** **bổ sung cho dạy PAD**, chủ yếu ở phần **in giấy và poster**, là phần FAS-VN thiếu. Ngoài ra dùng làm **tập test khác miền**.

- Không dùng để chọn ngưỡng cho người Việt.
- Nếu tải, ưu tiên bản chính thức hoặc một phần nhỏ (chẳng hạn tập test khoảng 5 GB) và ghi rõ nguồn.
- Bản mirror HF là phân phối lại trái với điều khoản gốc, nên cần nhóm quyết định trước khi dùng.
- Chia theo đúng split gốc (đã theo người).

---

## 4. Bảng tổng hợp

| Bộ | Nội dung thực tế | Vấn đề chính | Vai trò |
|---|---|---|---|
| FAS-VN | 11.376 ảnh người Việt; live là ảnh tại quầy cửa hàng (nguồn A) và selfie camera trước (nguồn B); spoof là **chụp lại màn hình** phone/tablet/PC, gần như không có ảnh in | Test lộ đề (AUC chiều rộng 0,989, EXIF 0,991); 274 bản trùng byte, 8 nhóm mang hai nhãn, 114 cụm gần trùng vắt train↔test; cùng người ở cả train và test (≥ 9% ảnh test trong mẫu); 2.331 PNG đội lốt .jpg; ảnh B cắt sát (SCRFD 56–75%) | Dạy PAD và hiệu chỉnh cho tấn công màn hình, **sau khi** chia lại theo người, lọc trùng, khử EXIF và độ phân giải; không dùng chia gốc |
| vn_celeb | 8.557 mặt cắt 160 px từ ảnh báo chí của 224 người nổi tiếng, khoảng 1/4 là người nước ngoài | 3 cặp nhãn là cùng người (61 nhóm trùng); nhãn sai (4,2% ảnh lệch, "Sĩ Thanh" có ≥ 7/40 ảnh là nam); không phải selfie hay CCCD | Không dùng chọn ngưỡng sản phẩm; chỉ dùng kiểm tra nhanh mô hình so mặt sau khi làm sạch |
| CelebA-Spoof | 625k ảnh, 10.177 người phương Tây/CelebA, 11 loại tấn công gồm in A4, poster, màn hình, mặt nạ | Không phải người Việt; chỉ cho nghiên cứu phi thương mại; bản chính thức nặng; mirror không chính thức | Bổ sung dạy PAD cho tấn công in, làm test khác miền; tải bản chính thức hoặc một phần nhỏ |
