# Giám định độc lập hoặc gắn hồ sơ — FOR-04

## Hai cách tạo job

`POST /v1/forensic/jobs` dùng StaffBearer, multipart gồm `file` và tùy chọn
`review_case_id`. Không gửi mã ca: luồng giám định file độc lập giữ nguyên.
Gửi mã ca: server kiểm ca và byte nguồn trước khi tạo/lưu job, không nhận
checkpoint, hash hoặc đường dẫn do client khai để thay phép đối chiếu.

Ca phải có quyết định ban đầu của nhân viên, giữ nguyên nguyên tắc duyệt trước
khi xem AI. Chưa có quyết định trả 409 review_link_not_ready. Không tìm thấy ca
trả 404; file không khớp trả 409 linked_media_mismatch; media đã dọn trả 410.
Job forensic mock không được gắn liên kết đã kiểm. Liên kết bị từ chối không
giữ slot hàng đợi hoặc tạo job/file giám định.

Nguồn được so với `video`, `audio`, `voice_video` trong snapshot phiên của ca,
không phải URL media do client gửi. Path phải thuộc đúng MEDIA_DIR/session_id,
không symlink/junction, file thường, giới hạn 64 MiB. SEC-01 giải mã bằng lease
hiện hành nếu bật riêng tư; SHA-256 clear bytes phải bằng hash file tải lên.
Lease được đóng và hành động forensic_source_link ghi vào access audit với
actor lấy từ credential server. Không đưa vector, CCCD, số điện thoại hoặc ghi
chú riêng tư vào checkpoint. Kiểm nguồn không chứng thực camera hoặc danh tính.

File cắt/chuyển mã không còn cùng byte sẽ không được gắn ca theo cách này; có
thể giám định độc lập. Khi nguồn đã hết hạn/khóa bị hủy, không tự suy ra liên kết
từ tên file hoặc tín hiệu mô hình. Link chỉ được tạo cùng job, không có endpoint
đổi ca cho job cũ.

## Mốc được ký

ForensicJob thêm `review_audit` tùy chọn; null/không có nghĩa là file độc lập.
Mốc v1 gồm case/session, role nguồn, source_sha256, thời điểm ghi nhận, số sự
kiện, ID/hash sự kiện cuối. Hash nguồn phải bằng file_sha256 của job. Canonical
signer/verifier kiểm lại điều kiện này, không chỉ tin một model_copy nội bộ.

Server kiểm chuỗi `review_events` trên payload đã lưu, kể cả private_note đã
mã hóa, không cần mở ghi chú. Case/action/actor/note/reason/time và trạng thái initial/final phải
khớp nhật ký. Giới hạn 4096 sự kiện; protocol hiện chỉ ghi initial rồi final.
Không sửa/xóa sự kiện trong code sản phẩm; trigger append-only giữ nguyên.

Khi xuất HTML/PDF, server kiểm prefix đã neo trước khi tiến tới mốc mới. Thiếu
đuôi, hash/ID không khớp hoặc trạng thái ca bất nhất trả 409 review_audit_invalid,
không ký lại một chuỗi ngắn hơn. Thêm final hợp lệ được chấp nhận. Conditional
UPDATE trên checkpoint cũ ngăn snapshot SQLite cũ ghi lùi mốc mới; xung đột trả
409 report_conflict. PostgreSQL còn khóa row job/case. Cập nhật mốc và ký/xuất
cùng transaction, lỗi rollback. Không thêm migration hoặc dựa vào khóa Python.

HTML hiển thị mốc trước khi ký; JSON có mốc nằm trong chữ ký PDF-bundle v1 và
PDF hash bảo vệ cả nội dung PDF. Mốc đã xuất cần được giữ bên ngoài DB với chữ
ký và public key tin cậy; không coi một hash chỉ lưu trong cùng DB là neo ngoài.

## Đối chiếu sau khi xuất

`POST /v1/forensic/review-audit/verify`, StaffBearer, JSON gồm:

- `report_json`: đúng chuỗi ASCII trong report.json, không serialize/format lại.
- `signature`: chuỗi base64 report.sig của cùng lần xuất.

Kiểm chữ ký/key cấu hình trước khi parse nội dung, rồi kiểm canonical schema
trước khi truy cập DB.
Không dùng key trong tài liệu. JSON sai hoặc không ký được trả invalid_signature
trước truy cập DB/model. JSON hợp lệ nhưng độc lập trả unlinked, cũng không cần
DB. Với mốc hợp lệ, đối chiếu trực tiếp ca/nhật ký, không phụ thuộc việc job còn
trong DB hoặc media/key giải mã còn tồn tại.

Response có scope cố định **signed_json_review_audit**. Endpoint này không nhận
PDF nên **không xác minh byte PDF**; vẫn dùng verify_pdf_bundle.py để kiểm đầy
đủ gói và pin public key. signature_valid nghĩa chữ ký và định dạng JSON hợp lệ
với khóa report hiện tại, không phải kết luận sinh trắc hoặc giá trị pháp lý.

| status | Ý nghĩa |
|---|---|
| intact | Chuỗi hiện tại khớp đúng mốc đã ký |
| extended | Prefix khớp, có thêm sự kiện hợp lệ; appended_count cho biết số thêm |
| tail_truncated | Chuỗi hiện tại thiếu sự kiện so với mốc đã ký |
| anchor_mismatch | Hash/ID tại ranh giới prefix không khớp |
| chain_invalid | Chuỗi hoặc trạng thái initial/final bất nhất |
| case_unavailable | Không còn ca hoặc session của ca không khớp |
| invalid_signature | Không xác minh được chữ ký/định dạng với khóa hiện tại |
| unlinked | Tài liệu hợp lệ nhưng không có mốc ca liên kết |

Chỉ intact/extended trả ok=true. Kiểm này là ảnh chụp trạng thái tại lần đọc,
không dự đoán việc sửa sau đó. Không phát hiện sự kiện chưa từng được neo nếu
cả DB bị khôi phục về trước sự kiện ấy. Chữ ký không chứng minh sự thật của mọi
thao tác trước lúc ký; thời gian server không phải TSA. Xoay khóa/KMS/revocation
chưa có: endpoint dùng khóa hiện tại, CLI có thể kiểm key cũ nếu còn được tin.

SDK web có createForensicJob(file, filename, {reviewCaseId}), getForensicJob và
verifyForensicReviewAudit qua credential callback trong RAM/no-store. Không sửa
UI. Bộ dựng giao diện dùng type mới; không ghi credential vào public env/URL.

## Kiểm thử

Test dùng khóa thật, media tổng hợp và phân tích giả, không phải số đo chống
deepfake. Có đủ ba role, plain/encrypted, duyệt trước AI, mismatch/expiry, ký
JSON/PDF, append hợp lệ, cắt đuôi, nguồn không khớp và CAS stale SQLite.
Corruption test chỉ bỏ trigger trên SQLite tạm đã kiểm path, mô phỏng quyền
phục hồi DB; không nới trigger sản phẩm. PostgreSQL CI kiểm rollback/JSON CAS và
xuất song song. FOR-04 vẫn chờ hiệu chỉnh/LR/ENFSI và nghiệm thu UI/vật chứng thật.
