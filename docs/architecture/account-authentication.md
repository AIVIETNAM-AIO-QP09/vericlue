# Tài khoản, L0 và khôi phục — FLOW-05 / SEC-02

## Phạm vi và chốt an toàn

Migration `0006_account_auth` bổ sung claim L0 và receipt khôi phục. API đã nối
receipt ghi danh, kiểm khóa đã đăng ký và service thay khóa sau đầy đủ điều kiện.
Android có model/client/kiểm ngữ cảnh/ký L0 trong LiveFlow; không đổi màn hình.

**L0 chỉ chứng minh quyền giữ khóa P-256.** Không phải Passkey/FIDO2, attestation,
nguồn camera hoặc kết quả sinh trắc. Tài khoản vẫn tự hết hạn sau 24 giờ.

Tạo phiên có account_id cho phép kiểm thử L0/OTP mô phỏng; các bước sinh trắc
account-bound vẫn trả `503 flow_unavailable`, kể cả mock. Chốt real/mixed của
luồng động vẫn giữ; không có cờ để mở. Phiên mock cũ không có tài khoản giữ hành
vi cũ. Không thể kết hợp khóa hợp lệ với sinh trắc mock để đạt hoặc thay khóa.

## Receipt và quyền truy cập

`VoiceResponse.account` chỉ có sau pass và ghi danh/khôi phục thành công trong
transaction quyết định. Chỉ gồm account_id/device_id/expires_at: tham chiếu,
không phải credential; không chứa template/public key/PII/điểm.

`GET /v1/sessions/{session_id}/account` dùng bearer của đúng phiên đã hoàn tất
để lấy lại receipt khi mất phản hồi bước giọng. Không nhận account_id tùy ý.
Sau khi thiết bị bị thay tiếp, phiên cũ không thể lấy receipt hiện hành.
Response đặt `Cache-Control: no-store`. Không có endpoint lấy template.

## L0: kiểm khóa thiết bị đã ghi danh

1. Tạo phiên `purpose=reauth`, nonce client, account_id và device_id; không gửi
   public key mới. Server kiểm tài khoản/device và lấy public key đã ghi danh.
2. Response có `device_challenge.message`: base64 của đúng các byte JSON ASCII
   cần ký. Hạn tối đa 60 giây, không vượt hạn tài khoản/token. Ràng buộc version
   `vericlue-device-auth-v1`, session_id/account_id/device_id/purpose/nonce client,
   server_nonce 256 bit và expires_at_ms.
3. Android kiểm ngữ cảnh/hạn, ký nguyên byte bằng SHA256withECDSA P-256/DER;
   gửi base64 chữ ký tới `POST /v1/sessions/{session_id}/device-proof` kèm bearer.
4. Server kiểm khóa hiện hành/chữ ký/hạn và claim session/message hash duy nhất
   trong device_proof_uses; commit cùng device_verified. Response chỉ
   `{"received": true}`, không phải verdict sinh trắc.

Sai khóa/chữ ký/hạn/phát lại trả `409 recovery_required`; sai bearer trả 401.
Mỗi bước sau kiểm account TTL/device hiện hành/claim DB; thay khóa vô hiệu hóa
cả phiên đã qua L0 bằng khóa cũ. Refresh challenge giữ bằng chứng L0 theo phiên,
không gia hạn tài khoản. Cờ device_verified không có claim hợp lệ không có giá trị.

`LiveFlow.ensureSession(..., "reauth", account=receipt)` chỉ công bố session
sau ACK L0. Lỗi không để lại session dùng được; lần thử tiếp tạo phiên mới.

## So mẫu đã lưu

`Orchestrator.run(reference_template=...)` là tham số nội bộ, ngoài DetectorInput,
JSON/HTTP/signals. Chỉ job FACE_MATCH nhận vector, ngoài repr, dùng chung instance
LVFace/hàng đợi/deadline/plaintext lease. Không nạp thêm mô hình hoặc ghi vector
vào snapshot/ModuleResult/log/HTTP.

`face.enrolled.match_enrolled` bỏ qua selfie/CCCD/nhãn góc/ngưỡng client.
Reauth chọn khung video tại 500 ms và kiểm tư thế. Recovery chọn chính diện
theo lịch server, kiểm lại ba góc từ video. Chỉ so template với chính diện;
consistency ba góc riêng, không xác nhận chiều sâu.

| Cấu hình artifact | Protocol |
|---|---|
| IDENTITY_ACCOUNT_CALIBRATION | REAUTH_MATCH_VERSION |
| IDENTITY_RECOVERY_CALIBRATION | RECOVERY_MATCH_VERSION |

Artifact MatchThreshold phải từ calib_ltt đúng version; thiếu/sai không đạt.
Không tái dùng ngưỡng CCCD hoặc tự đặt ngưỡng. Consistency và mặt–giọng giữ
protocol riêng. Mặt–giọng nhận kết quả recovery đúng version/ngữ cảnh rồi kiểm
lại nguồn video/pixel. Chưa có số liệu người thật cho các protocol mới.

## Khôi phục và thu hồi thiết bị

Tạo phiên purpose=recovery với account_id và public key mới. Server lưu device_id
hiện hành làm điều kiện thay khóa. Trước gửi OTP phải khớp HMAC số điện thoại đã
lưu; sai thì không gửi/tăng lượt/tạo mã. OTP vẫn **mô phỏng**, chưa chứng minh
quyền giữ số điện thoại ngoài đời; luồng thật chưa mở.

AccountStore.recover yêu cầu chế độ thật/mã hóa/HMAC đúng, OTP đúng số, phiên
hoàn tất pass chưa từng review, đủ các bước, mọi cổng bắt buộc đạt, enrolled
face match đúng account/version, consistency, mặt–giọng đúng lượt/hash và hai
nonce media đã dùng. Không yêu cầu quét CCCD mới.

Chỉ khi device_id chưa bị phiên khác thay mới cấp device_id/public key/DEK mới,
mã hóa lại cả envelope/payload vì AAD có device_id. Giữ nguyên account_id,
template gốc, phiên nguồn và hạn 24 giờ; không tạo tài khoản thứ hai. Thay khóa,
receipt khôi phục, audit và quyết định nằm trong cùng transaction. Constraint
chặn thay cùng thiết bị cũ hai lần; rollback giữ khóa cũ. Không gửi thông báo
cho bên tích hợp. Kết quả ký theo ADR-0013 tách khỏi receipt; xem
[signed-session-results.md](signed-session-results.md). Chốt luồng thật còn giữ.

## Còn phải nghiệm thu

- Artifact từ calibration, đánh giá độc lập, hoàn tất các cổng PAD/GenD/ánh sáng/
  giọng/khớp môi. Không dùng test để chọn ngưỡng hoặc mở chốt thật cho demo.
- Bên làm UI nối receipt/account context, lưu mã tham chiếu cùng đúng alias
  Keystore; thử trên thiết bị thật. Không cần xuất/lưu private key ra ngoài.
- Nghiệm thu kết quả ký với backend tích hợp; receipt/ACK không thay thế kết quả đã ký.

Test dùng khóa P-256 thật/HTTP/DB và verdict/vector/ảnh tổng hợp. PostgreSQL CI
kiểm claim đồng thời và hai phiên khôi phục tranh cùng khóa. Đây là kiểm chứng
triển khai, không phải đánh giá chất lượng sinh trắc.
