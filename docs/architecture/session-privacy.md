# Riêng tư dữ liệu phiên — SEC-01

Opt-in mã hóa dữ liệu phiên eKYC. Mặc định tắt để giữ tương thích kho demo hiện có;
không tự đổi hoặc xóa dữ liệu cũ. Xác thực nhân viên review/forensic nay luôn bắt
buộc theo PLAT-06, độc lập với cờ mã hóa.

## Bật cho kho demo mới

Chạy migration `alembic upgrade head` trong `services/api` với DATABASE_URL đúng
kho dự định dùng. Migration 0003 thêm `session_keys`, `access_events` và trigger
chỉ ghi thêm cho access audit trên SQLite/PostgreSQL. Không chạy downgrade trên
kho có nhật ký cần giữ.

Đặt `SESSION_PRIVACY=true`, `SESSION_MASTER_KEY` là base64 chuẩn của **32 byte
ngẫu nhiên**, `STAFF_ACCESS_TOKENS` là JSON `{ "<token ngẫu nhiên ít nhất 32 byte>":
"<mã nhân viên>" }`. Giữ bí mật trong cấu hình máy, không Git, URL, log hay frontend
public env. Khóa master độc lập với khóa token phiên và HMAC định danh. Khi thiếu,
sai khóa, sai tag hoặc cấu hình thì lỗi rõ ràng, không ghi/đọc dữ liệu dạng rõ thay thế.
Nhân viên dùng `Authorization: Bearer <staff token>`, khác token người dân.

Dùng DATABASE_URL/MEDIA_DIR mới hoặc có kế hoạch chuyển đổi dữ liệu trước khi bật.
Snapshot/media cũ dạng rõ bị từ chối ở chế độ riêng tư, không được xem là đã mã hóa.
Kho demo phải dùng cùng master key giữa các worker và sau restart. Đổi master
key chưa có quy trình rewrap trong lát cắt này.

## Dữ liệu được bảo vệ

Mỗi phiên có DEK 256 bit ngẫu nhiên; master key AES-GCM bọc DEK và chỉ lưu bản
đã bọc. Mỗi lần mã hóa sinh nonce 96 bit mới. AAD gắn mã phiên và vai trò artifact,
ngăn đổi chéo snapshot, media, kết quả và ghi chú giữa các phiên.
Recipe dùng API [AESGCM của cryptography](https://cryptography.io/en/stable/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM).

- Snapshot phiên, thông tin thẻ/số CCCD cần duyệt, kết quả và bằng chứng ML,
  snapshot ca duyệt và ghi chú nhân viên được mã hóa.
- Ảnh/âm thanh/video phiên lưu ciphertext; tên do server cấp. Ảnh JPEG/PNG/WebP
  được áp dụng orientation rồi loại metadata EXIF và mã hóa, không giữ bản gốc.
  Đây có thể là phép mã hóa ảnh lại, cần giữ cấu hình này khi hiệu chỉnh/đánh giá.
- Số điện thoại vẫn chỉ HMAC; số CCCD HMAC để tra cứu. Số CCCD đầy đủ chỉ lưu
  trong snapshot mã hóa khi bật riêng tư, không xuất trong hồ sơ duyệt mặc định.
- Cột tra cứu vẫn có ID, trạng thái, phiên bản mô hình, mốc thời gian, hành động
  và người thao tác; không phải toàn bộ DB được mã hóa. Giám định có vòng đời
  chứng cứ riêng, chưa dùng vault eKYC này.

Native decoder cần đường dẫn: API giải mã tạm trong `MEDIA_DIR/_decoded/lease-*`.
Lease giữ tệp tới khi các job ML thực sự kết thúc, kể cả khi HTTP timeout; sau đó
dọn. Windows retry dọn tối đa 30 giây nếu subprocess còn giữ handle, lỗi được log
bằng mã chung. Không truyền DEK hoặc kết nối DB cho worker.

`MEDIA_DIR` cần quyền truy cập chỉ cho tài khoản chạy API, không được phục vụ
static qua web/reverse proxy và không sao lưu `_decoded`. Nếu tiến trình/máy bị
kill đột ngột, file tạm có thể còn; dọn thư mục lease sau khi đã dừng toàn bộ API/
worker. Chưa có quản lý temp qua crash giữa nhiều worker hoặc chống đọc RAM.

## Nhân viên và nhật ký

Mọi route review và forensic yêu cầu credential nhân viên, kể cả khi tắt riêng
tư hoặc chạy mock. Token sai/thiếu trả 401; cấu hình credential chưa có/sai trả
503. Không nhận actor từ header client. Đây là credential demo cấu hình theo
người, chưa phải SSO/RBAC/MFA. Chi tiết giới hạn/cấu hình:
[`services/api/README.md`](../../services/api/README.md#truy-cập-nhân-viên-plat-06).

Hồ sơ `/cases/{id}` vẫn không có điểm AI; ý kiến AI vẫn cần quyết định ban đầu.
Hai endpoint thêm cho người làm UI, không thay UI trong PR:

| Endpoint sau `/v1/review` | Dữ liệu |
|---|---|
| `GET /cases/{id}/identity` | CCCD còn ba số cuối; ngày sinh chỉ năm |
| `POST /cases/{id}/identity/reveal` | Thông tin đầy đủ, ghi sự kiện `identity_revealed` |

Cả hai chỉ hoạt động khi bật riêng tư và có credential nhân viên. Schema mới
`ReviewIdentity`; type web sinh lại từ OpenAPI. Không tự suy ra CCCD đầy đủ nếu
phiên cũ chưa có. Response review có `Cache-Control: no-store`.

Danh sách/xem hồ sơ/xem AI/mở thông tin đều ghi actor, thời gian và hành động vào
chuỗi `access_events` theo phiên, không ghi PII vào audit. Khóa hàng phiên và
UNIQUE(scope, prev_hash) ngăn rẽ nhánh; trigger chặn UPDATE/DELETE. Truy cập thành
công và sự kiện commit trong cùng transaction trước khi gửi phản hồi. Request
bị từ chối/rollback chưa có audit riêng; không coi đây là log an ninh toàn diện.
Chuỗi băm không chống được quản trị viên DB gỡ trigger/viết lại toàn bộ hoặc cắt
đuôi nếu không có neo ngoài. Nhật ký quyết định review cũ vẫn giữ chuỗi riêng.

## Hết hạn

Cleanup TTL xóa media và hủy wrapped DEK, giữ tombstone `destroyed_at`; không tạo
lại khóa cho ID đã hủy. Ciphertext còn trong snapshot/audit không giải mã lại
được bằng trạng thái kho khóa hiện hành. Hồ sơ hết hạn trả 410; danh sách vẫn có
metadata để tra cứu, không giải mã nội dung đã hết hạn.

Giữ bản sao DB/wrapped DEK hoặc master key trong backup có thể phục hồi dữ liệu;
muốn xóa thật trên toàn hệ thống phải quản lý vòng đời backup/khóa ngoài riêng.
Python không bảo đảm xóa sạch mọi bản sao byte trong RAM. Đây là tính năng demo,
chưa phải chứng nhận tuân thủ hoặc KMS/HSM cho triển khai thương mại.
