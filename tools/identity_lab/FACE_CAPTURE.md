# Kiểm tra selfie mới và nhiều ảnh chụp

Giữ baseline AdaFace IR18 single. Công cụ `face_capture_eval.py` thêm đánh giá cả
ma trận CCCD–selfie và template trung bình từ 2–10 selfie, kèm evidence từng ảnh.
Không chọn ảnh theo cosine với CCCD, không giữ score cao nhất. Template bình quân
có thể kém một ảnh tốt; không bảo đảm cải thiện mọi trường hợp.

Ảnh trùng pixel hoặc một selfie lỗi làm nhóm trả retry; các cặp đơn hợp lệ vẫn được
báo cáo. Không bỏ ảnh lỗi rồi giả vờ đã chấm đủ nhóm. Không tự loại mặt thứ hai,
không có quality gate/consistency threshold đã hiệu chỉnh. Có kiểm normalization,
mean vector suy biến, nonfinite input. Chỉ review, identity_verified=false; không PAD.
Embedding chỉ giữ trong RAM, ảnh debug local là dữ liệu cá nhân và không commit.

## Kết quả 24/10/2026

Ảnh mới `selfie_2.jfif` không nằm trong training adapter; checkpoint cũ giữ nguyên.

| CCCD | Baseline + selfie_2 | Adapter + selfie_2 | Baseline gộp 3 selfie |
|---|---:|---:|---:|
| anh_cccd | 0.673524 | 0.663847 | 0.572573 |
| anh_cccd_1 | 0.672833 | 0.667126 | 0.589739 |
| anh_cccd_2 | 0.660067 | 0.657764 | 0.635651 |

Cosine không phải xác suất danh tính. Selfie mới có vùng mặt sáng hơn (mean gray
149 so với 99/106), nhưng đây là tương quan, không thí nghiệm chứng minh nguyên nhân.
Không suy ra ảnh thật/camera trực tiếp từ hình ảnh; không suy đoán danh tính bằng mắt.
Không dùng điểm cá nhân để chọn ngưỡng hoặc train lại. Adapter chưa hơn baseline;
không đưa vào API mặc định. Nhóm ba ảnh là ảnh rời, không khẳng định cùng phiên live.

Validation public sample: 4 người, nhóm 3 ảnh không chồng lặp theo tên file cố định,
56 cặp nhóm, 49 scored/7 retry (13 genuine/36 impostor scored). So trên cùng nhóm
đủ ảnh: single-first genuine median 0.763732 -> mean3 0.854033; impostor max
0.110722 -> 0.097152. AUC cả hai1.0, chỉ thử development; chưa kết luận tổng quát.
Không chạy lại test để chọn cấu hình sau khi đã xem test từ vòng train adapter.
Các ảnh dataset khác điều kiện chụp, đây chưa phải đánh giá chuỗi video thực.

## Chạy local

```powershell
$env:IDENTITY_MODELS_DIR='F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/face_capture_eval.py capture --references data/images/test_ocr/anh_cccd.jfif data/images/test_ocr/anh_cccd_1.jfif data/images/test_ocr/anh_cccd_2.jfif --selfies data/images/test_ocr/selfie.jfif data/images/test_ocr/selfie_1.jfif data/images/test_ocr/selfie_2.jfif --out outputs/face_capture_selfie2_02
```

Output lượt đã chạy: `outputs/face_capture_selfie2_01/report.json` + ảnh alignment.
Development: `outputs/face_capture_dev_01/report.json`.
Adapter ảnh mới: `outputs/face_adapter_train_01/personal_selfie2.json`.
36 tests face pass, Ruff sạch. Không thay pipeline_config hoặc contracts/thresholds.
