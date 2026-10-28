# Profile bảo vệ dữ liệu — SEC-05

`SECURITY_PROFILE=synthetic` giữ tương thích các lab, không là tuyên bố dùng được
với dữ liệu thật. `protected` kiểm cấu hình ngay trong `create_app`, trước DB/model
startup hoặc nhận request. Profile không tự mở đường sinh trắc thật/account-bound.

## Điều kiện bắt buộc

- `PRODUCT_MODE=ekyc`, `SESSION_PRIVACY=true`, `REQUIRE_MEDIA_PROOF=true`,
  `REQUIRE_PRIVACY_CONSENT=true`, `USE_MOCK_MODELS=false`. Profile protected không
  bật route công cụ future work. `PRIVACY_POLICY_VERSION` là mã thông báo server
  công khai; client cần đồng ý đúng phiên bản trước thu dữ liệu (phần SEC-06).
- `SESSION_MASTER_KEY` là base64 chuẩn của 32 byte CSPRNG ngẫu nhiên.
- `ID_HMAC_KEY` và `SESSION_SIGNING_SECRET` là các bí mật độc lập, ít nhất 32 byte
  UTF-8; không dùng giá trị dev/placeholder hoặc một ký tự lặp.
- Không dùng lại master (byte gốc hoặc chuỗi base64) cho HMAC/token, không dùng
  chung HMAC/token. Kiểm cú pháp không chứng minh entropy: operator phải sinh bằng CSPRNG.
- Khóa phải giữ bền qua restart và có ACL riêng. Không tự sinh master khi khởi động,
  không đổi master để mở lại kho cũ, không commit hoặc log khóa.

Thiếu điều kiện trả lỗi cấu hình chung, không in giá trị; chương trình không bắt đầu
nhận dữ liệu. Các khóa Ed25519/BBS và pin/runtime opt-in vẫn phải kiểm riêng bằng
`scripts/check_credentials.py` khi dùng BBS. Preflight này không kiểm toàn bộ hệ thống.

## Compose

```powershell
docker compose -f docker-compose.yml -f docker-compose.protected.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.protected.yml up -d db api
docker compose -f docker-compose.yml -f docker-compose.protected.yml exec api python scripts/check_security_profile.py
```

Chuẩn bị các khóa bằng quy trình operator trước khi chạy; các lệnh không tạo hoặc
ghi đè `.env`. Mặc định Compose chỉ bind API lên loopback. Cần HTTPS reverse proxy
được kiểm soát cho app từ xa; chỉ đổi API_BIND_ADDRESS để mở mạng sau khi kiểm
proxy/firewall, không mở trực tiếp port công khai không bảo vệ.

Overlay đưa multipart OS temp vào tmpfs riêng 256 MiB với quyền cho UID 10001.
Dung lượng này phải nghiệm thu theo capture/concurrency; đầy temp phải xử lý lỗi,
không chuyển sang thư mục công khai. Plaintext inference lease vẫn ở vùng riêng
`MEDIA_DIR/_decoded` theo SEC-01: loại khỏi backup, dọn orphan có kiểm soát sau khi
dừng API/worker. Tmpfs không thay ACL, crash cleanup hoặc bảo vệ RAM.

Khi dùng BBS có thể thêm `-f docker-compose.bbs.yml`; không bỏ protected overlay
hoặc coi BBS overlay cũ tự đáp ứng mọi điều kiện. BBS TTL/pin/consent/registry và
guard nguồn sinh trắc vẫn giữ.

## OTP

Kênh hiện tại là `SimulatedSms`, chỉ được gửi/kiểm trong profile synthetic với
`USE_MOCK_MODELS=true`. Real/mixed hoặc protected phải trả `503 otp_unavailable`
trước ghi trạng thái. Không trả simulated_sms, không công nhận mã đã tạo ở mock
sau khi đổi mode. Chưa có nhà cung cấp SMS thật; profile không tự biến mô phỏng
thành xác nhận quyền giữ số điện thoại.

App cần build cờ ký media tương ứng, lưu đúng alias Keystore và nghiệm thu trên
thiết bị. `protected_configuration_ok` chỉ là kiểm cấu hình nền, không chứng minh
camera thật, AI đúng, UI consent, TLS/proxy, quyền tệp hay backup đã nghiệm thu.

## Rescan

`MAX_ID_CARD_SCANS=5` (1–20) và `MAX_ID_CARD_TOTAL_MB=128` (1–512) là trần cấu hình
demo bảo thủ cho phần SEC-04. Chọn lại sau khi đo capture hợp lệ; counters theo
phiên phải lưu bền và không bỏ hạn mức bằng restart. Không dùng số liệu này làm
đánh giá chất lượng AI.
