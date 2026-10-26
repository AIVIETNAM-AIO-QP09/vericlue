# Mẫu mặt và khóa thiết bị của tài khoản — FLOW-05 / SEC-02

## Phạm vi

Đây là **luồng ghi danh nội bộ opt-in**, chưa phải luồng eKYC thật đã nghiệm thu.
Migration `0005_accounts` thêm bảng tài khoản; `AppState.accounts` cấp service
trong transaction. `ACCOUNT_ENROLLMENT=true` nối lời gọi sau `pass` của bước giọng
onboarding, cùng transaction với quyết định. Không đổi UI/client/hợp đồng HTTP;
không có endpoint ghi danh hoặc lookup tài khoản. Chốt real/mixed vẫn giữ nguyên,
không cờ nào trong thay đổi này mở được luồng đó. FLOW-05 và SEC-02 giữ `doing`.

Còn thiếu: nghiệm thu luồng thật, ngưỡng được kiểm chứng, L0 reauth và
khôi phục/thu hồi khóa. Đã có opt-in [so cùng người mặt–giọng](face-voice-continuity.md),
dùng LVFace chung và protocol/ngưỡng riêng; chưa có ngưỡng thực cho phép đạt.

## Mẫu mặt của server

`VideoFaceMatchDetector.enrollment_template(input, approved)` dùng lại LVFace-B,
SCRFD và khóa của detector đã nạp. Chỉ nhận kết quả đúng version, `ok/pass`;
chấm lại đầu vào, đối chiếu hash video/pixel với kết quả trước, rồi trích vector
từ đúng khung chính diện. Không nhận embedding/nhãn góc từ client hoặc fallback
selfie. `Orchestrator.extract_template` đã nối phương thức này vào worker dùng
chung instance, slot và hàng đợi `face_match`; không nạp thêm LVFace, không tạo
executor riêng. Deadline tính cả chờ, dùng phần ngân sách request còn lại.
`PlaintextLease` được giữ tới khi future thực sự xong, kể cả HTTP đã timeout.

`EnrollmentService.complete` kiểm điều kiện trước, chỉ giải mã video mặt và ảnh
CCCD từ đường dẫn server, tạo `DetectorInput` với thử thách server rồi gọi worker.
Mẫu chỉ trả về RAM của service; tài khoản được mã hóa sau khi kiểm lại nguồn,
phiên/lượt, điều kiện và hạn dùng. Timeout/model lỗi/nguồn đổi/ghi DB lỗi không
trả `pass` thành công: ngoại lệ rollback quyết định, bước giọng và tài khoản trong
cùng transaction. Worker không có DB hoặc callback tạo tài khoản; kết quả trả
muộn không thể tự ghi danh. Không gia hạn token hay deadline để cứu lượt lỗi.

Cờ mặc định tắt và phải giữ tắt khi thử luồng mock thông thường. Bật cờ không cho
mock/mixed tạo tài khoản: service từ chối trước khi trích mẫu. `recovery`, `reauth`
và API cũ không có `purpose` không đi vào hook tạo tài khoản onboarding.

`FaceTemplate` theo schema nội bộ `face_template.schema.json` chứa phiên/lượt,
version/tiền xử lý, hash video/pixel, 512 số hữu hạn có chuẩn L2 bằng 1. Vector
là tuple bất biến, loại khỏi `repr`. Không phải detector response; không đưa vào
`ModuleResult`, session snapshot, log, bàn duyệt hoặc HTTP.

## Điều kiện ghi danh

`AccountStore.create` chỉ nhận đầu vào tin cậy do code server tạo, caller nắm khóa
hàng phiên. Không truyền thẳng dữ liệu HTTP vào service. Service kiểm lại:

- Chế độ mô hình thật, bật các opt-in video/mắt/đầu/consistency/mô hình mặt/giọng;
  bắt buộc mã hóa và master 32 byte, HMAC key tối thiểu 32 byte.
- Onboarding hoàn tất, DB quyết định `pass`, chưa từng vào bàn duyệt, chưa hết
  token/xóa dữ liệu; OTP và CCCD từ server đã xác nhận, không sửa thẻ.
- Đủ mặt/signals/finalize/giọng; cổng bắt buộc `ok/pass`, các mô hình phân loại
  có xác suất hiệu chỉnh; lỗi/degraded/mock/thiếu mô-đun bị chặn.
- Mẫu đúng phiên/lượt/version/hash pixel/hash video và consistency ba góc.
- Kết quả so cùng người giữa mặt và đọc câu phải đúng protocol riêng, `ok/pass`,
  ràng buộc mã hai lượt/hash video mặt. Kết quả riêng `face_continuity` dùng
  `FACE_VOICE_VERSION`, bật bằng `IDENTITY_VOICE_CONTINUITY`. Không tái dùng
  ngưỡng CCCD hoặc ba góc. Thiếu bằng chứng này trả 503.
- Hai bước đã tiêu thụ nonce chữ ký hiện hành, cùng public key P-256.

Fixture thành công dùng verdict/vector tổng hợp ở server để kiểm lưu trữ;
không phải bằng chứng xác minh sinh trắc thật.

## Mã hóa và kiểm trùng

Tài khoản có DEK AES-256 ngẫu nhiên riêng, được bọc bằng `SESSION_MASTER_KEY`;
mỗi lần AES-GCM có nonce 96 bit mới. Namespace `vericlue-account-v1`/magic `VCA1`
tách khỏi phiên. AAD ràng buộc account/device/phiên nguồn, HMAC CCCD/điện thoại,
thời điểm tạo/hết hạn và mục đích. Sửa ciphertext/metadata/master không đọc được,
không hạ xuống plaintext. Payload mã hóa chứa template, public key và SHA-256
public key. DB không lưu số CCCD/điện thoại/private key/ảnh/video trong tài khoản.

Unique constraint trên HMAC CCCD chặn trùng tài khoản đang hiệu lực; unique trên
phiên nguồn chặn tạo lại từ một phiên, kể cả sau hết hạn. Retry cùng phiên trả
cùng receipt, không xoay khóa. Insert dùng savepoint; xung đột trả 409 trung tính.
Receipt chỉ có account_id/device_id/expires_at. Lookup template chỉ là nội bộ;
chưa có HTTP trả receipt/template.

Tạo tài khoản, đọc template và hủy khóa ghi chuỗi `access_events` riêng theo
account_id, khóa hàng tài khoản để tuần tự hóa. Nhật ký chỉ chứa actor hệ thống,
action/thời điểm/mã opaque, không chứa vector, public key hay HMAC danh tính.

## Vòng đời 24 giờ

Hạn demo cố định 24 giờ từ lúc tạo, không gia hạn khi đọc/retry. Lookup chặn ngay
tại hạn dù worker trễ. Cleanup xóa wrapped DEK, ciphertext và HMAC; giữ tombstone
opaque/phiên nguồn, ghi số đã dọn trong `CleanupAuditRow.details.expired_accounts`.
Dọn không cần master và chạy lại an toàn. Sau hết hạn, CCCD có thể đăng ký bằng
phiên mới; phiên cũ không hồi sinh tài khoản. Worker dọn theo chu kỳ cấu hình.

Khóa tài khoản độc lập khóa phiên: hủy phiên sớm vẫn giữ mẫu trong thời hạn tài
khoản, nhưng sau 24 giờ khóa tài khoản vẫn bị dọn riêng. Backup DB/master có thể
phục hồi khóa đã xóa; chưa có hủy backup/KMS. Python không bảo đảm xóa ngay RAM.

Gắn public key đã ký hai bản ghi với device_id không cấp `device_verified`.
Cờ này phải chờ L0 xác minh khóa đã đăng ký trên nonce mới. Chưa có L0/thu hồi/
xoay khóa hoặc hardware attestation. Chữ ký không chứng minh nguồn camera.

## Kiểm tra

`pytest services/api/tests/test_enrollment_pipeline.py services/api/tests/test_accounts.py ml/tests/test_face_template.py` kiểm
contract/chuẩn vector/nguồn pixel, roundtrip, các cổng, idempotency, trùng CCCD,
tamper ciphertext/metadata/master, TTL và cleanup độc lập khóa phiên; worker dùng
chung, quá tải, deadline/lease, lỗi sau trích mẫu và rollback quyết định. Không dùng
người thật, camera/micro, dữ liệu CCCD hoặc trọng số mô hình.
