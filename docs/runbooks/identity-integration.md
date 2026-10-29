# Tích hợp Android với QR, chân dung và LVFace-B

Giai đoạn demo opt-in, nối UI Android hiện có với runtime identity lab. API chính
và bộ đọc QR đều dùng Python 3.12, trong hai venv riêng. So mặt chạy
trực tiếp bằng SCRFD + LVFace-B ONNX trong API, không gọi AdaFace qua HTTP.
Môi trường API cần extra `face` (CPU) hoặc `cuda` hiện có; không cần Paddle/VietOCR
trong API. Không thay môi trường CUDA đang dùng chỉ để cài extra CPU.

## Luồng

1. App tự nhận QR/chân dung qua camera, chụp ảnh tĩnh rõ rồi kiểm lại trên chính ảnh đó.
   Gửi mặt trước vào `/v1/sessions/{id}/id-card` với token phiên; mặt sau chỉ cần
   nếu mặt trước chưa đọc được QR. Sau thời gian chờ có chụp thủ công hoặc dừng.
2. API gọi bridge `qr_app`. ZXing-C++ và OpenCV đọc QR từ pixel, SCRFD kiểm một
   chân dung có landmark và đủ kích thước. Bật `IDENTITY_CARD_PORTRAIT_REQUIRED=true`
   trong cấu hình app này. Thiếu QR/chân dung trả retry; bridge không cung cấp
   trạng thái chân dung trả unavailable. Hai QR hợp lệ khác nhau trả retry.
   Không dùng OCR hoặc QR do client tự khai để thay kết quả đọc ảnh.
3. App hiện thông tin, cho sửa cả số CCCD. Trường thiếu không được thay bằng dữ liệu mẫu.
   Phải có tên, số CCCD 12 số, ngày sinh hợp lệ, giới tính và địa chỉ để xác nhận.
4. Server giữ riêng bản quét và bản xác nhận; số CCCD chỉ lưu HMAC. Sửa khác bản quét
   sẽ chặn tự động đạt và ghi tên trường thay đổi cho ca duyệt. Quét lại xóa xác nhận cũ.
5. Finalize so ảnh CCCD với ảnh tĩnh đầu tiên server nhận của lượt mặt, không chọn
   điểm cao nhất. Orchestrator nạp một LVFace-B + SCRFD từ `MODELS_DIR` khi khởi động,
   kiểm revision/SHA và dùng lại qua hàng đợi/deadline hiện có. SCRFD tìm mặt trên
   ảnh thẻ, căn 5 điểm về 112×112 rồi LVFace so với selfie; không dùng context fallback.
   Mặc định ảnh đầu tiên chưa được kiểm tư thế tự động. Bật `IDENTITY_FACE_FROM_VIDEO`
   để lấy khung chính diện từ video theo lịch server, kiểm tư thế bằng MediaPipe
   rồi so với CCCD; xem [hướng dẫn các cổng phiên](../architecture/session-verification.md).
6. Kết quả PAD, liveness, voice và policy vẫn có hiệu lực. Người dân không nhận điểm.

### Ngưỡng và điểm so mặt

- `score = 1 - cosine(reference, front)`, không phải xác suất. Cosine nằm trong
  evidence nội bộ; điểm thấp hơn nghĩa là hai embedding gần nhau hơn.
- `IDENTITY_FACE_THRESHOLD=0.40` của AdaFace **không còn được sử dụng**.
  `IDENTITY_FACE_CALIBRATION` trỏ tới artifact LVFace do server quản lý, theo
  [`head-and-match.md`](../architecture/head-and-match.md). Thiếu artifact vẫn trả
  điểm nhưng `degraded/unclear`, yêu cầu duyệt thay vì tự đạt. Artifact sai/lỗi model
  làm `face_match` xuất hiện trong `failed_modules` của `/healthz`.
- Version mới có hậu tố `+front-reference-v2`. Artifact cũ tính min sáu phép so hoặc
  của AdaFace bị từ chối; kết quả AdaFace đã lưu trong phiên cũ không được cấp đạt.
- API chỉ so tham chiếu với một selfie. Diagnostic ba góc chỉ so tham chiếu–chính
  diện; cosine giữa các góc là evidence riêng, chưa hiệu chỉnh/ngưỡng hay xác nhận
  nhất quán. Không so ảnh nghiêng trực tiếp với CCCD.

### Bảo toàn ảnh và phạm vi luồng (bản sửa review PR #65)

- Kiểm trạng thái trước khi đọc ảnh/gọi runtime; sau khi nhận media/signals hoặc chấm mặt,
  đổi CCCD trả 409 và không ghi file mới.
- Chỉ lưu ảnh sau khi runtime trả kết quả hợp lệ. Mỗi lần quét dùng một cặp tên file mới;
  chỉ đổi tham chiếu phiên khi các ảnh được cung cấp đã ghi xong. Bridge lỗi (503), ghi file
  lỗi hoặc commit DB lỗi giữ nguyên thông tin, xác nhận và byte ảnh của thẻ trước.
- Lần quét hoàn thành trả `ok` **hoặc** `retry` đều thay cặp ảnh và hủy xác nhận/kết quả
  so mặt cũ. File cũ, hoặc file không được DB tham chiếu sau lỗi, theo TTL của phiên.
- Cầu nối CCCD–selfie áp dụng cho luồng cũ, onboarding và recovery. `reauth` giữ policy
  thiết bị của FLOW-01: không gọi cầu nối này, không yêu cầu quét lại thẻ và không tạo
  ca duyệt CCCD. Đối chiếu mẫu danh tính đã đăng ký vẫn thuộc FLOW-05/SEC-02; bản sửa này
  không bổ sung xác minh thiết bị thật, không gỡ chặn real/mixed.

QR chỉ trích xuất nội dung; SCRFD kiểm ảnh chân dung xử lý được, không xác minh thẻ thật.
Dữ liệu đã sửa cần duyệt;
việc sửa số CCCD không thay ảnh tham chiếu. Không cho đổi thẻ/thông tin sau khi
bắt đầu nhận media của lượt xác minh.

## Chạy tại máy phát triển

Terminal 1, từ repo root (thay đường dẫn venv/model cho máy khác):

```powershell
$env:MODELS_DIR="$PWD/models/selected-2026-10-24"
# Venv Python 3.12 riêng, cài tools/identity_lab/requirements-qr.txt.
& tmp/identity-qr-runtime/Scripts/python.exe -m uvicorn qr_app:app --app-dir tools/identity_lab --host 127.0.0.1 --port 8010 --no-access-log
```

Runtime `/internal/*` không có xác thực riêng, chỉ bind localhost. Không công khai
cổng 8010 hoặc đưa URL này vào Android. Chỉ API chính được gọi runtime.

Terminal 2, cấu hình DB và chạy migration theo README API, rồi:

```powershell
$env:IDENTITY_LAB_URL='http://127.0.0.1:8010'
$env:IDENTITY_CARD_PORTRAIT_REQUIRED='true'
$env:IDENTITY_LAB_TIMEOUT_SECONDS='90'
$env:USE_MOCK_MODELS='true'
$env:MODELS_DIR="$PWD/models/selected-2026-10-24" # Đổi theo thư mục model đã tải.
$env:DEVICE='cpu' # Hoặc cấu hình GPU hiện có đã kiểm tra.
# Chỉ đặt IDENTITY_FACE_CALIBRATION khi đã có artifact thật đúng version.
& .venv\Scripts\python.exe -m uvicorn vericlue_api.main:app --host 127.0.0.1 --port 8000
```

**Cấu hình ví dụ này là demo hỗn hợp:** QR/chân dung/so mặt thật, các detector khác theo
`USE_MOCK_MODELS=true`. Luồng dynamic onboarding/recovery trên main vẫn chặn
real/mixed tới khi đầy đủ các mô-đun khác. Không gỡ chặn đó, không tuyên bố toàn bộ
eKYC đã chạy AI thật. Tắt `IDENTITY_LAB_URL` để trở lại hành vi mock cũ.
Trong chế độ real/mixed, thiếu bridge thì bước quét thẻ trả unavailable.

App Android gọi API chính, không gọi trực tiếp bridge. Profile **VeriClue QR** dùng
localhost:8421 qua ADB reverse; ví dụ API :8000 ở trên dành cho môi trường phát triển.
Mặt sau đã thành tùy chọn và có retry `PORTRAIT_UNREADABLE` trong contract; client
cũ vẫn gửi được hai ảnh. Lỗi dịch vụ dùng `{error_code, message}`.
Ảnh lưu theo MEDIA_DIR/retention hiện có; bridge chỉ xử lý trong RAM và tắt access log.
Profile laptop giữ nguyên mã hóa phiên/media và khóa hiện có, không tạo lại DB.

## Kiểm chứng

- Unit/integration synthetic kiểm QR-only, thiếu QR/chân dung, bỏ qua trường OCR/client
  QR, mặt sau tùy chọn, QR xung đột, sửa thông tin,
  bảo toàn ảnh khi rescan lỗi; LVFace preload một lần, ảnh tham chiếu đúng phiên,
  artifact đúng/sai/thiếu, không dùng ngưỡng AdaFace, không lộ điểm và chặn error.
- Kiểm checkpoint LVFace/SCRFD thật bằng tensor tổng hợp chỉ xác nhận nạp/chạy;
  không phải benchmark CCCD–selfie, nghiệm thu camera hoặc độ chính xác.
- CI Android build/unit/lint/snapshot đạt, gồm trạng thái quét, timeout và retry
  ở màn hình nhỏ/font 200%. Native bridge/HTTP chỉ dùng ảnh tổng hợp, chưa chứng
  minh chất lượng quét thẻ thật. Nghiệm thu camera còn cần điện thoại.
