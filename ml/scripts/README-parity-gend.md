# Đối chiếu số học GenD ngoại tuyến

`parity_gend.py` so sánh wrapper đang có trong checkout với mã GenD upstream
độc lập. Công cụ chỉ sinh ảnh/tensor tổng hợp; không nhận ảnh người, video,
điện thoại hay dữ liệu đánh giá. Kết quả **không chứng minh accuracy**, khả năng
chống deepfake, calibration hoặc tính sẵn sàng triển khai eKYC.

## Chuẩn bị

Dùng Python 3.12 và môi trường CPU có sẵn các thư viện của GenD: PyTorch,
Transformers, safetensors, NumPy, Pillow, OpenCV, PyYAML và gói VeriClue.
Công cụ không tải dữ liệu, cài package, sửa trọng số hay đổi threshold.
Mỗi worker chặn kết nối socket và đặt Hugging Face/Transformers ở chế độ offline.

`--models-dir` phải chứa hai thư mục `gend-clip-l14/` và
`clip-vit-large-patch14/`, đầy đủ các file được liệt kê trong hàm `provenance`.
SHA-256 và revision phải khớp `models/manifest.yaml` của checkout.
Upstream cần cả checkpoint CLIP và tokenizer/processor để dựng đúng lớp gốc,
dù chỉ chạy nhánh vision; wrapper không dùng checkpoint CLIP thay GenD.

`--upstream-dir` là thư mục nguồn đã được kiểm duyệt, gồm bốn file **nguyên bản**
từ [yermandy/GenD tại commit 387a422](https://github.com/yermandy/GenD/tree/387a42266dd385fbe8f7626c5d3aa03eea3bfaab):

| Tên file cục bộ | Đường dẫn upstream | SHA-256 |
|---|---|---|
| `detector.py` | `detector.py` | `c7cbdf2dc37ffd5612f3a6b5583027e8eaa42e5eb261eae447bf92b1919eb7b7` |
| `modeling_gend.py` | `src/hf/modeling_gend.py` | `4b76b83df8d0f5c59082e97ececeb67735eb79a1fa0fc09d9299710179b75ad0` |
| `app_run.py` | `app/run.py` | `97432055d9330f3cdc59bb97ee82579483306d84a7cc4506efdc8393db13f891` |
| `LICENSE` | `LICENSE` (MIT) | `f478adb5d8cbcb41e0236408a98a0b44269798b026e73f2da16b9cc0e55f842a` |

Không có nguồn hoặc hash khác thì kết quả là `UNVERIFIED`. Không tự thay hash
để chấp nhận phiên bản mới. Công cụ không chép hoặc tải các file này vào repo.

## Chạy

Từ checkout, dùng executable của môi trường có sẵn (thay các đường dẫn mẫu):

```powershell
& "<runtime>/Scripts/python.exe" ml/scripts/parity_gend.py `
  --models-dir "<models>" `
  --upstream-dir "<reviewed-upstream>" `
  --out "<new-empty-results-directory>"
```

`--repo` mặc định suy ra từ vị trí script; có thể chỉ định một checkout khác.
`--out` phải là thư mục mới hoặc rỗng khi chạy mặc định. Nếu đã có bằng chứng,
lệnh bị từ chối với exit 2 và giữ nguyên các file cũ. Các worker chạy tuần tự,
CPU FP32, bốn luồng, không autocast; timeout mỗi worker 600 giây.
Không chạy đồng thời với công việc native nặng khác trên máy ít RAM.

Các bước được lưu riêng:

1. Sáu ảnh BGR tổng hợp qua CLIPImageProcessor gốc so với `to_tensor`,
   `atol=rtol=1e-6`; sáu bộ landmark tổng hợp so `align_face` với hàm trích
   nguyên AST từ `detector.py` đã kiểm hash, yêu cầu pixel khớp tuyệt đối.
2. Chín tensor tổng hợp, seed `20261103`, chạy batch 1/2/9 ở hai tiến trình riêng.
   Upstream dựng `GenD` nguyên bản, chỉ thay `config.backbone` bằng thư mục CLIP
   đã kiểm hash để chạy offline; nạp **394 tensor bằng `strict=True`**.
   Phía còn lại gọi `_load_classifier` và `p_fake` thật của wrapper.
3. So pooled feature, feature chuẩn hóa L2, logits, softmax và `p_fake`
   (`atol=rtol=1e-5`): 15 mục đối chiếu, 12 lượt forward mẫu mỗi phía nhưng
   chỉ có 9 tensor duy nhất. Kiểm inventory, shape, hữu hạn, L2, softmax và
   nhãn giả ở cột 1 độc lập với việc hai phía có bằng nhau hay không.

## Đọc kết quả

`report.json` có `report_version=1`, status `PASS` (exit 0), `FAIL` (exit 1)
hoặc `UNVERIFIED` (exit 2). Sai khác số học/tiền xử lý là FAIL; thiếu file,
thiếu metadata/metric, shape sai, hash sai, worker lỗi hoặc provenance thay đổi
không thể được coi là PASS. Lỗi được giữ trong `<stage>-error.json`, gồm traceback;
các bằng chứng đã tạo trước lỗi vẫn được giữ. Sai khác tiền xử lý vẫn cho chạy
hai forward native để báo cáo đầy đủ nguyên nhân.

Các file `upstream.npz`, `wrapper.npz`, JSON của từng worker và
`preprocessing.json` là bằng chứng để chạy lại bước so sánh bằng `--mode compare`
với cùng các tham số. Không sửa hoặc trộn file từ nhiều lần chạy. Bước compare
kiểm lại nguồn/trọng số/runtime hiện tại; nếu checkout hoặc môi trường đã đổi,
hãy chạy toàn bộ vào thư mục mới.

Provenance gồm commit và cờ `repo_dirty` của checkout, hash wrapper/script/manifest/nguồn upstream,
hash các helper `face/pad.py`, `face/frames.py`, `common/device.py`,
revision và hash từng file mô hình, version wrapper, Python executable và hash
của nó, phiên bản thư viện, hash bản kê runtime, cùng cờ kiểm trước/sau chạy.
Hash runtime là hash bản kê phiên bản và executable, không phải toàn bộ môi
trường cài đặt. Version wrapper ghi trong report là version khởi tạo; báo cáo
không nạp SCRFD hoặc chứng minh cả pipeline phát hiện mặt/điểm video.

Kiểm tra logic báo cáo không cần mô hình hoặc GPU:

```powershell
python -m pytest ml/tests/test_gend_parity_tool.py
python -m ruff check ml/scripts/parity_gend.py ml/tests/test_gend_parity_tool.py
```
