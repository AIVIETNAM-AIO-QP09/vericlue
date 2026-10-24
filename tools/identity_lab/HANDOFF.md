# Bàn giao OCR + face matching cho nhóm SW

Nhánh `feat/FLOW-05-identity-lab` lưu code trước khi tích hợp UI/UX, dựa trên
`main` a98098e. Đây là developer lab, không thay module LVFace của FLOW-05 đã có
trong main. Không gọi API lab là luồng eKYC hoàn chỉnh.

## Bản giữ lại

| Phần | Lựa chọn hiện tại | Chạy/đọc ở đâu |
|---|---|---|
| Detector trường CCCD | checkpoint tự train `best.pt` | `try_card_detector.py` |
| Đọc chữ từ crop | VietOCR vgg_seq2seq pretrained | `prepare_vietocr.py`, `field_recognition.py` |
| OCR ảnh đầy đủ trong lab API | PaddleOCR + VietOCR | `app.py`, `README.md` |
| So mặt | SCRFD-10G + AdaFace IR18, single embedding | `face_matching.py`, `FACE_MATCHING.md` |
| Khắc phục không thấy mặt sát khung | thử lại với viền khi zero detections | `face_context.py`, `FACE_CONTEXT.md` |

Adapter đã train, AdaFace IR101 và ArcFace không được chọn làm mặc định.
Code benchmark/training vẫn được giữ để kiểm chứng; không đóng gói trọng số các bản đó.
`face_context_trial.py` là runner kiểm tra cấu hình/hash đã đánh giá ở máy phát triển;
không có các output cục bộ đó thì dùng `face_matching.py` baseline hoặc tự chạy lại
giao thức FG-NET. Context fallback chưa bật trong developer API.

## File cần người phụ trách tải lên kho model

**Chỉ cần tải `cccd_field_detector_v1.zip`**, khoảng 208 MB (198.6 MiB), vào
Drive chung của nhóm hoặc phần Assets của GitHub Release. Không `git add` ZIP/model.
Gói có duy nhất `best.pt`, không ảnh hay kết quả OCR cá nhân.

- SHA-256 ZIP: `0373ded72471508a28784026e3288c531344ba49ab84f1e2d782019202815dff`
- SHA-256 `best.pt`: `92510cb983808bc2b4e426a4e82a062676df35419f38eb009ede67a2e3805827`
- Máy nhận giải nén thành `vericlue/models/cccd_detector/best.pt`.
- Sau khi upload, gửi link cho nhóm cùng SHA-256; chưa có URL chia sẻ trong repo.

VietOCR pretrained và SCRFD/AdaFace là trọng số có nguồn tải chính thức. Không cần
upload lại. Tạo venv riêng theo README và đặt `IDENTITY_MODELS_DIR` trước khi chạy:

```powershell
$env:IDENTITY_MODELS_DIR="$PWD/models/identity_lab"
python tools/identity_lab/prepare_vietocr.py --architecture seq2seq
python tools/identity_lab/prepare_face_models.py --recognizer adaface_ir18
python tools/identity_lab/try_card_detector.py path/to/card.jpg --checkpoint models/cccd_detector/best.pt --vietocr-models models/identity_lab/vietocr --out outputs/card_trial_new
python tools/identity_lab/face_matching.py path/to/card.jpg path/to/selfie.jpg --recognizer adaface_ir18 --out outputs/face_trial_new/result.json
```

Không upload ZIP VinText, face adapter, ảnh CCCD/selfie, dataset, output OCR/embedding,
cache hay `.venv`. Bản VinText bị loại ở lượt kiểm tra này; ZIP gốc người dùng giữ riêng.
Giấy phép sử dụng trọng số/dataset cần được rà theo mục đích triển khai; việc tải được
không tự chứng minh có quyền triển khai thương mại.

## Kết quả VinText ngày 24/10/2026

Gói người dùng cung cấp: SMOKE=False, 10 epoch, 3.017 crop validation.
Log ghi CER pretrained 0.202369, thấp nhất 0.105367 ở epoch index 8 (epoch thứ 9),
exact match tại epoch đó 0.789526. Đây là log kèm export, chưa tái chạy VinText test;
gói không có `final_test.json`. Weight SHA-256:
`64f2a868dbfdd16bffd4fec67f27fb64b3ac99d80f65b3ca95da7182719a0d02`.

Đã chạy hai recognizer với cùng checkpoint detector/cách tạo crop trên ba ảnh CCCD
phát triển: 9, 9, 8 box. Bản VinText làm hai trường ngày hết hạn chuyển từ giá trị
hợp lệ sang null và thay đổi tên theo hướng không mong muốn; có vài thay đổi dấu
địa danh. Không có ground truth độc lập để công bố CER/accuracy CCCD. Không chọn
model bằng confidence cao hơn hoặc lấy kết quả tốt nhất theo từng ảnh.
Giữ pretrained, chưa đưa VinText thành mặc định.

## Điểm tích hợp khi UI/UX xong

- Chạy `python -m uvicorn app:app --app-dir tools/identity_lab --host 127.0.0.1 --port 8010`.
- Xem `/docs` và `openapi.json` để thử multipart OCR/face. API chỉ dùng cục bộ cho developer.
- UI production không hiển thị cosine/confidence như phần trăm đúng danh tính.
- Cần adapter sang contracts hiện hành, session/token, đồng ý xử lý dữ liệu,
  quality/retry, PAD, policy và retention trước khi nối luồng thực.
- Ngưỡng CCCD–selfie chưa được xác lập. Không chuyển `review` thành `pass`.
- Model detector riêng chưa được đưa vào `/dev/v1/ocr`; CLI thử checkpoint là luồng riêng.

## Kiểm tra và dọn dẹp

103 unit tests đạt trên Python 3.10/CPU của lab; Ruff sạch, notebook không chứa output.
Chưa chạy toàn bộ production stack hoặc tái huấn luyện trên Colab trong đợt bàn giao.
Đã chuyển script probe một lần và nhật ký cũ ra kho lưu trữ cục bộ, xóa thư mục pytest
tạm và trọng số face không được chọn. Dataset, checkpoint detector, baseline OCR/face,
báo cáo đánh giá và ảnh gốc vẫn giữ tại máy, bị Git ignore.
