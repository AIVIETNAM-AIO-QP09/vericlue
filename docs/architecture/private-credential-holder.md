# Ví BBS trên trình duyệt — LIVE-05

SDK xử lý holder độc lập với giao diện: kiểm kết quả Ed25519, giữ secret trong
RAM, kiểm nội dung trước khi nhờ khóa thiết bị ký và tạo BBS proof cho bên nhận
được người dùng đồng ý. Không có HTTP client, màn hình consent hoặc lưu ví lâu dài.
Backend và các cổng sinh trắc giữ nguyên; SDK không tạo được quyết định pass.

Sau PR #101 có thêm `createVerificationSession`: điều phối gọi API qua callback,
giữ nguyên body để thử lại khi mất phản hồi, giới hạn thời gian và hủy khi logout.

## Build và kiểm thử

```powershell
cd services/credentials
npm ci --ignore-scripts
npm run build:holder
npm test
# Cần npm ci trong apps/web và npx playwright install chromium tại đó trước.
npm run test:holder
```

Phân phối cùng `dist/holder.mjs`, `dist/holder.d.mts` và `dist/LICENSES.txt`.
Không commit bundle sinh ra. Build dùng BBS 3.1.0 đã pin, adapter Web Crypto chính
thức và AJV biên dịch trước từ hợp đồng; không cần Buffer, Node hoặc eval ở runtime.
Chỉ dùng secure context có Web Crypto Ed25519, SHA-256, ECDSA P-256 và CSPRNG;
không hỗ trợ thì từ chối, không hạ xuống Math.random hay chữ ký giả.

## Trình tự tích hợp cho người phụ trách giao diện

1. Ứng dụng lấy kết quả phiên có chữ ký qua luồng hiện có. Cung cấp hai public pin
   Ed25519/BBS đã xác thực qua cấu hình hoặc kênh tin cậy. Không tin khóa chỉ vì
   nó đi cùng artifact; fingerprint khớp chỉ chứng minh tính nhất quán của khóa.
2. Tạo `expected` từ phiên/tài khoản/thiết bị ứng dụng đang làm việc: issuer,
   audience của kết quả nguồn, session_id, nonce, purpose, account_id, device_id.
   Không lấy expected bằng cách giải mã chính kết quả đang cần kiểm tra.
3. `createVerificationWallet` kiểm chữ ký, payload canonical, đủ bảy trường
   context, status pass và hạn nguồn tối đa 60 giây. Credential làm tròn xuống
   theo cohort 10 giây; không dùng toàn bộ hạn nếu kết quả đến sát thời điểm hết hạn.
4. Hiển thị đề nghị cấp credential và chờ người dùng đồng ý. Khi đã đồng ý,
   `prepare({consent:true})` sinh commitment; gửi nguyên body tới
   `POST /v1/sessions/{id}/credential-authorization` bằng bearer của phiên.
5. `authorize(response, signDevice)` so chính xác byte authorization với
   session/result/account/device, commitment hash, BBS key ID, hạn và consent.
   Chỉ sau khi khớp mới gọi callback ký bằng **khóa P-256 đã ghi danh**. SDK trả
   body `{commitment, consent:true, device_signature}` để POST `/credential`.
6. `accept(credential)` kiểm toàn bộ claim, key ID và blind signature gắn đúng
   secret của ví trước khi giữ credential. Lỗi mạng sau authorize có thể gửi lại
   cùng body khi còn hạn; backend đã có idempotency. Không tạo ví/offer mới để
   thay commitment đã cấp trong cùng phiên.
7. Bên nhận lấy challenge từ HTTP verifier bằng credential tích hợp riêng trên
   **server của bên nhận**, có thể chọn key_id đã pin của credential khi xoay key.
   Chuyển challenge tới holder qua transport của ứng dụng. SDK không nhận hoặc
   lưu token tích hợp server-to-server. Audience của kết quả nguồn và origin
   HTTPS của verifier là hai context khác nhau.
8. Hiển thị bên nhận và các claim sẽ tiết lộ, chờ đồng ý riêng mỗi lần xuất trình.
   Gọi `present(challenge, {audience: approvedOrigin, consent:true})`, gửi proof
   tới server bên nhận để gọi `/v1/credentials/verify`. approvedOrigin lấy từ
   lựa chọn/kết nối đã tin cậy của ứng dụng; không tự chép từ challenge chưa kiểm.
9. Khi đăng xuất, chuyển tài khoản hoặc hủy luồng, gọi `destroy()` và bỏ mọi bản
   sao response/body ứng dụng đang giữ. Không log/persist credential hay payload nguồn.

Ví dụ dưới đây dùng adapter HTTP của ứng dụng, không phải export của SDK:

```javascript
import {createVerificationWallet, webCryptoP256Signer} from './holder.mjs';

const wallet = await createVerificationWallet({
  result: signedResult,
  resultKey: trustedResultPin,
  credentialKey: trustedBbsPin,
  expected: currentSessionContext,
});
// Chỉ chạy sau khi giao diện đã nhận được đồng ý cấp credential.
const offer = await wallet.prepare({consent: true});
const authorization = await api.credentialAuthorization(sessionId, offer);
const request = await wallet.authorize(authorization, webCryptoP256Signer(enrolledDeviceKey));
await wallet.accept(await api.issueCredential(sessionId, request));
// Chỉ chạy sau khi người dùng đồng ý với đúng bên nhận này.
const proof = await wallet.present(verifierChallenge, {
  audience: approvedOrigin,
  consent: true,
});
// Khi kết thúc luồng, kể cả khi HTTP lỗi, ứng dụng gọi wallet.destroy().
```

`webCryptoP256Signer` yêu cầu private CryptoKey non-extractable, P-256 và có quyền
sign; chuyển chữ ký raw Web Crypto thành ASN.1 DER cho API. Không tạo khóa đăng ký
mới. Native/WebView có thể cấp callback trả DER từ khóa đã ghi danh nhưng bridge
Android và kiểm thử thiết bị thật chưa được triển khai trong SDK này.

## Trạng thái và giới hạn

`ready → prepared → authorized → issued → closed`. Một phép toán mật mã mỗi lần;
gọi đồng thời trả `holder_busy`. Có thể thử lại authorize/accept khi dữ liệu lỗi
mà ví còn hạn. Mọi thao tác kiểm thời gian trước/sau await. Logout hoặc hết hạn
trong lúc ký/tạo proof khiến kết quả bị loại; không hủy được phép tính đang chạy.
`metadata()` chỉ trả trạng thái và hạn, không xuất secret/credential; nó không tự
chuyển trạng thái theo đồng hồ khi không có thao tác. Hết hạn được chặn khi thao tác.

Secret không vào localStorage/IndexedDB, không có export/import/backup; reload mất
ví và phải bắt đầu phiên mới nếu commitment đã được cấp. `destroy` bỏ tham chiếu,
ghi đè byte secret theo khả năng JS; không bảo đảm xóa BigInt/GC hoặc khóa phần cứng.
Không chống được script độc hại chạy cùng origin/XSS. Boolean consent là điều kiện
SDK, **không chứng minh đã có ý chí người dùng** nếu giao diện tự truyền true.

Proof chỉ lộ bảy claim chung và bí danh theo origin; che result/account/device/
purpose/secret/signature. Bí danh ổn định theo credential và origin, không phải
mã định danh toàn đời. Issuer key, claim chung, IP và transport vẫn có thể liên kết.
Không có tuổi, range proof, FIDO, PQC, bảo đảm camera thật hoặc độ chính xác AI.

## Bằng chứng kiểm thử

Chromium thực chạy bundle dưới CSP `script-src 'self'; connect-src 'none'`, không
eval/polyfill Buffer hoặc tải tài nguyên ngoài. Vector public chứa **claim tổng
hợp** được Python ResultSigner ký; Python kiểm lại chữ ký, Chromium kiểm nguồn và
ký P-256, issuer/verifier Node dùng BBS thật. Có test khác context/khóa/chữ ký/
consent, credential ví khác, replay, hết hạn, logout trong lúc chờ ký/tạo proof,
giới hạn đồng thời và không ghi storage.

Các bài trên kiểm tương thích thành phần. Có thêm kiểm HTTP xuyên suốt bên dưới;
chưa nghiệm thu Android/Safari/Firefox hoặc AI thật. Không bật đường pass sinh trắc
thật, không dùng kết quả này làm R1–R7 hoặc số liệu chất lượng mô hình.

## Điều phối cấp credential và thử lại

`createVerificationSession` nhận cùng nguồn/pins/expected như factory wallet,
thêm `signDevice`, `transport.authorize(body, {signal})` và
`transport.issue(body, {signal})`. Hai callback vận chuyển đúng JSON theo schema
tới hai endpoint phiên đã có; bearer/token ở closure của ứng dụng, không trong
proof hoặc thông điệp holder. Đây không phải HTTP client hay API backend mới.

```javascript
const session = await createVerificationSession({
  result: signedResult, resultKey: trustedResultPin,
  credentialKey: trustedBbsPin, expected: currentSessionContext,
  signDevice: webCryptoP256Signer(enrolledDeviceKey),
  transport: {
    authorize: (body, {signal}) => postAuthorization(body, {signal}),
    issue: (body, {signal}) => postCredential(body, {signal}),
  },
});
// Chỉ gọi sau khi người dùng đồng ý. Không tự thử lại hoặc tự cấp khi mở trang.
await session.issue({consent: true});
// Khi lỗi mạng, UI có thể cho người dùng thử lại cùng lệnh trên khi còn hạn.
// Kết thúc/chuyển tài khoản/logout:
session.destroy();
```

- Lỗi trước authorization: giữ nguyên offer, lần thử lại dùng đúng commitment.
- Lỗi sau ký/mất phản hồi cấp: giữ nguyên body đã ký, không ký lại hoặc sinh offer
  mới. Backend quyết định điều kiện và idempotency; SDK không tự trả pass khi lỗi.
- Đã accept: gọi issue lần nữa khi còn hạn chỉ trả metadata, không gọi mạng/ký lại.
- Callback mạng có hạn mặc định 10 giây (cấu hình 1–15.000 ms) và nhận AbortSignal.
  Timeout hủy signal, trả `holder_request_timeout`; có thể thử lại cùng body.
  Không tự retry. Transport phải tôn trọng signal và dùng endpoint/origin đã tin,
  không đi theo redirect mang bearer tới origin khác hoặc ghi log body/token.
- SDK giới hạn từng action; lỗi callback được rút thành `holder_request_failed`.
  Không cho gọi issue/present đồng thời. Consent cấp và consent xuất trình riêng.
- `destroy` trả lỗi cho thao tác đang chờ kể cả callback không phản hồi, bỏ kết quả
  đến muộn và đóng wallet. Abort không đảo được transaction backend đã commit.
  Hết hạn nguồn đóng ví; không timeout ngắn cho hộp thoại ký thiết bị nhưng vẫn
  chặn theo hạn nguồn. GC/xóa bộ nhớ và UI consent giữ giới hạn đã nêu ở trên.

## Kiểm HTTP xuyên suốt

Từ gốc repo, sau khi cài Playwright/Chromium và build SDK:

```powershell
$env:TEST_CREDENTIAL_NODE = (Get-Command node).Source
$env:TEST_CREDENTIAL_BROWSER = 'true'
uv run pytest services/api/tests/test_credential_browser_http.py
```

Test chạy server loopback với API production nguyên bản và harness HTML chỉ có
trong test. Chromium fetch `/result`, ký P-256, gọi authorization/cấp credential,
tạo proof; adapter bên nhận trong process Node gọi HTTP challenge/verify bằng
credential server-to-server. Verifier token không truyền vào page. Nonce nằm trong
DB, issuer/verifier chạy worker BBS thật. Cả reauth/recovery kiểm mất phản hồi sau
commit, thử lại cùng body/một chữ ký/một issuance, hai origin, replay và phân quyền.

**Quyết định sinh trắc là fixture server tổng hợp**, không đến từ browser/request.
Khóa P-256 test do Python tạo và ghi danh bằng fixture, sau đó import non-extractable
vào Web Crypto chỉ trong test; không chứng minh quy trình ghi danh hoặc phần cứng.
Harness không có endpoint seed/pass và không được gắn vào app production.
Đây là HTTP xuyên suốt của phần chứng nhận, chưa là toàn luồng eKYC/consent người
thật hoặc Android. Test mặc định skip nếu không opt-in; CI Linux bật rõ hai biến.
