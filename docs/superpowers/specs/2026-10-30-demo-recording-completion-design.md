# Hoàn thiện bản quay demo Android và quyền lưu mẫu SEC-09

Ngày 30/10/2026. Trạng thái: thiết kế để người dùng review, chưa triển khai thay đổi hợp đồng.

## Mục tiêu và bằng chứng hiện có

Người dùng muốn tự quay video demo bằng điện thoại Android, OTP mô phỏng,
không cần iOS trong đợt này. Không thay ngưỡng tùy ý, không dùng lỗi/degraded
để tạo kết quả đạt. Người dùng tự thử thiết bị sau khi phần mềm sẵn sàng.

Nhánh local `codex/APP-01-demo-integration` đã có consent xử lý phiên,
adapter/công cụ hiệu chỉnh PAD/GenD video, 533 regression test liên quan qua.
Chưa có dữ liệu đúng protocol để fit/đánh giá thật. AccountStore chủ động
chặn `USE_MOCK_MODELS=true`; OTP mô phỏng không đồng nghĩa đủ điều kiện
ghi danh thật. SEC-09 hoàn tất cũng không tự mở chốt này.

## Phương án

1. **Đề xuất:** chuẩn bị bản quay trung thực bằng hai đoạn riêng: trải nghiệm
   giao diện mô phỏng, rồi một lượt API/AI thật với kết quả server thực sự trả.
   Đồng thời hoàn thiện SEC-09 để code sẵn sàng khi có đủ bằng chứng ghi danh.
   Có thể quay tiến độ ngay, không tuyên bố đã nghiệm thu eKYC toàn luồng.
2. Chỉ quay luồng AI thật đạt và tài khoản thật: phải chờ bộ dữ liệu, hiệu chỉnh,
   đánh giá độc lập và giải quyết protocol OTP/guard bằng thiết kế riêng.
   Không hứa thời điểm hoặc kết quả đạt khi chưa có bằng chứng.

Không đưa cơ chế ép pass hoặc tự chuyển từ kết quả API sang màn thành công
mô phỏng vào sản phẩm. Màn mô phỏng hiện tại chỉ trình bày hoàn tất xác minh/
tài khoản mẫu; chưa phải ứng dụng quản lý tài khoản có đăng xuất/đăng nhập bền.

## Phạm vi triển khai SEC-09

### Hợp đồng trước

Thêm các definition riêng cho mục đích `account_template`, không thêm category
giả vào `PrivacyCategory` của phiên. Mở rộng schema privacy và ví dụ, OpenAPI,
type/SDK web và model/method Android cùng thay đổi. Không sửa ADR/ngưỡng.

Endpoint có bearer phiên hiện hành:

- `GET /v1/sessions/{id}/privacy/account-template`: trạng thái quyền lưu mẫu.
- `POST .../account-template/consent`: `policy_version`, `consent:true` và
  `purpose:account_template`; server ấn định thời hạn mẫu 24 giờ từ ghi danh.

Receipt có `session_id`, scope `account_template`, purpose, policy version,
status (`not_granted|granted|withdrawn`), receipt ID/time và `retention_seconds`
86400. Không chứa mẫu, HMAC danh tính, điểm số hoặc token. Version độc lập
`account-template-v1`, hiển thị đúng nội dung app đóng gói; version đổi phải xin
lại lựa chọn. Kiểu request strict, không nhận field thời hạn tùy ý từ client.

Chỉ onboarding còn hoạt động được grant. Xử lý phiên phải được đồng ý trước.
Phiên đã rút, đóng, hết hạn, sai purpose hoặc token cũ không được cấp quyền.
Grant lặp cùng phiên/version trả cùng receipt; quota hữu hạn với version mới.
Lỗi giữ format API hiện hành; dùng mã riêng `account_template_consent_required`
và `account_template_policy_changed`, không dùng lỗi consent phiên để che nghĩa.

### Lưu và kiểm tra phía server

Migration thêm bảng receipt lưu mẫu riêng, metadata tối thiểu và append-only,
gắn session; không lưu bytes sinh trắc, token, CCCD hoặc số điện thoại vào bảng.
AccountRow thêm tham chiếu receipt nullable cho dữ liệu cũ; không tự backfill
consent cho tài khoản cũ. Grant và enrollment cùng khóa session trước thao tác.

Kiểm consent trong `validate_enrollment` trước worker trích mẫu và kiểm lại
trong `create` trước ghi DB. Kiểm cùng phiên, purpose, policy hiện hành, thời
điểm hợp lệ, không có tombstone withdrawal. Cấu hình enrollment không thay
receipt. Mọi điều kiện biometric/OTP/signature hiện tại vẫn áp dụng.
Receipt chỉ là điều kiện cần, không phải kết quả xác minh.

Ghi danh mới lưu receipt reference trong transaction tạo tài khoản. Retry chỉ
trả binding cũ nếu receipt gốc hợp lệ; không đổi nguồn consent, quay vòng khóa
hoặc hồi sinh account hết hạn. Các account cũ thiếu receipt không được coi là
đã đồng ý theo hợp đồng mới; giữ chốt và yêu cầu luồng mới.

Withdrawal phiên trước ghi danh làm quyền lưu mẫu không sử dụng được. Sau ghi
danh, withdrawal phiên tiếp tục **không xóa account**; response hiện hành vẫn
`account_data_erased=false`. Không thêm hành động xóa tài khoản vào thay đổi
này, không hứa đã thu hồi mẫu/chứng nhận. Thời hạn tài khoản giữ 24 giờ và
read-time TTL hiện có; dọn file/backup không được suy diễn từ hủy khóa.

### Android

Onboarding có checkbox lưu mẫu riêng, mặc định bỏ chọn, nội dung giải thích
đối chiếu khi đăng nhập lại, mã hóa, hạn 24 giờ và phạm vi rút phiên. D1: từ chối
thì không tiếp tục tạo tài khoản. Reauth/recovery không tự grant quyền mới.

Sau thao tác chủ động, ghi receipt xử lý phiên rồi receipt lưu mẫu; cả hai phải
khớp trước gửi dữ liệu đăng ký. Tuần tự hóa với refresh/withdraw bằng mutex hiện
có, không log bearer. Lỗi giữ màn đồng ý và cho retry; không tự tick/đổi version.
Giả lập giao diện không gọi API để tạo receipt thật. Luồng API chỉ báo có tài
khoản khi binding và receipt account đã lưu bền như kiểm tra hiện có.

## Kiểm chứng và tiêu chí bàn giao

- Contract examples/type/SDK/server/client đồng bộ; request/receipt lạ bị chặn.
- Thiếu/sai version/sai phiên/withdrawn/hết hạn/reauth không ghi danh và không
  trích mẫu; cờ config không thay receipt. Test cả hai điểm kiểm server.
- Hai grant/retry và grant/withdraw/enrollment đồng thời không dùng receipt cũ
  để vượt chốt; giữ test real/mixed/account-bound 503 đang có.
- Android không tick sẵn, policy đổi không tự grant, lỗi mạng không tiến tiếp,
  refresh dùng bearer mới, withdrawal dừng upload, chưa có account không báo mở.
- Chạy test/lint phù hợp, Android testDebugUnitTest/assembleDebug; ghi ảnh màn
  đồng ý trước/sau bằng Paparazzi. Cập nhật task/backlog/handoff, không sửa STATUS.
- Giữ nhánh local, không push/PR. Người dùng tự nghiệm thu camera/micro/thiết bị.

## Các điều kiện chưa thể thay bằng code

Chưa có bộ video/lịch/nhãn/nhóm người đúng protocol; không fit từ fixture tổng
hợp hoặc từ test. Các protocol ChromaPulse, LVFace/danh tính/continuity và giọng
cần artifact và đánh giá riêng. Chưa thay thiết kế guard OTP hoặc cho phép ghi
danh thật từ OTP demo. Không gọi các mục này hoàn tất chỉ vì server health xanh.

Chỉ triển khai thay đổi SEC-09 sau review thiết kế và kế hoạch theo workflow.
Tài liệu quay và kiểm lại runtime hiện có có thể thực hiện ngay, không mở chốt.
