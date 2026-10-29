# Chạy và bàn giao BBS cho bản demo

Phạm vi kỹ thuật: cấp credential, holder binding, proof tiết lộ tối thiểu, bí danh
theo dịch vụ, nonce DB, vòng đời khóa, SDK browser/retry và runtime container.
Không gọi đây là toàn bộ eKYC đã nghiệm thu: nguồn sinh trắc thật và UI/app còn
điều kiện riêng. Theo trao đổi 28/10, nhóm sẽ thống nhất/rút gọn workflow trước
khi chỉnh giao diện iOS/Android; không tự thêm màn hoặc lượt xác minh cho new user.

## 1. Runtime được đóng gói

`services/api/Dockerfile` build thêm package Node đã pin bằng package-lock,
browser bundle/type/license, chỉ giữ production dependency. Image có Node 22,
hai worker, đầy đủ JSON Schema/public conformance vector và CLI operator.
Không chứa private key, model weights, dữ liệu người thật, npm/esbuild runtime
hoặc trình duyệt. Chạy API bằng UID 10001. Đây là image nền/API/BBS, không tự
cài các extra AI/GPU hoặc Chromium dùng xuất PDF.

```powershell
docker build -f services/api/Dockerfile -t vericlue-api:bbs .
docker run --rm --network none --read-only --tmpfs /tmp --entrypoint node vericlue-api:bbs /app/services/credentials/runtime-check.mjs
```

Kiểm đầu dùng vector **công khai** đúng/sai context; không cấp credential hoặc
đọc khóa triển khai. CI còn tạo khóa tạm trong tmpfs để kiểm preflight/khớp pin,
không ký quyết định tổng hợp bằng khóa triển khai.

## 2. Chuẩn bị khóa một lần

Không ghi đè bộ khóa hoặc `.env` đang dùng. Các lệnh sau dùng thư mục mới;
khóa hiện có phải được operator đối chiếu và đặt đúng đường dẫn tương ứng.

```powershell
uv run python scripts/gen_keys.py --out secrets/bbs-runtime/results
node services/credentials/keygen.mjs --out secrets/bbs-runtime/bbs/bbs-private.json
node services/credentials/export-public-key.mjs --key-file secrets/bbs-runtime/bbs/bbs-private.json --out secrets/bbs-runtime/bbs/bbs-public.json
```

`gen_keys` còn tạo khóa token phiên riêng: không tự thay SESSION_SIGNING_SECRET
đang dùng. Master AES-256, khóa Ed25519, khóa BBS và token tích hợp là các bí mật
độc lập. Không đưa lên Git/GitHub, URL, NEXT_PUBLIC_* hoặc log. Public pin phải
đến holder/bên nhận qua cấu hình hoặc kênh tin cậy, không chỉ đi kèm artifact.

| Cấu hình trên máy chạy Compose | Giá trị/ý nghĩa |
|---|---|
| BBS_SECRETS_DIR | Đường dẫn tuyệt đối tới `secrets/bbs-runtime`; mount read-only |
| RESULT_ISSUER | Ví dụ `https://vericlue.example`, thống nhất issuer/verifier |
| RESULT_AUDIENCE | Mã bên nhận kết quả nguồn, ví dụ `demo-integrator` |
| SESSION_MASTER_KEY | Base64 của khóa 32 byte, lưu bền/bảo mật; giữ khóa cũ nếu đã có dữ liệu |
| CREDENTIAL_VERIFIER_TOKENS | JSON `{token_ngẫu_nhiên: origin_HTTPS_chính_xác}`; token chỉ ở server bên nhận |
| CREDENTIAL_KEY_REGISTRY | `false` dùng public pin file; `true` phải đăng ký/kích hoạt trust registry |

Cấu hình DB, SESSION_SIGNING_SECRET và các biến nền vẫn theo `.env` hiện có.
Directory/file phải đọc được bởi UID 10001 trong container; Linux dùng owner/ACL
phù hợp, không mở khóa riêng cho mọi người đọc. Windows kiểm ACL thư mục host.
Đổi master key làm dữ liệu cũ không đọc được; không sinh master mới mỗi lần chạy.

## 3. Chạy và kiểm cấu hình

```powershell
docker compose -f docker-compose.yml -f docker-compose.bbs.yml build api
docker compose -f docker-compose.yml -f docker-compose.bbs.yml up -d db api
docker compose -f docker-compose.yml -f docker-compose.bbs.yml exec api python scripts/check_credentials.py
```

Overlay chủ động bật issuer/verifier, đặt đường dẫn Node/worker trong image và
mount thư mục khóa read-only. Không đổi USE_MOCK_MODELS, policy, thresholds hoặc
chốt pass. Khi thay cấu hình/khóa phải khởi động lại API theo quy trình operator.

Preflight đọc cấu hình, kiểm phiên bản/library/vector, private–public BBS khớp,
Ed25519 có thể nạp, master đúng 32 byte và cấu hình token/pin verifier. Không tạo
khóa, ký verdict, cấp credential, tạo challenge hay mở DB. Output chỉ trạng thái
và fingerprint công khai, không đường dẫn/bí mật. Exit 2 khi thiếu/sai cấu hình.
Khi không bật hai vai trò, output `disabled` và runtime_checked=false, không phải
đã kiểm runtime. `configuration_ok` **không** chứng minh AI/nguồn/consent đã đạt.

Nếu registry bật, preflight ghi `registry=not_checked`. Sau migration, operator
phải register/activate pin trong DB bằng CLI đã có:

```powershell
docker compose -f docker-compose.yml -f docker-compose.bbs.yml exec api python scripts/credential_keys.py --issuer https://vericlue.example register --public-key /run/vericlue-secrets/bbs/bbs-public.json
docker compose -f docker-compose.yml -f docker-compose.bbs.yml exec api python scripts/credential_keys.py --issuer https://vericlue.example list
```

Đối chiếu fingerprint rồi chạy `activate --key-id <fingerprint>` bằng cùng CLI.
Không tự kích hoạt key chỉ vì tệp tồn tại; đọc [vòng đời khóa](../architecture/private-credential-keys.md).

## 4. Tích hợp app và bên nhận

1. App có tài khoản/khóa thiết bị đã ghi danh, kết quả phiên reauth/recovery có
   chữ ký Ed25519 đủ điều kiện; không lấy verdict tự khai từ client.
2. UI hỏi riêng việc cấp credential. SDK `createVerificationSession` giữ secret
   trong RAM, `issue({consent:true})` kiểm nguồn/context, gọi authorization, ký
   nguyên byte bằng khóa thiết bị hiện hành, gọi cấp và kiểm chữ ký BBS.
3. Server bên nhận giữ token verifier, xin challenge gắn origin/nonce/hạn/policy;
   chuyển challenge tới app qua transport của dịch vụ. Không nhúng token vào app.
4. UI hiển thị đúng bên nhận và claim chung sẽ chia sẻ, xin đồng ý riêng. SDK
   tạo proof, server bên nhận gọi verify; chỉ dùng kết quả valid=true sau commit.
5. Logout/chuyển tài khoản gọi destroy. Lỗi mạng thử lại **cùng object/body** khi
   còn hạn; không tạo offer mới. Reload mất ví; có thể phải bắt đầu phiên mới.

Chi tiết callback/JSON: [SDK holder](../architecture/private-credential-holder.md).
App iOS/Android chưa được coi đã nối BBS chỉ vì SDK Chromium có test. Native dùng
khóa đã ghi danh; không thay bằng một khóa WebView mới rồi gọi đó là cùng thiết bị.
Nội dung consent/giao diện được chốt cùng nhóm khi thống nhất workflow.

## 5. Checklist nghiệm thu và giới hạn

| Kiểm gì | Bằng chứng/tiêu chí |
|---|---|
| Crypto lõi | Node tests/conformance; sai key/context/byte không qua |
| HTTP cấp/kiểm | Chromium HTTP reauth/recovery với fixture server; một issuance khi retry |
| Runtime | CI build image, UID 10001, filesystem read-only, network none, preflight khóa tạm |
| Cấu hình triển khai | Operator chạy preflight + đối chiếu pin; registry active nếu bật |
| App và consent thật | Nhóm cần nối/kiểm trên iOS/Android sau khi thống nhất workflow |
| Nguồn sinh trắc thật | Cần nghiệm thu module/policy; hiện HTTP luồng động account-bound còn chặn |

Fixture HTTP là nguồn tổng hợp ở server, không là số liệu AI hoặc endpoint demo
bỏ cổng. Không tắt guard chỉ để có credential trên UI. Onboarding hiện cấp biên
nhận tài khoản, **chưa cấp BBS trực tiếp**; không bắt new user làm thêm reauth chỉ
để có BBS. Nếu nhóm muốn BBS ngay sau onboarding, phải chốt thay đổi nguồn/schema
và tiêu chí riêng trước khi code, không lén dùng biên nhận thay SignedResult.

BBS không có PQC, chứng minh tuổi hoặc thu hồi cá nhân trong profile tích hợp.
Secret RAM không là phần cứng/secure erase; TTL lấy từ nguồn tối đa 60 giây và
làm tròn xuống cohort 10 giây. Các claim chung/IP/key metadata vẫn có thể liên kết.
