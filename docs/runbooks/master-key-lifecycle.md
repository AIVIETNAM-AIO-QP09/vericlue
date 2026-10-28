# Vòng đời master key và kiểm kê tệp tạm

Công cụ SEC-08 dành cho người vận hành kho demo đã bật `SESSION_PRIVACY`.
Chỉ chạy khi có quyền quản trị kho và bản sao lưu; nhóm phát triển chỉ kiểm thử
trên SQLite đã migration với dữ liệu tổng hợp. Không có lần đổi khóa nào trên
kho thật được thực hiện trong task này.

## Phạm vi

`scripts/rotate_master_keys.py` mở DEK bằng master cũ rồi bọc lại bằng master
mới, giữ nguyên định dạng AES-GCM/AAD của `SessionKeyRow` và `AccountRow`.
Không giải mã ảnh, âm thanh, video, snapshot hay thông tin định danh. Payload
đã mã hóa giữ nguyên; DEK đã hủy không được khôi phục. Mọi hàng đang hoạt động
phải mở được trước khi giao dịch được commit; một hàng lỗi làm rollback toàn bộ.

Đây không phải công cụ chuyển đổi dữ liệu rõ cũ, kiểm tra toàn vẹn mọi media,
đổi khóa HMAC/token/chữ ký/BBS hay quản lý KMS. Fingerprint là nhãn SHA-256 có
miền riêng để đối chiếu khóa, không phải bằng chứng về danh tính người vận hành.
Python không bảo đảm xóa sạch mọi bản sao khóa trong RAM.

## Chuẩn bị và quyền truy cập

1. Chọn cửa sổ bảo trì. Dừng **tất cả** API, worker, tác vụ retention/cleanup và
   công cụ khác có thể đọc hoặc ghi kho; tắt cơ chế tự khởi động lại. Người vận
   hành phải kiểm tra cả các máy/container khác. Cờ xác nhận trong CLI chỉ ghi
   nhận lời xác nhận này, không chứng minh dịch vụ đã dừng.
2. Tạo bản sao lưu nhất quán của DB và kho media. Kiểm tra quy trình phục hồi
   trên bản sao cô lập. Giữ bản sao cấu hình hiện hành và master cũ trong kho
   bí mật riêng, hạn chế quyền truy cập; không đưa khóa vào cùng gói backup DB.
3. Cấp khóa mới độc lập: đúng 32 byte ngẫu nhiên, mã hóa base64 chuẩn. Công cụ
   không sinh khóa, không sửa `.env`, không ghi đè tệp khóa. Tránh đặt giá trị
   khóa trong tham số dòng lệnh, lịch sử shell, log hoặc tệp thuộc Git.
4. Chỉ tài khoản vận hành cần thiết được đọc tệp khóa, biến môi trường tiến
   trình, DB và media. Dùng ACL Windows hoặc quyền thư mục/tệp riêng trên Unix;
   kiểm tra quyền của thư mục cha, backup và thư mục tạm. Không bật SQL echo
   hay ghi toàn bộ môi trường vào log. Biến môi trường vẫn có thể bị tài khoản
   cùng quyền hoặc quản trị máy đọc; không xem đây là kho bí mật chuyên dụng.

SQLite: chỉ dùng tệp đã có, dịch vụ đã dừng và không còn tệp `-wal`, `-shm`,
`-journal`. CLI từ chối các sidecar này để tránh bỏ qua dữ liệu chưa checkpoint.
Checkpoint/backup bằng quy trình SQLite đúng trước đó; **không tự xóa sidecar**.
Dry-run mở SQLite ở chế độ chỉ đọc; apply mở tệp hiện có, không tạo DB mới.

PostgreSQL: apply lấy khóa `EXCLUSIVE` trên `session_keys` và `accounts`, chờ tối
đa 5 giây để lấy khóa. Tài khoản DB cần quyền đọc/cập nhật và khóa các bảng này.
Khóa giao dịch chặn ghi trong lúc chạy; nó không ngăn một worker còn sống ghi
bằng master cũ sau commit. Đường khóa PostgreSQL có trong code nhưng chưa được
kiểm chứng với một PostgreSQL đang chạy trong task này.

## Dry-run và apply

Chạy từ checkout đã cài phụ thuộc API, dùng Python của môi trường dự án.
`ROTATION_DB_URL` chứa URL kết nối do người vận hành nạp riêng. Hai tệp khóa
chỉ chứa base64 chuẩn của master cũ/mới; đường dẫn dưới đây là ví dụ, không phải
tệp được công cụ tạo. Không sao chép khóa vào câu lệnh.

```powershell
python scripts/rotate_master_keys.py --database-env ROTATION_DB_URL --old-master-file D:/Private/old-master.key --new-master-file D:/Private/new-master.key --dry-run
```

Cũng có thể thay cặp `--old-master-file`/`--new-master-file` bằng
`--old-master-env ROTATION_OLD_MASTER` và `--new-master-env ROTATION_NEW_MASTER`.
Tham số nhận **tên** biến môi trường, không nhận giá trị khóa. Dry-run là mặc
định khi không chọn chế độ. Kết quả JSON chỉ chứa trạng thái, số lượng,
fingerprint và giới hạn kiểm tra; lỗi trả mã an toàn và exit code 2. Không có
URL DB, đường dẫn tệp, định danh người dùng hoặc khóa trong output.

Đối chiếu fingerprint và số lượng với kế hoạch; kiểm tra lại dịch vụ đã dừng.
Chỉ người vận hành được phép mới chạy:

```powershell
python scripts/rotate_master_keys.py --database-env ROTATION_DB_URL --old-master-file D:/Private/old-master.key --new-master-file D:/Private/new-master.key --apply --confirm-services-stopped
```

Apply diễn ra trong một giao dịch: SQLite dùng `BEGIN IMMEDIATE`; PostgreSQL
dùng khóa bảng nêu trên. Sai khóa/tag hoặc lỗi trước commit giữ nguyên các
envelope. Nếu mất kết nối/tiến trình đúng lúc commit, phía người gọi có thể
không biết giao dịch đã commit hay chưa: **không tự chạy lại hoặc đổi cấu hình
theo phỏng đoán**. Trong khi dịch vụ vẫn dừng, dry-run với master mới làm khóa
nguồn (đảo hai đầu vào) để xác định trạng thái; dry-run này không đổi khóa.
Nếu cả hai hướng đều lỗi, giữ kho cô lập và điều tra/phục hồi từ backup.

Sau khi apply thành công:

1. Người vận hành cập nhật `SESSION_MASTER_KEY` của **tất cả** dịch vụ sang khóa
   mới qua kênh cấu hình bí mật hiện có. Công cụ không thực hiện bước này.
2. Chạy preflight protected profile theo runbook tương ứng, khởi động lại và
   kiểm tra luồng trên tài khoản/dữ liệu tổng hợp được phép sử dụng. Preflight
   cấu hình không chứng minh mọi media cũ giải mã được.
3. Chỉ mở lại lưu lượng khi toàn bộ worker dùng cùng master. Nếu cần quay lại,
   dừng toàn bộ dịch vụ rồi dùng chính công cụ để bọc DEK từ mới về cũ; đổi
   `.env` về cũ đơn thuần sẽ làm mất khả năng mở DEK đã đổi.
4. Ghi lại thời điểm, fingerprint, số lượng và kết quả kiểm tra vào nhật ký
   vận hành có kiểm soát; không ghi khóa hay PII. Xử lý master cũ theo chính sách
   backup và phục hồi được duyệt, không tự xóa khi còn backup phụ thuộc nó.

## Backup và giới hạn xóa

Rewrap kho đang hoạt động không đổi các bản sao DB trước đó. Backup còn DEK
bọc bằng master cũ có thể khôi phục dữ liệu nếu master cũ còn tồn tại. Nếu khóa
cũ bị lộ, rewrap hiện tại không thu hồi được dữ liệu mà kẻ khác đã sao chép.
Phải quản lý riêng thời hạn giữ backup, quyền truy cập, bản sao ngoại tuyến,
restore và lịch hủy khóa. Crypto-shred ở kho hiện tại không đồng nghĩa đã xóa
mọi bản sao, log, snapshot máy ảo hoặc backup. Task này không xác minh việc
xóa ở hạ tầng bên ngoài.

## Kiểm kê tệp tạm

```powershell
python scripts/inspect_private_temp.py --media-dir-env MEDIA_DIR
```

Công cụ chỉ đọc cấu trúc `MEDIA_DIR/_decoded`, đếm thư mục `lease-*`, tệp và
tổng dung lượng logic; không đọc nội dung, không in tên/đường dẫn, không xóa.
Nó từ chối symlink/junction hoặc đường dẫn thoát khỏi phạm vi, giới hạn 10.000
entry để tránh duyệt không giới hạn. Entry ngoài mẫu được đếm riêng và giữ
nguyên. Dùng thư mục riêng có ACL hạn chế; tránh để tiến trình không tin cậy
đổi cây thư mục trong khi kiểm kê.

`candidate_leases` không có nghĩa là orphan: hiện chưa có sổ lease bền vững
chứng minh tiến trình nào còn dùng tệp. Vì vậy chưa cung cấp lệnh tự xóa.
Khi cần dọn sau sự cố, dừng và kiểm tra mọi dịch vụ trước, đối chiếu đường dẫn
chuẩn đúng `_decoded` của cấu hình rồi áp dụng quy trình quản trị tệp được duyệt.
Không xóa `MEDIA_DIR` hay các vùng ngoài `_decoded`; không xóa theo danh sách
đường dẫn chưa được kiểm tra. Tệp tạm cần được loại khỏi backup thông thường.
Việc dọn file khi lease còn hoạt động và việc xóa an toàn trên SSD/backup chưa
được công cụ này bảo đảm.
