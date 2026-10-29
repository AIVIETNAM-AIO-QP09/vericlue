# Đồng bộ toàn app iOS theo Android upstream

## Phạm vi và nguồn khóa

Sếp mở rộng từ Release (mức 1) sang toàn app ngày 28/10/2026. Nguồn Android:
`upstream/main` tại `54acaad` (đã fetch lại, không merge main vào nhánh đang làm).
Android có code không đồng nghĩa đã nghiệm thu trên điện thoại; giữ nguyên giới
hạn phía server, không tạo receipt mẫu hoặc mở chốt real/mixed/account-bound.

Hai ngoại lệ **sếp xác nhận giữ**:

1. Recovery iOS bỏ CCCD sau OTP, không đổi về Android H32.
2. Tổng số OTP sai tối đa 5/phiên mặc định, resend không khôi phục ngân sách.
   Backend iOS đã có commit riêng e7cfa6d; Android upstream vẫn reset khi resend.

Không phát triển tính năng ngoài Android: không thêm FIDO2/Passkey, attestation,
credential/BBS hoặc đổi detector/ngưỡng chỉ vì API backend có khả năng đó.

## Bảng công việc có thứ tự

Cập nhật kiểm chứng 29/10/2026: một lượt toàn bộ iOS đạt 181/183 test,
208/210 runs, 0 bỏ qua; AccountBindingFlowTests 15/15, ProofProtocolTests 6/6,
ReleaseConfigurationTests 3/3 đạt. Hai lỗi còn lại là quét chữ cấm bắt format hex
`%02x` và UI dark AX3 không thấy Gallery title sau tap.
Đã nghiệm thu khóa thử, ký mặt/giọng và native input/rung trên iPhone; chưa có
binding tài khoản/GET receipt 200 thật. Kết quả 184/185 ở lượt kiểm hai bản sửa
thay cho checkpoint trên: còn UI light AX3 Back. Đã siết đồng bộ đúng navigation
bar trong test, không tăng timeout/tap lại. Suite của bản UX mới cần ghi riêng.

| Chặng | Android tham chiếu | iOS hiện tại / điều kiện chốt |
|---|---|---|
| 0. Bảo toàn nền | main 54acaad, không giả định tài liệu cũ còn đúng | Đã khóa nguồn; giữ Debug.xcconfig local và phần IOS-07 đang làm |
| 1. Protocol/API/khóa | security/MediaProof.kt, DeviceProof.kt, AndroidMediaSigner.kt, data/api/Api.kt | Đã nối, ký mặt/giọng có biên nhận backend; checkpoint khóa riêng trên iPhone đạt tạo/reopen/sign/mất khóa/dọn |
| 2. Receipt gắn khóa | data/AccountStore.kt, flow/AccountFlow.kt | AccountBindingStore/StoredAccount, JSON receipt+alias nguyên tử, không gán đoán receipt-only; suite binding 15/15 đạt với memory storage/keys |
| 3. Auth theo tài khoản | AccountFlow.begin + App.kt | Đã nối Auth async: reauth mở đúng khóa cũ, mất khóa tới recovery_required; thiếu binding/tắt signed fallback đăng ký; chặn bấm trùng |
| 4. LiveFlow ký + L0 | ensureSession/prepareFace/submitFace/submitVoice | L0 trước công bố session, ký đúng byte/offset; ack/generation, không downgrade; suite binding/protocol đạt, backend/iPhone chưa chốt |
| 5. Lưu sau pass/đổi khóa | AccountFlow.finish | Persistence trước success, metadata lỗi giữ pass; lưu mới rồi xóa cũ, lease chặn side effect trễ; test tổng hợp đạt, nghiệm thu thật còn thiếu |
| 6. UX | ui/SmsConsent.kt, components/Feedback.kt | Đã nối native oneTimeCode với bàn phím hệ thống, giữ keypad cũ và không auto verify; rung tại chụp CCCD/thành công. iPhone nhập/rung đạt; chưa thử gợi ý từ SMS thật |
| 7. Release | build.gradle.kts, manifest Debug, BuildConfig.DEBUG | Đã có guard HTTPS khi build, plist riêng, scheme Release không LLDB, README/checklist và SIGNED_MEDIA=NO mặc định. Chưa domain/Release HTTPS thật/iPhone/số đo |
| 8. Kiểm chứng cuối | các test Android tương ứng + giới hạn README | Chưa hoàn tất; port test signed/account/mất khóa/ghi bền/response trễ; chạy khi sếp yêu cầu, thử thiết bị rồi review diff |

Đây là bảng tiến độ, không tuyên bố đã hoàn tất đồng bộ hoặc được nhóm review.
Không dùng 159/159 trước đây làm bằng chứng cho code Security mới.

## Quy tắc triển khai các chặng tiếp

- `SIGNED_MEDIA` phải là opt-in giống Android, mặc định false. Chỉ bật khi đã có
  backend cùng contract/migration; không tự đổi packages/contracts hoặc backend.
- Phần Security đã được live flow gọi qua AccountEntry opt-in; xem
  [account-binding.md](account-binding.md). Suite wiring đạt, toàn suite còn 2 lỗi;
  đã có kiểm khóa thử/ký mặt/giọng trên iPhone; binding/account-bound còn chờ backend,
  không báo toàn app đã nghiệm thu đầy đủ.
- Public key là SPKI P-256; chữ ký DER base64, SHA-256 trên nguyên message.
  Canonical media JSON ASCII, sorted keys mọi cấp, audio_offset_ms có null rõ ràng.
- Device proof kiểm message/base64/context/hạn rồi ký chính byte server gửi;
  ACK chỉ là đã kiểm khóa, không phải xác minh sinh trắc thành công.
- Lớp khóa iPhone dùng Security/Keychain, Secure Enclave trên máy thật; Simulator
  có nhánh keychain phục vụ phát triển. Sếp đã kiểm create/reopen/sign/delete khóa
  thử qua checkpoint riêng trên iPhone; không suy thành attestation/device proof
  server hay binding thật. Không xuất private key.
- Giữ lỗi mạng không success, confirm trước media/finalize, retry chỉ phần chưa ack;
  không thay lịch, RGB, clock, chấm sáng hoặc quality threshold để phục vụ đồng bộ.
- Tính năng Android chỉ khai báo model/API nhưng UI chưa dùng (ví dụ signed result)
  được port wrapper tương ứng; không tự mở thêm màn hoặc suy pass từ envelope.

## Các chốt backend không được gỡ

Theo docs/architecture/media-proof.md và account-authentication.md nguồn 54acaad:

- Media proof chỉ chứng minh khóa ký đúng byte/context, không chứng minh camera thật.
- GET receipt 200 cần tài khoản được ghi danh đủ điều kiện; mock/mixed không cấp
  receipt thật chỉ bằng ACCOUNT_ENROLLMENT=true.
- Account-bound reauth/recovery sinh trắc hiện bị chặn 503 flow_unavailable,
  kể cả mock. Không lấy chữ ký/L0 hoặc test tổng hợp để tuyên bố các luồng đã chạy thật.
- Backend nền IOS-06 trong working tree chưa có toàn bộ endpoint/schema mới.
  Dùng backend tham chiếu tương thích để nghiệm thu, không merge cả main ngầm.

## Build/test của chặng 1

- Debug app + test bundle compile exit 0:
  `/tmp/vericlue-ios-parity-foundation.log`.
- Release iPhone không ký compile exit 0:
  `/tmp/vericlue-ios-parity-release.log`; API override `https://build-check.invalid/`
  chỉ dành cho build, không dùng làm bằng chứng kết nối.
- Unit mới tại ProofProtocolTests.swift: vector public upstream, sửa byte/context/
  expiry, alias, Codable tương thích và HTTP multipart/device-proof. Không có private
  key hoặc media người thật. Đã chạy riêng một lượt theo sếp cho phép: **6/6 đạt,
  0 lỗi, 0 bỏ qua**, Simulator iPhone 17 Pro, iOS 26.3.1, ngày 28/10/2026.
  Bundle `/tmp/vericlue-ios-proof-protocol-20261028.xcresult`, log cùng tên `.log`.
  Không chạy toàn bộ iOS/ReleaseConfigurationTests, không gọi backend/Keychain thật.
- Lượt compile đầu lỗi test fixture gán sessionId immutable; đã sửa bằng tạo
  response mới, không thay model let hoặc nới assertion.
