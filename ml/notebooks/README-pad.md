# Hướng dẫn chạy notebook tinh chỉnh PAD trên Kaggle (và Colab)

Dành cho người **không chuyên**. Làm đúng từng bước, không cần hiểu code.
Nhóm có **2 người chạy song song**, mỗi người **một file notebook riêng** (trưởng nhóm gửi đúng file cho bạn).
Hai file giống hệt nhau, chỉ khác mô hình được dạy. Việc của bạn: **chạy notebook và gửi lại 1 file zip**.
Trong notebook bạn **chỉ được sửa một chỗ: `SMOKE`** (chạy thử hay chạy thật). Không sửa gì khác.

### Người 1 — MiniFASNet (file `finetune_pad_minifasnet.ipynb`)
- Dạy MiniFASNet và đo luôn MiniFASNet gốc để so sánh.
- Chạy thật mất khoảng **1–2 giờ** trên GPU T4. Chạy thử (SMOKE) khoảng 10 phút.
- Gửi lại: file `pad_export_minifasnet_<ngày-giờ>.zip`.

### Người 2 — DINOv2 (file `finetune_pad_dinov2.ipynb`)
- Dạy DINOv2 (tải thêm khoảng 350 MB trọng số).
- Chạy thật mất khoảng **1,5–2,5 giờ** trên GPU T4. Chạy thử (SMOKE) khoảng 15 phút.
- Gửi lại: file `pad_export_dinov2_<ngày-giờ>.zip`.

**Cả hai người đều làm y hệt các Phần A–G bên dưới.** Hai người phải dùng cùng loại GPU (T4 x2) để chia tập ra giống hệt nhau.
Notebook in dòng `SHA-256 các file chia tập`. Nếu trưởng nhóm gửi bạn một mã SHA-256, dán mã đó vào dòng
`EXPECTED_SPLITS_SHA = ""` (giữa hai dấu ngoặc kép). Notebook sẽ tự dừng nếu cách chia tập của bạn khác.

**Gửi lại cho trưởng nhóm:**
1. File zip.
2. Ảnh chụp bảng ở cuối Bước 7.
3. Dòng `splits.csv  <mã SHA-256>` ở cuối Bước 3.

Nếu gặp chuyện gì không có trong hướng dẫn: **chụp màn hình** phần chữ đỏ cuối cùng và gửi trưởng nhóm. Đừng tự sửa code.

---

## Phần A — Chuẩn bị tài khoản Kaggle (làm 1 lần, khoảng 10 phút)

1. Mở trình duyệt, vào **https://www.kaggle.com**.
2. Bấm nút **Register** (góc phải trên) → chọn **Register with Google** (dùng Gmail của bạn) → làm theo màn hình.
   Nếu đã có tài khoản thì bấm **Sign In**.
3. **Xác minh số điện thoại** (bắt buộc, không có thì không bật được GPU và Internet):
   - Bấm vào **ảnh đại diện** (góc phải trên) → **Settings**.
   - Kéo xuống mục **Phone Verification** → bấm **Not verified / Verify** → chọn quốc gia **Vietnam (+84)** → nhập số điện thoại → bấm gửi → nhập mã 6 số nhận qua SMS.
   - Thấy chữ **Verified** là xong.

## Phần B — Tạo notebook và nạp file

1. Ở cột trái trang Kaggle, bấm **Create** (dấu +) → **New Notebook**. Một notebook trống mở ra.
2. Trên thanh menu của notebook, bấm **File** → **Import Notebook**.
3. Bấm **Browse Files** → chọn **đúng file của bạn** (`finetune_pad_minifasnet.ipynb` hoặc `finetune_pad_dinov2.ipynb`) trên máy → bấm **Import**.
   Notebook trống được thay bằng nội dung của nhóm (dòng đầu là "VeriClue — Tinh chỉnh PAD…").
4. (Tùy chọn) Bấm vào tên notebook ở góc trái trên (dạng "notebookxxxx") để đổi tên, ví dụ `vericlue-pad`.

## Phần C — Cài đặt notebook (cột phải, mục "Session options" / "Settings")

Nếu không thấy cột phải, bấm biểu tượng **mũi tên |<** hoặc menu **View → Show sidebar**.

1. **Accelerator** (bộ tăng tốc): chọn **GPU T4 x2**. Nếu không có thì chọn **GPU P100**.
   Kaggle hỏi xác nhận thì bấm **Turn on GPU**.
2. **Internet**: gạt sang **On**. (Không bật được → bạn chưa xác minh số điện thoại, xem Phần A bước 3.)
3. **Persistence** (nếu có): chọn **Files only**. Khi đó thư mục `/kaggle/working` (dữ liệu đã làm sạch + checkpoint) được giữ lại giữa các phiên → bị ngắt thì chỉ cần Run All lại.

## Phần D — Thêm dữ liệu (Add Input)

Ở cột phải, mục **Input**, bấm **+ Add Input**. Một ô tìm kiếm hiện ra. Với **mỗi** dòng dưới, gõ đúng tên vào ô tìm kiếm, chọn tab **Datasets**, rồi bấm **dấu + (Add)** ở dataset có đúng tên tác giả:

| Bắt buộc? | Gõ vào ô tìm kiếm | Đúng dataset là | Dùng để |
|---|---|---|---|
| **Bắt buộc** | `maihongtng/face-anti-spoofing` | "face-anti-spoofing" của **maihongtng** (~8,9 GB) | dạy, chọn mô hình (FAS-VN) |
| Nên có | `hlly34/liveness-detection-zalo-2022` | "liveness-detection-zalo-2022" của **hlly34** | test phụ (khẩu trang) |

- Dữ liệu **Axon** và **UniData** (test phụ) notebook **tự tải** từ Hugging Face khi Internet bật — bạn không phải làm gì.
- Sau khi thêm, mục **Input** ở cột phải hiện tên dataset. Đóng ô tìm kiếm bằng dấu **X**.

## Phần E — Chạy

**Khuyên dùng: chạy thử nhỏ trước (10–15 phút)** để chắc mọi thứ ổn:
1. Bấm vào ô code có dòng `SMOKE = False` (ô thứ 2 có code, mục "Bước 0 — Cấu hình").
2. Sửa `False` thành `True` (viết hoa chữ T).
3. Trên thanh menu bấm **Run All** (hoặc **Run → Run All**).
4. Kéo xuống cuối: thấy dòng **"XONG. File cần gửi trưởng nhóm: …_smoke.zip"** là notebook chạy được.
   (Bản chạy thử **không cần gửi**, trừ khi trưởng nhóm yêu cầu.)

**Chạy thật:**
1. Sửa lại `SMOKE = True` thành `SMOKE = False`.
2. Bấm **Run All**.
3. **Thời gian dự kiến:** Người 1 khoảng 1–2 giờ, Người 2 khoảng 1,5–2,5 giờ (GPU T4). Mỗi file chỉ chạy bước 6a **hoặc** 6b. Notebook in ước tính ở đầu và thời gian thật sau mỗi bước:

| Bước | Việc | Ước tính (T4) |
|---|---|---|
| 1 | Cài thư viện, tải trọng số (~380 MB), kiểm SHA-256 | 3–6 phút |
| 2 | Kiểm kê dữ liệu | 1–2 phút |
| 3 | Làm sạch, dò mặt, gom người, chia tập | 30–60 phút (lâu nhất) |
| 4 | Kiểm lộ đề | 1–2 phút |
| 5 | Đo mô hình gốc | < 1 phút |
| 6a | Dạy MiniFASNet | 10–20 phút |
| 6b | Dạy DINOv2 | 30–60 phút |
| 7 | Chọn mô hình | < 1 phút |
| 8 | Test phụ (tải ~1,7 GB video) | 5–15 phút |
| 9–10 | Kiểm cuối, đóng gói zip | 2–5 phút |

### Theo dõi khi đang chạy

- Ô đang chạy có vòng tròn quay / dấu `[*]` bên trái. Ô xong có số `[3]`, `[4]`…
- Bên dưới mỗi ô có dòng chữ tiến độ, ví dụ `2500/11376 ảnh, 6.3 ảnh/giây, còn ~23.4 phút`.
- **Giữ tab trình duyệt mở** và máy không ngủ. Kaggle tự ngắt phiên nếu không ai tương tác khoảng 1 giờ hoặc sau 12 giờ.
  Mẹo: thỉnh thoảng bấm vào notebook / cuộn trang.
- Dòng chữ **đỏ** có chữ `RuntimeError` hoặc `DỪNG:` = notebook dừng có chủ đích → đọc thông báo tiếng Việt ngay phía trên, làm theo, hoặc chụp màn hình gửi trưởng nhóm.

### Nếu bị ngắt giữa chừng (mất mạng, hết giờ, tắt máy)

Notebook **lưu checkpoint** sau mỗi epoch và lưu dữ liệu đã làm sạch (thư mục `pad_work`).

- **Phiên vẫn còn** (cột phải vẫn hiện GPU đang bật): chỉ cần bấm **Run All** lại. Notebook tự nhận ra phần đã làm, **bỏ qua bước 3–4** và **chạy tiếp từ epoch cuối**.
- **Phiên đã tắt** (Kaggle xóa `/kaggle/working`): trước khi tắt, nếu kịp, vào tab **Output** (cột phải) bấm **Save Version → Quick Save** để giữ file. Lần sau:
  1. Mở lại notebook → **+ Add Input** → tab **Notebooks** (hoặc "Your Work") → chọn chính notebook này (phiên bản đã lưu) → **Add**.
  2. Bấm **Run All**. Notebook tự tìm `pad_work` cũ trong Input, sao chép về và chạy tiếp.
- Không giữ được gì thì chạy lại từ đầu (mất thêm 1,5–3 giờ quota GPU).

## Phần F — Lấy file kết quả và gửi trưởng nhóm

1. Khi cuối notebook hiện **"XONG. File cần gửi trưởng nhóm: /kaggle/working/pad_export_…zip"**:
2. Ở cột phải, mở mục **Output** (hoặc **Data → Output**), thấy thư mục `/kaggle/working`.
3. Bấm vào file **`pad_export_minifasnet_<ngày-giờ>.zip`** (Người 1) hoặc **`pad_export_dinov2_<ngày-giờ>.zip`** (Người 2) → bấm **Download** (biểu tượng mũi tên xuống, hoặc dấu ⋮ → Download).
4. **Gửi file zip cho trưởng nhóm** qua **Google Drive** của nhóm (thư mục mà trưởng nhóm chia sẻ, đặt chế độ **chỉ người trong nhóm xem được**), rồi nhắn link trong nhóm chat.
   - **KHÔNG** đăng file lên chỗ công khai, **KHÔNG** bấm "Make Public" notebook hay output trên Kaggle (dữ liệu có ảnh mặt người thật, chỉ dùng nghiên cứu).
5. Nhắn kèm: ảnh chụp **bảng "Bảng trước/sau trên calib_fit"** (cuối bước 7) và dòng **"Thời gian từng bước"** (cuối notebook).

Zip gồm (không chứa ảnh):
- **mô hình:**
  - Người 1: `minifasnet_v2_ft.onnx`, thay thẳng được vào hệ thống;
  - Người 2: `dinov2_pad.onnx` + `dinov2_pad_delta.safetensors` + `dinov2_pad_config.json`;
- **calibrator:** `calibrators/face_pad/*.json`, fit trên calib_fit;
- **điểm từng mẫu:** `scores_calib_fit.csv` và `scores_calib_ltt.csv` (mã mẫu, nhóm người, nhãn, điểm thô, xác suất đã hiệu chỉnh), `aux_scores.csv` (test phụ);
- **chia tập:** `splits.csv` + `split_train/calib_fit/calib_ltt/test.csv`;
- **báo cáo:** `card.md`, `metrics.json`, `cleaning_report.json`, `leak_check.json`, `SHA256SUMS.txt`.

## Phần G — Lỗi thường gặp

| Bạn thấy | Nghĩa là | Làm gì |
|---|---|---|
| `KHÔNG TÌM THẤY FAS-VN` | Chưa Add Input dataset | Làm lại Phần D (dòng **Bắt buộc**), rồi **Run All** |
| `KHÔNG TẢI ĐƯỢC … từ Hugging Face` hoặc `URLError` | Internet đang tắt, hoặc Hugging Face lỗi tạm | Cột phải: **Internet → On**. Nếu đã On: đợi 15 phút rồi Run All lại |
| `SAI SHA-256` | File tải về bị hỏng / khác bản nhóm dùng | Run All lại 1 lần; vẫn lỗi → chụp màn hình gửi trưởng nhóm |
| `CẢNH BÁO: KHÔNG THẤY GPU` | Chưa bật GPU | Cột phải → **Accelerator → GPU T4 x2** → Run All. Không bật được → xác minh số điện thoại |
| `CUDA out of memory` | Hết bộ nhớ GPU (VRAM) | Ô "Bước 0": đổi `BATCH_DINO = 16 if SMOKE else 48` thành `… else 24` (vẫn lỗi: `16`); với lỗi ở bước 6a đổi `BATCH_MINIFAS` từ `256` thành `128`. Rồi Run All (notebook chạy tiếp, không làm lại bước 3) |
| Notebook tự khởi động lại, báo "Your notebook tried to allocate more memory than is available" | Hết RAM | Ô "Bước 0": đổi `NUM_WORKERS = 0 if os.name == "nt" else 2` thành `… else 0`, Run All |
| `DỪNG: mô hình chỉ nhìn siêu dữ liệu vẫn đoán được nhãn` | Kiểm lộ đề không đạt | **Không chạy tiếp.** Chụp màn hình bước 4 gửi trưởng nhóm |
| `DỪNG: nhóm người lớn nhất chiếm …` | Gom người gộp quá nhiều | Ô "Bước 0": đổi `ARC_THRESHOLD = 0.40` thành `0.45`, Run All, và báo trưởng nhóm |
| Kaggle báo hết **quota GPU** (30 giờ/tuần) | Đã dùng hết giờ GPU tuần này | Quota làm mới mỗi tuần (Kaggle hiện số giờ còn lại và ngày làm mới ở cột phải / trang Settings). Nhờ bạn khác chạy, hoặc dùng Colab (Phần H) |
| `ONNX CUDA lỗi, dùng CPU` | Bộ dò mặt chạy CPU | Không sao, chỉ chậm hơn (bước 3 mất 60–90 phút). Cứ để chạy |
| Test phụ ghi `BỎ QUA …` | Không tải được dữ liệu phụ | Không sao. Kết quả chính vẫn dùng được; báo trưởng nhóm |
| Phiên bị ngắt | Mất kết nối / quá giờ | Xem mục "Nếu bị ngắt giữa chừng" |

---

## Phần H — Chạy trên Google Colab (dự phòng)

Colab miễn phí cũng có GPU T4 nhưng hay bị ngắt hơn. Notebook tự tải dữ liệu bằng Kaggle API và lưu kết quả vào Google Drive của bạn.

1. **Lấy khóa Kaggle API:** vào kaggle.com → ảnh đại diện → **Settings** → mục **API** → bấm **Create New Token**.
   Máy tải về file `kaggle.json`. Mở file bằng Notepad, thấy dạng `{"username":"abc","key":"123…"}` — giữ bí mật, không gửi ai.
2. Vào **https://colab.research.google.com** → **File → Upload notebook** → chọn đúng file của bạn (`finetune_pad_minifasnet.ipynb` hoặc `finetune_pad_dinov2.ipynb`).
3. Menu **Runtime → Change runtime type** → **Hardware accelerator: T4 GPU** → **Save**.
4. Thêm khóa vào **Secrets**: bấm biểu tượng **chìa khóa** ở thanh bên trái → **+ Add new secret** hai lần:
   - Name `KAGGLE_USERNAME`, Value = giá trị `username` trong `kaggle.json`;
   - Name `KAGGLE_KEY`, Value = giá trị `key`.
   Bật công tắc **Notebook access** cho cả hai.
5. Menu **Runtime → Run all**. Khi notebook hỏi quyền **Google Drive**, bấm **Connect to Google Drive** → chọn tài khoản → **Allow**.
   (Notebook lưu mọi thứ vào `My Drive/vericlue_pad/` để chạy tiếp khi bị ngắt.)
6. Notebook tự tải FAS-VN (~8,4 GB, 5–10 phút). Test phụ Zalo trên Colab không tự tải — bỏ qua cũng được.
7. Bị ngắt: mở lại notebook, **Runtime → Run all** — notebook đọc lại `My Drive/vericlue_pad/pad_work` và chạy tiếp.
8. Kết quả: file `pad_export_<minifasnet|dinov2>_<ngày-giờ>.zip` trong **Google Drive → My Drive → vericlue_pad**. Chia sẻ file đó cho trưởng nhóm (chỉ người trong nhóm).

Lỗi riêng của Colab:
- `userdata` / `SecretNotFoundError`: chưa thêm 2 secret hoặc chưa bật **Notebook access** (bước 4).
- `403 Forbidden` khi tải dataset: vào trang dataset `maihongtng/face-anti-spoofing` trên Kaggle bằng đúng tài khoản đó, bấm **Download** một lần để chấp nhận điều khoản, rồi chạy lại.
- Colab báo hết GPU: đợi vài giờ hoặc chuyển sang Kaggle.

---

## Ghi chú cho trưởng nhóm

- Hai notebook được sinh từ cùng một mẫu bằng `uv run --no-sync python scripts/build_pad_notebook.py`. Mẫu nhúng `pad.py`, `eval/metrics.py`, `face/pad_tuning.py`, `common/calibration.py` và manifest. Hai file chỉ khác dòng `MODEL`. Commit nguồn ghi ở ô đầu notebook và trong `metrics.json`/`card.md`.
- Chạy thử trên máy: đặt biến môi trường `PAD_SMOKE=1`, `PAD_FASVN_DIR`, `PAD_OUT_DIR`, `PAD_INPUT_ROOT`, `PAD_LOCAL_MODELS_DIR`, `PAD_AUX_DIRS` rồi `jupyter nbconvert --execute` (xem bàn giao FACE-04).
- **Gộp 2 zip trên laptop** (CPU, vài giây):
  `uv run --no-sync python ml/notebooks/combine_pad.py --minifasnet <zip Người 1> --dinov2 <zip Người 2> --out <thư mục>`.
  - Script kiểm SHA-256 các file chia tập phải trùng, rồi ghép từng mẫu calib_fit.
  - Script đo MiniFASNet / DINOv2 / GỘP (max xác suất đã hiệu chỉnh), cả theo từng nguồn A/B.
  - Khuyến nghị "dùng cả hai" hay "dùng một mô hình" được ghi vào `combine_report.md` và `combine_report.json`.
- Nếu hai zip lệch SHA-256: lấy `splits.csv` SHA-256 của Người 1, gửi Người 2 dán vào `EXPECTED_SPLITS_SHA`, rồi chạy lại.
- Nhận zip: kiểm `SHA256SUMS.txt`, rồi đặt mô hình và calibrator vào `MODELS_DIR/finetuned/pad/<ngày>/` và `ml/configs/calibrators/face_pad/`. Split `test` của FAS-VN mới chia **chưa** được dùng — chạy test **một lần** trên máy sau khi chốt.
