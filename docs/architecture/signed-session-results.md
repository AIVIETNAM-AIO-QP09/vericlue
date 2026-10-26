# Kết quả phiên có chữ ký — PLAT-06 / FLOW-01

## Phạm vi

Có công cụ sinh khóa Ed25519, signer/verifier dùng cryptography và endpoint lấy
kết quả có chữ ký cho bên tích hợp. Đây là phần chữ ký thông thường đã có trong
PLAT-06/ADR-0013; không hoàn thành LIVE-04 (ML-DSA/ML-KEM), ZKP hoặc FOR-04.
Báo cáo forensic hiện vẫn theo cơ chế riêng; thay đổi này không ký báo cáo PDF.
Không sửa UI hoặc mở chốt sinh trắc real/mixed/account-bound mock.

Kết quả ký chứng minh nội dung do server cấp; độ chính xác sinh trắc vẫn cần
calibration/đánh giá. Test thành công bơm verdict tổng hợp từ server, không phải
số liệu mô hình thật và không cung cấp endpoint nhận verdict/template từ client.

## Khóa và cấu hình

```powershell
uv run python scripts/gen_keys.py
```

Mặc định tạo `secrets/server-signing/` (gitignore): private PEM PKCS8, public PEM
SPKI và session-signing-secret.txt (256 bit ngẫu nhiên). Không in bí mật, không
tự sửa .env/áp dụng khóa hoặc ghi đè bộ khóa có sẵn. Chạy lại kiểm bộ khóa đủ và
khớp, giữ nguyên byte. Muốn bộ mới dùng --out tới thư mục mới. POSIX tạo thư mục
0700/file 0600; Windows cần giữ ACL thư mục cho tài khoản chạy API. Chưa có KMS,
HSM, hủy backup hoặc xoay khóa tự động. Không commit bất kỳ file bí mật nào.

Cấu hình kết quả là opt-in, không tự lấy khóa HMAC/token/master làm khóa Ed25519:

```dotenv
RESULT_SIGNING_KEY_FILE=secrets/server-signing/ed25519-private.pem
RESULT_ISSUER=vericlue-demo
RESULT_AUDIENCE=demo-integrator
RESULT_TTL_SECONDS=60
```

Issuer/audience là mã ASCII do server cấu hình cho **một bên tích hợp** của demo.
Không lấy từ body/query/Host/headers người dùng. Server ghi lại issuer/audience
và chế độ mô hình lúc tạo phiên. Phiên cũ thiếu ràng buộc, phiên mock/mixed hoặc
phiên có issuer/audience khác cấu hình hiện hành không được ký. Sau cấu hình
cần khởi động lại API và tạo phiên mới. Signer nạp một lần; thiếu/sai khóa trả
503 trung tính, không sinh khóa tạm hoặc hạ xuống chữ ký MOCK.

Khóa token phiên vẫn độc lập. Không tự đổi SESSION_SIGNING_SECRET khi kích hoạt
kết quả ký: đổi khóa đó thu hồi bearer phiên đang có. REPORT_SIGNING_KEY_PATH
trong .env.example là cấu hình dự kiến của FOR-04, chưa nối vào tính năng này.

## API và quyền

- `GET /v1/result-signing-key`: thuật toán Ed25519, SHA-256 của DER SPKI
  (key_id) và public_key_spki base64 chuẩn. Không cần bearer; route không truy cập
  DB hay gọi khởi tạo mô hình để đọc khóa. Không trả private key.
- `GET /v1/sessions/{session_id}/result`: bearer của đúng phiên. Chỉ đọc quyết
  định cuối đã commit; không nhận payload/trạng thái/nonce/audience từ HTTP.
  Trả envelope SignedResult. Các phản hồi thành công đặt Cache-Control: no-store.

Không ký onboarding/legacy, phiên chưa hoàn tất, L0 ACK, review/staff override,
quyết định không khớp bản ghi cuối, đã xóa media hoặc quá hạn. Sai bearer 401;
không có kết quả phù hợp 409 result_not_available; cấu hình ký thiếu/sai 503.

Reauth pass phải có claim L0/thiết bị hiện hành, nonce media đã dùng, đủ các bước
và mọi cổng bắt buộc đạt; match đúng protocol/account đã lưu. Nếu có bước giọng,
cũng phải đủ bằng chứng giọng và chữ ký. Recovery pass kiểm lại đầy đủ điều kiện
khôi phục và receipt thay khóa; ký device_id **mới**. Không tái cấp cho thiết bị
đã bị thay. Kết quả deny/recovery_required cuối của reauth giữ nguyên trạng thái,
không mang account/device. Lỗi L0 409 không tự trở thành kết quả ký.

Chốt full flow còn giữ, vì thế chưa có đường HTTP tạo một pass sinh trắc thật
để ký. Endpoint/worker và kiểm thử triển khai đã nối cho giai đoạn nghiệm thu;
không bỏ chốt chỉ để lấy kết quả ký trong mock.

## Định dạng byte và xác minh

Hợp đồng: packages/contracts/schemas/result.schema.json. Envelope v1 gồm
algorithm, key_id, payload và signature. Payload là base64url không padding
của JSON ASCII chứa version, issuer, audience, result_id, session_id, purpose,
nonce, status, issued_at/expires_at (giây Unix); pass thêm account_id/device_id.
Không có vector, số CCCD/điện thoại, điểm hoặc lý do an ninh.

Chữ ký Ed25519 áp dụng lên đúng chuỗi byte:

```text
ASCII("vericlue-session-result-v1") || 0x00 || ASCII(key_id) || 0x00 || payload_bytes
```

Server dùng JSON sort_keys/separators cố định; bên nhận giải base64url rồi kiểm
**nguyên byte**, không serialize lại JSON. Đây là envelope riêng, không phải
JWT/JWS. Chỉ Ed25519, không thương lượng thuật toán, không nhận URL/JWK từ token.
Verifier kiểm khóa đã tin cậy, fingerprint, chữ ký, base64url chuẩn, JSON không
trùng khóa, schema chặt, issuer/audience/session_id/nonce/purpose đã biết và hạn.

Thời điểm cấp lấy từ DecisionRow, hạn tối đa 60 giây và không vượt token/tài
khoản. Tải lại trả cùng result_id/payload/chữ ký, không kéo dài hạn. Sau thay khóa,
server chặn cấp mới cho thiết bị cũ; kết quả đã cấp vẫn kiểm được ngoại tuyến
đến expires_at. Bên tích hợp cần thu hồi tức thời phải kiểm trạng thái thiết bị
với server của họ, không dựa vào chữ ký ngoại tuyến đơn lẻ.

Public key/fingerprint phải được trao tin cậy hoặc pin từ trước; không lấy khóa
cùng một nguồn chưa được tin rồi coi nó là chứng minh danh tính server.

## Cách bên tích hợp dùng

Python: core.signing.verify_result(envelope, pinned_public_key, issuer=...,
audience=..., session_id=..., nonce=..., purpose=..., now=...). Truyền ngữ cảnh
đã giữ từ yêu cầu của mình, không lấy expected_nonce/audience từ payload vừa nhận.

```powershell
uv run python scripts/verify_session_result.py --result tmp/result.json --public-key secrets/server-signing/ed25519-public.pem --issuer vericlue-demo --audience demo-integrator --session-id ses_... --nonce NONCE_DA_GUI_TU_TRUOC --purpose reauth
```

CLI trả valid cùng status; chữ ký đúng trên deny vẫn là deny. Sau xác minh,
bên tích hợp phải tiêu thụ result_id hoặc nonce đúng **một lần**, cùng transaction
với hành động của họ. Verifier thuần không thay DB/giao dịch của bên tích hợp;
không tuyên bố chữ ký tự ngăn tái sử dụng cùng kết quả trong thời hạn.

Android SessionApi.signedResult chỉ vận chuyển envelope nguyên vẹn cho backend
tích hợp; không đọc payload rồi tự cho người dân đạt. Không thêm màn hình.

## Nguồn triển khai

- [Cryptography 50: Ed25519](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/).
- [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html): kiểm thuật toán, ngữ
  cảnh, bên phát/bên nhận và tránh dùng chéo giao thức. Envelope này không nhận
  là triển khai JWT hoặc tiêu chuẩn chữ ký hậu lượng tử.
