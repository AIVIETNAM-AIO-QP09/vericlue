# Xuất và kiểm chứng ONNX FP32 — FACE-06

FS-VFM-L và GenD-L dùng đúng loader/trọng số gốc đã kiểm SHA-256. Đầu vào là
`[1,3,224,224]` FP32 đã tiền xử lý; đầu ra gồm logits và xác suất hai lớp.
PAD dùng nhãn giả 0, GenD dùng nhãn giả 1. Không đổi detector, chuẩn hóa, gộp
điểm, ngưỡng hoặc backend đang chạy của server.

## Môi trường

Dùng môi trường xuất riêng với dependency `face`/`gend`, rồi cài
`python -m pip install -r ml/requirements-onnx-export.txt`. Không cài đè môi
trường server. Đợt thử dùng Python 3.12, Torch 2.14.1, Transformers 4.57.6;
phiên bản thực tế được ghi trong mỗi JSON. Chọn ONNX Runtime CPU hoặc GPU phù
hợp, không cài đồng thời `onnxruntime` và `onnxruntime-gpu`.

Model đọc từ `MODELS_DIR`, không tải mạng. FS-VFM cần checkpoint và thống kê
chuẩn hóa. GenD dùng checkpoint GenD và config/preprocessor của CLIP, không cần
nạp bản trọng số CLIP nền thứ hai. Output phải là thư mục mới.

## Chạy từng tiến trình

Từ gốc repo, thay `python` bằng interpreter của môi trường xuất:

```powershell
$env:PYTHONPATH = "$PWD/ml/src"
$env:MODELS_DIR = 'D:/VeriClue/models'
python -m vericlue_ml.eval.onnx_export export --model fsvfm --output models/onnx/fsvfm-fp32-b1
python -m vericlue_ml.eval.onnx_export benchmark --bundle models/onnx/fsvfm-fp32-b1 --engine torch --device cpu
python -m vericlue_ml.eval.onnx_export benchmark --bundle models/onnx/fsvfm-fp32-b1 --engine onnx --device cpu
python -m vericlue_ml.eval.onnx_export summarize --bundle models/onnx/fsvfm-fp32-b1 --device cpu
```

Lặp với `--model gend` và thư mục `models/onnx/gend-fp32-b1`. Mỗi lệnh phải đạt
trước khi chạy tiếp; tách tiến trình để trả bộ nhớ model trước. Không chạy hai
model Large đồng thời trên laptop RAM hạn chế. Dựng graph cần RAM bổ sung.

Đo CUDA bằng hai lệnh benchmark và summarize với `--device cuda` trong môi
trường GPU. Provider không kích hoạt thì báo lỗi, không ghi số CPU thành GPU.
Một số phép toán vẫn có thể được giao về CPU dù provider CUDA đã kích hoạt.

CUDA phải chạy bản Torch trước: ONNX GPU được đối chiếu với Torch trên cùng
GPU, kiểm hash bản tham chiếu. `cpu_reference_parity` ghi riêng độ lệch so với
bản CPU lúc xuất; không trộn thay đổi phần cứng với sai lệch chuyển đổi. Bản
Torch GPU còn được kiểm với classifier gốc trên GPU, không tự coi đạt nếu lỗi.

## Kết quả và giới hạn

- Giữ `model.onnx` và external data cùng thư mục.
- `bundle.json`: commit/hash source, revision model, môi trường, dtype/shape,
  số mẫu/seed và checksum. Mỗi benchmark kiểm lại byte trong bundle.
- `torch-*.json`, `onnx-*.json`: đối chiếu logits/xác suất, p50/p95 sau 3 lượt
  làm nóng và 20 lượt đo, thời gian nạp, RSS, provider và môi trường.
- `comparison-*.json`: tỷ số thời gian Torch/ONNX; lớn hơn 1 là ONNX nhanh hơn
  trong phép đo này, không suy ra toàn bộ quy trình eKYC.

Tám mẫu màu/nhiễu tổng hợp tái lập được, không ảnh người dùng. Tolerance đặt
trước: `atol=1e-5`, `rtol=1e-4`, kiểm cả logits và xác suất thay vì chỉ nhãn.
Đây **không phải AUC/APCER/BPCER** hoặc chứng minh hiệu quả chống giả mạo.

Đo mạng batch 1, có copy NumPy ↔ thiết bị; loại camera, đọc video, dò/căn mặt
và tiền xử lý khỏi thời gian đo. RSS lấy mẫu mỗi 20 ms trong tiến trình riêng.
VRAM là snapshot toàn thiết bị từ nvidia-smi, bao gồm tiến trình khác, không
phải peak VRAM riêng model. Tải laptop ảnh hưởng số đo; các lượt lặp không
phải các người thử độc lập.

Trước khi thay server cần đo thêm trên dữ liệu phát triển phù hợp, giữ nguyên
ngưỡng, rồi kiểm thử luồng tích hợp. Phép thử tổng hợp không đáp ứng tiêu chí
AUC của FACE-05. Không chọn cấu hình hoặc ngưỡng bằng tập test.
