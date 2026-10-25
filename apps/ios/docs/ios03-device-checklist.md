# IOS-03 — OTP và CCCD trên iPhone thật

## Phạm vi và trạng thái

Code đã nối giai đoạn A với API: OTP, camera sau, đo chất lượng/đọc QR, gửi hai
ảnh và xác nhận thông tin sửa. Debug mặc định vẫn là demo IOS-01. Phải bật
**API thật** theo hướng dẫn dưới đây để nghiệm thu IOS-03.

Sếp đã báo checklist thủ công trên iPhone đạt; Codex không trực tiếp quan sát
thao tác. Lượt test đầu ngày 25/10/2026 đạt 52/53, lỗi Vision QR Code 9. Sau khi
thêm fallback Core Image chỉ trên Simulator (iPhone thật vẫn dùng Vision), lượt
chạy lại theo yêu cầu sếp đạt **53/53 test cases, 0 lỗi, 0 skip**. Artifact:
`/tmp/vericlue-ios03-qr-fix-20261025.xcresult`. Review cuối sửa thêm deadline OTP
khi đổi số rồi mất mạng; test hồi quy mới cùng toàn suite đạt **54/54, 0 lỗi,
0 skip** trong lượt cuối (`/tmp/vericlue-ios03-final-review-20261025.xcresult`).
Chưa commit/push/PR merge.
Máy thật theo xác nhận của sếp: **iPhone 14 Pro, iOS 18.7.8**.

## 1. Chuẩn bị server và iPhone

Trong Terminal ở thư mục gốc repo:

```bash
mkdir -p tmp/media
export DATABASE_URL="sqlite:///$PWD/tmp/dev.db"
export MEDIA_DIR="$PWD/tmp/media"
export USE_MOCK_MODELS=true
export SESSION_SIGNING_SECRET="$(openssl rand -hex 32)"

uv run --frozen alembic -c services/api/alembic.ini upgrade head
uv run --frozen uvicorn vericlue_api.main:app \
  --app-dir services/api/src --host 0.0.0.0 --port 8000
```

Giữ Terminal này mở. Kiểm tra IP Mac bằng `ipconfig getifaddr en0` trong Terminal
khác; đối chiếu `Config/Debug.xcconfig`. iPhone/Mac dùng cùng Wi-Fi; Safari trên
iPhone phải mở được `http://<IP-Mac>:8000/docs`.

Khóa ở trên chỉ tạo trong môi trường shell, không in ra hoặc commit. Chỉ tạo
một lần trước khi khởi động server; đổi khóa làm token của các phiên cũ mất hiệu
lực. Nếu server đang chạy, dừng bằng Ctrl+C rồi chạy lại trong Terminal đã export
khóa; app quay về ngân hàng và bắt đầu phiên mới.

Nếu bấm Gửi mã lập tức tới màn "Tạm thời chưa thể xác minh", kiểm tra response
`POST /v1/sessions`. HTTP 503 `security_unavailable` nghĩa là khóa ký phiên server
không dùng được (ngắn hơn 32 byte). Thuần mock tự sinh khóa nếu không cấu hình,
nhưng một giá trị cấu hình không rỗng mà quá ngắn vẫn bị từ chối. `/healthz` trả
`ok` không chứng minh tạo phiên đã hoạt động. Không sửa app để bỏ kiểm tra token.

Mở project Xcode, chọn Debug và iPhone thật, xử lý Signing/Trust/Developer Mode,
nhấn Run. Simulator không có camera sau thật và không thay được nghiệm thu này.

## 2. Bật đúng chế độ

1. Màn Ngân hàng Mẫu → **Xem tất cả màn (bản demo giao diện)**.
2. Chọn **API thật**, kịch bản **genuine**.
3. Bấm Back về ngân hàng. Không mở riêng màn điện thoại/CCCD trong gallery:
   các item gallery luôn là preview demo, không tạo phiên live.
4. Bấm **Mở tài khoản → Đăng ký**, đi qua điều khoản/đồng ý/giới thiệu.
5. **Cho phép và tiếp tục** yêu cầu quyền camera. Chưa ghi âm micro ở IOS-03.

Release mặc định dùng API; không có gallery. URL Release còn cần cấu hình hợp
lệ ở IOS-07, nên nghiệm thu giai đoạn này bằng Debug trên iPhone.

## 3. Số điện thoại và OTP

- Nhập số demo như `0912345678`. Chỉ `0` + 9 số ASCII được chấp nhận.
- Bấm Gửi mã nhanh hai lần. Trong lúc loading, nút/keypad bị khóa. Server phải
  nhận tạo phiên trước rồi mới OTP, không có hai phiên do cùng thao tác.
- Đọc mã thực từ khung **SMS mô phỏng**. Không mặc định mã là `123456`: server
  sinh mã ngẫu nhiên.
- Nhập một mã khác mã đang hiện → có câu "Mã chưa đúng. Bạn còn N lần thử."
  với N từ server. Nhập lại đúng mã → sang chụp CCCD.
- Gửi lại chỉ bật sau 45 giây tính từ khi server chấp nhận gửi. Thử ra Home
  khoảng 20 giây rồi quay lại: thời gian phải giảm tương ứng, không đứng ở số cũ.
- Back về điện thoại rồi bấm Gửi mã cùng số trong 45 giây: quay về OTP cũ,
  không phát thêm request. Đổi số điện thoại thì tạo phiên mới.
- Khi gửi lại thành công: SMS/mã/attempts được cập nhật, bắt đầu deadline 45s mới.
- Để mã quá hạn (mặc định server 2 phút) → thông báo hết hạn, xin mã mới.
- Nhập sai tới khóa → không cho xác nhận tiếp, vẫn cho xin mã mới khi hết cooldown.
- Gửi mã quá giới hạn server (mặc định 3 lần) → màn tạm thời chưa thể xác minh.
- Sau OTP đúng, Back từ chụp trước về OTP và xác nhận lại: server
  `otp_already_verified` được coi là đã qua, không quay vòng nhập mã.

Mất Wi-Fi trong lúc gửi/verify phải báo lỗi tại chính màn đó. Bật lại Wi-Fi và
thử lại; không tự đi tới kết quả thành công.

## 4. Chuẩn bị thẻ in thử, tuyệt đối không dùng CCCD thật

Làm hai mặt thẻ mẫu bằng dữ liệu bịa, nhiều dòng chữ nhỏ rõ nét. Nền xám/kem nhạt
để phân biệt với mảng phản chiếu trắng. Mặt sau có QR chứa nguyên văn:

```text
000000000001||NGUYEN VAN MAU|01011995|Nam|DIA CHI MAU|01012021
```

Đây là số/danh tính tổng hợp chỉ để thử định dạng. Tạo QR offline, in hoặc hiển
thị trên thiết bị thứ hai; không dùng dịch vụ tạo QR với thông tin cá nhân thật.

## 5. Chụp và kiểm tra chất lượng

1. Đặt mặt trước vào khung ngang `1.586:1`, bấm chụp.
2. Xem đúng ảnh vừa chụp, kiểm dòng nét/lóa. Ảnh chưa đạt thì nút tiếp tục khóa.
3. Chụp lại với máy rung/mất nét → phải nhắc ảnh bị mờ.
4. Chiếu đèn gây mảng trắng phản chiếu → phải nhắc thẻ bị lóa.
5. Với ảnh đạt, đi sang mặt sau; không có QR/QR không giống định dạng CCCD thì
   yêu cầu chụp lại mặt sau, chưa gửi ảnh lên server.
6. Để thử retry QR từ server, dùng QR có 12 chữ số và đủ trường nhưng ngày sinh
   sai như `32011995`. Vision vẫn đọc được và local gate cho gửi; server phải trả
   `QR_INVALID`. App quay đúng capture mặt sau, giữ ảnh mặt trước.
7. Dùng lại QR hợp lệ → upload hai ảnh, tới màn kiểm tra thông tin server trả.
8. Tắt quyền camera trong Cài đặt → thông báo quyền; Mở Cài đặt và cấp lại,
   quay lại/Thử lại phải mở preview được. Ra Home khi đang chụp không được tự
   chuyển sang review với ảnh thiếu hoặc ảnh cũ.

Ảnh được xoay thẳng theo EXIF và crop giữa theo khung trước khi đo/đọc QR/gửi.
Ngưỡng ban đầu theo Android: Laplacian variance ≥60; glare fraction ≤0.02,
sample luma ≥250. Đây là ngưỡng khởi đầu, chưa hiệu chỉnh bằng đo trên iPhone.
Không nới ngưỡng chỉ để một ảnh thử đi qua; ghi thiết bị/ánh sáng/ảnh lỗi để review.

## 6. Kiểm tra thông tin và dữ liệu sửa

- Tên viết HOA, số CCCD nhóm ba, ngày `01/01/1995`; không dùng dữ liệu mẫu cố định
  của gallery trong luồng API thật.
- Mở Sửa thông tin: số CCCD là text khóa, không có ô nhập.
- Đổi tên sang `NGUYEN VAN MAU B` và ngày sang `02/01/1995`.
- Back về kiểm tra thông tin: vẫn thấy dữ liệu sửa. Mở lại Sửa: vẫn giữ bản nháp.
- Ngày không tồn tại như `31/02/1995` phải báo lỗi và không gửi confirm.
- Lưu và tiếp tục gửi `/id-card/confirm` với `full_name` đã sửa,
  `date_of_birth = 1995-01-02`, giữ `id_number` và `issued_on` gốc.
- Tắt Wi-Fi lúc confirm: ở lại màn, giữ bản nháp để thử lại; không tự hoàn tất.

Trong bản IOS-03, sau confirm thành công app dừng ở **Đã xác nhận thông tin**.
Bước khuôn mặt live thuộc IOS-04. App không chuyển sang mô phỏng mặt/giọng rồi
báo thành công cho một phiên API thật chưa được server kiểm tra.

## 7. Kiểm tra server nhận ảnh và dữ liệu

Terminal server phải có request `/id-card` và `/id-card/confirm` thành công.
Với MEDIA_DIR ở trên, kiểm tra hai file trong cùng thư mục phiên:

```bash
find tmp/media -type f \( -name 'id_front.jpg' -o -name 'id_back.jpg' \) -print
```

Đối với SQLite ở trên, đọc phiên mới nhất:

```bash
sqlite3 tmp/dev.db "SELECT session_id, json_extract(payload, '$.id_front'), json_extract(payload, '$.id_back'), json_extract(payload, '$.id_edited') FROM sessions ORDER BY created_at DESC LIMIT 1;"
```

Hai đường dẫn phải tồn tại và `id_edited` phải có `full_name`/`date_of_birth` nếu
đã sửa hai trường. Chỉ dùng dữ liệu bịa khi kiểm tra hoặc chụp bằng chứng.

Lưu ý backend hiện chỉ giữ danh sách trường thay đổi trong `id_edited`; snapshot
`id_fields` vẫn là dữ liệu QR gốc. Không thể dùng snapshot đó làm bằng chứng
server đã lưu giá trị sửa mới. Để xem chính payload gửi, đặt breakpoint trong
`SessionApi.confirmIdCard`, xem `fields` bằng debugger trên dữ liệu bịa. Test
`IdentityFlowTests.editsPersistAndOnlyEditedValuesAreConfirmed` cũng kiểm JSON
request bằng MockURLProtocol (đã qua trong lượt chạy ngày 25/10/2026).

## Checklist nghiệm thu

Các mục thao tác được tích theo xác nhận của Lý Anh Quân trong chat ngày
25/10/2026, không phải video/quan sát trực tiếp của Codex. JSON ISO và số CCCD
khóa có thêm bằng chứng unit test; hai ảnh và trường thay đổi có kiểm tra DB/file.
Base commit: `2e043e2` + working tree nhánh `feat/IOS-03-otp-id-card`; chưa có
commit IOS-03. API local: `http://192.168.1.11:8000/`, mock/genuine.

- [x] Ghi model iPhone/iOS, base commit + working tree, IP/API mock đang dùng.
- [x] OTP sai rồi đúng; attempts đúng server; gửi nhanh hai lần không trùng request.
- [x] Resend đủ 45 giây, đúng khi background/foreground.
- [x] Hết hạn/khóa/quá số lần/đã xác nhận xử lý đúng.
- [x] Chụp hai mặt bằng camera sau; khung và ảnh không lệch vùng thẻ.
- [x] Ảnh thiếu/mờ/lóa bị chặn; từ chối quyền không crash.
- [x] Local QR lỗi và server QR_INVALID quay đúng mặt sau, giữ mặt trước.
- [x] Sửa tên/ngày được giữ trong app, gửi đúng JSON ISO, khóa số CCCD.
- [x] Server nhận đủ hai JPEG, xác nhận các trường thay đổi.
- [x] Mất mạng không đi tắt qua bước đang gửi hoặc ra success.
- [x] Diff dự kiến commit không có ảnh thật, QR thật, audio/video hoặc token; cần kiểm lại staged diff nếu bổ sung file.

## Tham khảo kỹ thuật

- Android `capture/IdCard.kt`: ngưỡng và phép đo chất lượng ban đầu.
- [Apple AVCaptureSession](https://developer.apple.com/documentation/avfoundation/avcapturesession): start/stop trên serial queue để không chặn UI.
- [Apple VNDetectBarcodesRequest](https://developer.apple.com/documentation/vision/vndetectbarcodesrequest): nhận diện QR qua Vision.
