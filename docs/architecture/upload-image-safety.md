# Kiểm ảnh và thay thế CCCD theo giao dịch — SEC-04

Ảnh thuộc vai trò selfie hoặc mặt trước/sau CCCD được nhận diện bằng nội dung
trên server, không dựa vào tên hoặc MIME do client gửi. Áp dụng cả mock và real:
mock chỉ thay kết quả detector, không bỏ kiểm định dạng file.

## Ảnh đầu vào

- Chỉ JPEG, PNG, WebP một khung, cạnh tối đa 4096 và tổng tối đa 16 triệu pixel.
- Áp EXIF orientation, chuyển RGB, loại metadata và mã hóa lại theo định dạng
  được decoder nhận diện. Giữ recipe encoder mặc định của bước privacy trước đây;
  không đổi ngưỡng mô hình hoặc mở guard sinh trắc.
- Media có chữ ký được kiểm trên byte gốc trước biến đổi. Nếu validation/ghi file/
  commit lỗi thì nonce và trạng thái DB rollback; caller có thể gửi lại đúng proof.
- CCCD được chuẩn hóa trước khi gọi QR/OCR. Cùng buffer chuẩn hóa dùng để lưu,
  tránh OCR nhận bản gốc chứa metadata trong khi kho lưu một ảnh khác.
- Server cấp tên ngẫu nhiên và đuôi chuẩn của nội dung; PNG mang tên `.jpg` vẫn
  là ảnh PNG hợp lệ, nhưng mọi ảnh đều qua cùng validation và sanitation.
- API runtime khai báo Pillow là dependency bắt buộc, không dựa vào extra ML/dev.

## Thay cặp ảnh và hạn mức

Mỗi Session snapshot có `id_scan_count`, `id_scan_bytes`, mặc định 0 cho snapshot
cũ. PostgreSQL khóa hàng phiên như hiện có. SQLite mở BEGIN IMMEDIATE trước đọc
snapshot cho mọi route phiên: save_all ghi lại snapshot kể cả GET, nên refresh,
signals hoặc đọc kết quả cũng cần tuần tự để không ghi đè counter bằng bản cũ.
Hai rescan không thể cùng tiêu thụ một slot còn lại.

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| MAX_ID_CARD_SCANS | 5 | Tổng số lượt quét đã commit trong một phiên |
| MAX_ID_CARD_TOTAL_MB | 128 | Ngân sách byte cộng dồn cho các lượt đã commit |
| MAX_SESSION_MEDIA_MB | 256 | Ngân sách byte cộng dồn CCCD + mặt + giọng trong phiên |

Byte cộng dồn gồm input thô **và** ảnh chuẩn hóa của cả hai mặt. Đây là ngân sách
bảo thủ, không phải dung lượng đĩa hiện hành. Lượt trả `retry` vì QR cũng tính nếu
đã lưu ảnh; lỗi validation/ghi/commit không làm mất slot hoặc tăng counter.
Các giới hạn byte request/file hiện có vẫn áp dụng độc lập. `uploaded_media_bytes`
ghi tổng cả ba giai đoạn, không bị reset bởi refresh/retry. Audio/video được tính
hai lần kích thước (input + bản lưu), ảnh tính input + canonical. Snapshot cũ có
counter 0; không truy ngược được lượng upload lịch sử của phiên đó. Counter không
thay thế hạn mức mạng chống DDoS hoặc dung lượng free trên máy chủ.

Quy trình thay thế:

1. Kiểm quyền/trạng thái, slot và ngân sách input; kiểm cả hai ảnh trước QR/OCR.
2. Kiểm ngân sách gồm input + canonical, chạy OCR rồi ghi hai tên file mới riêng.
3. Cập nhật snapshot, counter trong cùng transaction. Không ghi đè ảnh đã commit.
4. DB commit thành công mới dọn **đúng cặp ảnh cũ đã biết**. Không glob mọi file
   để tránh xóa ảnh một request khác đang ghi sau khi lấy được khóa.
5. Ghi/commit thất bại dọn chỉ các tên file mới của request, giữ nguyên cặp cũ.

`FileChanges` gắn với transaction DB, theo dõi cả media ký nên rollback không để
lại bản ghi mới không được DB chấp nhận. Callback sau commit không được đổi một
HTTP success đã commit thành lỗi retry.

## Giới hạn vận hành

Nếu OS từ chối xóa sau commit, lỗi được ghi bằng mã chung `upload_cleanup_deferred`,
không chứa dữ liệu cá nhân. File còn lại được dọn theo TTL của phiên; chưa có
outbox/janitor bền vững thử lại ngay từng file. Kill tiến trình giữa ghi file và
commit cũng có thể để file mồ côi tới cleanup TTL. Ngân sách cộng dồn và trần lượt
giới hạn các lượt thành công, không thay thế kiểm đĩa/proxy hoặc quản lý crash.

Không tự xóa/migrate kho đã triển khai. Không thay đổi retention review ở task này;
việc làm TTL hữu hạn cho profile eKYC mới thuộc SEC-06. Mọi claim về đầu vào ML/OCR
cần được nghiệm thu trên dữ liệu/thiết bị của nhóm khi hoàn tất tích hợp.
