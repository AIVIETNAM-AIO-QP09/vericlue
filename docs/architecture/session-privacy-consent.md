# Đồng ý và rút lại xử lý dữ liệu theo phiên (SEC-06)

API này ghi nhận lựa chọn cho **một phiên eKYC**, không đại diện cho thao tác xóa tài khoản.
Hợp đồng: `packages/contracts/schemas/privacy.schema.json`; migration: `0010_privacy_receipts`.
API dùng cùng bearer mới nhất của phiên, kiểm lại trước và sau khi nhận body; không đưa token vào URL.

## API

| Phương thức / đường dẫn | Nội dung |
| --- | --- |
| `GET /v1/sessions/{session_id}/privacy` | Trạng thái và biên nhận tối thiểu của phiên |
| `POST /v1/sessions/{session_id}/privacy/consent` | `{ "policy_version": "demo-v1", "categories": ["face_biometrics"], "consent": true }` |
| `POST /v1/sessions/{session_id}/privacy/withdraw` | `{ "confirm": true }`, rút toàn bộ xử lý của phiên |

Body JSON tối đa 8 KiB, chỉ nhận thuộc tính đã khai báo và boolean `true` rõ ràng.
Trạng thái gồm `not_granted`, `granted`, `withdrawn`; `scope` luôn là `session`.
Không có điểm số, ảnh, số điện thoại, thông tin CCCD hay khóa trong biên nhận.

`REQUIRE_PRIVACY_CONSENT=false` giữ tương thích fixture/demo cũ; cấu hình bảo vệ phải bật.
`PRIVACY_POLICY_VERSION` là phiên bản thông báo mà bên tích hợp thực sự đã hiển thị.
Đổi phiên bản yêu cầu đồng ý lại; API không tự diễn giải văn bản chính sách hoặc chứng nhận pháp lý.

| Nhóm dữ liệu | Endpoint phải có quyền khi bật yêu cầu đồng ý |
| --- | --- |
| `contact` | Gửi và xác minh OTP |
| `id_document` | Nhận và xác nhận CCCD, gồm ảnh chân dung trên giấy tờ |
| `face_biometrics` | Nhận ảnh/video, signals và chấm xác minh |
| `voice_biometrics` | Nhận giọng nói; bước này đồng thời cần `face_biometrics` vì video có mặt và kiểm tra liên tục danh tính |

Kiểm tra trước parser ngăn nhận/spool dữ liệu chưa được cho phép; dependency của handler kiểm lại
sau parser để bắt thay đổi token/chính sách hoặc rút lại trong lúc upload. Thử lại cùng lựa chọn
không tạo sự kiện mới; mỗi phiên tối đa tám sự kiện đồng ý, một sự kiện rút lại và một xác nhận
xóa file. Nhãn nhóm là metadata, không phải giá trị sinh trắc học.

## Rút lại và xóa

Trong một transaction khóa hàng phiên, server xác thực bearer hiện hành, ghi sự kiện rút lại và
hủy khóa mã hóa riêng của phiên. Không gọi `SessionStore.save_all()` từ luồng này.
Chỉ sau commit mới xóa thư mục nguồn mã hóa; xóa file thất bại không mở lại xử lý, và gọi lại
endpoint có thể hoàn tất việc dọn file. Chưa hỗ trợ yêu cầu này cho phiên lưu plaintext cũ:
trả `503 privacy_unavailable`, cần quy trình chuyển đổi/xóa riêng.

Sau commit, endpoint eKYC thông thường trả `410 session_withdrawn`; không cấp kết quả hoặc
chứng nhận BBS mới cho phiên. Chỉ bearer mới nhất đã được băm và lưu tại thời điểm rút lại
có thể đọc biên nhận hoặc gọi lại yêu cầu, đến hết hạn bearer ban đầu. Token trước khi refresh
không được dùng thay thế. API không kéo dài thời gian lưu trữ hoặc TTL phiên.

Phản hồi tách rõ:

- `storage_erasure=key_destroyed`: khóa đã hủy; chưa xác nhận xóa file nguồn vật lý.
- `storage_erasure=files_deleted`: thư mục nguồn của phiên đã được xóa.
- `processing_cleanup=not_verified`: chưa xác nhận mọi bản plaintext tạm của tác vụ đang chạy
  đã được giải phóng. Lease xử lý được giải phóng theo vòng đời tác vụ; API không tuyên bố xóa tức thì.
- `account_data_erased=false`: mẫu đã đăng ký ở tài khoản, dữ liệu phiên khác, bản giám định độc lập
  và bản sao bên ngoài phạm vi kho phiên không thuộc yêu cầu này.
- `credential_revocation=not_performed`: chứng nhận/biểu diễn BBS đã cấp trước đó không được thu hồi
  bằng thao tác này. Bên kiểm chứng vẫn phải áp dụng hạn và thử thách một lần hiện có (tối đa 60 giây);
  không tuyên bố thu hồi tức thời bản đã cấp.

Nhật ký append-only chỉ giữ mã phiên, phiên bản chính sách, nhóm dữ liệu, thời điểm và ID biên nhận;
sự kiện rút lại thêm hash token và hạn dùng để xác thực lại sau khi khóa bị hủy.
Trigger SQLite/PostgreSQL chặn sửa/xóa sự kiện qua tài khoản ứng dụng; đây không phải bảo vệ
chống quản trị viên cơ sở dữ liệu toàn quyền. Chính sách xóa metadata nhật ký cần quyết định riêng.

## Giới hạn và phần tích hợp còn lại

Bearer chứng minh quyền truy cập phiên, **không chứng minh một người đã đọc và bấm đồng ý**.
Bên web/Android phải hiển thị thông báo đúng phiên bản, mục đích, nhóm dữ liệu và thao tác tự nguyện;
không tự gọi consent API trước khi có lựa chọn. Không có UI mới trong thay đổi này.
Việc chứng minh ý chí của con người, quyền đại diện, xóa tài khoản và chính sách dữ liệu liên hệ
cần thiết kế sản phẩm/pháp lý riêng; API không tự bịa các chính sách đó.

Migration phải được áp dụng trước khi phục vụ request. Bảng biên nhận bị thiếu/lỗi phải làm
request thất bại; không được hạ xuống bỏ qua chốt đồng ý hoặc trạng thái đã rút lại.
Các kiểm thử dùng dữ liệu tổng hợp, SQLite disposable và AEAD thật; PostgreSQL cần CI có dịch vụ DB.
