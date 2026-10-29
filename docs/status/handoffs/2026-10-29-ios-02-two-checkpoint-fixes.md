# Bàn giao — IOS-02 — sửa hai lỗi kiểm chứng 29/10/2026

Nhánh: feat/IOS-07-release-handoff. Chưa commit/push; task vẫn doing.

## Thay đổi

- MediaProof.sha256 xuất hai chữ số hex lowercase qua bảng ASCII, không dùng
  format `%02x`. Giữ nguyên kiểm chữ cấm và contract/hash SHA-256. Thêm hai vector
  chuẩn chuỗi rỗng/abc để bắt lỗi zero-padding và chữ hoa.
- Primary/secondary button đặt contentShape trong label sau padding/frame để vùng
  trong suốt cũng nhận chạm. Không đổi lịch/clock/camera/signing hoặc điều hướng.
- Thêm ca UI dark AX3/Reduce Motion bấm padding Gallery đúng một lần rồi Back;
  giữ nguyên ca UI cũ, không tăng timeout, không tap lại để che lỗi.

## Bằng chứng và giới hạn

Lượt test trước sửa: 181/183 identities, 208/210 runs đạt, 2 lỗi, 0 bỏ qua;
AccountBindingFlow 15/15, ProofProtocol 6/6, ReleaseConfiguration 3/3 đạt.
Bundle `/tmp/vericlue-ios-account-full-20261028.xcresult`.

Cây accessibility tại lỗi UI vẫn ở ngân hàng, Gallery button frame
`x20 y663 w362 h157`; XCTest tap `x201 y741.5`. Bằng chứng này chưa xác định
duy nhất nguyên nhân. Vùng hit-test trong label được sửa để phủ padding/khoảng
giữa dòng; vẫn cần rerun hoặc thao tác iPhone để xác minh hiệu quả, không tuyên bố
đã nghiệm thu chỉ từ source/build. Graph cũ/thiếu file mới nên đọc source trực tiếp.

Theo quy ước sếp: viết test, chỉ build-for-testing, không thực thi test trong lượt
sửa này. Debug build-for-testing **exit 0**, không thấy warning/error trong log
`/tmp/vericlue-ios-two-fixes-build-20261029.log`. `git diff --check` sạch.
Hướng dẫn iPhone chi tiết: `apps/ios/docs/account-binding.md`, mục Thử trực tiếp.

## Chưa xong / câu hỏi cho nhóm

- Cần kiểm lại hai lỗi trên bản mới. Không dùng kết quả test cũ làm kết quả sau sửa.
- Khóa thật/binding/L0/account recovery cần iPhone + tài khoản thử backend hợp lệ;
  mock không cấp receipt thật. Không gỡ chốt, không sửa DB hay tạo receipt mẫu.
- Cấu hình SIGNED_MEDIA giữ NO ở Debug/Release, IP/cổng Debug local không đổi.

## Bước tiếp

1. Run bản mới trên iPhone, thử dark/chữ lớn/Reduce Motion, Gallery/Back/OTP/confirm.
2. Khi sếp yêu cầu, chạy test kiểm bản sửa, giữ nguyên assertion.
3. Nghiệm thu signed với backend tương thích, tách riêng khỏi UI; review diff sau đó.
