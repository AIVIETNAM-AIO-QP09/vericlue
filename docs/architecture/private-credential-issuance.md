# Cấp chứng nhận BBS từ quyết định phiên — LIVE-05

Lát cắt backend sau PR #96: API cấp credential ngắn hạn từ quyết định đã commit,
worker Node ký BBS thật, SDK holder tạo proof che account/device/result ID. Không
đổi UI, không mở chốt real/mixed/account-bound mock, không xác nhận tuổi từ OCR.

## Điều kiện cấp

`SignedResultService.issue` là cổng điều kiện duy nhất đang có: real, riêng tư,
reauth/recovery đã pass, đủ module/gate/nonce media/L0 hoặc recovery receipt,
chưa qua review, quyết định cuối khớp snapshot, tài khoản/thiết bị còn hiện hành,
media chưa xóa và kết quả chưa hết hạn. Chứng nhận không nhận kết quả hay claims
do HTTP client tự khai. Phải có cấu hình kết quả Ed25519 hiện có để dùng cổng này.

Đường HTTP tạo pass sinh trắc thật hiện vẫn bị khóa; test dựng quyết định lịch sử
tổng hợp ở server, không có endpoint bỏ cổng. Ký/proof hợp lệ chỉ chứng minh
server đã cấp thuộc tính, không chứng minh AI đúng, camera thật hoặc danh tính pháp lý.

## Cấu hình opt-in

Node/package cài riêng, không tự tải dependency trong request. Áp migration 0007
bằng quy trình Alembic hiện có. Tạo khóa BBS riêng (không dùng khóa report/result):

```powershell
cd services/credentials
npm ci --ignore-scripts
node keygen.mjs --out ../../secrets/private-credentials/bbs.json
```

Lệnh giữ nguyên bộ khóa hợp lệ đã có, không ghi đè hoặc tự sửa `.env`. POSIX
directory 0700/file 0600; Windows giữ ACL cho đúng tài khoản chạy API. Không
commit/chia sẻ file JSON bí mật. Cấu hình đường dẫn tuyệt đối theo máy chạy:

```dotenv
PRIVATE_CREDENTIALS=true
CREDENTIAL_NODE=/absolute/path/to/node
CREDENTIAL_WORKER_FILE=/absolute/path/to/services/credentials/issuer-worker.mjs
CREDENTIAL_SIGNING_KEY_FILE=/absolute/path/to/secrets/private-credentials/bbs.json
CREDENTIAL_TIMEOUT_SECONDS=4
```

Thiếu/sai cấu hình trả 503, không tự sinh khóa hoặc chuyển sang mock. Docker cần
mount package đã cài và `packages/contracts/` đúng cây thư mục; không có runtime
Node BBS trong image API hiện hành. Không quảng cáo chỉ bật cờ là eKYC thật chạy.

## Giao thức

1. Holder dùng `prepareHolder()` tạo commitment có proof. Secret/prover nym/blind
   ở holder; server không nhận. Không tái dùng secret lab cho phiên thật.
2. `POST /v1/sessions/{id}/credential-authorization`, bearer đúng phiên, body
   `{commitment, consent:true}`. Backend kiểm cổng điều kiện rồi trả đúng byte
   `message` base64, algorithm ES256-DER và hạn Unix.
3. Client kiểm message khớp session/result/account/device, commitment hash, issuer
   key ID, expiry và consent đang chấp thuận; ký **nguyên byte** bằng khóa P-256
   đã ghi danh. Chưa có màn consent/ví hoặc logic ký mới trong app ở PR này.
4. `POST /v1/sessions/{id}/credential`, cùng body thêm `device_signature` (base64
   DER). Server kiểm lại điều kiện và khóa thiết bị hiện hành, không dùng public
   key client gửi. Chữ ký L0/media không thay được chữ ký domain cấp credential.
5. Worker nội bộ nhận claims do server dựng và commitment qua stdin giới hạn;
   đọc khóa BBS riêng, kiểm secret/public khớp, ký mù và trả credential. Child không
   có DB/master/staff token/NODE_OPTIONS, stderr bị chặn, timeout/slot/output có hạn.
6. Server kiểm output khớp claims/key, kiểm lại thời gian, lưu response mã hóa
   bằng SEC-01 cùng transaction. Một session chỉ nhận một commitment. Cùng
   commitment và chữ ký đúng trả lại nguyên credential, không gọi signer lại;
   commitment khác bị từ chối. Lỗi/rollback không giữ lượt, retry còn được.

PostgreSQL giữ khóa session/account hiện có. Riêng POST cấp credential trên
SQLite lấy BEGIN IMMEDIATE trước khi đọc snapshot, để tránh ký từ trạng thái
thiết bị/quyết định cũ hoặc hai lượt tranh nhau. Nó serialize ghi trên SQLite;
demo cần song song nên dùng PostgreSQL. Các route khác giữ cách giao dịch cũ.

Authorization message domain `vericlue-credential-authorization-v1` ký context
session/result/account/device/offer SHA-256/BBS key ID/expiry/consent. Nó xác nhận
quyền giữ khóa thiết bị, chưa phải xác nhận ý chí người dùng nếu thiếu UI consent.
Không có server signing oracle nhận claims client.

`GET /v1/credential-signing-key` đọc khóa công khai mà không DB/model startup.
Key ID = SHA-256 byte public BLS12-381 (96 byte), không SPKI. Bên nhận phải pin
key ngoài artifact; không tin một khóa chỉ vì nó được gửi cùng credential.
Thành công có `Cache-Control: no-store`.

## Profile và hạn

Schema `credential.schema.json`, khác `private_credential.schema.json` của lab.
Header/domain `vericlue-private-verification-v1`, assurance `server-decision`.
11 claim theo thứ tự cố định: protocol, issuer, assurance, verification_completed,
valid_from, valid_until, policy_version, source_result_id, account_id, device_id,
source_purpose. Bảy claim đầu được tiết lộ; bốn claim sau và holder secrets ẩn.
Không có CCCD, tên, tuổi, transcript, vector, điểm hoặc video.

Hạn lấy từ kết quả phiên tối đa 60 giây, làm tròn **xuống** tới cohort 10 giây;
không kéo dài hạn nguồn. Nếu không còn khoảng hợp lệ thì từ chối cấp. Thời gian
cohort giảm độ chi tiết metadata, không bảo đảm ẩn danh. Credential hết hạn dù
DB/key vẫn còn; nonce verifier vẫn RAM và dành cho một process như bản lab.
`VerificationVerifier` pin issuer/key/origin, kiểm thời gian trước/sau crypto,
nonce một lần; chưa có HTTP verifier nhiều worker hoặc thu hồi từng credential.

Bảng `credential_issuances` PK session giữ hash offer, issuer key ID, expiry và
payload **mã hóa**; purpose AAD gắn session/offer/key. Không lưu holder secret.
Payload giữ theo khóa phiên/retention hiện có, không tự quảng cáo xóa byte đúng
giây credential hết hạn. Khi khóa phiên bị hủy, payload không đọc lại được.
Offline proof đã cấp còn kiểm được tới valid_until sau khi thiết bị bị thay;
nghiệp vụ cần thu hồi tức thời phải có dịch vụ trạng thái riêng.

## Kiểm chứng

- Node: lab cũ và profile server, chống dùng chéo, keygen idempotent, native worker.
- API: bearer + device signature, source guards, claims injection, cache mã hóa,
  đổi offer, worker lỗi, rollback và không cấp lại sau đổi quyết định.
- Native opt-in `TEST_CREDENTIAL_NODE` chạy HTTP → Python → Node BBS → holder proof
  thật cho reauth/recovery; chỉ quyết định sinh trắc là fixture server tổng hợp.
- PostgreSQL CI kiểm rollback và hai retry đồng thời ra cùng một credential.
- SDK web chỉ vận chuyển body/chữ ký đã có; UI/app do người phụ trách giao diện làm.
