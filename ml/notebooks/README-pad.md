# Hướng dẫn chạy notebook PAD trên Kaggle (và Colab)

Tài liệu này dành cho người **không chuyên**: làm đúng từng bước, không cần hiểu code.
Gặp chuyện gì không có trong hướng dẫn: **chụp màn hình** phần chữ đỏ cuối cùng rồi gửi trưởng nhóm.
Người cần **sửa** notebook (nhóm AI) đọc thêm [`HANDBOOK-pad.md`](HANDBOOK-pad.md).

## Tổng quan: 3 notebook, 2 người, theo thứ tự

| Thứ tự | Ai | File | Máy | Thời gian (chạy thật) |
|---|---|---|---|---|
| 1 | **Người 1** | `prep_pad.ipynb` — chuẩn bị dữ liệu, **chạy MỘT lần** | **CPU** (Accelerator: None) | khoảng 45–90 phút (ước tính) |
| 2 | **Người 1** | `finetune_pad_minifasnet.ipynb` | GPU T4 x2 | khoảng 1–2 giờ |
| 2 | **Người 2** | `finetune_pad_dinov2.ipynb` | GPU T4 x2 | khoảng 1,5–2,5 giờ |

- Bước 2 chỉ bắt đầu **sau khi** Người 1 chạy xong `prep_pad.ipynb` và **chia sẻ** nó (Phần P).
- Hai notebook dạy đều dùng **cùng một** dữ liệu đã chuẩn bị, nên cách chia tập giống hệt nhau. Notebook dạy **không** tự chia lại tập.
- Trong mọi notebook, bạn **chỉ sửa một chỗ: `SMOKE`** (`True` = chạy thử nhỏ, `False` = chạy thật). Không sửa gì khác, trừ khi được hướng dẫn trong ô "Chỉ khi lỗi hết bộ nhớ" ở Phần G.
- **Thứ tự chạy thử khuyên dùng:**
  1. Người 1 chạy `prep_pad.ipynb` với `SMOKE = True`, Save Version.
  2. Hai người chạy notebook dạy của mình với `SMOKE = True` để kiểm tra.
  3. Người 1 chạy lại `prep_pad.ipynb` với `SMOKE = False`, Save Version.
  4. Hai người chạy thật với `SMOKE = False`.
- Notebook dạy **từ chối** dạy thật trên dữ liệu chuẩn bị bản chạy thử.

---

## Phần A — Tài khoản Kaggle (làm 1 lần, khoảng 10 phút, cả hai người)

1. Vào **https://www.kaggle.com** → **Register** → **Register with Google**. Đã có tài khoản thì **Sign In**.
2. **Xác minh số điện thoại**, bắt buộc (không có thì không bật được GPU và Internet):
   1. Bấm **ảnh đại diện** → **Settings** → mục **Phone Verification** → **Verify**.
   2. Chọn **Vietnam (+84)** → nhập số → nhập mã SMS.
   3. Thấy **Verified** là xong.
3. **Gửi tên người dùng Kaggle** cho nhau (hiện ở trang cá nhân, dạng `@ten-nguoi-dung`). Người 1 cần tên của Người 2 để chia sẻ.

## Phần B — Nạp notebook

1. Bấm **Create** (dấu +) → **New Notebook**.
2. Bấm **File** → **Import Notebook** → **Browse Files** → chọn **đúng file của bạn** → **Import**.
3. Bấm vào tên notebook (góc trái trên) để đổi tên dễ nhớ, ví dụ `vericlue-prep-pad`, `vericlue-pad-minifasnet`, `vericlue-pad-dinov2`.

## Phần C — Cài đặt (cột phải, mục "Session options" / "Settings")

Không thấy cột phải thì bấm **View → Show sidebar**.

| Mục | `prep_pad.ipynb` | Notebook dạy |
|---|---|---|
| **Accelerator** | **None** (chạy CPU, không tốn quota GPU) | **GPU T4 x2** (không có thì **GPU P100**) |
| **Internet** | **On** | **On** |
| **Persistence** (nếu có) | Files only | **Files only** (giữ checkpoint khi phiên khởi động lại) |

## Phần D — Thêm dữ liệu (Add Input)

Ở cột phải, mục **Input** → **+ Add Input** → gõ tên vào ô tìm kiếm → tab **Datasets** (hoặc **Notebooks**) → bấm **dấu +**.

| Notebook | Phải thêm | Tìm ở đâu |
|---|---|---|
| `prep_pad.ipynb` | `maihongtng/face-anti-spoofing` (~8,9 GB, của **maihongtng**) | tab **Datasets** |
| Notebook dạy (cả hai) | **notebook `prep_pad` đã lưu của Người 1** (Phần P) | tab **Notebooks** → mục **Your Work** (Người 1) hoặc **Shared with you** (Người 2) |
| Notebook dạy (nên có) | `hlly34/liveness-detection-zalo-2022` (test phụ khẩu trang) | tab **Datasets** |

- Dữ liệu test phụ **Axon** và **UniData** được notebook dạy **tự tải** từ Hugging Face. Bạn không phải làm gì.
- Notebook dạy **không cần** dataset FAS-VN. Toàn bộ ảnh đã cắt nằm trong output của `prep_pad`.

## Phần P — Người 1 lưu và chia sẻ dữ liệu đã chuẩn bị

Làm sau khi `prep_pad.ipynb` in dòng **"XONG chuẩn bị: …/pad_prep"** ở cuối:

1. Góc phải trên bấm **Save Version** → chọn **Quick Save** → **Save**. Đợi thông báo lưu xong (vài phút, vì output khoảng 3–4 GB).
2. Bấm **Share** (góc phải trên) → ô **Add collaborators** → gõ **tên Kaggle của Người 2** → quyền **Can view** → **Save**.
   - **Giữ Private.** **KHÔNG** chọn Public.
3. Gửi Người 2 tên notebook. Gửi trưởng nhóm dòng `SHA-256 splits.csv = …` in ở cuối notebook.

Người 2 (và chính Người 1, khi mở notebook dạy) làm như sau:
1. Mở notebook dạy → **+ Add Input** → tab **Notebooks**.
2. Tìm tên notebook prep: Người 2 xem mục **Shared with you**, Người 1 xem **Your Work**.
3. Bấm **dấu +** → **Add**.

Nếu Người 2 không thấy notebook ở mục **Shared with you**:
- Người 1 kiểm tra lại đã thêm Người 2 làm collaborator và đã Save Version.
- Vẫn không được thì báo trưởng nhóm. Cách chia sẻ này chưa được thử trên Kaggle thật.

## Phần E — Chạy

1. Kiểm tra dòng `SMOKE = …` ở ô **"Bước 0 — Cấu hình"**:
   - `True` = chạy thử nhỏ, khoảng 10–15 phút;
   - `False` = chạy thật.
2. Bấm **Run All**.
3. Cuối notebook:
   - `prep_pad`: dòng **"XONG chuẩn bị"**;
   - notebook dạy: dòng **"XONG. File cần gửi trưởng nhóm: …zip"**.

**Thời gian từng bước (Kaggle, chạy thật; notebook in ước tính và thời gian thật):**

| Notebook | Bước | Ước tính |
|---|---|---|
| prep | 1 tải trọng số · 2 kiểm kê · 3 làm sạch/gom người/cắt mặt · 4 kiểm lộ đề · 5 lưu | 3 phút · 1–2 phút · **45–90 phút (CPU, ước tính)** · 1–2 phút · < 1 phút |
| dạy | 1 tải trọng số · 2 nạp dữ liệu chuẩn bị · 5 đo gốc · 6a hoặc 6b dạy · 7 hiệu chỉnh · 8 test phụ · 9–10 đóng gói | 3–6 phút · 1 phút · < 1 phút · **10–20 phút (MiniFASNet) / 30–60 phút (DINOv2)** · < 1 phút · 5–15 phút · 2–5 phút |

### Theo dõi

- Ô đang chạy có dấu `[*]` bên trái, ô xong có số.
- Tiến độ in dưới mỗi ô, ví dụ `2500/11376 ảnh, 6.3 ảnh/giây, còn ~23.4 phút`.
- **Giữ tab mở**, máy không ngủ. Kaggle tự ngắt phiên nếu không ai thao tác khoảng 1 giờ, hoặc sau 12 giờ.
- Chữ **đỏ** có `RuntimeError` hoặc `DỪNG:` nghĩa là notebook dừng có chủ đích. Đọc thông báo tiếng Việt ngay trên đó và làm theo, hoặc chụp màn hình gửi trưởng nhóm.

### Nếu bị ngắt giữa chừng

- **Notebook dạy** lưu checkpoint sau mỗi epoch vào `pad_work/ckpt`.
  - Phiên vẫn còn, hoặc Persistence = Files only: bấm **Run All** lại, notebook chạy tiếp từ epoch cuối.
  - Phiên đã mất: nếu kịp thì **Save Version → Quick Save** trước. Lần sau **+ Add Input** → tab **Notebooks** → chọn **chính notebook này** (bản đã lưu) → Run All. Notebook tự sao chép checkpoint cũ về và chạy tiếp.
- **`prep_pad`** mất khoảng 45–90 phút (ước tính). Bị ngắt thì Run All lại từ đầu.

## Phần F — Gửi kết quả cho trưởng nhóm

1. Cột phải → **Output** → thư mục `/kaggle/working`.
2. Bấm file zip → **Download**:
   - Người 1: **`pad_export_minifasnet_<ngày-giờ>.zip`**;
   - Người 2: **`pad_export_dinov2_<ngày-giờ>.zip`**.
3. Đưa zip vào **thư mục Google Drive của nhóm** (chế độ chỉ người trong nhóm xem), rồi nhắn link trong nhóm chat. Kèm theo:
   - ảnh chụp bảng cuối **Bước 7**;
   - dòng `splits.csv SHA-256 = …` ở **Bước 2**;
   - dòng **"Thời gian từng bước"** cuối notebook.
4. **Không bao giờ** bật Public notebook, version hay output (dữ liệu có mặt người thật, chỉ dùng nghiên cứu).
5. Sau khi trưởng nhóm xác nhận đã nhận zip, **xóa dữ liệu trung gian**:
   - Kaggle: cột phải → Output → xóa thư mục `pad_work`, hoặc xóa các version cũ không cần.
   - Colab: xóa thư mục `My Drive/vericlue_pad/pad_work` (và `pad_prep` khi trưởng nhóm báo xong).

Zip gồm (không chứa ảnh):
- **mô hình:**
  - Người 1: `minifasnet_v2_ft.onnx` (cùng đầu vào/ra với bản đang chạy);
  - Người 2: `dinov2_pad.onnx` + `dinov2_pad_delta.safetensors` + `dinov2_pad_config.json`;
- **calibrator** `calibrators/face_pad/*.json`, fit trên calib_fit, có `model_version` riêng cho từng mô hình:
  - bản tinh chỉnh: `minifasnet-v2-ft@<sha8>+…`, `dinov2-reg-b14-ft@<sha8>+…`;
  - calibrator ứng viên cho MiniFASNet gốc mang đuôi `.fasvn-candidate.json`, để không trùng file identity trong repo;
  - **KHÔNG chép vào `ml/configs/calibrators/`**: ROUT-01 quyết định;
- **điểm từng mẫu:** `scores_calib_fit.csv`, `scores_calib_ltt.csv` (mã mẫu, nhóm người, nhãn, nguồn, điểm thô, xác suất đã hiệu chỉnh), `aux_scores.csv` (test phụ);
- **chia tập:** `splits.csv`, `split_{train,calib_fit,calib_ltt,test}.csv`, `prep_done.json`;
- **báo cáo:** `card.md`, `metrics.json`, `cleaning_report.json`, `leak_check.json`, `SHA256SUMS.txt`.

## Phần G — Lỗi thường gặp

| Bạn thấy | Nghĩa là | Làm gì |
|---|---|---|
| `KHÔNG TÌM THẤY FAS-VN` (prep) | Chưa Add Input dataset | Phần D, rồi Run All |
| `KHÔNG TÌM THẤY DỮ LIỆU ĐÃ CHUẨN BỊ` (notebook dạy) | Chưa Add Input notebook `prep_pad` | Phần P, rồi Run All |
| `Dữ liệu chuẩn bị là bản CHẠY THỬ` | Prep đang là bản SMOKE | Đợi Người 1 chạy prep thật, Add Input bản mới |
| `Dữ liệu chuẩn bị được tạo bằng phiên bản code KHÁC` | Hai file notebook không cùng đợt | Xin trưởng nhóm bộ 3 file mới, Người 1 chạy lại prep |
| `KHÔNG TẢI ĐƯỢC … từ Hugging Face` / `URLError` | Internet tắt hoặc HF lỗi tạm | Bật **Internet → On**. Đã bật thì đợi 15 phút rồi Run All lại |
| `SAI SHA-256` | File tải về hỏng | Run All lại một lần. Vẫn lỗi thì gửi trưởng nhóm |
| `CẢNH BÁO: KHÔNG THẤY GPU` (notebook dạy) | Chưa bật GPU | **Accelerator → GPU T4 x2** → Run All |
| `DỪNG: mô hình chỉ nhìn siêu dữ liệu…` / `DỪNG: nhóm người lớn nhất…` (prep) | Kiểm tra chất lượng dữ liệu không đạt | **Không chạy tiếp.** Chụp màn hình gửi trưởng nhóm |
| Kaggle báo hết **quota GPU** (30 giờ/tuần) | Hết giờ GPU tuần này | Đợi tuần sau (Kaggle hiện ngày làm mới), nhờ người khác chạy, hoặc dùng Colab (Phần H) |
| Test phụ ghi `BỎ QUA …` | Không tải được dữ liệu phụ | Không sao. Báo trưởng nhóm |

> **Chỉ khi lỗi hết bộ nhớ.** Đây là chỗ duy nhất ngoài `SMOKE` được phép sửa, trong ô "Bước 0":
> - `CUDA out of memory` ở bước 6b: đổi `BATCH_DINO = 16 if SMOKE else 48` thành `… else 24` (vẫn lỗi thì `16`).
> - `CUDA out of memory` ở bước 6a: đổi `BATCH_MINIFAS` từ `256` thành `128`.
> - Notebook tự khởi động lại, báo "tried to allocate more memory than is available" (hết RAM): đổi `NUM_WORKERS = 0 if os.name == "nt" else 2` thành `… else 0`.
>
> Sau khi sửa, Run All: notebook chạy tiếp từ checkpoint. Ghi lại thay đổi khi gửi zip.
> Các thông số làm sạch và chia tập (ví dụ `ARC_THRESHOLD`) **chỉ có tác dụng trong `prep_pad`**, và chỉ trưởng nhóm được đổi.

---

## Phần H — Google Colab (dự phòng)

1. **Khóa Kaggle API** (chỉ cần cho `prep_pad`): kaggle.com → ảnh đại diện → **Settings** → **API** → **Create New Token**.
   Mở file `kaggle.json` vừa tải bằng Notepad để xem `username` và `key`. **Giữ bí mật.**
2. **colab.research.google.com** → **File → Upload notebook** → chọn đúng file.
3. **Runtime → Change runtime type**:
   - `prep_pad`: **CPU**;
   - notebook dạy: **T4 GPU**.
4. Chỉ cho `prep_pad`: biểu tượng **chìa khóa** (thanh trái) → **+ Add new secret** hai lần: `KAGGLE_USERNAME` và `KAGGLE_KEY`. Bật **Notebook access** cho cả hai.
5. **Runtime → Run all** → cho phép **Google Drive** (Connect → chọn tài khoản → Allow).
   - `prep_pad` tự tải FAS-VN và ghi vào `My Drive/vericlue_pad/pad_prep`.
6. **Chia sẻ cho Người 2:**
   1. Người 1 mở Google Drive → chuột phải thư mục `vericlue_pad` → **Share** → thêm Gmail của Người 2, quyền **Viewer**.
   2. Người 2 mở **Shared with me** → chuột phải `vericlue_pad` → **Organize → Add shortcut** → **My Drive**.
      Đổi tên lối tắt thành `vericlue_pad_nguoi1` (chuột phải → Rename), để không trùng thư mục `vericlue_pad` của chính Người 2.
   3. Notebook dạy tự tìm `pad_prep` trong My Drive.
7. **Bị ngắt:** Runtime → Run all lại. Checkpoint nằm ở `My Drive/vericlue_pad/pad_work`.
8. **Kết quả:** file zip trong `My Drive/vericlue_pad`. Chia sẻ cho trưởng nhóm (chỉ người trong nhóm).

Lỗi riêng của Colab:
- `SecretNotFoundError`: chưa thêm secret hoặc chưa bật Notebook access.
- `403 Forbidden` khi tải dataset: mở trang dataset trên Kaggle bằng đúng tài khoản đó, bấm **Download** một lần để chấp nhận điều khoản.

---

## Ghi chú cho trưởng nhóm

- Ba notebook được sinh từ một mẫu bằng `uv run --no-sync python scripts/build_pad_notebook.py`.
  - Code nhúng: `pad.py`, `eval/metrics.py`, `face/pad_tuning.py`, `common/calibration.py`, manifest.
  - Hai notebook dạy chỉ khác dòng `MODEL`.
  - **Không sửa tay file `.ipynb` trong repo.** Sửa mẫu trong `scripts/build_pad_notebook.py` rồi sinh lại.
- **Gộp 2 zip trên laptop** (CPU, vài giây):
  `uv run --no-sync python ml/notebooks/combine_pad.py --minifasnet <zip Người 1> --dinov2 <zip Người 2> --out <thư mục>`.
  - Script kiểm SHA-256 các file chia tập trùng nhau, rồi ghép từng mẫu calib_fit.
  - Script đo MiniFASNet / DINOv2 / GỘP (max xác suất đã hiệu chỉnh) và in khuyến nghị.
  - MiniFASNet dùng để gộp là bản tốt hơn giữa gốc và tinh chỉnh, chọn theo cùng quy tắc ở notebook và ở combine: APCER@BPCER≤1 %, hòa thì AUC (`rank_key`).
  - Checkpoint trong lúc dạy chọn theo APCER → EER → AUC (`selection_key`).
- Mô hình và calibrator đặt ở `MODELS_DIR/finetuned/pad/<ngày>/`. Calibrator **không** chép vào `ml/configs/` cho tới khi ROUT-01 quyết định.
- Split `test` của FAS-VN mới chia **chưa** được dùng. Chạy test **một lần** trên máy sau khi chốt.
- Chạy thử trên máy: các biến môi trường `PAD_SMOKE`, `PAD_FASVN_DIR`, `PAD_OUT_DIR`, `PAD_INPUT_ROOT`, `PAD_LOCAL_MODELS_DIR`, `PAD_AUX_DIRS`, `PAD_PREP_DIR` (xem bàn giao FACE-04).
