# Cải thiện OCR trên nhiều ảnh, không tối ưu riêng hai ảnh demo

## Trạng thái thực tế

Đã chuẩn bị 5.996 crop từ 668 ảnh có nhãn CCCD trong dataset Kaggle v1.
Giữ split gốc tạm: 4.423 train / 1.033 valid / 540 test crop. Các split này **chưa
xác minh theo người**, có trùng xuyên tập theo audit trước; không dùng làm benchmark chính thức.
Crop theo annotation (box có sẵn), không theo detector dự đoán: đánh giá recognition
riêng trước, sau này phải đo cả detector + recognition trên ảnh thẻ.

Đã chạy Seq2Seq và Transformer pretrained trên cùng 100 crop train, rải theo loại trường.
15 crop khác kết quả. Đây không là accuracy: chưa có transcript chuẩn được duyệt.
Không lựa chọn model bằng hai ảnh demo, không dùng output OCR làm ground truth.
Trọng số Transformer lấy từ nguồn VietOCR chính thức qua prepare_vietocr.py,
có SHA-256/provenance; không phải model vừa fine-tune.

## Duyệt nhãn trên máy

Chạy từ repo root:

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/review_recognition.py --dataset outputs/recognition_dataset_v1 --port 8020
```

Mở http://127.0.0.1:8020. Xem crop và ảnh thẻ gốc, so sánh hai gợi ý.
Gõ nội dung chính xác rồi bấm xác nhận. Nút chép gợi ý không tự duyệt.
Crop mất chữ, nhiều dòng hoặc không đọc được: đánh dấu không dùng, không đoán chữ.
Mỗi lần lưu ghi reviews.json và review_history.jsonl, không ghi đè prediction.
Chỉ bind localhost; ảnh và nhãn là dữ liệu cá nhân, không commit/chia sẻ công khai.
Giao diện/API đã kiểm bằng TestClient, chưa kiểm giao diện trực quan trong browser.

## Chạy thêm baseline

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/recognition_data.py predict --dataset outputs/recognition_dataset_v1 --models ../output/vericlue_identity_lab/models/vietocr --split train --limit 100
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/recognition_data.py predict --dataset outputs/recognition_dataset_v1 --models ../output/vericlue_identity_lab/models/vietocr_transformer --architecture transformer --split train --limit 100
```

`--limit` là số mẫu **mới** mỗi lần, cache mẫu đã đọc. Bỏ limit để đọc hết split đã chọn.
Mỗi prediction có hash model, config và crop. Không sửa transcript khi rerun.
Không dùng test để chọn model/biên crop/ngưỡng. Chỉ mở test sau khi chốt phương án.

## Đánh giá sau khi có transcript

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/recognition_data.py evaluate --dataset outputs/recognition_dataset_v1 --predictions outputs/recognition_dataset_v1/predictions_seq2seq.json --split valid
```

Trước đó phải có predictions và reviews cho split tương ứng. Không có nhãn người duyệt
thì công cụ dừng, không tạo accuracy giả. Đánh giá trên các crop đã duyệt usable; báo rõ
số mẫu từng trường, exact match, CER, số thiếu prediction. Prediction thiếu được tính
là chuỗi rỗng, không âm thầm loại mẫu. Chỉ chuẩn hóa Unicode NFC/khoảng trắng, không bỏ dấu,
không sửa số. Lưu hash samples/reviews/predictions để tái lập.
CER có thể >1 nếu chèn nhiều ký tự. Kết quả chưa xác minh split theo người luôn ghi rõ
giới hạn này; coverage nhãn ít không đại diện cả dataset.

## Chuẩn bị dữ liệu fine-tune VietOCR

Sau khi duyệt transcript, rà soát nhóm danh tính của **toàn bộ ảnh** (có thể bắt đầu từ
groups_auto.csv trên Colab nhưng không coi OCR grouping là verified). Dùng file groups
có image,group_id, cùng người cùng nhóm, và chia trước khi sinh split recognition:

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/recognition_data.py export --dataset outputs/recognition_dataset_v1 --groups outputs/card_audit/groups.csv --out outputs/vietocr_training_v1
```

Exporter chỉ dùng transcript reviewed+usable, yêu cầu đủ nhãn ở cả ba split,
giữ ảnh pixel trùng cùng nhóm, chia nhóm ổn định. Xuất crops, train.txt/valid.txt/test.txt
(đường dẫn ảnh + tab + chữ), manifest và hash provenance. Không tạo nhãn bằng regex.
File nhóm đầy đủ chỉ chứng minh có nhóm được cung cấp, không chứng minh kiểm tra người đúng.
Gói này dùng làm đầu vào training VietOCR; **chưa có lần fine-tune recognizer nào được chạy**.
Notebook detector vẫn chỉ train detector; không tuyên bố đã có notebook training recognition.

## Đối chiếu hai recognizer khi inference

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/try_card_detector.py data/images/test_ocr/anh_cccd_1.jfif --checkpoint models/cccd_detector/best.pt --out outputs/compare_new --vietocr-models ../output/vericlue_identity_lab/models/vietocr --secondary-transformer-models ../output/vericlue_identity_lab/models/vietocr_transformer
```

`comparison.value` là giá trị chung khi hai model đồng ý và confidence >=0.6; nếu bất đồng
hoặc điểm thấp thì null, giữ candidate_text/comparison_text để người xem. Chỉ hai model
đồng ý không chứng minh chữ đúng; vẫn review, không xác minh danh tính. Ngưỡng heuristic chưa
hiệu chỉnh. `text` cũ vẫn là ứng viên để debug, không tự động được coi là giá trị cuối.
Không nối thử nghiệm này vào API sản phẩm khi chưa có đánh giá độc lập.

## Giới hạn cần giải quyết bằng dữ liệu

- Bộ dữ liệu nhỏ, ảnh đã stretch 640×640, chưa bao phủ hết loại thẻ/chụp lóe/mờ/xoay.
- Bổ sung ảnh ngoài nguồn Kaggle, giữ theo người và thiết bị nếu có, gồm cả trường hợp
  phải yêu cầu chụp lại. Không tạo ground truth bằng dự đoán rồi báo model tự đạt.
- Đo box cắt mất nét, tỷ lệ đúng đủ từng trường, lỗi không trả được kết quả, latency
  trên máy đích. Recognition trên box chuẩn chưa phản ánh lỗi detector.
- Quyết định fine-tune Seq2Seq hay Transformer dựa trên validation được duyệt và latency,
  không dựa duy nhất vào confidence hoặc crop demo.
