# Ví BBS trên trình duyệt — LIVE-05

SDK xử lý holder độc lập với giao diện: kiểm kết quả Ed25519, giữ secret trong
RAM, kiểm nội dung trước khi nhờ khóa thiết bị ký và tạo BBS proof cho bên nhận
được người dùng đồng ý. Không có HTTP client, màn hình consent hoặc lưu ví lâu dài.
Backend và các cổng sinh trắc giữ nguyên; SDK không tạo được quyết định pass.

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

Đây là tương thích giữa các thành phần, **chưa phải browser → FastAPI end-to-end**
hoặc nghiệm thu Android/Safari/Firefox. API → Python → Node có bộ native test riêng
với quyết định sinh trắc fixture tổng hợp. Không bật đường pass sinh trắc thật,
không dùng kết quả này làm R1–R7 hoặc số liệu chất lượng mô hình.
