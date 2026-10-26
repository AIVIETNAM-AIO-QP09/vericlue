# Ký báo cáo HTML — PLAT-06

Đây là chữ ký Ed25519 cho báo cáo HTML hiện có, không phải gói báo cáo ENFSI
JSON/PDF của FOR-04. Không xuất PDF, không thêm LR, thang lời hoặc số đo chưa
được hiệu chỉnh. Chữ ký bảo vệ tính toàn vẹn từ lúc cấp báo cáo; không chứng nhận
kết luận mô hình hoặc chuỗi lưu giữ vật chứng trước thời điểm đó.

## Khóa và cấu hình

Sinh bộ khóa riêng bằng `uv run python scripts/gen_keys.py --out secrets/report-signing`.
Đặt `REPORT_SIGNING_KEY_PATH=secrets/report-signing/ed25519-private.pem` rồi restart
API. Lệnh này không tự áp dụng khóa, không in/ghi đè bí mật. Không dùng HMAC token
phiên hoặc đổi SESSION_SIGNING_SECRET. Không cần cấu hình issuer/audience của
kết quả eKYC để ký báo cáo; hai protocol có domain riêng.

Compose đã chuyển biến REPORT_SIGNING_KEY_PATH vào API nhưng không tự mount khóa.
Khi chạy container, mount thư mục khóa chỉ đọc (ví dụ
`./secrets/report-signing:/run/vericlue-report-keys:ro`) bằng compose override và
đặt biến thành `/run/vericlue-report-keys/ed25519-private.pem`. Không bake khóa
vào image hoặc commit secrets. Giữ file khóa bất biến khi API chạy, đổi khóa cần
restart; chưa có KMS/rotation tự động hoặc danh sách khóa lịch sử ở server.

Thiếu/sai khóa trả 503 `report_signing_unavailable` cho báo cáo job real, khóa
công khai và verify. Không sinh khóa fallback hoặc trả chữ ký MOCK cho job real.
Job mock vẫn xuất HTML có nhãn mô phỏng và checksum MOCK; `/verify` với khóa hợp
lệ luôn trả `valid=false` cho checksum đó. Không thể dùng nó làm chứng nhận.

## Giao thức byte

`D = SHA256(đúng byte UTF-8 của HTML trả về)`; K là public key Ed25519 đã tin cậy.
`key_id = hex_lower(SHA256(DER SubjectPublicKeyInfo(K)))`.

Nội dung ký, các dấu `\0` dưới đây là byte 0:

```text
"vericlue-forensic-html-report-v1\0" || ASCII(key_id) || "\0" || bytes.fromhex(D)
```

Ký Ed25519 thông thường trên message này; chữ ký 64 byte mã hóa base64 chuẩn có
padding (88 ký tự). Đây không phải Ed25519ph, JWS/JWT hoặc chữ ký kết quả eKYC.
Hash phải đúng 64 ký tự hex thường; base64 không chuẩn hoặc khóa khác bị từ chối.
Recipe dùng [cryptography Ed25519](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/).
Không chép code hoặc thêm dependency.

## API và kiểm offline

Mọi endpoint dưới `/v1/forensic` yêu cầu StaffBearer, kể cả khóa công khai:

- `GET /signing-key`: SigningKey Ed25519/SPKI/fingerprint; không cần DB/model.
- `GET /jobs/{id}/report`: HTML, `X-VeriClue-Report-SHA256`, `X-VeriClue-Signature`,
  `X-VeriClue-Signature-Algorithm=Ed25519` và `X-VeriClue-Key-Id`. HTML cũng in
  fingerprint. Job phải done; thiếu khóa không tạo artifact/chữ ký mới.
- `POST /verify`: body hiện có `{report_sha256, signature}`, trả `{valid}`;
  chỉ kiểm với khóa report đang cấu hình, không chọn khóa theo body/URL/HTML.
  Không cần DB/model. Không có API nhận hash hoặc HTML tùy ý để ký.

Phản hồi no-store; CORS expose các header metadata cho origin được phép.
Request verify giới hạn chữ ký 160 ký tự và không nhận trường lạ.
`valid=true` chỉ xác nhận hash có chữ ký khớp khóa hiện hành, không chứng minh
người gọi đã cung cấp hash đúng của tệp đang xem hoặc job/file họ mong muốn.

Lưu đúng byte HTTP response, lưu header chữ ký thành `report.sig`; kiểm bằng
khóa public PEM đã nhận qua kênh tin cậy riêng (không tự tin khóa trong HTML):

```powershell
uv run python scripts/verify_forensic_report.py --report report.html --signature-file report.sig --public-key trusted-report-key.pem
```

CLI tự hash tệp (tối đa 64 MiB), không thực thi HTML hoặc gọi mạng, exit 0 khi
hợp lệ; exit 1 và JSON `valid=false` khi lỗi/sai chữ ký. Đổi một byte, lưu lại HTML
theo cách trình duyệt sửa nội dung, hoặc xuất thành PDF làm hash khác. Đây là
chữ ký tách rời; phải giữ HTML gốc, chữ ký và public key tin cậy cùng hồ sơ.
Khóa cũ vẫn kiểm offline được sau rotation nếu được tin cậy; endpoint online chỉ
kiểm khóa đang cấu hình. Không có hết hạn/thu hồi trực tuyến hoặc dấu thời gian
của bên thứ ba. Người đọc phải đối chiếu job ID và hash vật chứng mong muốn.

FOR-04 đã có protocol gói JSON + hash PDF riêng:
[`forensic-pdf-bundle.md`](forensic-pdf-bundle.md). Chữ ký HTML không dùng thay chữ
ký gói. Ảnh/phổ opt-in xem [forensic-report-evidence.md](forensic-report-evidence.md).
Neo hash cuối review cho job gắn ca xem [forensic-review-audit.md](forensic-review-audit.md).
Còn LR/thang lời và kiểm ENFSI gốc; task chưa xong.
