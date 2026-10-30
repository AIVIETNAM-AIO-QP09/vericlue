# GenD mixed FP16 — FACE-07

Thí nghiệm GPU, chưa tích hợp server. Backbone vision dùng FP16; LayerNorm lưu
nguyên trọng số và tính bằng FP32, sau đó cast về FP16. Chuẩn hóa embedding,
head, logits, softmax và I/O dùng FP32. Đây là **mixed FP16**, không phải mọi
phép toán đều FP16. PyTorch chuyển trong RAM từ checkpoint gốc, không ghi đè
trọng số; ONNX xuất thành bundle riêng. Không dùng INT8, KD hoặc hiệu chỉnh ngưỡng.

## Điều kiện và tiêu chí đặt trước

- Dùng môi trường xuất của [FACE-06](onnx-export.md), bản Torch CUDA và ONNX
  Runtime GPU phù hợp. Chạy từng tiến trình vì model Large cần nhiều bộ nhớ.
- Bundle GenD FP32 phải có `bundle.json`, `inputs.npy`, `torch-cuda.json` và
  `torch-cuda-outputs.npz` đã đối chiếu với classifier gốc trên cùng GPU.
- So đúng 8 tensor tổng hợp của FACE-06, batch 1; không dùng ảnh người/CCCD.
- Giới hạn sai số xác suất tuyệt đối **0,001**, logits `atol=0,01; rtol=0,001`,
  argmax giữ nguyên toàn bộ mẫu. NaN, dtype/shape sai hoặc vượt budget đều lỗi.
  Đây là tiêu chí số học, không phải ngưỡng nhận diện hay cam kết APCER/BPCER.
- FP32 dùng budget nghiêm của FACE-06 (`atol=1e-5; rtol=1e-4`). Không nới budget
  sau khi xem kết quả. Không sửa ngưỡng hoặc backend đang chạy.

## Tái lập

Thay đường dẫn bằng thư mục model của máy; `python` là interpreter môi trường
xuất. Output bắt buộc là thư mục mới, giữ nguyên bundle FP32.

```powershell
$env:PYTHONPATH = "$PWD/ml/src"
$modelRoot = 'D:/VeriClue/models/selected-2026-10-24'
$sourceBundle = 'D:/VeriClue/models/onnx/gend-fp32-b1'
$halfBundle = 'D:/VeriClue/models/onnx/gend-mixed-fp16-b1'
python -m vericlue_ml.eval.fp16_gend export --models-dir $modelRoot --fp32-bundle $sourceBundle --output $halfBundle
```

Chỉ khi lệnh trên thành công, chạy mỗi dòng sau bằng tiến trình riêng, dừng nếu
lỗi. Mặc định 4 CPU threads, 3 warmup, 30 lần đo; không chạy đồng thời.

```powershell
python -m vericlue_ml.eval.fp16_gend benchmark --models-dir $modelRoot --fp32-bundle $sourceBundle --bundle $halfBundle --engine torch32
python -m vericlue_ml.eval.fp16_gend benchmark --models-dir $modelRoot --fp32-bundle $sourceBundle --bundle $halfBundle --engine torch16
python -m vericlue_ml.eval.fp16_gend benchmark --models-dir $modelRoot --fp32-bundle $sourceBundle --bundle $halfBundle --engine onnx32
python -m vericlue_ml.eval.fp16_gend benchmark --models-dir $modelRoot --fp32-bundle $sourceBundle --bundle $halfBundle --engine onnx16
```

Bundle ghi checksum, revision nguồn, commit/hash code, dtype/số trọng số, dung
lượng, đối chiếu số học. JSON mỗi engine chứa tất cả thời gian đo, p50/p95,
RSS và snapshot VRAM toàn GPU. Snapshot gồm ứng dụng khác, **không phải đỉnh
VRAM của model**. Thời gian chỉ tính network và copy GPU, không phải cả eKYC.

Không suy ra độ chính xác trên người thật/deepfake từ 8 tensor. Cần kiểm hồi
quy dữ liệu thật, đặc biệt mẫu gần ngưỡng, trước khi đổi backend demo. FS-VFM
chưa thử FP16 trong task này vì nhánh CUDA FP32 còn chênh số học cần điều tra.
