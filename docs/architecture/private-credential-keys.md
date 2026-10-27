# Vòng đời khóa issuer BBS — LIVE-05

Sau PR #99, registry opt-in trong DB quản lý các public pin của **một issuer**
theo cấu hình mỗi dịch vụ. Không thay primitive/header BBS, không thêm mã thu hồi
cá nhân vào proof và không sửa UI hoặc mở chốt sinh trắc thật.

## Trạng thái và hạn

| Trạng thái | Cấp chứng nhận qua API | Kiểm proof qua API registry |
|---|---|---|
| `staged` | Không | Không; public pin mới đăng ký chưa được tin |
| `active` | Có, nếu đủ mọi điều kiện nguồn/thiết bị hiện hành | Có |
| `verify_only` | Không, kể cả retry cache | Có trong thời gian chuyển tiếp, với hạn credential không vượt hạn tin khóa |
| `revoked` | Không | Không, kể cả challenge đã tạo trước đó |

Mỗi issuer có tối đa một key active, ràng buộc bằng unique partial index trong DB.
Kích hoạt key mới chuyển key active cũ sang verify_only trong cùng transaction.
Key cũ chỉ còn được tin **60 giây** kể từ lúc nghỉ cấp, tương ứng hạn credential
nguồn hiện hành. Proof không được kéo dài valid_until qua mốc này. Key đã revoke
không được activate hoặc register để khôi phục; vẫn giữ tombstone trong DB.

Key verify_only chưa revoke có thể được operator kích hoạt lại khi chủ động
rollback triển khai. Không xóa/sinh lại bí mật hoặc thay tệp cấu hình tự động.

## Bật registry

Áp migration `0009_credential_key_registry`, bật `CREDENTIAL_KEY_REGISTRY=true`
trên **mọi instance issuer/verifier sử dụng cùng DB trust registry**. Giữ các
cấu hình Node/runtime, issuer và credential tích hợp của bước trước. Verifier
không cần `CREDENTIAL_VERIFIER_PUBLIC_KEY_FILE` khi dùng registry; không fallback
sang file này nếu registry thiếu, lỗi hoặc key đã bị loại.

Flag mặc định false giữ chế độ public pin file của PR #99. CLI không tự bật flag,
không đổi `.env` hoặc khóa riêng. Revocation trong registry không áp dụng tới
SDK verifier offline, instance còn dùng legacy mode hoặc DB trust khác.

Đăng ký public pin đã đối chiếu qua kênh tin cậy (chỉ tệp từ công cụ xuất public):

```powershell
uv run python scripts/credential_keys.py --issuer https://vericlue.example register --public-key /absolute/public-bbs.json
uv run python scripts/credential_keys.py --issuer https://vericlue.example list
uv run python scripts/credential_keys.py --issuer https://vericlue.example activate --key-id <sha256-key-id>
```

CLI đọc `DATABASE_URL` và cấu hình DB hiện có, không nhận mật khẩu DB qua argv.
Không có endpoint HTTP quản trị hoặc quyền đổi key cho token nhân viên/bên tích
hợp. Chỉ operator có quyền DB chạy công cụ. Output là metadata công khai gồm key
ID/state/thời gian, không private/public key thô. Chỉ báo thành công sau commit;
lỗi trả exit 2, không in SQL/connection string/tệp bí mật.

## Xoay khóa

1. Tạo khóa BBS mới ở đường dẫn khác bằng `services/credentials/keygen.mjs`,
   xuất public pin bằng `export-public-key.mjs` và đối chiếu nguồn tin cậy.
   Không ghi đè private file đang dùng trong một request.
2. Register public pin mới (staged), kiểm metadata bằng `list`.
3. Tạm ngừng cấp; activate key mới, cập nhật/reload đường dẫn private key tương
   ứng trên các issuer rồi tiếp tục cấp. Sai key/cấu hình sẽ trả 503; việc đổi
   active và triển khai tệp bí mật không là một giao dịch phân tán.
4. Verifier tiếp tục đọc DB. Holder có credential cũ yêu cầu challenge với body
   `{"key_id":"<credential.key_id>"}`; `{}` hoặc `key_id:null` chọn key active.
   Public key từ request không được tin, key ID chỉ chọn một pin đã tin trong DB.
5. Credential cũ còn kiểm được trong hạn gốc và thời gian chuyển tiếp. Sau hạn,
   hoặc sau revoke, không tạo/kiểm proof với key đó được nữa. Response challenge
   vẫn như PR #99, không đổi proof/header hoặc thêm định danh người dùng.

Issuer kiểm active key cả ở authorization và cấp/retry, giữ khóa hàng tới commit.
Worker output phải khớp đúng key ID/claims đã được thiết bị chấp thuận, tránh
đổi private file giữa hai lần đọc rồi trả credential dưới một key khác.
Một phiên đã cấp dưới key cũ không tự được ký lại dưới key mới; nếu không thể
nhận lại artifact sau rotation thì cần phiên xác minh mới.

## Thu hồi và giao dịch

```powershell
uv run python scripts/credential_keys.py --issuer https://vericlue.example revoke --key-id <sha256-key-id>
```

Thu hồi **toàn bộ key issuer**, ảnh hưởng mọi credential mang key đó. Không phải
thu hồi riêng một người/credential; không đưa status ID liên kết người dùng giữa
dịch vụ vào proof. Bên kiểm chứng vẫn chỉ nhận public claims và bí danh theo origin.

PostgreSQL dùng FOR SHARE khi đọc pin xuyên suốt crypto/commit: proof độc lập có
thể chạy đồng thời, operator đổi trạng thái phải đợi. FOR UPDATE/advisory lock
serialize các thay đổi operator. Nếu kiểm đang chạy trước revoke thì nó có thể
commit trước; sau revoke commit, các lượt sau bị loại. Lock timeout trả lỗi để
operator thử lại, không báo đã revoke khi còn chưa commit. SQLite dùng BEGIN
IMMEDIATE trong API/CLI ghi và phù hợp demo ít người.

`credential_trust_keys` chỉ giữ public key, issuer, trạng thái và thời gian;
`credential_key_events` ghi thêm các chuyển trạng thái trong cùng transaction.
Đây là lịch sử vận hành trong DB tin cậy, không phải log ký/băm chống sửa hoặc
bằng chứng danh tính operator. Rollback không để lại trạng thái hoặc event nửa chừng.

## Giới hạn và nghiệm thu

Chưa có KMS/HSM, tự đồng bộ nhiều DB, key discovery tự động, khôi phục private key
hoặc thu hồi riêng từng credential. Không làm credential sống lâu hơn hạn nguồn.
Đúng chữ ký vẫn chỉ chứng minh issuer đã ký, không chứng minh AI chính xác hoặc
danh tính pháp lý. Không thay đổi giới hạn ví/consent, thiết bị thật hay PQC.

Test native dùng hai key BBS thật, claims server tổng hợp: chọn key cũ/mới,
rotation giữ proof cũ, proof nhầm key bị loại, revoke và restart không khôi phục
key. Test API cấp dùng P-256/Ed25519 thật với worker boundary stub tách biệt.
CI PostgreSQL kiểm revoke đợi proof đang chạy, proof khác nonce dùng share lock
đồng thời và hai operator activate vẫn chỉ còn một key active.
