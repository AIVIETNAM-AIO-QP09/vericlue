# Bàn giao · IOS-02 · Lý Anh Quân+Codex · 2026-10-28 23:16

**Nhánh:** feat/IOS-07-release-handoff (có phần IOS-07 chưa commit từ lượt trước)
**Trạng thái task sau phiên này:** doing — nền protocol/API, chưa đồng bộ toàn app

## Đã xong
- Sếp yêu cầu toàn app theo Android, giữ recovery bỏ CCCD và OTP tổng 5 lần sai.
- Fetch khóa Android tại upstream/main 54acaad, không merge/reset/stash main.
- Đối chiếu AccountStore/AccountFlow/keys/media/L0/API và phát hiện thêm SMS thật,
  haptic cần port. Bảng tuần tự ở apps/ios/docs/android-full-parity.md.
- Thêm optional media_nonce/device_challenge và request khóa/tài khoản; API
  proveDevice, signedResult, media_signature multipart giữ tương thích unsigned.
- Thêm MediaProof canonical/hash, DeviceProof context/deadline/exact bytes,
  DeviceKeyStore/KeychainMediaSigner cho P-256/SPKI/DER, không xuất khóa riêng.
- Viết test vector công khai upstream cùng ca sửa byte/context/hạn/HTTP/alias.

## Đang dở
- Chưa AccountStore binding/coordinator; chưa nối signer/L0 vào LiveFlow hoặc UI.
- Chưa SIGNED_MEDIA opt-in, receipt gắn khóa/khôi phục, SMS thật/haptic.
- Chưa runtime Keychain/Secure Enclave trên iPhone; protocol mới đã chạy 6/6 xanh,
  chưa chạy toàn bộ test iOS hoặc test cấu hình Release mới.
- Các file IOS-07 cùng worktree vẫn giữ; chưa commit/push thêm. Không sửa backend,
  packages/contracts, ADR, thresholds hoặc STATUS.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Protocol/API mới đã test xanh; giữ kết quả này làm checkpoint trước nối luồng.
2. Port storage binding + AccountFlow, nối Auth/LiveFlow với generation/cancel.
3. Giữ default signing false và server gates; nghiệm thu với backend tương thích.
4. Port UX còn thiếu, rồi test/nghiệm thu bản cuối theo bảng parity.

## Quyết định, lưu ý, bẫy
- Nền Security hiện chưa được live flow gọi, không báo ký thiết bị/đăng nhập đã xong.
- Không chạy Keychain thật trong unit; chưa có bằng chứng phần cứng từ compile.
- Android cũng chưa nghiệm thu mọi đường tài khoản; không nới chốt backend để giống UI.

## Câu hỏi cho nhóm
- Backend/migration/contract tham chiếu 54acaad và domain HTTPS dùng cho nghiệm thu?
- Chưa có bằng chứng GET receipt 200 thật hoặc sinh trắc account-bound đã mở chốt.

## Test đã chạy
Sếp đã cho phép chạy riêng test mới: **ProofProtocolTests 6/6 đạt**, 0 lỗi,
0 bỏ qua, Simulator iPhone 17 Pro iOS 26.3.1. Một lượt, không sửa source hoặc
tự chạy lại. Không gọi backend, không kiểm Keychain/Secure Enclave thật.
Không coi đây là toàn bộ iOS test xanh hoặc account flow đã hoàn tất.

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=F4629DA5-E113-4A6A-82EC-B2F27454F6AF' \
  -derivedDataPath /tmp/vericlue-ios07-debug \
  -resultBundlePath /tmp/vericlue-ios-proof-protocol-20261028.xcresult \
  -only-testing:VeriClueTests/ProofProtocolTests -parallel-testing-enabled NO test
```

Xcresult summary: Passed, totalTestCount=6, passedTests=6, failedTests=0,
skippedTests=0. Log `/tmp/vericlue-ios-proof-protocol-20261028.log`.

Build-for-testing Debug + Release iPhone không ký đều exit 0. Log:
`/tmp/vericlue-ios-parity-foundation.log`, `/tmp/vericlue-ios-parity-release.log`.
Release dùng API .invalid chỉ để compile. Lượt đầu lỗi fixture gán let sessionId,
đã sửa fixture và compile lại thành công, không đổi assertion/model để né lỗi.
