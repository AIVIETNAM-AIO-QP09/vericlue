# Receipt gắn khóa, Auth/L0 và ký media — iOS

Nguồn port: Android upstream `54acaad`, AccountFlow/AccountStore/LiveFlow và
security/MediaProof/DeviceProof. **Đã kiểm ký mặt/giọng và khóa thử trên iPhone;
receipt thật/account-bound còn bị backend chặn. Kết quả test theo từng bản bên dưới.**
Không thay backend, migration, contracts, detector hoặc ngưỡng.

## Bật đúng cấu hình

- `SIGNED_MEDIA=NO` mặc định cho cả Debug/Release, như Android signedMedia=false.
- Thử opt-in bằng build setting `SIGNED_MEDIA=YES` (CLI thêm vào xcodebuild;
  Xcode: target VeriClue → Build Settings → User-Defined → SIGNED_MEDIA → YES).
  Tắt lại NO nếu tiếp tục demo backend unsigned cũ. Không bật nếu backend chưa
  hỗ trợ cùng protocol/migration; không tự hạ xuống unsigned trong phiên signed.
- Bật cờ chỉ nối giao thức, không mở chốt server hay tạo receipt thật trên mock.
- Khi tắt ký hoặc chưa có binding, chọn đăng nhập/khôi phục sẽ về đăng ký với lời
  nhắc, giống Android. Demo offline trong Gallery vẫn đi ba purpose như trước.

## Receipt và khóa là hai kho riêng

- Legacy AccountStore lưu receipt-only vẫn dành cho checkpoint cũ; không dùng
  receipt đó để đoán khóa hay mở tài khoản. AccountBindingStore có service Keychain
  riêng `vn.vericlue.account-binding.v2`, một JSON gồm receipt + key_alias.
- Load hỏng/hết hạn/thiếu alias coi như chưa có; lỗi Keychain khóa/unavailable
  không xóa binding cũ. Save cập nhật nguyên item, không xóa trước ghi.
- Khóa riêng không nằm trong JSON. DeviceKeyStore giữ khóa P-256 trong Secure
  Enclave trên iPhone; Simulator có nhánh Keychain phát triển. Dùng access-control
  privateKeyUsage cho phép ký, không yêu cầu thêm Face ID so với luồng Android.
- Không gọi API xuất khóa riêng; chỉ public key SPKI và chữ ký DER/base64 đi HTTP.
  Không log receipt, token, alias hay message ký.

## Điều phối

1. Auth tạo AccountEntry mới, chặn bấm trùng khi đang đọc kho/khóa. Entry cố định
   purpose/receipt/alias/signer cho LiveFlow; đổi số tạo lại phiên nhưng giữ đúng entry.
2. Reauth có binding nhưng mất khóa → recovery_required; open(create:false),
   không tạo khóa mới thay thế. Lỗi kho không giả làm chưa có khóa.
3. Tạo reauth session gửi account_id/device_id, **không** gửi public key mới.
   Kiểm device_challenge context/hạn/base64, ký nguyên byte rồi POST device-proof.
   Chỉ giữ session/token sau received=true; 401/409/ACK false hoặc response trễ
   không tạo session dùng được.
4. Onboarding/recovery signed gửi public key mới khi tạo phiên; recovery gửi
   account_id cũ. Giữ ngoại lệ recovery iOS bỏ CCCD và OTP tổng 5 lần sai/phiên.
5. Trước media/voice, hash đúng Data/filename/offset đã giữ cho lượt. Công việc
   hash/canonical chạy ngoài MainActor, ký qua lớp khóa. Thiếu seed, ký lỗi hoặc
   challenge sai → lỗi, không gửi unsigned. Refresh/retry dùng seed/token mới.
6. Media ack xong thì không đọc/ký/gửi lại media khi signals/finalize retry. Voice
   retry dùng lại WAV/video/offset/voice ID đang chờ, không lấy tham số mới thay thế.
7. Server pass: lấy receipt (hoặc account trong voice), ghi binding xong mới trả
   success. Receipt/ghi kho lỗi không đổi pass và không resubmit sinh trắc; có thể
   gọi receiptAfterPass để thử lại riêng metadata. Unsigned không tạo binding giả.
8. Recovery kiểm cùng account_id, device_id mới và alias mới. Save binding bền
   thành công rồi mới xóa alias cũ. Lỗi ghi giữ khóa cũ; lỗi cleanup giữ binding mới.
   Compare-before-save chặn ghi đè một binding đã được lượt khác thay.

OperationLease + generation hủy quyền ghi của response cũ; lease giữ lock chỉ
quanh ghi/xóa đồng bộ, không quanh await. Back/reset/hủy tác vụ không cho response
cũ đổi token/ack/binding hoặc điều hướng thành công của lượt mới.

Khi server đã pass, expiry monitor dừng trước phần metadata; lỗi/timeout lấy
receipt không đổi pass thành hết phiên. Back/Dừng vẫn hủy quyền ghi và điều hướng.

## Test thực thi ngày 29/10/2026

AccountBindingFlowTests: 15 hàm, memory storage/keys, MockURLProtocol; không mạng,
không Keychain thật. Bao phủ binding cũ/mới/lỗi, mất khóa, L0 ACK/401/409/trễ,
retry mặt/giọng, token rotation, ký lỗi/seed thiếu, receipt lỗi không đổi pass,
ghi bền trước xóa, cleanup lỗi và hai lượt recovery tranh binding.

Đã chạy đúng một lượt toàn bộ iOS: **181/183 test đạt, 2 lỗi, 0 bỏ qua**;
tính cả tham số là **208/210 runs đạt**. AccountBindingFlowTests **15/15**,
ProofProtocolTests **6/6**, ReleaseConfigurationTests **3/3** đều đạt trong lượt này.
Simulator iPhone 17 Pro, iOS 26.3.1; xcodebuild exit 65, chưa chốt toàn suite xanh.

- Kiểm chữ cấm bắt `%02x` của hàm hash trong MediaProof.swift; test đang quét mọi
  string literal, kể cả chuỗi kỹ thuật không hiển thị. Chưa sửa hoặc bỏ assertion.
- WarmThemeUITests/testDarkAccessibilityTextAndReducedMotion lỗi tại bước chờ
  `debug-gallery-title` sau tap Gallery (WarmThemeUITests.swift:22), chưa tới các
  màn OTP/confirm. Chưa đủ bằng chứng kết luận do timing hay lỗi điều hướng/layout.
- Bundle: `/tmp/vericlue-ios-account-full-20261028.xcresult`; log cùng tên `.log`.
  Tên file giữ ngày bắt đầu, lượt chạy kết thúc sau nửa đêm 29/10.

## Nghiệm thu thiết bị và phần còn chờ

### Bằng chứng iPhone đã nhận ngày 29/10

- Sếp xác nhận đủ 6 ca UI của bản sửa: dark/light, chữ lớn, Reduce Motion,
  Gallery mở bằng một lần bấm, Back Điều khoản, OTP/confirm cuộn và sửa được.
- Backend thử `tmp/receipt-backend` f034fa9, DB receipt-check.db, phiên
  `ses_706c13b149a0fbd3`: onboarding/mock/pass, có public key và dòng
  media_proof_uses stage face; accounts có 0 dòng source_session_id tương ứng.
- Phiên `ses_2b9bb769c12cb296`: scenario voice_clone, mock, trạng thái review;
  có biên nhận stage face và voice trong media_proof_uses. Đã đối chiếu mã backend:
  biên nhận được ghi sau verify ECDSA thành công, không chỉ suy từ HTTP 200.
- Chốt được ký/upload mặt và giọng cho hai lượt này; chưa chứng minh vòng đời
  khóa qua đóng/mở, binding bền, mất khóa/recovery hoặc receipt thật.
- Chưa có domain được nhóm duyệt; nghiệm thu kết nối HTTPS Release để pending.
- Sếp xác nhận checkpoint khóa riêng mới: tạo → đóng/mở app → public key không
  đổi/ký hợp lệ → xóa khóa thử vẫn giữ metadata → open(create:false) bị từ chối
  → dọn kho thử. Không phải bằng chứng lưu binding tài khoản hoặc recovery backend.
- Sếp xác nhận nhập bằng bàn phím hệ thống rồi Xong không auto verify; chụp CCCD
  và màn thành công rung nhẹ một lần. Chưa thử nhận SMS thật/QuickType suggestion.

Cập nhật bản sửa 29/10: bỏ String(format:) khỏi hash, dùng hai chữ số hex mỗi
byte; thêm vector SHA-256 cho chuỗi rỗng/abc. Nút primary/secondary đặt contentShape
ngay trong label sau frame; thêm UI regression bấm một lần vào padding trong suốt
của Gallery với dark/AX3/Reduce Motion. Không đổi bộ quét chữ cấm, không tăng
timeout, không tự tap lại khi thất bại. Bản sửa chưa được thực thi test; kết quả
181/183 ở trên là trước sửa, không được báo thành kết quả của bản mới.

### Thử trực tiếp trên iPhone

1. Xcode mở VeriClue.xcodeproj, scheme VeriClue, chọn iPhone đã Trust/Developer Mode,
   Run bản mới (không chỉ mở lại app cũ). Thử UI trước với SIGNED_MEDIA=NO mặc định.
2. iPhone Settings → Display & Brightness → Dark; Accessibility → Display & Text
   Size → Larger Text → bật Larger Accessibility Sizes, chọn cỡ lớn. Accessibility
   → Motion → Reduce Motion bật. Tên mục tùy ngôn ngữ máy.
3. Ở ngân hàng, bấm một lần giữa nút Xem tất cả màn, kể cả khoảng trống giữa các
   dòng. Phải mở Gallery. Back rồi bấm padding trái/phải của nút (không ra ngoài
   hình nút); vẫn mở. Không cần bấm hai lần hoặc chờ rồi bấm lại để đạt.
4. Gallery → Điều khoản → Back: trở về Gallery bằng một lần Back. Thử OTP/confirm:
   cuộn thấy đủ nội dung, sửa OTP bằng tay được, không auto submit; nút không bị che.
   Lặp lại light và cỡ chữ bình thường. Không dùng Gallery để chứng minh luồng API.
5. Kiểm ký riêng: chỉ đổi SIGNED_MEDIA Debug sang YES, Run lại, chọn API thật +
   genuine, đăng ký và gửi OTP. Nếu có lỗi kho/khóa hoặc cấu hình, dừng và ghi đúng
   thông báo; không sửa DB hay tạo receipt mẫu. Tới OTP/POST sessions 200 chỉ chứng
   minh một phần tạo khóa/phiên, chưa chứng minh chữ ký hoặc binding bền.
6. Với backend tương thích, đi hết mặt/giọng khi server yêu cầu; cần xác nhận phía
   server đã kiểm media_signature đúng, không chỉ thấy HTTP 200. Hiện backend mock
   không cấp receipt thật: không tick đóng/mở giữ binding, reauth/L0 thật, đổi khóa
   recovery hoặc GET receipt 200 khi chưa có tài khoản thử hợp lệ do backend cấp.
7. Khi xong, trả SIGNED_MEDIA Debug về NO; Release giữ NO. Không xóa app/Keychain
   hoặc khóa đang dùng để giả lập mất khóa nếu chưa có kế hoạch phục hồi.

Sếp báo riêng kết quả UI và ký; không gộp hai nhóm thành một mục "đều đạt".

### Checkpoint khóa mới — đã được sếp xác nhận trên iPhone

Gallery → **Kiểm tra khóa ký · DEBUG** (khác checkpoint receipt cũ):

1. Tạo khóa thử; đóng hẳn app rồi mở từ biểu tượng.
2. Mở lại/ký: public key phải như metadata đã giữ, chữ ký hợp lệ; dữ liệu bị sửa
   không qua. Không dùng open(create:true) để thay khóa mất.
3. Xóa khóa thử nhưng giữ metadata: open(create:false) phải bị từ chối.
4. Dọn khóa và metadata thử.

Metadata có service Keychain riêng `vn.vericlue.debug.device-key`, chỉ chứa alias
thử/public key, không receipt/token. Chỉ nhận alias `vericlue.media.debug-check-`
kèm UUID; từ chối mở/xóa nếu metadata trỏ sang alias tài khoản. Lưu handle trước
tạo khóa để vẫn có thể dọn khi tác vụ bị gián đoạn. Không có thao tác mạng.
Simulator không được dùng làm bằng chứng Secure Enclave. Toàn bộ checkpoint nằm
trong `#if DEBUG`, artifact Release kiểm không có marker của nút này.

- Xử lý hai lỗi toàn suite rồi kiểm chứng bản sửa theo yêu cầu, không nới assertion.
- Khóa thử thật đã đạt; binding tài khoản bền và mất khóa dẫn recovery thật còn chờ.
- Ký mặt/giọng thật đã có biên nhận. Proof sai/seed cũ/không downgrade có test tổng
  hợp; không ghi thành ca tấn công đã thử trên iPhone/backend thật.
- GET receipt 200 thật và account-bound sinh trắc còn phụ thuộc chốt backend:
  theo nguồn tham chiếu, mock không cấp receipt thật và reauth/recovery có account
  còn bị 503 flow_unavailable. Không gỡ chốt để tick nghiệm thu.
- SMS oneTimeCode/rung đã nối; nhập hệ thống/rung được sếp nghiệm thu. Gợi ý SMS
  thật còn chờ; HTTPS Release chưa có domain. Xem android-full-parity.md.
