# Sổ tay kỹ thuật: sửa `calibrate_gend.ipynb` trên Kaggle/Colab (FACE-04)

Dành cho thành viên nhóm AI phải **sửa lỗi** notebook khi chạy. Bạn không cần là chuyên gia, nhưng nên dùng trợ lý AI (mẫu câu hỏi ở mục 5).
- Muốn chạy bình thường: đọc `README-gend.md`.
- Muốn sửa lỗi: đọc file này.

> Notebook được **sinh tự động** từ `ml/notebooks/templates/calibrate_gend.py` bằng `scripts/build_gend_notebooks.py`. Code trong `vericlue_ml/…` được **nhúng nguyên văn** (ô số 2) và kiểm SHA-256.
>
> Bạn được sửa notebook **trên Kaggle/Colab** để chạy cho xong. **Không sửa tay** file `.ipynb` trong repo. Trưởng nhóm sẽ chuyển chỗ sửa vào khuôn (mục 6).

---

## 1. Bản đồ notebook (từng ô)

Thời gian ghi trong bảng:
- **SMOKE** là số đo thật trên máy RTX 4050 (mẫu rất nhỏ).
- **Chạy thật trên T4** là **ước tính, chưa đo** (khoảng 1.200 RTFS giả, 400 RTFS thật, 800 FAS). Số đo thật nằm trong `step_times.json` của zip.

| Ô | Tên (dòng đầu ô) | Làm gì | Vào → ra | Log mong đợi | Thời gian | Kiểm thế nào |
|---|---|---|---|---|---|---|
| 0 | (markdown) | Giới thiệu | — | — | — | — |
| 1 | `CẤU HÌNH` | Đặt biến (mục 2) | — | — | tức thì | `SMOKE` đúng ý |
| 2 | `CODE NHÚNG TỪ REPO` | Ghi code repo ra `vc_src/`, kiểm SHA-256, thêm vào `sys.path` | → `vc_src/` | `Code nhúng: N file từ commit …` | < 5 s | Không có `Code nhúng bị sửa` |
| 3 | `0. Thông tin môi trường` | In phiên bản Python/torch/transformers/onnxruntime, GPU, RAM, ổ đĩa | → `ENV_INFO` (ghi vào `metrics.json`) | JSON có `cuda_available: true`, `gpu.name` | < 10 s | Dán nguyên khối này khi báo lỗi |
| 4 | `1. Môi trường` | Nhận nền tảng (kaggle/colab/local), tạo `OUT`/`WORK`, cài gói thiếu, tìm ffmpeg | → `OUT`, `WORK`, `FFMPEG` | `Nền tảng: kaggle \| GPU: Tesla T4 …`, đường dẫn kết quả, `ffmpeg version …` | 10 s – 2 phút | `OUT` = `/kaggle/working/calibrate_gend[_smoke]` |
| 5 | `2. Trọng số` | Tải GenD, CLIP (config), SCRFD theo `models/manifest.yaml` đúng revision; tải ArcFace; kiểm SHA-256; dựng GenD; assert `model_version` | → `WORK/models/…`, `DETECTOR` | `Mô hình: gend-clip-l14@891ce014+clip@32bd6428+scrfd-10g@bfcc7d48+agg-maxmeantop25-v1` | 0,1–1 phút (có sẵn) / vài phút (tải ~1,3 GB) | Chuỗi mô hình phải đúng như trên |
| 6 | `3. Tìm dữ liệu` | Tìm RTFS-10k và FAS-VN (biến môi trường → `/kaggle/input/<slug>` hoặc `/kaggle/input/datasets/<chủ>/<slug>` → Colab tải ZIP bằng Kaggle API) | → `RTFS_ROOT`, `FAS_ROOT` | Hai dòng `RTFS-10k:` / `FAS-VN  :` | tức thì (Kaggle); 20–40 phút (Colab tải) | Có `inswapper.csv` trong `RTFS_ROOT` |
| 7 | `4. Lập danh sách mẫu` | Chia RTFS theo video YouTube + ảnh donor (chỉ đọc CSV); lấy mẫu; dò `live` FAS-VN (bỏ trùng byte); nếu `USE_VLR` thì đọc mục lục ZIP VLR | → `SAMPLES`, `RTFS.report` | `RTFS — báo cáo chia: {...components_before_cut: 1...}`, `RTFS file có trên đĩa: a/b thật, c/d giả`, `FAS-VN live: {...}`, `Mẫu theo nguồn: {...}` | SMOKE ~10 s; thật: vài phút (băm toàn bộ ảnh FAS 8,9 GB) | Số file có trên đĩa > 0 |
| 8 | `5. … dò mặt + ArcFace` | (VLR nếu bật: tải song song 8 luồng.) Mỗi mẫu đọc 3 khung trong 3 s đầu (ảnh: 1 khung) → SCRFD → hộp mặt; ArcFace cho FAS-VN (và RTFS thật, chỉ để đo). **Mẫu RTFS thuộc test không được mở** | → `OUT/faces.jsonl`, `WORK/emb/*.npy` | `Dò mặt: i/n, … còn khoảng … phút`, `SCRFD có mặt (nguồn, có mặt): …` | SMOKE 1–4 phút; thật ước tính 20–40 phút | Hầu hết mẫu `True` (có mặt) |
| 9 | `6. Chia tập theo nhóm` | FAS-VN: gom người bằng ArcFace (ngưỡng 0,35) → nhóm → `calib_fit`/`calib_ltt`/`test` (0,4/0,3/0,3, theo `SEED`); đo cos ArcFace lớn nhất giữa các tập; ghi `splits.csv` | → `OUT/splits.csv`, `ROWS` | `Nhóm người Việt: {...}`, `Cos ArcFace lớn nhất giữa hai tập: …` (< 0,35), `RTFS thật — cos ArcFace lớn nhất calib_fit↔calib_ltt: …`, bảng phân bố | < 1 phút | Không có `CẢNH BÁO: một nhóm … > 30%` |
| 10 | `7. Cắt mặt + mã hóa lại` | Chỉ `calib_fit` + `calib_ltt` (`gt.rows_for` chặn test): cắt vuông 2,5× quanh mặt → 320×320 → H.264 CRF 23, 25 fps, ≤ 3 s; ảnh → video 1 khung | → `WORK/proc/<tập>/<nguồn>/*.mp4` | `Mã hóa lại: i/n …` | SMOKE 0,4–3 phút; thật ước tính 10–20 phút | Lỗi ffmpeg ghi ở `OUT/logs/ffmpeg.log` |
| 11 | `8. Kiểm lộ đề NGUỒN` | AUC đơn biến của đặc trưng thô (bitrate, độ nét, độ sáng…) trên `calib_fit`. **Chỉ cảnh báo, không dừng** | → `OUT/leak_report.json` | `[fas_vn_vs_rtfs_fake] CẢNH BÁO LỘ ĐỀ NGUỒN …` là **bình thường** | < 1 phút | — |
| 12 | `9. Chấm điểm GenD` | `DETECTOR.predict` đúng `face/gend.py` (8 khung/clip); ghi tiến độ từng mẫu | → `OUT/scores_progress.jsonl` | `Chấm điểm: i/n …`, `Đỉnh VRAM khi chấm: ~200–300 MB`, đếm trạng thái `ok/degraded/not_applicable` | SMOKE 0,4–1 phút; thật ước tính 30–45 phút | Phần lớn `ok` |
| 13 | `10. Fit calibrator` | `calibration.fit` **chỉ** trên `calib_fit`, nguồn `FIT_SOURCES` (FAS-VN + RTFS thật/giả); báo tỉ lệ vượt B=0,15/A=0,60 trước/sau | → `CAL`, `REPORT` | JSON có `"method": "platt"` hoặc `"isotonic"`, `exceed_rates_calib_fit` | < 1 phút | SMOKE có thể in `KHÔNG fit được calibrator` (bình thường) |
| 14 | `11. Lưu điểm` | Ghi điểm `calib_fit`, `calib_ltt` (không chọn ngưỡng) | → `scores_calib_fit.csv`, `scores_calib_ltt.csv` | `Đã lưu scores_…csv (n dòng)` | tức thì | — |
| 15 | `12. Tập test — TẮT` | Hàm `run_test()` bị khóa | — | `Tập test: TẮT (đúng luật)…` | tức thì | Phải thấy dòng này |
| 16 | `13. Xuất ZIP` | Lưu calibrator (định dạng `CalibrationStore`), `card.md`, `metrics.json`, CSV, `SHA256SUMS.txt` → zip; **xóa** `WORK/emb` và `faces.jsonl` | → `OUT/gend_calibration_[smoke_]YYYYMMDD_HHMM.zip` | `XONG sau … phút`, `SHA-256 zip: …` | tức thì | Zip có `calibrators/face_deepfake/….json` (khi fit được) |

**Chạy tiếp khi bị ngắt** (trong cùng phiên, hoặc khi `OUT`/`WORK` còn nguyên):
- Bước 5 đọc lại `OUT/faces.jsonl`.
- Bước 7 bỏ qua clip đã có trong `WORK/proc`.
- Bước 9 đọc lại `OUT/scores_progress.jsonl`.
- Mục lục ZIP VLR được cache ở `WORK/vlr_index`.

Trên Kaggle, `WORK` nằm ở `/kaggle/tmp` hoặc `/tmp` nên mất khi phiên mới. Vì vậy hãy dùng **Save & Run All (Commit)**.

---

## 2. Cấu hình (ô số 1)

| Biến | Mặc định | Khoảng an toàn | Ảnh hưởng | Mức |
|---|---|---|---|---|
| `SMOKE` | `True` | `True`/`False` | `True` dùng số mẫu nhỏ ở cuối ô | **an toàn** |
| `SEED` | `20261019` | — | Đổi `SEED` là đổi **cách chia tập** và mẫu được lấy; số đo không còn so được với lần chạy khác | **CẤM đổi** |
| `DEVICE` | `"cuda"` | `"cuda"`/`"cpu"` | `cpu` chậm hơn nhiều lần | an toàn |
| `USE_VLR` | `False` | Giữ `False` | Bật thì tải VLR từ Zenodo, **chỉ để tham khảo**, không vào fit | chỉ trưởng nhóm bật |
| `VLR_PARTS`, `VLR_VIDEOS_PER_PART`, `VLR_CLIPS_PER_VIDEO` | part1–6, 40, 3 | — | Chỉ có tác dụng khi `USE_VLR = True` | không cần đụng |
| `N_FAS_LIVE` | 800 | 200–800 | Giảm thì ít người Việt hơn; số đo nhiễu hơn | **chỉ khi lỗi bộ nhớ/thời gian** |
| `N_RTFS_REAL` | 400 | 100–400 | Như trên | chỉ khi lỗi bộ nhớ/thời gian |
| `N_RTFS_FAKE` | 1200 | 300–1200 | Như trên | chỉ khi lỗi bộ nhớ/thời gian |
| `ARCFACE_THRESHOLD` | 0,35 | — | Ngưỡng gom người; đổi là đổi cách chia | **CẤM đổi** |
| `RUN_TEST`, `TEST_CONFIRMATION` | `False`, `""` | — | Mở tập test | **CẤM** (chỉ trưởng nhóm) |

Nếu phải giảm số mẫu, ghi rõ trong tin nhắn gửi trưởng nhóm. `metrics.json` và `card.md` tự ghi lại số mẫu thật.

Biến môi trường (thường **không cần** trên Kaggle):
- `VC_OUT`, `VC_WORK`: đổi thư mục kết quả/nháp.
- `VC_RTFS_ROOT`, `VC_FAS_ROOT`: chỉ thẳng thư mục dữ liệu.
- `VC_FFMPEG`, `VC_FFPROBE`: chỉ đường dẫn ffmpeg.
- `VC_SRC`: nơi ghi code nhúng.
- `KAGGLE_USERNAME`, `KAGGLE_KEY`: Colab.

---

## 3. VÙNG CẤM SỬA

Nếu cách sửa **bắt buộc** đụng vào một trong các mục dưới: **DỪNG**, gửi lỗi cho trưởng nhóm, không tự sửa.

| Vùng | Ở đâu | Vì sao cấm |
|---|---|---|
| Chặn tập test | `RUN_TEST`, `TEST_CONFIRMATION`, `gt.rows_for(...)`, `gt.assert_no_test(...)`, `gt.check_test_unlocked`, đoạn bỏ qua mẫu test ở bước 5 | Test chỉ được dùng **một lần** sau khi chốt. Nhìn test là làm hỏng số liệu báo cáo (AGENTS.md luật 8) |
| Chia tập | `SEED`, `ARCFACE_THRESHOLD`, `gc.split_groups`, `gc.person_groups`, `CALIB_RATIOS` | Đổi cách chia thì `calib_fit`/`calib_ltt` không còn độc lập với lần trước, và ROUT-03 mất hiệu lực |
| Luật donor của RTFS | `gc.split_rtfs`, `gc.check_rtfs_split` | Bảo đảm một ảnh donor và một video gốc không nằm ở hai tập |
| Tiền xử lý GenD và phiên bản | `vericlue_ml/face/gend.py`, `pad.py`, `frames.py` (ô nhúng), `EXPECTED_MODEL_VERSION`, `assert MODEL_VERSION == …`, URL/SHA-256 trong manifest | Calibrator chỉ đúng với **đúng** pipeline mà máy chủ chạy. Lệch một bước là calibrator vô nghĩa |
| Cắt mặt / mã hóa lại | `gc.square_crop_box`, `gc.crop_encode_cmd`, `CROP_*`, `ENCODE_*` | Mọi nguồn phải đi cùng một đường để giảm lộ đề |
| API hiệu chỉnh và định dạng xuất | `calibration.fit`, `CalibFit`, `CalibrationStore(...).save`, cấu trúc zip | Server nạp JSON này bằng `CalibrationStore`; sai định dạng thì không dùng được |
| Nguồn để fit | `gc.FIT_SOURCES` (FAS-VN live + RTFS thật/giả), `gc.REFERENCE_SOURCES` | Quyết định trưởng nhóm 20/10: VLR **không** vào fit |
| Ngưỡng B/A | `gc.REPORT_THRESHOLDS` | Chỉ để báo cáo, phải khớp `ml/configs/thresholds.yaml` |
| Ô nhúng (ô 2) | toàn bộ | Có kiểm SHA-256. Sửa sẽ báo `Code nhúng bị sửa` |

---

## 4. Lỗi thường gặp → cách sửa

| Triệu chứng | Nguyên nhân hay gặp | Cách sửa (ngoài vùng cấm) |
|---|---|---|
| `ImportError`/`ModuleNotFoundError` (onnxruntime, cv2…) ở ô 4 | Ảnh Kaggle thiếu gói | Ô 4 tự `pip install`. Nếu vẫn lỗi: thêm một ô trước ô 4 với `!pip install -q <gói>`, rồi **Restart & Run all** |
| Lỗi CUDA/torch không khớp (`CUDA error: no kernel image`, `torch.cuda.is_available() == False`) | Chưa bật GPU, hoặc cài nhầm torch | Settings → Accelerator **GPU T4 x2**. **Không** `pip install torch` khác bản Kaggle. Xem ô 3: `torch_cuda`, `cuda_available` |
| onnxruntime chỉ có `CPUExecutionProvider` | Máy có `onnxruntime` (bản CPU) chứ không phải `onnxruntime-gpu` | Vẫn chạy được (SCRFD trên CPU, chậm hơn). Muốn nhanh: `!pip uninstall -y onnxruntime && pip install -q onnxruntime-gpu`, rồi Restart |
| `SHA-256 sai cho …` | File tải hỏng hoặc bị chặn giữa chừng | Xóa `WORK/models/<id>/<file>`, chạy lại ô 5. **Không** sửa SHA-256 |
| `Sai phiên bản mô hình: …` | Trọng số hoặc code khác bản đã chốt | **Vùng cấm** → gửi trưởng nhóm |
| Lỗi transformers khi dựng CLIP (`CLIPVisionConfig`, `local_files_only`) | Bản transformers quá cũ/mới | Ghi `transformers` từ ô 3, gửi trưởng nhóm. Có thể thử `!pip install -q "transformers>=4.40,<5"` rồi Restart |
| HTTP 429 / tải Hugging Face chậm | Hugging Face giới hạn lượt tải | Đợi 5–10 phút rồi chạy lại ô 5 (file đã đủ thì bỏ qua) |
| `CUDA out of memory` | GPU đang bị chiếm bởi phiên/ô khác | Restart kernel. Nếu vẫn lỗi: `DEVICE = "cpu"` (chậm). GenD chỉ chấm 8 khung một lần (~200–300 MB) nên hiếm gặp |
| Hết RAM (kernel chết) | Video 1080p, máy yếu | Giảm `N_RTFS_REAL`/`N_RTFS_FAKE`/`N_FAS_LIVE` (mục 2) và ghi lại |
| `No space left on device` | `WORK/proc` + dữ liệu (Colab giải nén ~27 GB) | Kaggle: dữ liệu Add Input không tốn chỗ. Colab: xóa `/content/vc_work/datasets/*.zip` còn sót. Xem ô 3: `disk_free_gb` |
| `Thiếu inswapper.csv trong …` / không thấy dữ liệu | Chưa Add Input, hoặc đường dẫn mới `/kaggle/input/datasets/<chủ>/<slug>` | Kiểm `!ls /kaggle/input` và `!ls /kaggle/input/*`. Nếu khác: thêm ô trước ô 6 `import os; os.environ["VC_RTFS_ROOT"]="<thư mục có inswapper.csv>"; os.environ["VC_FAS_ROOT"]="<thư mục chứa Image>"` |
| `RTFS file có trên đĩa: 0/…` | `VC_RTFS_ROOT` trỏ sai cấp thư mục | Thư mục phải chứa `videos.csv`, `original_videos/`, `inswapper/`, `uniface/` |
| ffmpeg không có (`Lệnh lỗi … ffmpeg`) | Máy thiếu ffmpeg | Kaggle/Colab thường có sẵn; nếu không, ô 4 tự tải bản tĩnh (cần Internet). Hoặc `!apt-get -y install ffmpeg` |
| `Lệnh lỗi (mã …)` ở bước 7 | Một video RTFS hỏng hoặc giải mã lỗi | Xem `OUT/logs/ffmpeg.log`, gửi tên file cho trưởng nhóm. **Không** tự bỏ mẫu (sẽ đổi số mẫu) |
| Nhiều `not_applicable`/`degraded` ở bước 9 | Không thấy mặt trong video đã cắt | Vài % là bình thường; > 10% thì gửi trưởng nhóm |
| Hết 12 giờ / phiên nghỉ do idle | Giới hạn của Kaggle | Dùng **Save & Run All (Commit)** để chạy ngầm. Chạy lại trong cùng phiên thì tự chạy tiếp (mục 1) |
| Colab: `Không thấy dữ liệu Add Input và không có KAGGLE_KEY` | Chưa thêm Secrets | Biểu tượng chìa khóa → thêm `KAGGLE_USERNAME`, `KAGGLE_KEY`, bật **Notebook access** |
| Colab: Drive không mount | Chưa cho phép | Chạy lại ô 4, bấm **Allow** |
| `KHÔNG fit được calibrator: Một fold fit thiếu lớp…` / `GroupKFold cần ít nhất hai subject` / `calib_fit phải có cả hai lớp` | Quá ít nhóm hoặc mẫu | SMOKE: **bình thường**. Chạy thật: kiểm số mẫu ở bước 6; gửi trưởng nhóm |
| `AUC < 0.5: nghi score ngược chiều tấn công` | GenD chấm giả thấp hơn thật trên `calib_fit` | **Không sửa**. Gửi trưởng nhóm (là kết quả, không phải lỗi code) |
| `Không được dùng tập test …` / `Hàm test đang TẮT …` | Có code chạm vào test | Đặt lại `RUN_TEST = False`; hoàn tác chỗ sửa |
| `CẢNH BÁO LỘ ĐỀ NGUỒN …` | Đặc trưng thô (độ nét, bitrate…) khác nhau giữa thật/giả vì khác nguồn | **Không phải lỗi**. Đã ghi vào `card.md`, cứ chạy tiếp |
| `CẢNH BÁO: một nhóm người Việt chiếm > 30% mẫu` | Nhiều ảnh cùng một người | Chạy tiếp, báo trưởng nhóm |
| `LƯU Ý: có thể cùng một người RTFS ở cả calib_fit và calib_ltt` | RTFS chia theo video, không theo người | Thông tin, đã ghi vào `card.md` |
| `Code nhúng bị sửa: …` | Ai đó sửa ô 2 | Import lại notebook gốc |

> Notebook này không có thông báo "DỪNG:". Các lỗi chặn là `AssertionError`/`RuntimeError`/`CalibrationError`/`TestSplitAccessError` ở trên.

---

## 5. Mẫu câu hỏi gửi trợ lý AI (dán nguyên văn)

```
Tôi đang chạy notebook calibrate_gend.ipynb (VeriClue, FACE-04) trên <Kaggle/Colab>. Một ô bị lỗi.

LUẬT BẮT BUỘC:
- Không sửa VÙNG CẤM: RUN_TEST/TEST_CONFIRMATION, rows_for/assert_no_test/check_test_unlocked,
  đoạn bỏ qua mẫu test, SEED, ARCFACE_THRESHOLD, split_groups/person_groups/split_rtfs,
  face/gend.py/pad.py/frames.py (ô nhúng), EXPECTED_MODEL_VERSION, SHA-256, crop_encode_cmd,
  calibration.fit/CalibrationStore, FIT_SOURCES, REPORT_THRESHOLDS.
- Nếu chỉ sửa được bằng cách đụng vùng cấm: nói rõ và DỪNG, không đưa code.
- Sửa tối thiểu (ưu tiên: cài gói, đường dẫn, biến môi trường, chạy lại ô). Giải thích ngắn vì sao.
- Không tự giảm số mẫu hay bỏ mẫu nếu tôi không hỏi.

Ô "0. Thông tin môi trường" in ra:
<dán JSON>

Code của ô bị lỗi:
<dán toàn bộ ô>

Traceback đầy đủ:
<dán toàn bộ, đừng cắt>

Các ô trước đó in gì (nếu liên quan):
<dán>
```

---

## 6. Sau khi sửa

1. Ghi chú ngay **trong ô đã sửa**, dòng đầu: `# SỬA bởi <tên> <ngày>: <lý do ngắn>`.
2. Chạy xong, gửi trưởng nhóm **cả hai**:
   - file `.ipynb` đã sửa (Kaggle: File → Download Notebook; Colab: File → Download .ipynb);
   - file zip kết quả và số SHA-256.
3. Trưởng nhóm chuyển chỗ sửa vào `ml/notebooks/templates/calibrate_gend.py` (hoặc file nguồn được nhúng), rồi chạy `uv run python scripts/build_gend_notebooks.py`. **Không ai sửa tay** `ml/notebooks/calibrate_gend.ipynb` trong repo. Test `scripts/tests/test_build_gend_notebooks.py` và `--check` sẽ báo lệch.
