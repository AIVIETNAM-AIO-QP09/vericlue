# Hướng dẫn chạy notebook hiệu chỉnh GenD (FACE-04) — cho người không chuyên

Notebook: `ml/notebooks/calibrate_gend.ipynb`. Notebook **không dạy lại** mô hình. Nó làm ba việc:

1. Chấm điểm bằng GenD gốc.
2. Học cách đổi điểm thành xác suất (calibrator) từ ảnh người Việt thật (FAS-VN) và video RTFS, để người Việt thật không bị bắt đọc câu oan.
3. Đóng gói kết quả thành **một file zip** để bạn gửi trưởng nhóm.

Bạn **không cần cài gì trên máy** và **không tải dữ liệu về máy**. Mọi thứ chạy trên Kaggle (hoặc Colab).

> Không sửa file `.ipynb` bằng tay. Nếu notebook báo lỗi, chụp màn hình ô bị lỗi gửi trưởng nhóm (xem bảng lỗi ở cuối).

---

## Phần A — Chạy trên Kaggle (khuyên dùng)

### A1. Tài khoản (làm một lần)
1. Vào https://www.kaggle.com, bấm **Register**. Đăng ký bằng Google cho nhanh.
2. **Xác minh số điện thoại.** Bước này bắt buộc, vì không xác minh thì không bật được GPU và Internet.
   - Bấm ảnh đại diện (góc phải trên) → **Settings**.
   - Tìm mục **Phone verification** → nhập số điện thoại (+84…) → nhập mã SMS.

### A2. Đưa notebook lên Kaggle
1. Lấy file `calibrate_gend.ipynb` từ trưởng nhóm, hoặc từ repo (thư mục `ml/notebooks/`).
2. Trên Kaggle, bấm **Create** (dấu +, góc trái) → **New Notebook**.
3. Trong notebook mới: menu **File** → **Import Notebook** → chọn file `calibrate_gend.ipynb` → **Import**.

### A3. Cài đặt máy chạy (cột bên phải, mục **Session options**)
- **Accelerator:** chọn **GPU T4 x2**. Nếu không có thì chọn **GPU P100**.
- **Internet:** bật **On**. Nếu bị khóa nghĩa là chưa xác minh số điện thoại (xem A1).
- **Persistence:** để mặc định là được.

### A4. Thêm dữ liệu (Add Input)
Ở cột bên phải, bấm **+ Add Input**, rồi lần lượt thêm **2 bộ**. Mỗi bộ: gõ tên vào ô tìm kiếm, chọn tab **Datasets**, bấm dấu **+** cạnh đúng bộ.

| Gõ để tìm | Chọn đúng bộ có tên | Chủ sở hữu | Dung lượng |
|---|---|---|---|
| `rtfs-10k` | **RTFS-10k** | `stplusplus` | khoảng 17,7 GB |
| `face anti spoofing maihongtng` | **Face_anti_spoofing** | `maihongtng` | khoảng 8,9 GB |

Thêm xong, cột phải mục **Input** phải hiện đủ hai bộ trên. Chỉ cần hai bộ này, không phải thêm gì khác.

### A5. Chạy thử nhỏ (SMOKE) — BẮT BUỘC làm trước
1. Ô đầu tiên có dòng `SMOKE = True`. Giữ nguyên.
2. Menu **Run** → **Run all**.
3. Đợi khoảng **10–20 phút**. Lần đầu notebook phải tải mô hình khoảng 1,3 GB.
4. Thấy dòng `XONG sau … phút` cùng đường dẫn file `.zip` ở ô cuối là chạy thử đã đạt.
   - Lúc chạy thử, có thể thấy dòng **"KHÔNG fit được calibrator"**. Lý do là chạy thử có quá ít mẫu, nên vẫn tính là đạt.
   - Lỗi đỏ ở bất kỳ ô nào thì dừng lại, xem bảng lỗi.

### A6. Chạy thật
1. Ở ô đầu, sửa thành `SMOKE = False`.
2. Để chạy không bị ngắt khi tắt trình duyệt, bấm **Save Version** (góc phải trên) → chọn **Save & Run All (Commit)** → **Save**.
   - Kaggle sẽ chạy ngầm, tối đa 12 giờ. Bạn có thể đóng trình duyệt.
3. **Thời gian dự kiến** trên GPU T4:
   - Tổng khoảng **1–2 giờ**.
   - Các bước tốn thời gian nhất là dò mặt, cắt mặt rồi mã hóa lại, và chấm điểm, mỗi bước khoảng 20–60 phút.
   - Mỗi bước in "còn khoảng … phút". Thời gian thật nằm trong file `step_times.json` của zip.

### A7. Lấy kết quả
1. Chạy xong, vào trang notebook → tab **Output** của phiên bản vừa chạy (hoặc mục **Output** ở cột phải nếu chạy trực tiếp).
2. Tải file **`gend_calibration_YYYYMMDD_HHMM.zip`** về.
3. **Gửi zip đó cho trưởng nhóm**, kèm số SHA-256 in ở dòng cuối của notebook.
4. Không đăng zip lên chỗ công khai. Zip chỉ có số liệu, không có video hay ảnh, nhưng vẫn là tài liệu nội bộ.

### A8. Nếu bị ngắt giữa chừng
- Mở lại notebook rồi **Run all** lần nữa. Các bước đã xong được ghi trong thư mục kết quả (`faces.jsonl`, `scores_progress.jsonl`), nên notebook **chạy tiếp** chứ không làm lại từ đầu.
  - Điều này đúng với phiên đang mở. Nếu Kaggle đã xóa phiên, notebook sẽ chạy lại từ đầu.
- Dùng **Save & Run All (Commit)** như ở A6 để tránh bị ngắt.

---

## Phần B — Chạy trên Google Colab (dự phòng)

1. Vào https://colab.research.google.com → **File** → **Upload notebook** → chọn `calibrate_gend.ipynb`.
2. Menu **Runtime** → **Change runtime type** → **T4 GPU** → **Save**.
3. Lấy khóa Kaggle:
   - Trên Kaggle: **Settings** → **API** → **Create New Token**.
   - Ghi lại username và key. Key bắt đầu bằng `KGAT_` hoặc là chuỗi 32 ký tự.
4. Trong Colab, bấm biểu tượng **chìa khóa** (Secrets, cột trái) → thêm 2 dòng:
   - `KAGGLE_USERNAME` = tên đăng nhập Kaggle;
   - `KAGGLE_KEY` = key ở trên;
   - bật **Notebook access** cho cả hai.
5. **Runtime** → **Run all**. Colab sẽ hỏi quyền truy cập Google Drive, bấm **Allow**.
   - Kết quả lưu ở `MyDrive/vericlue/calibrate_gend/`, nên không mất khi Colab ngắt.
6. Colab tự tải hai bộ RTFS-10k (17,7 GB) và FAS-VN (8,9 GB) bằng Kaggle API, mất thêm khoảng 20–40 phút.
7. Làm SMOKE trước (A5), rồi `SMOKE = False` (A6). Lấy file zip trong thư mục Drive ở trên và gửi trưởng nhóm.

---

## Bảng lỗi thường gặp

| Thông báo | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Internet` bị khóa, hoặc lỗi `ConnectionError` / `Name or service not known` | Chưa bật Internet hoặc chưa xác minh số điện thoại | Làm A1 rồi A3 |
| `Thiếu inswapper.csv …` hoặc `Không thấy dữ liệu Add Input …` | Chưa thêm, hoặc thêm nhầm bộ dữ liệu | Làm lại A4, đúng tên và đúng chủ sở hữu |
| `CUDA` / `No GPU` / chạy rất chậm | Chưa chọn GPU | A3, chọn **GPU T4 x2** rồi **Run all** lại |
| `SHA-256 sai cho …` | File mô hình tải hỏng | **Run all** lại. Lặp lại thì báo trưởng nhóm |
| `Sai phiên bản mô hình` | Mô hình không đúng bản đã chốt | Báo trưởng nhóm, **không** sửa code |
| `CẢNH BÁO LỘ ĐỀ NGUỒN …` | Đây là thông tin, **không phải lỗi**. Dữ liệu thật và giả khác nguồn | Cứ để chạy tiếp. Cảnh báo đã tự ghi vào `card.md` |
| `CẢNH BÁO: một nhóm người Việt chiếm > 30% mẫu` | Có quá nhiều clip cùng một người | Cứ chạy tiếp, nhắn trưởng nhóm |
| `KHÔNG fit được calibrator` (khi `SMOKE = False`) | Dữ liệu không đủ, hoặc điểm GenD ngược chiều | Gửi trưởng nhóm ảnh chụp và file zip (nếu có) |
| `Hàm test đang TẮT …` | Ai đó bật `RUN_TEST` | Đặt lại `RUN_TEST = False`. Chỉ trưởng nhóm được bật |
| `429 Too Many Requests` (Colab) | Kaggle API giới hạn lượt gọi | Đợi 10 phút rồi **Run all** lại |
| Hết 12 giờ | Phiên Kaggle hết hạn | **Run all** lại (A8). Lặp lại thì báo trưởng nhóm |

## Dữ liệu và giấy phép (để biết)
- **RTFS-10k:** CC BY-SA 4.0, người nước ngoài. Video gốc dùng làm lớp **thật**, video ghép mặt dùng làm lớp **giả**.
- **FAS-VN (maihongtng):** CC BY 4.0. Chỉ dùng ảnh `live` (người thật).
- **VLR** (Zenodo 19705466): mặc định **tắt** (`USE_VLR = False`), **không bật**. Nếu trưởng nhóm bật, VLR chỉ để tham khảo, không dùng để tính.
- Nhóm **không tự tạo deepfake**. Hiện **không có deepfake người Việt**, nên `card.md` ghi rõ giới hạn này.
