# Chứng nhận riêng tư — LIVE-05

Đóng gói/chạy trên máy demo: [runbook BBS](../../docs/runbooks/bbs-demo.md).
`node runtime-check.mjs` kiểm runtime bằng vector công khai, không cấp credential;
có tùy chọn kiểm private/public key theo cấu hình triển khai mà không in bí mật.

Sau PR #101 có `createVerificationSession` điều phối authorization/cấp qua callback,
giữ nguyên yêu cầu khi thử lại, timeout/cancel và bỏ phản hồi đến muộn. Có kiểm
Chromium → HTTP FastAPI → worker BBS thật cho reauth/recovery bằng fixture nguồn
tổng hợp; không có UI, Android hoặc nghiệm thu sinh trắc. Xem hướng dẫn SDK bên dưới.

Sau PR #100 có SDK holder trình duyệt không UI: kiểm nguồn Ed25519 và context
trước khi ký P-256, ví RAM và BBS proof theo consent/origin. Build bằng
`npm run build:holder`; kiểm Chromium bằng `npm run test:holder` (cần Playwright
từ apps/web). Phân phối cả bundle, type và license trong dist. Xem
[hướng dẫn SDK](../../docs/architecture/private-credential-holder.md).

Sau PR #96 có thêm profile server-decision, `issuer-worker.mjs` nội bộ và
`keygen.mjs --out ...` tạo khóa BBS riêng. Không dùng persona demo để cấp thật.
Holder dùng `prepareHolder` rồi `presentVerification`; bên nhận pin key/issuer
và dùng `VerificationVerifier`. API, khóa thiết bị ký chấp thuận và giới hạn:
[hướng dẫn tích hợp](../../docs/architecture/private-credential-issuance.md).

Sau PR #97 có `verifier-worker.mjs` chỉ nhận public key, dùng chung crypto stateless
với verifier RAM. API lưu nonce DB để kiểm qua nhiều worker/restart; xuất pin bằng
`export-public-key.mjs`. Xem [API verifier](../../docs/architecture/private-credential-verifier.md).

Bản thử nghiệm mật mã độc lập: issuer cấp credential tổng hợp, holder chỉ tiết
lộ claim cần thiết, hai verifier kiểm proof với khóa issuer đã pin. Không kết
nối luồng công dân, không cấp credential từ kết quả eKYC thật, không sửa UI.

## Chạy

Cần Node.js 22.13+ (nhánh 22) hoặc 24+, npm, không GPU/model/mạng lúc chạy demo.

```powershell
cd services/credentials
npm ci --ignore-scripts
npm run lint
npm run format:check
npm test
npm run demo -- --runs 20
```

`node cli.mjs --help` có hướng dẫn. Muốn lưu số liệu, từ gốc repo:

```powershell
node services/credentials/cli.mjs demo --runs 20 > tmp/private-credentials-demo.json
```

Output chỉ gồm số đo, số lần, metadata máy/commit/phụ thuộc và giới hạn. Không
in khóa, credential, proof hay PII. Khóa issuer/holder ngẫu nhiên chỉ trong RAM;
không lưu credential. `code_dirty=true`/commit unknown phải được giữ nguyên khi
trích số liệu. Trên Windows dùng thư mục `tmp` đã tồn tại và lưu UTF-8 nếu cần.

## Luồng

```mermaid
sequenceDiagram
    participant H as Holder
    participant I as Issuer demo
    participant V as Verifier dịch vụ
    H->>H: Secret + prover nym + blinding (RAM)
    H->>I: Commitment có proof, không secret
    I->>H: Blind signature + claim tổng hợp + signer entropy
    V->>H: Nonce, audience, policy, thời hạn
    H->>H: Kiểm chữ ký và tạo proof
    H->>V: Claim được tiết lộ + proof + bí danh theo audience
    V->>V: Kiểm schema/key/context/policy/hạn; tiêu thụ nonce
```

Hợp đồng lab: `packages/contracts/schemas/private_credential.schema.json`;
profile server-decision/holder dùng `credential.schema.json` và `result.schema.json`.
AJV kiểm ở từng vai trò. Giao tiếp thử nghiệm được serialize JSON giữa vai trò;
holder secrets không được serialize vào thông điệp gửi issuer/verifier.

## Profile và ranh giới tin cậy

- Profile `vericlue-private-credential-lab-v1`, issuer `vericlue-lab`, assurance
  `synthetic-demo` bắt buộc trong claim và header. Persona chỉ `adult`/`minor`;
  không nhận CCCD/ngày sinh/tên người thật hoặc verdict client.
- Thứ tự 11 claim cố định trong `profile.mjs`. Luôn lộ protocol, issuer,
  assurance, valid_from/until, verified, policy_version; policy adult thêm
  age_over_18. Tên, mã demo và DOB không tới verifier BBS/SD-JWT.
- `verified` chỉ là thuộc tính tổng hợp do demo dựng, không phải kết quả model.
  `age_over_18` được issuer tính từ DOB bằng lịch UTC rồi ký; không phải chứng
  minh bất đẳng thức từ DOB ẩn. Nguồn dữ liệu vẫn cần được kiểm khi tích hợp thật.
- BBS dùng SHA-256/BLS12-381, NymCommit với một committed holder secret và prover
  nym; BlindSignWithNym trộn entropy issuer. Proof cùng chứng minh biết signature,
  các secret tương ứng và nym theo audience. Không đưa public key holder chung
  vào mọi proof. Biết cả credential và toàn bộ secrets vẫn có thể chuyển nhượng.
- Commitment 176 byte, signature 80 byte; proof verifier kiểm đúng số message
  và hidden scalar của profile, giới hạn byte trước tính toán. Không tự viết curve,
  pairing, Fiat-Shamir hoặc RNG. Dùng primitive upstream và CSPRNG Node.
- Thời gian credential theo cohort 300 giây, hết hạn 600 giây từ đầu cohort.
  Không có serial/result ID hoặc thời điểm cấp riêng trong presentation BBS.
- Verifier cấu hình origin HTTPS chính xác và pin key riêng ngoài packet. Nonce
  32 byte, lượt 60 giây, tối đa 128 lượt đang chờ. Challenge lấy từ RAM verifier;
  không tin origin/nonce/key/header do presentation tự khai. Chỉ tiêu thụ sau
  thành công; reserve trước await chống ba request cùng dùng một lượt.
- RAM dùng một process; restart từ chối mọi lượt cũ. Không chia nonce giữa máy/
  worker, không có lưu durable hay thu hồi từng credential. Chưa gắn phần cứng/
  passkey, chưa có transport ví hoặc xác nhận consent ngoài CLI.

## Đối chứng và số đo

JWT+PoP công khai đủ claim; SD-JWT+KB chỉ mở claim được yêu cầu nhưng cùng issuer
JWT vẫn xuất hiện giữa dịch vụ; BBS che signature và dùng proof ngẫu nhiên, nym
ổn định trong một audience, đổi khi audience đổi. Không coi hai chuỗi proof khác
nhau là bằng chứng thực nghiệm đầy đủ của unlinkability; cơ sở là giao thức BBS.
Các thuộc tính lộ ra, issuer key hiếm, IP và metadata vẫn có thể liên kết người dùng.
Nym ổn định theo credential, không chứng minh một người chỉ có một tài khoản.

Demo đo số trường PII hiện diện, byte JSON presentation, thời gian tạo/kiểm kèm
từng mẫu và median; cùng persona và policy, chạy tuần tự trên một máy. Mỗi scheme
dùng cùng credential cho hai dịch vụ; mỗi lần có nonce riêng. Mỗi presentation
được kiểm và thử phát lại. Không có test tập người thật, không đo sức chống deepfake.
Thời gian tạo BBS gồm kiểm credential phía holder; schema/serialization nằm trong
phép đo. Chưa warm-up chuẩn hay kiểm CPU tải, không dùng để suy ra SLA điện thoại.

SD-JWT là profile flat disclosure theo RFC 9901 với salt 128 bit, _sd_alg SHA-256,
KB-JWT ký sd_hash/aud/nonce/iat và context riêng. JSON canonical-only, EdDSA cố định,
không tải JWK qua URL. JWT+PoP là đối chứng riêng, không gọi là giao thức chuẩn mới.
Không nhận library này là triển khai tổng quát RFC/W3C/OpenID4VP.

## Kiểm thử và nguồn

`npm test` dùng mật mã thật, có vector public upstream, sửa byte/claim/key/context,
copy credential thiếu secret, hết hạn, minor/adult, replay và cạnh tranh. Test có
schema ở producer/consumer, không dùng mock signature hay bỏ cổng để lấy kết quả.

`@digitalbazaar/bbs-signatures` 3.1.0 có API nâng cao trong file package nhưng
không export public. `lib/bbs.mjs` resolve entry point rồi import file tương đối
đúng package, không tìm đường dẫn từ request. Lockfile + vector kiểm tương thích;
thay version phải rà lại. Không tuyên bố thư viện/profile đã được audit.

Vector `bbs-nym-public-v1.json` chỉ chứa input xác minh công khai, trích fixture
upstream pin `1d4c1731`; không có SK/secret holder. Attribution và license ở
`third_party/README.md` và `third_party/licenses/bbs-signatures-BSD-3-Clause.txt`.

Thiết kế và việc còn lại: [ADR-0018](../../docs/adr/0018-chung-nhan-rieng-tu-bbs.md).
