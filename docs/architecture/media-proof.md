# Chữ ký media theo phiên — SEC-02, lát cắt mặt/giọng

API và lớp điều phối Android đã có ký/kiểm media mặt và giọng bằng ECDSA P-256,
SHA-256, signature DER mã hóa base64 chuẩn. Public key là DER SubjectPublicKeyInfo
P-256 base64 chuẩn. Chỉ giữ public key ở server; khóa riêng do Android Keystore
quản lý, không xuất khỏi lớp ký.

Recipe: [Android Keystore](https://developer.android.com/privacy-and-security/keystore),
[cryptography ECDSA](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ec/).
Không chép code thư viện hoặc phụ thuộc giấy phép mới.

## Bật thử

- Chạy migration `0004_media_proof` (`alembic upgrade head`).
- Android build thêm `-Pvericlue.signedMedia=true`. Lớp `LiveFlow` tự dùng
  `AndroidMediaSigner`, xử lý khóa/hash/ký trên Dispatchers.IO, không thay UI.
- Có thể đặt `REQUIRE_MEDIA_PROOF=true` ở API để từ chối mọi phiên không ràng buộc
  public key. Mặc định false giữ tương thích client cũ. Dù cờ server false, một
  phiên đã gửi public key vẫn bắt buộc ký, không tự hạ về unsigned.
- Nên dùng cùng SEC-01 để mã hóa dữ liệu lưu. Public key/nonce không phải bí mật.

Tạo phiên gửi thêm `device_public_key_spki`; server kiểm P-256/SPKI chuẩn, ràng
buộc khóa bất biến trong phiên rồi trả `challenge.media_nonce`. Luồng chưa hỗ trợ
được giữ chặn: public key tự gửi không được cấp `device_verified`, không được
tự đăng ký thành khóa tài khoản, không tạo đường reauth mới. Dynamic real/mixed
vẫn bị chặn như trước. Đường ký chạy được với API mock để hoàn thiện tích hợp.

## Nội dung ký `vericlue-media-v1`

Nội dung là JSON ASCII, khóa sắp xếp tăng dần **ở mọi cấp**, không khoảng trắng
(`json.dumps(sort_keys=True,separators=(",",":"),ensure_ascii=True)`). Các trường:

| Trường | Giá trị server kiểm lại |
|---|---|
| `protocol` | `vericlue-media-v1` |
| `session_id`, `purpose`, `client_nonce` | Snapshot phiên server |
| `challenge_id` | Lượt mặt hiện hành |
| `stage` | `face` hoặc `voice` |
| `attempt_id` | `challenge_id` cho mặt; `voice_challenge_id` hiện hành cho giọng |
| `nonce` | SHA-256 hex của ASCII `media_nonce:stage:attempt_id` |
| `audio_offset_ms` | Số nguyên gửi thật, hoặc JSON null; chỉ có với video giọng |
| `files` | Map role → `{sha256, size, suffix}` của **byte tải lên gốc** |

Role mặt: bắt buộc `image`, tùy chọn `video`. Role giọng: bắt buộc `audio`, tùy
chọn `video`. Suffix chữ thường theo whitelist storage; ngoài danh sách thành
`.bin`. Size là số nguyên byte. Không ký tên/path đầy đủ. Các ID/nonce dùng ASCII;
không đưa thông tin định danh hoặc câu tiếng Việt vào JSON ký.

`media_nonce` là seed ngẫu nhiên 256 bit do server cấp. Nonce suy ra khác nhau
theo stage/lượt; mỗi nonce chỉ được dùng một lần. Làm lại mặt/gia hạn cấp seed và
challenge mới; đọc lại câu đổi voice_challenge_id nên có nonce mới. Không dùng
nonce do client tự chọn làm bằng chứng nguồn ngẫu nhiên server.

Android gửi `media_signature` trong multipart `/media` và `/voice`. Server tự
hash mọi role, kiểm session/challenge/token/hạn và signature **trước ghi tệp**.
Hash tính trước loại EXIF/mã hóa SEC-01. Thay nội dung, thêm/bớt video, đổi suffix
hoặc offset làm signature không hợp lệ. Không nhận hash/manifest do client khai
thay cho việc hash byte thật.

Sau kiểm signature, server claim `media_proof_uses.nonce_hash` bằng ràng buộc PK
trong DB. Claim và nhận media cùng transaction, rollback nếu ghi thất bại. Finalize/
voice kiểm lại đã có claim đúng lượt/khóa, để phiên cũ hoặc thay đổi cấu hình
không bỏ qua kiểm upload. Lặp endpoint vẫn giữ lỗi `step_already_received` để
client xử lý trường hợp mất phản hồi, không chạy lại hoặc ghi đè media.

## Kiểm thử và giới hạn

Mẫu chung `packages/contracts/test-vectors/media-proof-v1.json` chứa canonical JSON,
hash, public key và signature bằng khóa tạm **đã bỏ**, không có private key/media
người thật. Python/Kotlin cùng kiểm byte và signature này. Test API dùng khóa
sinh trong RAM và media tổng hợp; không tấn công hệ thống bên ngoài.

Chữ ký chỉ chứng minh người giữ khóa phiên đã ký đúng byte; chưa chứng minh camera
thật, thiết bị không root/hook, hardware-backed key hay người ký đúng danh tính.
Android Keystore thật chưa được nghiệm thu trên điện thoại. Chưa ký CCCD/signals
hoặc kết quả trả bên tích hợp. Đăng ký khóa gắn tài khoản, L0 reauth, thu hồi/đổi
thiết bị và mẫu mặt mã hóa còn phần tiếp theo của SEC-02/FLOW-05. Không coi lát cắt
này là hoàn tất toàn bộ xác thực thiết bị hoặc hệ thống chống phát lại.
