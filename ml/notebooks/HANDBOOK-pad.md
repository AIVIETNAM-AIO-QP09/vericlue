# Sổ tay kỹ thuật — notebook PAD (FACE-04)

Dành cho thành viên nhóm AI cần **sửa** notebook khi chạy trên Kaggle/Colab gặp lỗi. Người chỉ cần chạy notebook thì đọc [`README-pad.md`](README-pad.md).

Có 3 notebook, **sinh tự động** từ `scripts/build_pad_notebook.py`. Cả 3 dùng chung code nhúng từ repo:

| File | Vai trò | Máy |
|---|---|---|
| `prep_pad.ipynb` | Chuẩn bị dữ liệu **một lần**: kiểm kê, làm sạch, gom người, chia tập, cắt mặt, kiểm lộ đề | CPU |
| `finetune_pad_minifasnet.ipynb` | Dạy MiniFASNet V2 + đo MiniFASNet gốc, hiệu chỉnh, xuất zip | GPU |
| `finetune_pad_dinov2.ipynb` | Dạy DINOv2-reg ViT-B/14, hiệu chỉnh, xuất zip | GPU |

Hai notebook dạy **chỉ khác một dòng `MODEL`**. Trưởng nhóm gộp hai zip bằng `ml/notebooks/combine_pad.py` trên laptop.

> **Quy tắc vàng:** sửa ít nhất có thể. Thấy cần đụng vào **VÙNG CẤM SỬA** (mục 3) thì **dừng lại và gửi trưởng nhóm**.

---

## 1. Bản đồ notebook (từng ô)

Thời gian "chạy thử" là số đo thật trên laptop nhóm (RTX 4050, 400 ảnh, 1 epoch, 20/10). Thời gian "chạy thật T4" là **ước tính**, chưa đo trên Kaggle.

### Các ô chung (cả 3 notebook)

| Ô | Mục đích | Đầu vào | Đầu ra | Log mong đợi | Kiểm tra đã chạy đúng |
|---|---|---|---|---|---|
| **Thông tin môi trường** | In phiên bản Python và thư viện (đọc bằng `importlib.metadata`, không import), GPU (`nvidia-smi`), đĩa trống, RAM | — | — | `Python 3.x …`, danh sách gói, `GPU: …`, `Đĩa /kaggle/working: trống … GB` | Có dòng GPU khi notebook dạy (Accelerator = GPU) |
| **NGUỒN** (sinh tự động) | Hằng số: `SOURCE_COMMIT`, `SOURCE_DIRTY`, `SOURCE_FILES` (SHA-256 file nguồn), `MANIFEST` (URL + revision + SHA-256 trọng số), `AUX_HF` (test phụ) | — | biến toàn cục | không in gì | — |
| **Bước 0 — Cấu hình** | Đọc `SMOKE`, nhận môi trường (`kaggle`/`colab`/`local`), đặt thư mục, hằng số, hàm `step()` in thời gian. Notebook dạy: sao chép checkpoint cũ nếu có trong Input | biến môi trường `PAD_*` (chỉ máy nhóm) | `ENV`, `INPUT_ROOT`, `OUT_DIR`, `WORK`, `CONFIG`, `PREP_HASH` | `Môi trường: kaggle \| MÔ HÌNH: … \| SMOKE=…`, bảng ước tính | Đúng `MÔ HÌNH` theo tên file |
| **NHÚNG TỪ REPO** ×4 | Code sản phẩm chép nguyên văn: `pad.py` (SCRFD, cắt MiniFASNet), `eval/metrics.py`, `face/pad_tuning.py`, `common/calibration.py` + `Module` | — | hàm/lớp | không in gì | Chạy không lỗi |
| **Bước 1** | Cài gói ghim nếu thiếu (`onnx==1.23.2`, `safetensors==0.8.0`; `onnxruntime-gpu==1.31.0` chỉ khi chưa có CUDA; `transformers==4.57.6` chỉ khi thiếu `Dinov2WithRegistersModel`; Colab thêm `kaggle==1.7.4.5`). Tắt TF32. Tải trọng số theo `MANIFEST`, kiểm SHA-256. Tạo phiên ONNX | Internet | `WORK/weights/<id>/…`, `FINDER`, `ARC_SESSION`, `MINIFAS_SESSION`, `MINI_SIZE`, `DEVICE`, `VERSIONS` | `OK minifasnet/minifasnet_v2.onnx rev=bfcc7d48 sha256=…`, `ONNX Runtime dùng: …` | Mọi dòng `OK …`. Prep phải in `CPUExecutionProvider` |

### `prep_pad.ipynb`

| Ô | Mục đích | Đầu vào | Đầu ra | Log mong đợi | Thời gian (chạy thử / chạy thật) | Kiểm tra |
|---|---|---|---|---|---|---|
| **Bước 2 — Kiểm kê** | Tìm thư mục chứa `train_photo` (sâu tối đa 5 cấp dưới `INPUT_ROOT`). Liệt kê ảnh `live`/`not_live`, đọc định dạng thật theo byte đầu. Colab: tải bằng Kaggle API | dataset `maihongtng/face-anti-spoofing` | `FAS_ROOT`, `rows` (danh sách dict) | `FAS-VN ở …: 11376 ảnh`, bảng nguồn A/B, `Ảnh sai đuôi …: 2331` (bản đầy đủ) | ~0 / 1–2 phút | Tổng khoảng 11.376 ảnh (chạy thật) |
| **Bước 3 — Làm sạch, gom người, chia** | Đọc từng ảnh **một lần**: SHA-256, dHash, SCRFD (đệm viền 33 % khi trượt), ArcFace (chỉ trong RAM), cắt mặt bằng `pad_crop` (= `MiniFasNetClassifier._crop`) → ảnh **thô** `raw80/raw224` + ảnh **nén lại JPEG** `crops80/crops224`. Lọc trùng, gom nhóm (dHash ≤ 8 hoặc ArcFace ≥ 0,40, union-find), `assign_splits`, ghi 0 vào ảnh cắt của test | ảnh FAS-VN | `pad_prep/rows.csv`, `splits.csv`, `split_{train,calib_fit,calib_ltt,test}.csv`, `crops80.npy`, `crops224.npy`, `raw80.npy`, `raw224.npy`, `cleaning_report.json` | `250/N ảnh, … ảnh/giây, còn ~… phút`, `Giữ …/… ảnh; … nhóm người; nhóm lớn nhất …`, `SHA-256 các file chia tập …` | 1,3 phút (400 ảnh, 5,2 ảnh/giây CPU laptop) / 63 phút trên laptop nhóm (3,0 ảnh/giây CPU 4 luồng, 11.360 ảnh, đo 20/10) | Nhóm lớn nhất < 40 % số ảnh; split có cả live và not_live |
| **Bước 4 — Kiểm lộ đề** | Mô hình chỉ dùng siêu dữ liệu của ảnh đã nén lại (StratifiedGroupKFold, AUC trung bình theo fold). Chặn nếu > 0,6. In thêm cỡ file, phân tầng theo nguồn A/B | `rows` (train + calib_fit) | `leak_check.json`, `prep_done.json` | Bảng đặc trưng, `ĐẠT: AUC siêu dữ liệu = 0.5xx ≤ 0.6` | < 1 phút | Có dòng `ĐẠT`. `prep_done.json` tồn tại |
| **Bước 5 — Lưu** | Liệt kê file, in SHA-256 `splits.csv`, nhắc Save Version | — | — | `XONG chuẩn bị: … (… GB)` | ~0 | Kích thước khoảng 3–4 GB (chạy thật) |

### Notebook dạy (`finetune_pad_minifasnet` / `finetune_pad_dinov2`)

| Ô | Mục đích | Đầu vào | Đầu ra | Log mong đợi | Kiểm tra |
|---|---|---|---|---|---|
| **Bước 2 — Nạp dữ liệu chuẩn bị** | Tìm `pad_prep/prep_done.json` dưới `INPUT_ROOT`, `OUT_DIR` (và `MyDrive` trên Colab). Kiểm `pad.py`/`pad_tuning.py` cùng SHA-256 với lúc prep. Từ chối prep SMOKE khi dạy thật. Nạp `rows`, các mảng ảnh cắt, hash chia tập, `LEAK` | output `prep_pad` | `PREP_DIR`, `rows`, `CROPS80/224`, `RAW80/224`, `SPLITS_SHA`, `SPLIT_FILE_SHA` | `Dùng dữ liệu chuẩn bị ở …`, `splits.csv SHA-256 = …` | SHA-256 giống dòng Người 1 gửi |
| **Bước 5 — MiniFASNet gốc** | Chỉ khi `MODEL = "minifasnet"`: chấm `raw80` (đúng đường `pad.py`) trên calib_fit và calib_ltt | `MINIFAS_SESSION` | `SCORES`, `SCORES_LTT`, `METRICS["baseline"]` | `MiniFASNet gốc AUC=… EER=… APCER@BPCER≤1%=…` | — |
| **Bước 6 (ô định nghĩa)** | `CropSet` (dạy: `crops*` + tăng cường; đo: `raw*`), `train_model` (checkpoint mỗi epoch vào `pad_work/ckpt/<tên>/last.pt` và `best.pt`, tự chạy tiếp), trọng số lớp | — | hàm | `train: … live, … not_live → trọng số lớp …` | — |
| **Bước 6a** (MiniFASNet) | Đồ thị ONNX gốc → PyTorch (`build_torch_graph`), dạy toàn bộ | `PATH_MINIFAS` | `mini_model`, `HISTORY`, `SCORES["minifasnet_ft"]` | `Đồ thị PyTorch khớp ONNX gốc: lệch tối đa …`, `minifasnet_ft epoch k/12: …`, `chọn checkpoint epoch …` | Lệch < 1e-2 |
| **Bước 6b** (DINOv2) | `Dinov2WithRegistersModel` + đầu tuyến tính; dạy 2 khối cuối + layernorm + đầu, fp16 | `DINO_DIR` | `dino_model`, `SCORES["dinov2_ft"]` | `Tham số được dạy: 14.2 triệu / 86.6 triệu`, `dinov2_ft epoch …` | — |
| **Bước 7 — Hiệu chỉnh** | `calibration_fit` (= `common/calibration.fit`) cho từng mô hình trên calib_fit; xếp hạng theo `rank_key` (APCER, rồi AUC); khuyến nghị | `SCORES`, nhóm người | `CALIBRATORS`, `METRICS`, `RECOMMENDATION`, `MODEL_VERSIONS` | `Hiệu chỉnh …: platt, log-loss … → …`, bảng so sánh, `KHUYẾN NGHỊ: …` | Có dòng `Hiệu chỉnh` cho mỗi mô hình |
| **Bước 8 — Test phụ** | Axon/UniData tải từ HF (ghim revision, nếu `AUX_FROM_HF`), Zalo nếu có `label.csv`; cắt mặt, chấm bằng ngưỡng calib_fit | Internet, Input Zalo | `AUX_ROWS`, `AUX_RESULTS` | `tải axon_print: 5 file …`, khối `axon: … khung từ … file` | Không sao nếu `BỎ QUA` |
| **Bước 9 — Kiểm cuối** | `USED ∩ test = ∅`; ảnh cắt của test đều bằng 0 | — | — | `OK: … ảnh đã dùng …, 0 ảnh thuộc test` | Phải có dòng `OK` |
| **Bước 10 — Xuất** | ONNX (MiniFASNet: thay initializer trong đúng đồ thị gốc; DINOv2: cố định vị trí 224), calibrator JSON, `scores_calib_{fit,ltt}.csv`, `card.md`, `metrics.json`, `SHA256SUMS.txt`, zip | — | `OUT_DIR/pad_export_<MODEL>_<giờ>[_smoke].zip` | `đầu vào/ra giống bản gốc = True; lệch …`, `Calibrator: …`, `XONG. File cần gửi trưởng nhóm: …` | Zip có trong Output |

Thời gian chạy thật trên T4 (ước tính): bước 6a 10–20 phút; bước 6b 30–60 phút; bước 8 5–15 phút; các bước còn lại vài phút.

---

## 2. Cấu hình (ô "Bước 0")

**An toàn** = đổi được, không ảnh hưởng tính so sánh. **Chỉ khi lỗi bộ nhớ** = chỉ đổi theo bảng lỗi. **CẤM đổi** = chỉ trưởng nhóm, vì đổi sẽ làm hỏng cách chia tập hoặc so sánh.

| Biến | Tác dụng | Khoảng an toàn | Mức |
|---|---|---|---|
| `SMOKE` | `True` = chạy thử (100 ảnh/thư mục, 1 epoch, test phụ 4 file) | True/False | **an toàn** (member chỉ đổi biến này) |
| `USE_DRIVE` | Colab: lưu vào Google Drive | True | an toàn (để True) |
| `BATCH_MINIFAS` | Lô bước 6a (chạy thật 256) | 64–256 | **chỉ khi lỗi bộ nhớ** |
| `BATCH_DINO` | Lô bước 6b (chạy thật 48) | 16–48 | **chỉ khi lỗi bộ nhớ** |
| `NUM_WORKERS` | Tiến trình đọc dữ liệu (Linux 2, Windows 0) | 0–2 | **chỉ khi lỗi bộ nhớ** |
| `SEED` | Seed chia tập, tăng cường, dạy | 42 | **CẤM đổi** |
| `MODEL` | Vai trò file (sinh tự động) | — | **CẤM đổi** (mở file đúng thay vì sửa) |
| `SMOKE_PER_FOLDER`, `JPEG_QUALITY`, `DET_PAD_RATIO`, `DHASH_DUP`, `DHASH_LINK`, `ARC_THRESHOLD`, `MAX_GROUP_SHARE`, `FRACTIONS`, `DINO_SIZE` | Tham số chuẩn bị dữ liệu, chỉ có tác dụng trong `prep_pad`. Notebook dạy đọc lại giá trị từ `prep_done.json` | — | **CẤM đổi** sau khi đã chạy prep (đổi thì phải chạy lại prep, và hai notebook dạy phải dùng prep mới) |
| `MAX_BPCER` | Ngưỡng BPCER khi chọn mô hình | 0,01 | **CẤM đổi** |
| `LEAK_GATE_FILE_SIZE` | Chặn cả theo cỡ file JPEG (trưởng nhóm đã chốt: False) | False | **CẤM đổi** |
| `EPOCHS_MINIFAS`, `EPOCHS_DINO`, `LR_*`, `DINO_TRAIN_BLOCKS` | Siêu tham số dạy | — | **CẤM đổi** (trưởng nhóm quyết) |
| `EXPORT_DINO_ONNX` | Xuất ONNX cho DINOv2 | True | an toàn (False chỉ khi xuất ONNX làm treo, báo trưởng nhóm) |
| `N_BOOT` | Số lần bootstrap CI | 50/500 | an toàn |
| `AUX_FROM_HF`, `AUX_MAX_FILES` | Tải test phụ từ HF; giới hạn số file | — | an toàn (tắt nếu HF lỗi mãi) |
| Biến môi trường `PAD_*` | Chỉ dùng khi chạy thử trên máy nhóm | — | không dùng trên Kaggle |

---

## 3. VÙNG CẤM SỬA

Nếu cách sửa có vẻ đòi đụng vào các phần dưới: **dừng lại, gửi trưởng nhóm** (traceback + output ô Thông tin môi trường).

| Vùng | Ở đâu | Vì sao cấm |
|---|---|---|
| Chặn split `test`: `assert_not_test`, `rows_of_split`, `take_idx`, `USED`, ghi 0 ảnh cắt test, bước 9 | `pad_tuning.py`, bước 3, 5, 6, 9 | Test chỉ được dùng **một lần** sau khi chốt mô hình. Lộ test thì mọi số R1 vô giá trị (thể lệ cấm làm giả kết quả) |
| Gom người và chia tập: dHash, ArcFace, `link_groups`, `assign_splits`, `SEED`, `ARC_THRESHOLD`, `FRACTIONS`, nội dung các file `split_*.csv` | bước 3 (prep), `pad_tuning.py` | Hai notebook dạy và `combine_pad.py` phải dùng **cùng một** cách chia (kiểm bằng SHA-256). Chia sai thì người trùng giữa train và test |
| Tiền xử lý chép từ `pad.py`: `ScrfdFaceFinder`, `MiniFasNetClassifier._crop`, `pad_crop`, `PAD_CROP_SCALE`, cách đưa ảnh BGR 0–255 vào MiniFASNet, `raw80/raw224` | ô NHÚNG, `to_input`, bước 5 | Phải **khớp server**. Lệch là mô hình tinh chỉnh không cắm lại được, calibrator sai |
| Cổng lộ đề: `meta_features`, `leak_auc`, `LEAK_AUC_MAX = 0,6`, bước 4 | prep | Là bằng chứng mô hình không học lối tắt (EXIF, độ phân giải). Không được nới để "cho qua" |
| API hiệu chỉnh: `calibration_fit`, `CalibFit`, `Calibrator` (chép nguyên văn `common/calibration.py`) | ô NHÚNG, bước 7 | Calibrator phải nạp được bằng `CalibrationStore` của hệ thống (ADR-0010) |
| Định dạng xuất: tên file zip, cột `scores_*.csv`, `metrics.json` (`model`, `dataset.split_files_sha256`), cách đặt `model_version` (`minifasnet-v2-ft@<sha8>+scrfd-10g@bfcc7d48`, `dinov2-reg-b14-ft@<sha8>+…`, file gốc mang đuôi `.fasvn-candidate.json`), ONNX giữ đúng đầu vào/ra | bước 10 | `combine_pad.py` và ROUT-01 đọc đúng các tên này |
| Trọng số: `MANIFEST` (URL, revision, SHA-256) | ô NGUỒN, bước 1 | Ghim nguồn để tái lập được. SHA-256 sai thì **không** được sửa mã cho khớp |

Code nhúng (ô NHÚNG TỪ REPO) **không sửa tay**. Nếu lỗi nằm ở đó, sửa trong repo rồi sinh lại notebook. Việc này do trưởng nhóm làm.

---

## 4. Lỗi thường gặp và cách sửa

| Dấu hiệu (chuỗi trong lỗi) | Nguyên nhân | Cách sửa |
|---|---|---|
| `ERROR: pip's dependency resolver does not currently take into account …` | Cảnh báo xung đột phiên bản trên image Kaggle | Thường **vô hại**; đọc tiếp. Chỉ xử lý khi sau đó có `ImportError` |
| `ImportError` / `cannot import name 'Dinov2WithRegistersModel'` | `transformers` quá cũ, bước 1 không cài được | Thêm một ô ngay trước bước 1: `!pip install -q transformers==4.57.6`, rồi **Restart & Run All**. Ghi lại thay đổi |
| `… requires torch>=…` khi import transformers | Image Kaggle có torch cũ hơn | Không nâng torch (rất nặng). Thử `!pip install -q "transformers>=4.48,<4.58"`, Restart & Run All |
| `ONNX CUDA lỗi, dùng CPU: … libcudnn …` hoặc `CUDAExecutionProvider` không có | `onnxruntime-gpu` không hợp CUDA của image | Notebook **tự lùi CPU**, vẫn chạy được, chỉ chậm hơn (dò mặt ở bước 8). Không cần sửa |
| `CUDA out of memory` / `torch.OutOfMemoryError` | Hết VRAM | Giảm `BATCH_DINO` (48 → 24 → 16) hoặc `BATCH_MINIFAS` (256 → 128), rồi Run All (chạy tiếp từ checkpoint) |
| "Your notebook tried to allocate more memory than is available", kernel tự khởi động lại | Hết RAM | `NUM_WORKERS = 0`, Run All |
| `OSError: [Errno 28] No space left on device` | `/kaggle/working` đầy (giới hạn khoảng 20 GB) | Xóa thư mục `pad_export_*` cũ và `pad_work/aux`. **Không** xóa `pad_prep` khi chưa xong. `prep_pad` cần khoảng 4 GB, notebook DINOv2 khoảng 1 GB zip |
| `KHÔNG TÌM THẤY FAS-VN` | Chưa Add Input, hoặc cấu trúc dataset khác (không có `train_photo`) | Add Input `maihongtng/face-anti-spoofing`. Nếu đã add mà vẫn lỗi: chạy `!find /kaggle/input -maxdepth 4 -name train_photo` để xem đường dẫn; sâu hơn 5 cấp thì báo trưởng nhóm. **Không** đổi thư mục `live`/`not_live` |
| `KHÔNG TÌM THẤY DỮ LIỆU ĐÃ CHUẨN BỊ` | Chưa Add Input output `prep_pad` | Add Input notebook prep (tab Notebooks). Kiểm tra: `!find /kaggle/input -maxdepth 3 -name prep_done.json` |
| `Dữ liệu chuẩn bị được tạo bằng phiên bản code KHÁC` | Notebook dạy và prep không cùng đợt sinh | Xin trưởng nhóm bộ 3 file cùng commit, chạy lại prep. **Không** xóa dòng kiểm tra |
| `Dữ liệu chuẩn bị là bản CHẠY THỬ` | Prep SMOKE | Đợi prep thật |
| `File chia tập trong pad_prep bị sửa` | Có ai sửa `split_*.csv` | Dùng lại output prep gốc. Báo trưởng nhóm |
| `HTTP Error 429` / `Too Many Requests` khi tải từ HF | Bị giới hạn lượt tải | Đợi 15–30 phút rồi Run All (file đã tải đúng SHA thì không tải lại) |
| `SAI SHA-256 …` | File tải về hỏng, hoặc nguồn HF đổi file | Run All lại một lần. Vẫn sai thì **dừng, báo trưởng nhóm** (không sửa SHA) |
| `KHÔNG TẢI ĐƯỢC … từ Hugging Face` | Internet tắt | Settings → Internet On |
| Phiên bị ngắt (12 giờ hoặc khoảng 1 giờ không thao tác) | Giới hạn Kaggle | Notebook dạy: Run All, tự chạy tiếp từ `pad_work/ckpt/<tên>/last.pt` (Persistence = Files only), hoặc Add Input bản đã Save Version của chính notebook. Prep: chạy lại |
| Colab `drive.mount` lỗi / `credential propagation was unsuccessful` | Chưa cho phép Drive | Chạy lại ô Bước 0, chọn đúng tài khoản, Allow |
| Colab không thấy `pad_prep` của Người 1 | Chưa thêm lối tắt | Shared with me → Add shortcut vào My Drive, đặt tên `vericlue_pad_nguoi1` |
| `Không xuất được ONNX cho DINOv2 (vẫn có safetensors): …` | Bản torch không xuất được một toán tử | Chấp nhận được: zip vẫn có `dinov2_pad_delta.safetensors`. Ghi chú cho trưởng nhóm |
| `AssertionError` ở bước 10, dòng `assert same_io and gap < 1e-3` | ONNX MiniFASNet xuất ra lệch PyTorch | **Dừng, báo trưởng nhóm** (vùng cấm: định dạng xuất) |
| `Đồ thị PyTorch không khớp MiniFASNet gốc` | Bản ONNX/torch lạ | Dừng, báo trưởng nhóm |
| `KHÔNG hiệu chỉnh được …: GroupKFold cần ít nhất hai subject` / `Một fold fit thiếu lớp` / `AUC < 0.5` | calib_fit quá ít nhóm người, hoặc mô hình tệ (thường do SMOKE quá nhỏ) | Với SMOKE: chấp nhận. Chạy thật mà gặp: **báo trưởng nhóm**. Thiếu calibrator thì `combine_pad.py` không gộp được |
| `DỪNG: mô hình chỉ nhìn siêu dữ liệu vẫn đoán được nhãn` | Cổng lộ đề không đạt | **Không sửa.** Gửi trưởng nhóm |
| `DỪNG: nhóm người lớn nhất chiếm …` | **Nối chuỗi**: nhiều người khác nhau bị nối thành một nhóm qua chuỗi cặp "hơi giống" (A giống B, B giống C…). Đã gặp ngày 20/10 với ngưỡng cũ ArcFace 0,40 + dHash 8: 4.887/10.878 ảnh. Ngưỡng hiện tại (0,45 + dHash 4) cho nhóm lớn nhất 51 ảnh (0,47 %). Chặn ở 5 % | **Không tự đổi ngưỡng.** Kiểm tra đang dùng file `prep_pad.ipynb` mới nhất (Bước 0 phải có `ARC_THRESHOLD = 0.45`, `DHASH_LINK = 4`). Đúng file mà vẫn lỗi thì gửi trưởng nhóm 2 dòng `Giữ …` và `Cặp dHash …` |
| `File notebook hỏng: MODEL phải là …` | Đã sửa dòng `MODEL` | Tải lại file gốc trưởng nhóm gửi |

---

## 5. Nhờ AI sửa (mẫu prompt, dán nguyên văn rồi điền)

```
Tôi đang chạy notebook <tên file .ipynb> của dự án VeriClue (tinh chỉnh PAD) trên <Kaggle/Colab>.
Ô bị lỗi là "<tên bước, ví dụ Bước 6b>". Dưới đây là:

1) Toàn bộ code của ô bị lỗi:
<dán code>

2) Toàn bộ traceback (từ dòng đầu tới dòng cuối, không cắt):
<dán traceback>

3) Output của ô "Thông tin môi trường":
<dán output>

QUY TẮC BẮT BUỘC khi đề xuất sửa:
- Chỉ sửa TỐI THIỂU để hết lỗi. Giải thích rõ: sửa dòng nào, vì sao, có ảnh hưởng gì.
- KHÔNG được sửa các vùng cấm: chặn split test (assert_not_test, USED, bước 9); logic gom người/chia tập,
  SEED, ARC_THRESHOLD, FRACTIONS, file split_*.csv; tiền xử lý chép từ pad.py (ScrfdFaceFinder,
  MiniFasNetClassifier._crop, pad_crop, to_input); cổng lộ đề (meta_features, leak_auc, ngưỡng 0,6);
  API hiệu chỉnh (calibration_fit, CalibFit, Calibrator); định dạng xuất (tên file, cột CSV, model_version);
  MANIFEST/SHA-256 trọng số; các ô "NHÚNG TỪ REPO".
- Nếu cách sửa duy nhất là đụng vùng cấm: KHÔNG sửa, chỉ giải thích nguyên nhân để tôi gửi trưởng nhóm.
- Không bịa số liệu, không tắt kiểm tra để "cho chạy qua".
```

---

## 6. Sau khi sửa

1. Thêm comment ngay dòng đã sửa: `# SỬA bởi <tên> <ngày>: <lý do ngắn>`.
2. Run All lại. Kiểm tra bước 9 vẫn in `OK: … 0 ảnh thuộc test`.
3. Gửi trưởng nhóm cùng lúc với zip:
   - file `.ipynb` đã sửa (Kaggle: **File → Download notebook**);
   - một dòng mô tả lỗi và cách sửa.
4. Trưởng nhóm đưa bản sửa vào **mẫu** `scripts/build_pad_notebook.py` (hoặc file nguồn trong `ml/src`), rồi sinh lại notebook. **Không** sửa tay các file `.ipynb` trong repo, vì test `scripts/tests/test_build_pad_notebook.py` sẽ báo lệch.

---

## 7. Số đo chạy thử trên máy nhóm (20/10, thử tay, không phải R1)

Xem bàn giao FACE-04 (`docs/status/handoffs/2026-10-19-1146-face-04-lead-claude.md`) để có số đo mới nhất. Lệnh tái lập dùng các biến `PAD_SMOKE=1`, `PAD_FASVN_DIR`, `PAD_OUT_DIR`, `PAD_INPUT_ROOT`, `PAD_LOCAL_MODELS_DIR`, `PAD_AUX_DIRS`, `PAD_PREP_DIR`, kèm `jupyter nbconvert --execute`.
