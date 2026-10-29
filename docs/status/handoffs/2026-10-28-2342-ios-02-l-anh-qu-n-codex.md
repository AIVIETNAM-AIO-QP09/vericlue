# Bàn giao · IOS-02 · Lý Anh Quân+Codex · 2026-10-28 23:42

**Nhánh:** feat/IOS-07-release-handoff (giữ cả phần IOS-07 chưa commit)
**Trạng thái task sau phiên này:** doing — nối code tài khoản, chờ test/iPhone

## Cập nhật kiểm chứng 29/10/2026 — chưa chốt xanh

Theo yêu cầu sếp, chạy đúng một lượt toàn bộ iOS, không sửa code hoặc chạy lại:

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=F4629DA5-E113-4A6A-82EC-B2F27454F6AF' \
  -derivedDataPath /tmp/vericlue-ios07-debug \
  -resultBundlePath /tmp/vericlue-ios-account-full-20261028.xcresult \
  -parallel-testing-enabled NO test
```

- Xcode exit **65**: **181/183 test đạt, 2 lỗi, 0 bỏ qua**; **208/210 runs** đạt
  khi tính tham số. Simulator iPhone 17 Pro, iOS 26.3.1.
- AccountBindingFlowTests **15/15**, ProofProtocolTests **6/6**,
  ReleaseConfigurationTests **3/3** đạt trong đúng lượt toàn bộ này.
- Chữ cấm: literal format hex `%02x` trong MediaProof.sha256 bị bộ quét mọi
  literal coi là chữ UI; không phải bằng chứng UI đang hiển thị phần trăm.
- UI dark AX3/Reduce Motion: chờ debug-gallery-title sau tap Gallery không đạt
  (WarmThemeUITests.swift:22). Chưa kết luận timing hay điều hướng/layout.
- Bundle `/tmp/vericlue-ios-account-full-20261028.xcresult`, log cùng basename;
  tên file là ngày bắt đầu, kết thúc 29/10. Không nới assertion hay tự rerun.
- Kiểm lại artifact Release bằng check_ios_release.py đạt kiểm tĩnh;
  git diff --check sạch. plan_check chạy qua .venv/bin/python: 0 lỗi/10 cảnh báo
  kế hoạch (uv bị sandbox chặn cache). Không phải test TLS/thiết bị.
- Backend local 8001 healthz OK, mock_models=true; OpenAPI có account/result/
  device-proof và các field create session mới. Backend tham chiếu f034fa9 vẫn
  chặn receipt thật cho mock/mixed và account-bound sinh trắc bằng flow_unavailable.
- iPhone 14 Pro kết nối, sếp đồng ý thao tác; đã hướng dẫn bật SIGNED_MEDIA=YES
  chỉ ở Debug và thử tạo phiên. Chưa nhận kết quả thiết bị; chưa chứng minh
  create/reopen/sign/delete khóa thật, binding bền hoặc receipt GET 200 thật.

Các mục "chưa chạy" bên dưới giữ lịch sử checkpoint trước lượt kiểm này.
Trạng thái vẫn doing; bước kế tiếp là xử lý hai lỗi và hoàn tất bằng chứng thiết bị.

## Đã xong
- AccountBindingStore một item receipt+alias, không đoán receipt cũ; lease/generation
  chặn ghi từ lượt đã hủy, recovery compare-before-save giữ binding mới của lượt khác.
- AccountFlow/Auth async, chặn bấm trùng; mất khóa reauth → recovery_required,
  không tạo khóa thay thế. Tắt ký/thiếu binding → đăng ký theo Android.
- LiveFlow L0 trước công bố session/token, signed media/voice đúng byte/filename/
  offset đang chờ. Hash/canonical ngoài MainActor; retry chỉ phần chưa ack.
- Lấy/lưu receipt trước success, lỗi metadata vẫn pass; recovery ghi bền trước
  xóa khóa cũ, cleanup lỗi không rollback binding mới.
- Expiry monitor dừng khi server đã pass để metadata chờ không biến pass thành
  hết phiên; Back/Dừng vẫn revoke thao tác cũ. Assertion kiểm flag pass khi GET chờ.
- SIGNED_MEDIA=NO mặc định Debug/Release; sửa privateKeyUsage theo tài liệu Apple
  và protocol isolation, không nới concurrency hoặc xuất private key.
- Viết 15 hàm test AccountBindingFlowTests, memory keys/storage và MockURLProtocol.

## Đang dở
- Chưa thực thi test wiring/regression; 6/6 protocol trước đó không phải kết quả mới.
- Chưa nghiệm thu khóa thật/binding/L0/media proof trên iPhone và backend tương thích.
- Domain HTTPS/Release và SMS AutoFill/rung còn riêng; không gỡ chốt server để demo.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Khi sếp cho phép: chạy AccountBindingFlowTests, ProofProtocolTests và regression
   LiveFlow/receipt/OTP/capture; sửa lỗi nếu có, không nới assertion.
2. iPhone + backend tham chiếu: bật SIGNED_MEDIA=YES, thử khóa qua đóng/mở,
   mất khóa/L0, media proof, metadata lỗi và giữ/xóa khóa đúng thứ tự.
3. Tiếp tục UX còn thiếu rồi nghiệm thu HTTPS; review/PR/commit/push khi sếp yêu cầu.

## Quyết định, lưu ý, bẫy
- Giữ recovery iOS bỏ CCCD và ngân sách OTP tổng 5 sai/phiên.
- Legacy receipt collector chỉ cho đường không có AccountEntry; đường Auth mới
  ký xong/lưu binding trước Success. Không đổi pass thành lỗi do metadata.
- Bộ lớp/endpoint mới cần backend/schema tham chiếu Android 54acaad; không sửa
  packages/contracts, services/api, ADR, thresholds hoặc STATUS trong lượt này.
- Bật flag không mở account-bound sinh trắc: 503 flow_unavailable và không ghi
  danh mock/mixed vẫn phải giữ. Chưa có bằng chứng GET receipt 200 thật.
- Không commit/push, không thay IP/cổng Debug local hoặc signing team.

## Câu hỏi cho nhóm
- Backend/migration/domain dùng nghiệm thu ký và account-bound khi các chốt đã đủ điều kiện?

## Test đã chạy
Không chạy test theo yêu cầu hiện hành; chỉ compile app/test bundle. Bản cuối:

- Debug app + test bundle: build-for-testing **exit 0**, log
  `/tmp/vericlue-ios-account-binding-final.log`.
- Release iPhone không ký: build **exit 0**, log
  `/tmp/vericlue-ios-account-binding-release.log`.
- Không thấy error/warning trong hai log cuối. Release dùng
  `API_BASE_URL=https://build-check.invalid/` chỉ để compile, không kết nối thật.
- Artifact check đạt; plist built Release `SIGNED_MEDIA=NO`, không ngoại lệ ATS
  hoặc marker debug theo script quét. Không phải kiểm chứng TLS/backend/thiết bị.
- Diff whitespace sạch, plan_check 0 lỗi/10 cảnh báo kế hoạch.
- Debug.xcconfig vẫn chỉ có diff local 8000→8001 từ trước; không sửa backend,
  packages/contracts hay STATUS. Không commit/push.

Lệnh build từ gốc repo:

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios07-debug build-for-testing
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue-Release \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios07-release CODE_SIGNING_ALLOWED=NO \
  API_BASE_URL=https://build-check.invalid/ build
```

Không có kết quả thực thi 15 test wiring mới; không dùng kết quả xanh bản cũ thay.

Các lượt compile phát hiện warning isolation của protocol/key store/StoredAccount/
AccountReceipt. Đã sửa bằng nonisolated ở value/protocol thuần và dùng actor cho
I/O, không tắt concurrency check hoặc nới assertion. Khóa Secure Enclave dùng
privateKeyUsage theo [Apple](https://developer.apple.com/documentation/security/protecting-keys-with-the-secure-enclave),
không suy compile thành bằng chứng khóa thật.
