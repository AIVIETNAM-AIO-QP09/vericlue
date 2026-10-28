# Tiếp nhận phiên eKYC — SEC-03

`SessionAPIRoute` chạy kiểm quyền trước handler gốc của FastAPI, nên trước khi
FastAPI parse JSON/multipart. Public create-session và public-key endpoints giữ
chính sách riêng. Route có `session_id` yêu cầu đúng một bearer header, token
HMAC đúng phiên/hạn và khớp hash hiện hành trong snapshot. Token cũ sau refresh,
phiên hết hạn hoặc khóa riêng tư đã hủy không được dùng để gửi body.

Kiểm trước dùng một DB session ngắn, không gọi `save_all`, không cập nhật hoạt
động và không giữ row lock qua lúc chờ client upload. Dependency `require_session`
vẫn kiểm lại sau parser: token bị thu hồi hoặc hết hạn trong khi nhận không được
ghi nhận. Preflight không tự khởi tạo model và không mở guard real/mixed.

PostgreSQL áp `DB_LOCK_TIMEOUT_SECONDS` bằng thiết lập transaction-local **trước**
lần đọc session/DEK đầu tiên, kể cả preflight privacy và transaction privacy sau
body. Khóa đang bận trả `503 storage_busy` mà chưa parse hoặc thay trạng thái;
không chờ tới `get_state` mới đặt timeout. SQLite preflight vẫn chỉ đọc, còn
transaction privacy giữ BEGIN IMMEDIATE. Kiểm thử PostgreSQL giữ nguyên yêu cầu
trả lời trong 2 giây khi một kết nối khác đang giữ khóa phiên.

## Multipart

Parser chỉ nhận các vai trò đã khai báo:

| Endpoint | File | Field |
|---|---|---|
| `media` | image, video tùy chọn | challenge_id, media_signature |
| `voice` | audio, video tùy chọn | voice_challenge_id, media_signature, audio_offset_ms |
| `id-card` | front, back | qr |

File/field trùng, vai trò ngoài allowlist hoặc tráo loại field/file trả
`400 invalid_multipart`. FastAPI vẫn kiểm các trường bắt buộc và giá trị nghiệp
vụ theo hợp đồng. Không suy ra định dạng ảnh từ tên file hoặc MIME client.

- Trần mỗi file lấy `MAX_UPLOAD_MB` hiện có, được kiểm trong callback trước khi
  chunk vượt giới hạn được chuyển sang ghi file tạm.
- Trần tổng body ASGI/`MAX_REQUEST_MB` vẫn áp dụng, kể cả thiếu Content-Length.
- Field QR tối đa 16 KiB, mã challenge tối đa 256 byte, signature tối đa 160 byte,
  audio_offset_ms tối đa 8 byte; header của mỗi part tối đa 8 KiB. Đây là hằng số
  bảo vệ parser, không phải ngưỡng AI. Trần field/file không phải quota tổng phiên.
- Các phần vượt trần byte trả 413; dữ liệu multipart lỗi hoặc thiếu boundary cuối
  bị từ chối. File tạm được đóng khi parser, stream hoặc handler lỗi.
- Form đã parse được đặt vào cache request để handler không parse/spool lần nữa;
  wrapper đóng form cả khi handler lỗi. Tests ghim hành vi này trên phiên bản
  Starlette trong lockfile.

Lỗi preflight/parser có `Cache-Control: no-store`. Lỗi nghiệp vụ được ném tiếp
cho handler lỗi chung: không bắt rồi trả response trước khi dependency `yield`
thấy exception, vì như vậy có thể commit nonce của một upload thất bại.
Token sai không gọi
parser, còn phần đọc hợp lệ vẫn có file tạm của multipart: đây không phải mã hóa
end-to-end hoặc chống DDoS. Proxy, filesystem temp riêng, hạn kết nối/concurrency
và quota bền vững vẫn cần theo cấu hình triển khai.

## Kiểm chứng

`services/api/tests/test_session_ingress.py` dùng dữ liệu tổng hợp để kiểm thiếu/
sai/khác phiên/trùng/hết hạn token, token cũ sau refresh, thay token trong lúc
receive, file/field lạ hoặc trùng, trần byte và file tạm đóng sau multipart lỗi.
Các bộ test media-proof/request-limits kiểm lại chữ ký byte gốc, nonce rollback và
trần ASGI. Không sửa schema, ngưỡng hoặc mô hình trong SEC-03.
