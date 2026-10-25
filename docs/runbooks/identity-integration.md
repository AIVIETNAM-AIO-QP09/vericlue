# Tích hợp Android với OCR/QR và AdaFace

Giai đoạn demo opt-in, nối UI Android hiện có với runtime identity lab. API chính
vẫn dùng Python 3.12; runtime model dùng venv Python 3.10 đã kiểm tra. Không cài
Paddle/Torch vào API chỉ để chạy cầu nối. Không đổi module LVFace của registry.

## Luồng

1. App gửi hai ảnh vào `/v1/sessions/{id}/id-card` với token phiên.
2. API gọi runtime riêng. Server đọc QR từ cả hai ảnh; QR hợp lệ được ưu tiên.
   Nếu không có QR hợp lệ, detector CCCD + VietOCR pretrained đọc các trường.
   Hai QR hợp lệ khác nhau trả retry. Chuỗi QR client không được tin trong chế độ này.
3. App hiện thông tin, cho sửa cả số CCCD. Trường thiếu không được thay bằng dữ liệu mẫu.
   Phải có tên, số CCCD 12 số, ngày sinh hợp lệ, giới tính và địa chỉ để xác nhận.
4. Server giữ riêng bản quét và bản xác nhận; số CCCD chỉ lưu HMAC. Sửa khác bản quét
   sẽ chặn tự động đạt và ghi tên trường thay đổi cho ca duyệt. Quét lại xóa xác nhận cũ.
5. Finalize so ảnh CCCD với ảnh tĩnh đầu tiên server nhận của lượt mặt, không chọn
   điểm cao nhất. Dùng SCRFD/AdaFace IR18 và context fallback; cosine >= 0.40 là
   qua riêng bước so mặt. Đây là ngưỡng người dùng chọn, chưa hiệu chỉnh CCCD–selfie.
   Không phải 40% xác suất. Lỗi/thiếu mặt/điểm không hợp lệ không được coi là đạt.
6. Kết quả PAD, liveness, voice và policy vẫn có hiệu lực. Người dân không nhận điểm.

### Bảo toàn ảnh và phạm vi luồng (bản sửa review PR #65)

- Kiểm trạng thái trước khi đọc ảnh/gọi runtime; sau khi nhận media/signals hoặc chấm mặt,
  đổi CCCD trả 409 và không ghi file mới.
- Chỉ lưu ảnh sau khi runtime trả kết quả hợp lệ. Mỗi lần quét dùng một cặp tên file mới;
  chỉ đổi tham chiếu phiên khi cả hai file được ghi. OCR lỗi/response lỗi (503), ghi file
  lỗi hoặc commit DB lỗi giữ nguyên thông tin, xác nhận và byte ảnh của thẻ trước.
- Lần quét hoàn thành trả `ok` **hoặc** `retry` đều thay cặp ảnh và hủy xác nhận/kết quả
  so mặt cũ. File cũ, hoặc file không được DB tham chiếu sau lỗi, theo TTL của phiên.
- Cầu nối CCCD–selfie áp dụng cho luồng cũ, onboarding và recovery. `reauth` giữ policy
  thiết bị của FLOW-01: không gọi cầu nối này, không yêu cầu quét lại thẻ và không tạo
  ca duyệt CCCD. Đối chiếu mẫu danh tính đã đăng ký vẫn thuộc FLOW-05/SEC-02; bản sửa này
  không bổ sung xác minh thiết bị thật, không gỡ chặn real/mixed.

QR/OCR chỉ trích xuất nội dung, không xác minh thẻ thật. Dữ liệu đã sửa cần duyệt;
việc sửa số CCCD không thay ảnh tham chiếu. Không cho đổi thẻ/thông tin sau khi
bắt đầu nhận media của lượt xác minh.

## Chạy tại máy phát triển

Terminal 1, từ repo root (thay đường dẫn venv/model cho máy khác):

```powershell
$env:IDENTITY_MODELS_DIR='F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
$env:CCCD_DETECTOR_CHECKPOINT="$PWD/models/cccd_detector/best.pt"
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe -m uvicorn app:app --app-dir tools/identity_lab --host 127.0.0.1 --port 8010
```

Runtime `/internal/*` không có xác thực riêng, chỉ bind localhost. Không công khai
cổng 8010 hoặc đưa URL này vào Android. Chỉ API chính được gọi runtime.

Terminal 2, cấu hình DB và chạy migration theo README API, rồi:

```powershell
$env:IDENTITY_LAB_URL='http://127.0.0.1:8010'
$env:IDENTITY_FACE_THRESHOLD='0.40'
$env:IDENTITY_LAB_TIMEOUT_SECONDS='90'
$env:USE_MOCK_MODELS='true'
& .venv\Scripts\python.exe -m uvicorn vericlue_api.main:app --host 0.0.0.0 --port 8000
```

**Đây là demo hỗn hợp có chủ đích:** OCR/QR/so mặt thật, các detector khác theo
`USE_MOCK_MODELS=true`. Luồng dynamic onboarding/recovery trên main vẫn chặn
real/mixed tới khi đầy đủ các mô-đun khác. Không gỡ chặn đó, không tuyên bố toàn bộ
eKYC đã chạy AI thật. Tắt `IDENTITY_LAB_URL` để trở lại hành vi mock cũ.
Trong chế độ real/mixed, thiếu bridge thì bước quét thẻ trả unavailable.

App Android vẫn gọi API :8000 theo README Android, không đổi hình dạng request/response.
Endpoint/JSON công khai giữ nguyên; lỗi dịch vụ dùng `{error_code, message}`.
Ảnh lưu trong MEDIA_DIR theo retention hiện có; runtime không lưu crop OCR/embedding.
Thông tin quét và xác nhận ở snapshot DB theo cơ chế hiện có, chưa có cơ chế mã hóa
riêng cho các trường này. Không triển khai production trước khi chốt bảo mật/retention.

## Kiểm chứng

- Unit/integration synthetic kiểm server QR ưu tiên, OCR thiếu trường, sửa thông tin,
  rescan, threshold boundary 0.4, NaN/bool/out-of-range, không lộ điểm và chặn error.
- Runtime thật đã đọc QR từ ảnh thử và so mặt HTTP 200; ảnh dùng hai lần chỉ để kiểm
  transport, không phải nghiệm thu chụp đúng hai mặt thẻ hoặc benchmark chính xác.
- Android có test mới `IdentityCorrectionTest`; máy phát triển chưa có SDK/JDK 17,
  cần chạy `gradlew testDebugUnitTest assembleDebug` và thử camera trên thiết bị.
