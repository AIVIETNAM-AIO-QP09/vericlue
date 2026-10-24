# Khắc phục bỏ sót mặt chụp sát khung hình

Thí nghiệm ngày 24/10/2026 giữ AdaFace IR18, SCRFD và ngưỡng detector hiện có.
Khi lượt đầu không thấy mặt, `face_context.py` thêm viền xám 127, mỗi bên bằng
nửa kích thước ảnh, rồi thử lại. Tọa độ được chuyển về ảnh gốc; recognizer nhận
crop căn chỉnh từ pixel gốc. Không giảm ngưỡng, không bỏ qua kiểm tra nhiều mặt
hoặc khuôn mặt bị cắt. Ảnh đã được phát hiện ở lượt đầu có đường xử lý giữ nguyên.

## Dữ liệu và kết quả

Nguồn: [FG-NET](https://yanweifu.github.io/FG_NET_data/index.html), bản tải có SHA-256
`228acddeba96e469f2ded9475ee87f4ab16398de27a2f3ec35a266a46ef2f7fc`.
Chọn 309 ảnh người trưởng thành, 49 người; ảnh tham chiếu sớm hơn ít nhất 3 năm.
Chia theo người: train 29, validation 10, test 10. Đây là ảnh khác tuổi,
không phải bộ CCCD–selfie. Không mặc định có quyền sử dụng thương mại.

| Chỉ số | Trước | Thêm bước thử lại |
|---|---:|---:|
| Ảnh xử lý thành công | 167/309 | 309/309 |
| Cặp validation có điểm | 100/520 | 520/520 |
| Cặp test có điểm | 130/500 | 500/500 |
| Cặp cùng người validation không đạt, kể cả retry | 35/52 | 17/52 |
| Cặp cùng người test không đạt, kể cả retry | 30/50 | 13/50 |

Các tỷ lệ không đạt sử dụng ngưỡng riêng của từng pipeline, chốt trên train
với mục tiêu không có nhận nhầm quan sát được. Vì số ảnh xử lý được thay đổi,
ngưỡng cũng thay đổi; không diễn giải bảng như so sánh tại cùng một ngưỡng.
Bản mới có 0/468 nhận nhầm trên validation và 0/450 trên test. Các cặp dùng chung
người, không độc lập; số 0 này không chứng minh FMR quần thể bằng 0.
Test FG-NET đã được xem trong giai đoạn phát triển, không gọi là kiểm định mới độc lập.

Đã train adapter đường chéo trên embedding cố định, 100 epoch, chọn epoch 74
bằng loss validation. Đây không phải fine-tune backbone. Adapter làm số cặp
cùng người bị từ chối trên validation tăng từ 17/52 lên 24/52 ở giao thức ngưỡng
nêu trên, nên **không chọn adapter**. Giữ IR18 gốc + bước thử lại.

Báo cáo máy đọc được:

- `outputs/face_fgnet_context_prepared_01/prepared.json`
- `outputs/face_fgnet_context_train_01/report.json`
- `outputs/face_fgnet_context_train_01/operating_points.json`
- `outputs/face_context_personal_01/selection.json` và `report.json`

## Chạy lại trên ảnh cá nhân

Chạy từ thư mục repo, dùng thư mục output mới. Runner kiểm hash cấu hình/model/runtime
với thí nghiệm, ghi lựa chọn trước khi mở ảnh cá nhân. Không dùng ngưỡng FG-NET
để cấp kết quả xác minh; đầu ra vẫn là review/retry, chưa chạy PAD/xác thực giấy tờ.

```powershell
$env:IDENTITY_MODELS_DIR='F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/face_context_trial.py --prepared outputs/face_fgnet_context_prepared_01/prepared.json --references data/images/test_ocr/anh_cccd_2.jfif --selfies data/images/test_ocr/selfie_1.jfif --out outputs/face_context_trial_02
```

Sáu ảnh cá nhân chỉ dùng kiểm thử sau khi chốt; không train, chọn model, ngưỡng
hay cách xử lý bằng chúng. Cải tiến này xử lý lỗi không phát hiện được mặt, không
cam kết tăng điểm các ảnh đã phát hiện tốt. Chưa thay API/threshold production.
Trên validation vẫn từ chối 17/52 cặp cùng người: chưa đủ để tuyên bố sẵn sàng eKYC.
