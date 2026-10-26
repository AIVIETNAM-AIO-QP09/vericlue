# Gói PDF/JSON có chữ ký — FOR-04

Đây là phần xuất artifact của FOR-04, độc lập với việc hiệu chỉnh khoa học đang
chờ. Không tính LR, thang lời ENFSI, neo audit hoặc tạo ảnh/phổ giả. PDF có nhãn
thử nghiệm và giới hạn hiện có. Chữ ký bảo vệ JSON và đúng tệp PDF, không chứng
nhận kết luận mô hình, quy trình trước lúc ký hoặc giá trị pháp lý của báo cáo.

## API và runtime

`GET /v1/forensic/jobs/{id}/report-bundle` yêu cầu StaffBearer và trả ZIP có đúng:

- `report.pdf`: PDF A4, font hệ thống hỗ trợ tiếng Việt, số trang, bảng và giới hạn.
- `report.json`: PdfReportManifest trong forensic.schema.json, gồm snapshot job,
  tên/hash file gốc, thời điểm tạo job, version công cụ/model, giới hạn và hash PDF.
- `report.sig`: Ed25519 base64 chuẩn (64 byte, 88 ký tự), tách rời, không phải PAdES.

Chỉ job đã done, lưu mode real và có khóa REPORT_SIGNING_KEY_PATH hợp lệ mới được
xuất. Job mock/chưa xong trả 409, không tồn tại trả 404. Thiếu runtime/khóa hoặc
render lỗi trả 503, không hạ xuống bản không ký. HTML ký ở PR84 vẫn hoạt động khi
chưa bật PDF. Mỗi lần xuất là một gói độc lập, PDF có thể khác byte metadata giữa
các lần; phải giữ ba tệp của cùng lần xuất, không tráo chúng giữa hai gói.

Runtime opt-in, không thêm dependency Python hoặc tự cài lúc nhận request:

```powershell
cd apps/web
npm ci
npx playwright install chromium
cd ../..
$env:FORENSIC_PDF_NODE = (Get-Command node).Source
$env:FORENSIC_PDF_PLAYWRIGHT_DIR = (Resolve-Path apps/web/node_modules/playwright).Path
$env:FORENSIC_PDF_TIMEOUT_SECONDS = '30'
```

Giữ các biến và REPORT_SIGNING_KEY_PATH trong cấu hình máy rồi restart API.
Hai đường dẫn runtime phải tuyệt đối, trỏ Node và package Playwright trên server.
Đã kiểm runtime native Windows; CI có job Windows chạy Chromium thật. Container
API mặc định không có Node/browser. Linux/container cần runtime và sandbox
Chromium hoạt động; không tự bỏ sandbox nếu khởi chạy lỗi.

Worker là code của repo, chỉ nhận HTML server tạo, không nhận HTML/URL do client
gửi để render/ký. Chromium bật sandbox, tắt JS/service worker, offline và abort
mọi request tài nguyên. Tiến trình con không nhận master key, staff token, HMAC,
proxy hoặc NODE_OPTIONS; chỉ chuyển env hệ thống/browser cần thiết. Windows chạy
ẩn. Một renderer/process API, hết chỗ trả 503 pdf_busy, không hàng đợi vô hạn.
Deadline mặc định 30 giây (1–60); parent có 5 giây chờ dọn rồi hủy cây tiến trình
của worker nếu cần. Không tự đổi budget inference của mô hình.

HTML tối đa 4 MiB, PDF 32 MiB, JSON 4 MiB. ZIP không nén, tên tệp cố định; không
persist gói vào kho media/DB nên không thêm dữ liệu tồn dư cần TTL. Browser có thể
dùng thư mục tạm của runtime; quyền tài khoản chạy API vẫn phải được quản lý.
Endpoint no-store, không đổi UI ứng dụng hoặc tải PDF riêng ở URL công khai.

## Giao thức ký và kiểm tra

JSON được serialize từ PdfReportManifest với khóa sắp xếp, ensure_ascii=true,
separators=(',',':'), exclude_none=true, không NaN/Infinity. Datetime có timezone;
đây là định dạng chuẩn hóa của protocol, không tuyên bố RFC 8785/JCS.
Key ID là SHA-256 DER SPKI như giao thức HTML, dùng lại khóa report nhưng tách domain:

```text
"vericlue-forensic-pdf-bundle-v1\0" || ASCII(key_id) || "\0" || canonical_JSON_bytes
```

PDF hash nằm trong JSON đã ký. Không lấy key từ ZIP/JSON/PDF, không đàm phán thuật
toán. Verifier kiểm chữ ký trước khi parse JSON, kiểm canonical encoding, fixed
protocol/algorithm/key_id, done/real và hash đúng byte PDF; có thể đối chiếu job ID.
Không chấp nhận chữ ký HTML/kết quả phiên trong protocol này.

```powershell
uv run python scripts/verify_pdf_bundle.py --bundle report.zip --public-key trusted-report-key.pem --expected-job-id job_...
```

CLI không giải nén ra filesystem, render PDF hoặc gọi mạng. Nó giới hạn tổng ZIP,
central directory trước khi materialize entries, đúng ba member, không nén/mã
hóa/symlink/path lạ hoặc trùng tên, giới hạn từng tệp. Sai byte JSON/PDF/chữ ký/key/
job trả exit 1 và JSON valid=false. Exit 0 chỉ xác nhận gói khớp khóa đã pin; người
đọc vẫn phải đối chiếu hash vật chứng và nội dung mong muốn. Key cũ kiểm offline
nếu còn được tin cậy, chưa có KMS/online revocation/dấu thời gian bên thứ ba.

Tham chiếu runtime: [Playwright page.pdf](https://playwright.dev/docs/api/class-page#page-pdf),
[Chromium sandbox](https://playwright.dev/docs/api/class-browsertype#browser-type-launch-option-chromium-sandbox),
[chặn request](https://playwright.dev/docs/network#block-requests).
Không chép code SDK; dùng dependency Playwright đã có trong web.

Ảnh/phổ opt-in dùng chung HTML/PDF: [forensic-report-evidence.md](forensic-report-evidence.md).

FOR-04 còn neo hash cuối review_events, LR/calibrator riêng, thang lời và
kiểm ENFSI 2015. Không đánh dấu hoàn thành toàn task bằng phần xuất này.
