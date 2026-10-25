# Kiểm chứng cải thiện bằng dữ liệu bên ngoài

## Kết quả thực nghiệm 24/10/2026

Đã hoàn tất `outputs/face_robustness_01/comparison.json`. Cả ba kịch bản trên
validation đều có161/168cặp scored (41 genuine,120 impostor;7retry). IR18 và IR101
đều có AUC1.0, false match0 và false non-match0 tại ngưỡng chọn từ clean train.
Median embedding CPU: IR18 **45.02ms**, IR101 **1778.84ms** (không tính detector,
decode/startup). Cấu hình khóa chọn **IR18** theo tiêu chí tốc độ khi lỗi tương đương.
Không chứng minh IR101 cải thiện trong miền này, không thay baseline bằng model nặng.

Phải hiểu giới hạn: validation chỉ4người, đã dùng development; 0 lỗi không có nghĩa
production hoàn hảo. Không có số liệu cải thiện qua tuổi tác. Tiến bộ lượt này là
benchmark stress có train-calibrated operating points và cơ chế khóa personal test,
**không phải đã chứng minh tăng độ chính xác**. Không đổi threshold/API production.

## Quy tắc giữ ảnh cá nhân ngoài phát triển

Sáu ảnh trong `data/images/test_ocr` chỉ được đọc ở lệnh `face_selected_trial.py`
sau khi model được khóa bằng `comparison.json`. Không dùng chúng để train, chọn
checkpoint/model/ngưỡng, hoặc chọn biến thể xử lý ảnh. Kết quả test cá nhân xấu
không được quay lại chỉnh hyperparameter theo chính các ảnh đó.

## So sánh IR18 và IR101

`face_robustness.py` chỉ đọc train và validation của AxonData sample đã chia theo
người trong `face_adapter_prepared_01/prepared.json`: 12 train / 4 validation.
Không đọc ảnh test 4 người còn lại, không đọc ảnh cá nhân. Hash nguồn ảnh được kiểm
tra trước inference. Dùng shared SCRFD alignment và AdaFace BGR chuẩn từ UniFace.

IR101 pretrained lấy qua registry UniFace, SHA-256:
`f2eb07d03de0af560a82e1214df799fec5e09375d43521e2868f9dc387e5a43e`.
Đây là so sánh pretrained model, không gọi là đã fine-tune backbone.

Ba kịch bản cố định trước khi chạy:

1. Ảnh nguyên bản sau alignment.
2. Reference giảm xuống 28×28, resize112×112, JPEG quality45.
3. Selfie có gradient sáng từ0.25 đến0.9 trên chiều ngang.

Stress áp dụng **sau detection/alignment**, nên không đo detector trong ảnh xấu và
không mô phỏng ageing. Không dùng sinh ảnh đổi tuổi/phục hồi khuôn mặt để bịa chi tiết.

Mỗi model chọn ngưỡng nghiên cứu trên clean train với 0 false match quan sát;
ngưỡng đó được giữ nguyên cho mọi kịch bản validation. Báo FMR/FNMR scored-only,
coverage và số genuine retry; 0 lỗi trên train không là bảo đảm FMR tổng thể.

Chọn model có worst-scenario balanced error thấp nhất trên validation; nếu khác
không quá0.01 thì ưu tiên median embedding latency thấp hơn. Balanced error ở đây
là `(FMR+FNMR)/2`, không phải AUC hoặc accuracy. Cả hai dùng cùng detector/coverage.
Chính sách ghi vào protocol trước khi đọc ảnh. Tiêu chí tốc độ là preference,
không phải kiểm định tương đương thống kê. Latency không gồm decode/detector/startup.

## Chạy và kiểm tra cá nhân sau khi khóa

```powershell
$env:IDENTITY_MODELS_DIR='F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
$facePython='..\output\vericlue_identity_lab\.venv\Scripts\python.exe'
& $facePython tools/identity_lab/face_robustness.py --dataset data/face_matching/axon_public_v1 --prepared outputs/face_adapter_prepared_01 --out outputs/face_robustness_02
& $facePython tools/identity_lab/face_selected_trial.py --comparison outputs/face_robustness_02/comparison.json --references data/images/test_ocr/anh_cccd.jfif data/images/test_ocr/anh_cccd_1.jfif data/images/test_ocr/anh_cccd_2.jfif --selfies data/images/test_ocr/selfie.jfif data/images/test_ocr/selfie_1.jfif data/images/test_ocr/selfie_2.jfif --out outputs/face_selected_personal_02
```

Lệnh personal kiểm lại chính sách chọn, hash code/weights và runtime; ghi selection
trước khi đọc ảnh cá nhân. Không áp ngưỡng nghiên cứu vào quyết định danh tính, vẫn
review/identity_verified=false. Không tự sửa API production hay ngưỡng hệ thống.

## Giới hạn

Validation đã được dùng ở các thí nghiệm development trước, chỉ có4người; không là
test độc lập, không chứng minh generalization hoặc hiệu quả CCCD Việt Nam/ageing.
Chưa audit overlap người với pretraining. Các cặp dùng chung người/ảnh phụ thuộc nhau.

Nguồn AgeDB chính thức https://ibug.doc.ic.ac.uk/resources/agedb/ yêu cầu xin mật khẩu
ZIP từ tác giả, dùng nghiên cứu phi thương mại; phiên này chưa có quyền truy cập ZIP
qua mật khẩu và chưa chạy AgeDB. Không gửi email thay người dùng. Không lấy kết quả
synthetic stress để tuyên bố giải quyết ảnh khác tuổi.
