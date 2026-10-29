# Bàn giao · IOS-02 · Lý Anh Quân+Codex · 2026-10-29 01:34

**Nhánh:** feat/IOS-07-release-handoff
**Trạng thái task sau phiên này:** doing — phần kiểm được đã tiến triển, còn backend/domain/SMS thật

## Đã xong
- Theo yêu cầu sếp, chạy regression sau hai bản sửa; giữ kiểm chữ cấm và native
  Back, không tăng timeout/tap lại để xanh. Lượt 185 test còn light AX3 Back lỗi;
  đã sửa test chờ đúng navigation bar Điều khoản, không chọn nút đầu toàn app khi
  bar Gallery đang rời AX. Native Back phải về Gallery đúng một lần như cũ.
- Thêm DeviceKeyProbe/DeviceKeychainCheckpoint Debug: namespace metadata riêng,
  alias prefix+UUID riêng; ghi handle trước tạo, reopen(create:false), so public key,
  ký/verify dữ liệu thử và dữ liệu bị sửa, xóa khóa thử/giữ metadata rồi dọn.
  Không có receipt mẫu hoặc request mạng trong probe, không đụng khóa tài khoản.
- OTP có sheet native .oneTimeCode/numberPad bên cạnh keypad cũ. Chỉ ASCII tối đa
  6 số; fill không verify, không reset attempts, không sửa khi busy/locked/verified.
- Rung hệ thống nhẹ một lần khi chụp xong CCCD hoặc vào Success. Gate theo sự kiện,
  reset khi retake; không thêm rung/timer vào camera trước, timeline màu/chấm/giọng.
- Bỏ build setting Release sinh NSLocalNetworkUsageDescription; giữ Debug, signing
  team, camera/micro và full-screen. Release build không ký + kiểm artifact đạt.
- Sếp xác nhận iPhone: sáu ca UI bản sửa đạt; khóa thử create/reopen/sign/mất khóa/
  cleanup qua đóng-mở app đạt; native keyboard nhập rồi Xong không verify và rung đạt.
- Backend DB chỉ đọc: ses_706c13b149a0fbd3 onboarding/mock/pass có public key và
  proof face, accounts không có dòng của phiên; GET receipt 409 là đúng giới hạn.
  ses_2b9bb769c12cb296 voice_clone/mock/review có biên nhận face và voice; mã backend
  chỉ ghi biên nhận sau ECDSA verify thành công. Chốt ký media của đúng các lượt này.

## Đang dở
- Suite UX mới đạt 190/191, 217/218 runs, 0 bỏ qua; các Back/theme đều qua, lỗi
  mới duy nhất là native OTP gõ nhanh còn 65432 thay vì 111111. Đã bỏ echo hai
  chiều draft/model, dùng một binding nguồn; giữ nguyên UI assertion. Kiểm gọn sau
  sửa gồm toàn bộ unit và đúng một UI test lỗi, theo sếp yêu cầu tiết kiệm usage.
- Đã khôi phục Debug Info.plist về $(SIGNED_MEDIA), default Debug/Release NO;
  thêm test kiểm cả hai plist không được hardcode flag. Artifact Debug sau sửa
  đọc được NO. Không đổi IP local hoặc signing team.
- Sếp chưa có domain HTTPS: chưa cài/nghiệm thu Release kết nối hay có số đo mới.
- Chưa nhận SMS thật/QuickType suggestion. Native text input đạt không thay thử SMS.
- Binding tài khoản thật, L0/account recovery còn bị backend chặn; khóa thử/receipt
  collector cũ không được dùng làm bằng chứng cho các phần này.

## Bước tiếp theo
1. Đọc kết quả quick-final (unit + UI OTP) và cập nhật tại đây. Không ghi là chạy
   lại toàn bộ UI trên bản cuối nếu chỉ chạy chọn lọc.
2. Config flag đã chốt; kiểm staged trước commit, giữ IP Debug local ngoài commit.
3. Nhận domain/backend đủ điều kiện và thử SMS thật; chỉ lúc đó tick các mục chờ.
4. Chuẩn bị commit/PR, không tự commit/push hoặc trộn cấu hình IP local.

## Quyết định, lưu ý, bẫy
- Giữ hai ngoại lệ iOS: recovery bỏ CCCD và tổng OTP sai 5/phiên qua resend.
- Backend tham chiếu f034fa9 và Android upstream 54acaad cùng chặn receipt mock/
  mixed; account-bound sinh trắc bị 503 flow_unavailable. Không gỡ chốt, seed DB,
  tạo receipt mẫu, sửa contracts/backend/STATUS/ADR/ngưỡng trong lượt này.
- Graph local cũ/thiếu Swift mới và loại tmp backend: đọc source trực tiếp ở phạm
  vi task, không dùng kết quả âm từ graph để kết luận file/chức năng không tồn tại.
- Không copy code Android vào Swift, không thêm phụ thuộc/vendor. SMS/rung dùng
  API nền tảng, tham chiếu [Apple AutoFill](https://developer.apple.com/documentation/security/enabling-password-autofill-on-a-text-input-view).
- Chưa commit/push, staged rỗng tại lần kiểm; vẫn phải rà staged trước commit.

## Câu hỏi cho nhóm
- Domain HTTPS/backend và tài khoản thử hợp lệ để nghiệm thu receipt, L0/recovery?
- Nhà cung cấp/kênh SMS thật của demo để thử QuickType AutoFill?

## Test đã chạy
- `/tmp/vericlue-ios-two-fixes-full-20261029.xcresult`: exit 65, **184/185** test,
  **211/212** runs đạt, 1 lỗi light AX3 Back; 0 bỏ qua. Hai lỗi cũ và padding mới qua.
- Key probe build-for-testing exit 0: `/tmp/vericlue-ios-key-probe-build-20261029.log`.
- UX build đầu lỗi macro #expect gọi mutating trực tiếp; sửa evaluate ra biến trước
  assertion, không đổi kỳ vọng. Bản cuối build exit 0, không warning/error:
  `/tmp/vericlue-ios-ux-parity-build-final-20261029.log`.
- Release build exit 0, không warning/error, `/tmp/vericlue-ios-parity-release-final-20261029.log`;
  API_BASE_URL=https://build-check.invalid/ chỉ để compile, không phải URL nghiệm thu.
  check_ios_release.py --app artifact: đạt, không ATS/local-network/marker Debug,
  đủ font/permission; không phải kiểm DNS/TLS/backend/iPhone.
- Ruff check/format script release đạt; plan_check qua .venv/bin/python: 0 lỗi,
  10 cảnh báo kế hoạch. git diff --check sạch ở lần kiểm.
- Lệnh regression bản UX mới (đang chạy tại thời điểm ghi):

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=F4629DA5-E113-4A6A-82EC-B2F27454F6AF' \
  -derivedDataPath /tmp/vericlue-ios07-debug \
  -resultBundlePath /tmp/vericlue-ios-parity-final-20261029.xcresult \
  -parallel-testing-enabled NO SIGNED_MEDIA=NO test
```

Lượt parity-final kết thúc exit 65: **190/191 identities, 217/218 runs**, 1 lỗi
native OTP nêu trên. Artifact lượt đó thực tế YES do plist ghi cứng; không ghi
thành nghiệm thu default NO chỉ vì CLI có override NO. Đã sửa flag và input sau
lượt đó; bundle kiểm gọn `/tmp/vericlue-ios-quick-final-20261029.xcresult`.
Protocol/binding unit dùng keys/storage tổng hợp; checkpoint iPhone riêng mới là
bằng chứng khóa thật. Sếp đã xác nhận native input/rung trên iPhone trước bản sửa
đồng bộ gõ nhanh; SMS thật chưa được thử.

## Kết quả cuối lượt kiểm gọn — chưa chốt UI OTP xanh

- Quick-final exit 65: **182/182 unit đạt**, UI OTP duy nhất được chọn vẫn lỗi
  65432 khác 111111; tổng 182/183 identities, 208/209 runs, 0 bỏ qua. Bỏ echo
  draft/model chưa giải quyết được lỗi này; giả thuyết race ban đầu chưa được chứng
  minh. Không bỏ/nới assertion, không chạy thêm toàn suite do sếp còn 4% usage.
- Config đã trở về build-setting-driven, Debug/Release mặc định NO; artifact
  Debug đọc NO, test kiểm source plist không hardcode đạt trong lượt quick-final.
- Release bản sửa cuối build exit 0, artifact check đạt:
  `/tmp/vericlue-ios-release-fixed-20261029.log`. Vẫn không có domain thật.
- Không commit/push; chưa thể ghi toàn bộ UI hoặc toàn app xanh. Cần điều tra
  tiếp ca nhập native OTP trước khi chốt; xác nhận nhập tay trên iPhone trước đó
  không thay thế assertion tự động đang thất bại.
- Sếp hỏi camera cận: source CameraSession.swift đang cố định builtInWideAngleCamera
  camera sau. Chưa sửa camera; đề xuất kiểm Ultra Wide có autofocus/macro cho CCCD,
  fallback wide, giữ nguyên camera trước/timeline. Cần nghiệm thu lại crop/QR/quality.
