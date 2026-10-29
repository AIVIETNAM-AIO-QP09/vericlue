# Chặng 5 — nghiệm thu theme “Tối giản ấm”

## Phạm vi

Theme nằm ở `VeriClue/UI/Theme/Theme.swift`. Đối chiếu token Android; không
thay lịch, màu flash, clock, tọa độ chấm sáng hoặc logic thu/gửi evidence.
Ảnh Simulator là bằng chứng giao diện demo, không thay nghiệm thu camera thật.

## Simulator

**Bản cuối 28/10 17:23: đạt phạm vi Simulator.** 159/159 bài, 186/186 lần thực
thi, 0 lỗi/0 bỏ qua. Bundle `/tmp/vericlue-ios-theme-final-20261028.xcresult`.

- [x] Light/dark × default/AX3, native Back Terms → Gallery 3 vòng mỗi cấu hình.
- [x] AX3: xóa mã, nhập sai, thấy 4 lượt demo còn lại, nhập đúng; đủ số không
  tự xác nhận, xác nhận đúng mới tới chụp CCCD, Back về OTP giữ code.
- [x] Cuộn đủ tên/ID/ngày/giới tính/địa chỉ confirm; nút đúng/sửa còn bấm được.
- [x] Xem ảnh cuối OTP/confirm AX3 cả hai theme, welcome/success dark có VC.
- [x] Release không ký build được; review diff phần sửa và diff --check sạch.

28 ảnh theme cuối nằm trong `/tmp/vericlue-ios-theme-final-qa/manifest.json`.
Các kết quả chưa xanh bên dưới là lịch sử trước bản cuối, giữ để đối chiếu.

Ma trận tự động trong `WarmThemeUITests`: light/dark × cỡ chữ mặc định/AX3.
AX3 bật override Reduce Motion chỉ trong Debug. Mỗi cấu hình mở welcome,
terms, OTP, review hai mặt, confirm và success; lưu ảnh vào xcresult.
Kiểm tra nút Gallery ≥44 pt, Đăng ký ≥56 pt, Back và nhãn “Dữ liệu mẫu”.
Các ảnh cần được xem trực tiếp, không chỉ dựa vào test element tồn tại.

Lịch sử đầu chặng 5: lượt toàn bộ 159/159 bài đạt, 186 lần thực thi. Đã xem 24 ảnh.
Lượt kiểm riêng dark sau thêm chờ chụp ảnh: 0/1 đạt ở Back Terms → Gallery;
welcome hiện đủ VC. Chưa chốt Simulator hoàn toàn. AX3 còn cần bằng chứng
cuộn đến OTP/fields và cuối nội dung. Chi tiết trong bàn giao chặng 5.

Lượt sửa tiếp theo: demo/Gallery dùng binding chuẩn SwiftUI, luồng API thật
giữ adapter Back có chốt capture. Màn confirm demo dùng cùng component màn
thật; chữ lớn xếp label/value dọc. Keypad giữ số lớn, bỏ ABC phụ ở cỡ AX.
UI test tăng Terms thành 3 vòng Back/push mỗi cấu hình, có nhập OTP sai/đúng
và cuộn đủ 5 trường confirm. Dark AX3 đã đạt; ca light AX3 riêng 1/1 đạt,
trace route xác nhận đủ 3 vòng. Sau đó lượt toàn bộ cuối đã xanh như kết luận
đầu mục này; không dùng lịch sử 159/159 thay kết quả source mới.

`WarmThemeTests` kiểm token, độ tương phản chữ, font đã bundle, chính sách
Reduce Motion/camera và màu flash không đổi. Đây không phải đo fps hay
chứng minh chất lượng thu camera trên điện thoại.

## iPhone — lượt nghiệm thu bản sửa mới

Ngày 28/10/2026, sếp xác nhận tất cả bốn nhóm A–D trên bản mới nhất đều đạt.
Đây là nghiệm thu thủ công do sếp báo, không phải agent tự thao tác iPhone.
Không dùng kết quả chặng 4 thay thế, không tự bổ sung số đo/log chưa được gửi.
Model/iOS và thời điểm Run cụ thể của lượt này chưa được xác nhận lại.

### Chuẩn bị

1. Mở `VeriClue.xcodeproj`, chọn scheme VeriClue và iPhone ở thanh Run Destination;
   Product → Run. Không dùng bản app cài trước lượt sửa Back/chữ lớn.
2. Mac/iPhone cùng mạng. Debug hiện trỏ `192.168.1.12:8001`; kiểm IP thực của Mac
   trước khi chạy nếu mạng đã đổi. Backend 8001 cần chạy; không tự chuyển sang
   API 8000 với chính sách OTP cũ.
3. Ngân hàng → Xem tất cả màn → API thật → genuine. Ghi model/iOS và thời điểm
   Run; source đang là worktree chưa commit, không ghi thành commit sạch.

### A — theme, Back và chữ lớn

Light/dark: Gallery → Điều khoản → Back, lặp ba lượt, mỗi lượt một lần bấm Back
phải về đúng Gallery. Kiểm VC welcome/success. Vào Settings → Accessibility →
Display & Text Size → Larger Text, bật Larger Accessibility Sizes và tăng chữ.
Mở OTP: cuộn thấy đủ sáu ô, sửa mã bằng keypad được, đủ sáu số không tự xác nhận.
Confirm: cuộn thấy đủ tên/ID/ngày/giới tính/địa chỉ, nút không che vùng đang đọc.
Bật Reduce Motion: không ảnh hưởng lịch thử thách, chỉ chuyển động trang trí.

### B — CCCD và camera

Đăng ký thật; tự chụp một mặt, nút tay mặt còn lại; không chuyển màn hai lần.
Review có đủ hai ảnh, retake giữ mặt còn lại. Home khi đang chụp → mở lại không
crash; không tự chuyển màn do tác vụ cũ. Không gửi ảnh/QR thật vào chat hoặc Git.

### C — quay, sửa và mất mạng

Quay xong mới confirm; sửa tên/ngày, số CCCD khóa. Tắt Wi-Fi và dữ liệu di động
trước confirm: báo lỗi, giữ draft/video, không media/success. Bật mạng trước
deadline rồi thử lại. Đối chiếu log cùng session: confirm → media → signals →
finalize; JSON ngày ISO, tên sửa, ID gốc. Không xuất token/dữ liệu định danh ra
bàn giao. Chi tiết expiry/retry ở checklist post-face-confirm.

### D — Home/Back/Dừng và cleanup

Một lượt mới: Home khi quay → dừng an toàn/quay lại chuẩn bị; không upload lượt
đã hủy. Back confirm hỏi dừng; Tiếp tục giữ lượt, Quay lại chuẩn bị bỏ bản cũ,
Dừng xác minh về ngân hàng. Gallery → Kiểm tra file tạm · IOS-06: sau dừng hẳn
file thu trong app bằng 0. Sau thành công/ack kiểm cleanup theo cùng chính sách.

### Ghi kết quả

```text
Model/iOS:
Thời điểm Run / nhánh / HEAD + worktree:
API / scenario:
A (light/dark, Back, chữ lớn, Reduce Motion): đạt/chưa đạt + chi tiết
B (CCCD auto/manual, retake, Home):
C (confirm sau mặt, sửa, offline/retry, thứ tự API):
D (Home/Back/Dừng, file tạm):
```

### Kết quả đã ghi nhận theo xác nhận của sếp

- [x] A: light/dark, Back, chữ lớn.
- [x] B: CCCD auto/manual, retake, Home.
- [x] C: quay → sửa/confirm, mất mạng rồi thử lại, đúng thứ tự API.
- [x] D: Home/Back/Dừng, file tạm về `0` sau dừng hẳn.

Không suy rộng xác nhận này thành số đo fps, thời lượng, log endpoint hoặc ca
hết hạn mới chưa được báo riêng. Khi bổ sung model/iOS/thời điểm Run, ghi đúng
thông tin sếp cung cấp, không đoán từ thiết bị đã dùng trong lượt nghiệm thu cũ.
