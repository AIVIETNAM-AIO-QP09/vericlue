# API kiểm chứng BBS với nonce bền vững — LIVE-05

Sau PR #97, bên tích hợp có API kiểm proof của profile `server-decision`. Nonce
lưu PostgreSQL/SQLite nên restart hoặc đổi worker không khôi phục lượt đã dùng.
Không sửa UI, không thêm thuộc tính tuổi, không mở chốt sinh trắc thật.

## Ranh giới

- Bên tích hợp gọi bằng credential server-to-server riêng. Token ánh xạ tới
  một **HTTPS origin chuẩn** do người vận hành cấu hình. Không lấy audience,
  policy, nonce, issuer hoặc khóa từ client/Origin header.
- Worker kiểm chứng chỉ nhận public key đã pin, không cần khóa bí mật issuer,
  khóa kết quả Ed25519, khóa phiên hoặc holder secrets. Route không gọi khởi tạo
  mô hình. Lifespan của ứng dụng API vẫn theo cấu hình chung hiện có.
- Chỉ chấp nhận profile `vericlue-private-verification-v1`, policy `verified`,
  assurance `server-decision`. Chứng minh server đã cấp thuộc tính; không tự
  chứng minh AI đúng, camera thật hoặc danh tính pháp lý. BBS không phải PQC.

## Cấu hình

Áp migration `0008_credential_challenges`. Cài package Node như phần cấp chứng
nhận; API image hiện chưa đóng gói Node/runtime package. Trên máy issuer, xuất
public key qua công cụ (không ghi đè tệp đã có):

```powershell
node services/credentials/export-public-key.mjs --key-file /absolute/issuer/bbs.json --out /absolute/export/public-bbs.json
```

Chỉ chuyển **public-bbs.json** sang bên kiểm chứng, kiểm pin qua kênh tin cậy.
Tệp chứa algorithm/key_id/public_key, không secret. Không cho client tự thay pin.
Cấu hình verifier, thay đường dẫn và token bằng giá trị riêng của máy triển khai:

```dotenv
CREDENTIAL_VERIFIER=true
CREDENTIAL_NODE=/absolute/path/to/node
CREDENTIAL_VERIFIER_WORKER_FILE=/absolute/path/to/services/credentials/verifier-worker.mjs
CREDENTIAL_VERIFIER_PUBLIC_KEY_FILE=/absolute/path/to/public-bbs.json
CREDENTIAL_VERIFIER_ISSUER=https://vericlue.example
CREDENTIAL_VERIFIER_TOKENS={"<token-ngau-nhien-it-nhat-32-ky-tu>":"https://service-a.example"}
CREDENTIAL_TIMEOUT_SECONDS=4
```

`CREDENTIAL_VERIFIER_TOKENS` là JSON tối đa 256 token → origin; token 32–512 ký tự
bearer, nên sinh từ ít nhất 32 byte ngẫu nhiên. Giữ ở backend của bên tích hợp,
không đưa vào browser, ví, app hoặc biến NEXT_PUBLIC. Không dùng token staff hoặc
token phiên. Có thể nhiều token cho cùng origin khi chuyển khóa. Thiếu cấu hình,
pin sai shape/hash hoặc worker lỗi trả 503; sai quyền trả 401 trước body/DB/crypto.
Thiết lập này độc lập với `PRIVATE_CREDENTIALS`; chỉ kiểm proof không cần bật cấp.

## Luồng cho bên tích hợp

1. Backend dịch vụ gọi `POST /v1/credentials/challenges`, bearer tích hợp, body
   `{}`. Kết quả có id, nonce, audience, format `bbs-nym`, policy `verified` và
   issued_at/expires_at Unix. Chuyển challenge tới holder, không chuyển token.
2. Holder pin issuer/public key, dùng `presentVerification(publicKey, credential,
   holder, challenge)` tạo proof. Không gửi credential gốc hoặc holder secret
   tới dịch vụ. Phần ví/consent/client giao diện vẫn chưa được tích hợp.
3. Backend dịch vụ chuyển presentation tới `POST /v1/credentials/verify` bằng
   credential của chính mình. HTTP 200 có `valid:false`, hoặc `valid:true` cùng
   assurance, bảy claim công khai và bí danh theo origin. HTTP 503 không có kết
   luận; không được suy thành đạt. Mọi response ở hai route có `no-store`.

Không lộ account/device/source result ID, tên, CCCD, media hoặc điểm AI trong
proof. Bí danh giúp liên kết trong cùng dịch vụ; metadata/traffic vẫn có thể
cho phép tương quan. Không hứa ẩn danh hoàn toàn hoặc không thể chuyển nhượng
nếu holder tự chia sẻ cả credential và toàn bộ secrets.

## Giao dịch và dùng một lần

- Challenge sống tối đa 60 giây. DB chỉ giữ challenge, origin, issuer, key ID,
  nonce và thời gian; không lưu proof, pseudonym hoặc dữ liệu sinh trắc.
- PostgreSQL khóa hàng xuyên suốt kiểm proof; SQLite dùng BEGIN IMMEDIATE.
  Chỉ sau crypto hợp lệ và kiểm lại thời hạn mới xóa hàng, rồi commit trước khi
  gửi thành công (`Depends(..., scope="function")`). Hai worker dùng cùng DB
  chỉ có một lượt thành công. PostgreSQL phù hợp khi cần song song.
- Proof sai không tiêu thụ lượt. Worker/DB lỗi rollback, có thể thử lại khi còn
  hạn. Sau commit thành công mà mất response mạng, thử lại trả `valid:false`;
  bên tích hợp phải xin challenge mới. Không có receipt thành công idempotent.
- Tối đa 128 challenge còn hạn cho mỗi origin, khóa advisory transaction theo
  origin trên PostgreSQL để giữ giới hạn qua nhiều worker; SQLite khóa ghi.
  Tạo challenge mới dọn các hàng hết hạn, không đẩy lượt còn hạn khỏi quota.
- Body verifier tối đa 8 KiB kể cả stream; worker input 4 KiB, output 8 KiB,
  deadline/slot dùng chung với worker cấp. Đây là giới hạn demo, không là chống DDoS.

## Giới hạn còn lại

`VerificationVerifier` trong SDK/lab vẫn là verifier RAM. HTTP API này dùng DB
riêng và hàm crypto stateless chung; không dùng RAM map làm nguồn nonce.

Verifier tin public pin cấu hình ngoài artifact; Python kiểm shape/hash, Node
kiểm proof bằng thư viện đã pin. Chưa có key discovery/registry hoặc nhiều khóa
cùng lúc. Đổi public pin/issuer làm các challenge đang chờ của pin cũ không còn
hợp lệ. Không có thu hồi từng credential hoặc proof danh tính đang online: một
credential đã cấp vẫn có thể tạo proof mới tới valid_until (tối đa hạn nguồn).
Quản lý khóa dài hạn, ví/consent và nghiệm thu thiết bị vẫn thuộc LIVE-05 đang doing.

## Kiểm chứng

Test native dựng quyết định sinh trắc lịch sử tổng hợp ở server, nhưng dùng thật
P-256/Ed25519/BBS và DB: cấp → holder proof → instance verifier chỉ có public key,
hai audience, sửa claim và replay. Test stub chỉ kiểm ranh giới nghiệp vụ, không
được lấy làm bằng chứng độ chính xác mật mã/AI. CI PostgreSQL kiểm rollback,
hai instance tranh cùng proof và quota challenge cạnh tranh.
