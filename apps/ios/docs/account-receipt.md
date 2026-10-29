# Receipt độc lập — IOS-02, chặng 1

## Nguồn hợp đồng và phạm vi

**Cập nhật nối tài khoản:** receipt-only trong tài liệu này vẫn là kho legacy,
không được tự gán alias để đăng nhập. Bản mới có kho binding riêng và đã nối
Auth/L0/media signing opt-in, mặc định tắt, chưa chạy test wiring/nghiệm thu.
Xem [account-binding.md](account-binding.md); lịch sử kiểm chứng dưới đây không
chứng minh bản wiring mới đã hoàn tất.

Đối chiếu `packages/contracts/schemas/session.schema.json` và OpenAPI tại commit
Android `f034fa9406ea9aef1ee86365ce82142de517d553`:
`account_id` là `acct_` + 32 ký tự hex thường, `device_id` là `dev_` + 32 ký tự
hex thường, `expires_at` là ISO 8601. Không thay đổi `packages/contracts/` local.
Backend trên nền IOS-06 chưa có GET account: cần backend tương thích để kiểm chứng
tích hợp. Không tạo receipt mẫu khi GET trả 404 hoặc lỗi khác.

Đã nối receipt, **chưa hoàn thành đăng nhập lại thật**. Receipt chỉ là tham chiếu,
không thay thế device proof, không chứa khóa ký và không dùng để bỏ bước xác thực.
Không thay đổi camera, điều hướng hay theme. Số tài khoản mẫu trên UI vẫn giữ nhãn
“Dữ liệu mẫu”, không lấy account_id làm số tài khoản ngân hàng.

## Luồng

- `AccountReceipt` kiểm ID/ngày khi decode; kiểm hết hạn trước lưu và khi load.
- `SessionApi.accountReceipt` GET `/v1/sessions/{id}/account`, Bearer token hiện tại,
  `Cache-Control: no-store`, không body. Map lỗi qua `ApiError` hiện hữu.
- Voice có thể trả `account`. Receipt đính kèm hỏng bị bỏ qua để có thể GET lại;
  status và các trường cốt lõi của voice vẫn decode nghiêm ngặt.
- Success màn live kích hoạt collector riêng do LiveFlow giữ; chỉ pass thật của
  onboarding/recovery được phép lấy/lưu. Demo, review và reauth không tạo receipt.
- Lỗi receipt tách ở `receiptIssue` (`api`, `invalidReceipt`, `storage`), không đổi
  kết quả pass, không gửi lại sinh trắc. Gọi `receiptAfterPass()` để thử lại metadata;
  lỗi lưu chỉ thử lưu lại, không GET thừa. Không tự retry vô hạn.
- Collector sống qua chuyển Success sang màn tài khoản; reset/rời luồng hủy request
  và loại response trễ. Reset xóa state trong RAM, không xóa receipt đã lưu hợp lệ.

## Kho riêng

`AccountStore.shared` là actor nối tiếp các lệnh Security, tránh chặn MainActor.
Kho Keychain riêng `vn.vericlue.account-receipt` / `receipt.v1`, không đồng bộ iCloud,
`WhenUnlockedThisDeviceOnly`. Không thêm entitlement hay sửa project.pbxproj.
Theo [Apple](https://developer.apple.com/documentation/security/ksecattraccessiblewhenunlockedthisdeviceonly),
item chỉ truy cập khi mở khóa và không di chuyển sang thiết bị khác qua restore.

Chỉ encode ba trường receipt, không session token/ảnh/audio/video; không log giá trị
receipt/token. Unknown JSON fields không được lưu lại. `load()` xóa dữ liệu hỏng
hoặc hết hạn; lỗi Keychain bị khóa/không sẵn sàng được trả về, không coi là corruption
để xóa dữ liệu. `save()` update trước, không xóa receipt cũ trước khi ghi thành công.
`clear()` xóa đúng item riêng, không xóa toàn Keychain. Cả ba API được gọi bằng
`try await`; chưa thêm UI quản lý receipt hay tự dùng receipt để đăng nhập.

## Bằng chứng và bước kiểm tra còn lại

Hướng dẫn thực hành: [backend riêng và Keychain trên iPhone](receipt-device-checklist.md).
Probe DEBUG dùng cùng storage với service kiểm tra riêng; không tạo receipt của
luồng thật. Backend tham chiếu từ chối ghi danh mock/mixed, nên chạy bản có endpoint
không đồng nghĩa có thể nhận receipt thật từ một phiên mock.

19 hàm test mới trong `AccountReceiptTests.swift`, `ReceiptFlowTests.swift`:
codec, trường thiếu/hỏng/hết hạn, GET/status/network, storage lỗi/clear, pass/review,
voice optional, token rotation, retry metadata không resubmit, reset/response trễ.
MockURLProtocol và kho RAM, không mạng/Keychain thật. Hai suite receipt đã chạy xanh.

Build test bundle Simulator và Release iPhone không ký thành công (xem bàn giao).
Một lượt toàn bộ test: 123/124 đạt, unit bundle Passed, UI `testDebugGalleryOpens`
timeout khi tổng hợp event; chưa kết luận nguyên nhân app hay Simulator. Ngày 28/10,
sếp xác nhận probe Keychain trên iPhone đạt ghi/đóng mở/đọc/xóa/hỏng/hết hạn và
app giữ thành công sau GET account 409. Xem nguồn bằng chứng trong checklist.
Chưa kiểm chứng GET 200 receipt thật → lưu kho live → đọc sau đóng/mở. Không đưa
receipt/token thật hoặc file sinh trắc vào báo cáo/commit.

Kiểm lại riêng `testDebugGalleryOpens` theo yêu cầu sếp: **1/1 Passed, 0 failed,
0 skipped**, không sửa assertion. Kết quả 123/124 ở trên là lượt toàn bộ trước đó;
không đổi thành tuyên bố toàn bộ 124 bài vừa chạy xanh. Backend riêng có accounts=0,
health mock_models=true; chưa có phiên đủ điều kiện GET 200 receipt thật.
