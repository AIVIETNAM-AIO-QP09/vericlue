# Huấn luyện thử adapter ID–selfie trên CPU

Đã tải và chạy training thật ngày 24/10/2026. Đây là **lớp điều chỉnh metric 512 trọng số
trên embedding AdaFace đóng băng**, không phải fine-tune backbone AdaFace. API mặc định
vẫn dùng AdaFace IR18 single ban đầu; checkpoint thử nghiệm không tự đưa vào API.

## Dữ liệu và quyền sử dụng

Nguồn: [AxonData / Axon Labs](https://huggingface.co/datasets/AxonData/Selfie_and_Official_ID_Photo_Dataset).
Dataset card khai báo CC BY 4.0; lưu bản card ở `data/face_matching/axon_public_v1/SOURCE_README.md`.
Revision cố định: `5da0a5cc8f9fc8e33e816330f02a8b98a33dc768`.
Attribution: AxonData / Axon Labs, Selfie and Official ID Photo Dataset, CC BY 4.0.
Thay đổi: trích face embedding và huấn luyện diagonal adapter; không phát hành lại ảnh.

Chỉ tải các thư mục sample có nhãn rõ: 159 ảnh / 20 identity-folder, 28.494.756 bytes.
Không nhầm con số quy mô bộ thương mại trên trang giới thiệu với bản miễn phí đã tải.
Không gộp nhánh numbered sample vì chưa xác minh trùng người với các thư mục này.
Ảnh và embedding là dữ liệu sinh trắc, lưu local trong data/outputs, không commit.
Kiểm hash nguồn, loại chéo exact pixel duplicate bằng cách dừng; nhãn theo nhà cung cấp,
chưa kiểm chứng trùng người giữa folder hoặc overlap với dữ liệu pretraining AdaFace.

## Thiết kế thực nghiệm

- Seed 2026, chia theo identity-folder: 12 train, 4 validation, 4 test trước extraction.
- SCRFD + AdaFace IR18 single, đúng 1 face; 155 ảnh scored, 4 selfie retry nhiều mặt.
- 512 scale dùng chung cho reference/selfie: `normalize(scale * embedding)`.
- Khởi tạo scale=1; Adam LR0.01, 100 epoch, regularization 0.1, log-scale chặn ±0.2.
- Loss cân bằng genuine `(1-cosine)^2` và impostor `relu(cosine-0.1)^2`.
  Mốc 0.1 là hyperparameter loss cố định, **không phải ngưỡng xác minh**.
- Chọn validation loss thấp nhất; baseline epoch0 đủ điều kiện được chọn.
- Test chỉ tính sau khóa artifact. 5 ảnh người dùng chỉ được đọc trong lệnh `personal` sau train.
- Năm ảnh đã được xem trong các lượt phát triển trước nên không gọi là independent benchmark.
  Người dùng xác nhận tất cả cùng một người; không có personal impostor pairs.

## Kết quả chạy thật

Checkpoint được chọn: epoch94. Artifact:
`outputs/face_adapter_train_01/adapter.json`.

| Tập | Cặp scored / tổng | AUC baseline | AUC adapter |
|---|---:|---:|---:|
| Train | 1656 / 1728 | 1.0 | 1.0 |
| Validation | 161 / 168 | 1.0 | 1.0 |
| Test | 192 / 192 | 1.0 | 1.0 |

Test gồm 48 genuine và 144 impostor pairs, nhưng chỉ 4 người: các cặp phụ thuộc nhau.
AUC=1.0 trên mẫu nhỏ dễ này không chứng minh 100% chính xác thực tế; không chọn ngưỡng
hay production model dựa trên test. Không có bằng chứng tăng khả năng phân biệt qua AUC.

| CCCD | Selfie | Baseline cosine | Adapter cosine |
|---|---|---:|---:|
| anh_cccd | selfie | 0.377960 | 0.372670 |
| anh_cccd | selfie_1 | 0.421839 | 0.426705 |
| anh_cccd_1 | selfie | 0.408690 | 0.411354 |
| anh_cccd_1 | selfie_1 | 0.435971 | 0.444553 |
| anh_cccd_2 | selfie | 0.489149 | 0.496235 |
| anh_cccd_2 | selfie_1 | 0.486418 | 0.489320 |

Cosine không phải xác suất/phần trăm đúng. Tăng 5/6 cặp genuine không chứng minh giảm
nhận nhầm, nên chưa thay baseline. Chưa train backbone; bước đó cần thêm dữ liệu đúng
miền và GPU (môi trường local hiện torch CPU, CUDA unavailable).

## Chạy lại

Chạy từ repo root, dùng folder output mới mỗi lần. Download có thể chạy lại kiểm hash.

```powershell
$env:IDENTITY_MODELS_DIR='F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
$facePython='..\output\vericlue_identity_lab\.venv\Scripts\python.exe'
& $facePython tools/identity_lab/download_face_sample.py --out data/face_matching/axon_public_v1
& $facePython tools/identity_lab/train_face_adapter.py prepare --input data/face_matching/axon_public_v1 --out outputs/face_adapter_prepared_02
& $facePython tools/identity_lab/train_face_adapter.py train --input outputs/face_adapter_prepared_02 --out outputs/face_adapter_train_02
& $facePython tools/identity_lab/train_face_adapter.py personal --adapter outputs/face_adapter_train_02/adapter.json --references data/images/test_ocr/anh_cccd.jfif data/images/test_ocr/anh_cccd_1.jfif data/images/test_ocr/anh_cccd_2.jfif --selfies data/images/test_ocr/selfie.jfif data/images/test_ocr/selfie_1.jfif --out outputs/face_adapter_train_02/personal_check.json
```

28 tests face pass, gồm role parsing, chia theo người, transform embedding, gradient loss,
cặp không xuyên split/retry, các regression API/ROI/calibration trước đó. Ruff pass.
