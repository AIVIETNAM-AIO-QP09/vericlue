# Nghiệm thu chặng 4 — confirm sau quay mặt

## Trạng thái

Đã triển khai code. Cập nhật: sếp xác nhận nhóm A/B/C/D đạt; kiểm DB phiên
ses_525f99d660051cc5 xác nhận tên/ngày đã sửa, ngày ISO hợp lệ và HMAC ID gốc khớp.
Đã sửa ba lỗi và kiểm lại toàn bộ: **148/148 test đạt, 0 lỗi, 0 bỏ qua**;
tính cả tham số là 174/174 lần thực thi. Chốt chặng 4 xanh về code/test cùng
nghiệm thu sếp đã báo; chưa commit/push/merge, chưa làm theme chặng 5.
Xem [kết quả và lịch sử sửa lỗi](../../../docs/status/handoffs/2026-10-28-1106-ios-03-l-anh-qu-n-codex.md).
Sếp đã xác nhận 4 ca chặng 3: auto/manual không chuyển trùng, QR mặt trước,
review/retake giữ mặt kia, Home lúc chụp không crash/không chuyển bằng task cũ.
Xác nhận này không thay thế nghiệm thu chặng 4.

## Chuẩn bị

1. Build/Run Debug mới nhất bằng Xcode trên iPhone. Không dùng app cũ đã cài.
2. Backend tương thích có OTP/CCCD/challenge/media/signals/finalize; Mac/iPhone
   cùng mạng. Debug API hiện giữ `192.168.1.12:8001`; kiểm healthz nếu đổi mạng.
3. Gallery chọn API thật, onboarding, genuine; về ngân hàng bắt đầu phiên mới.
4. Dùng thẻ/QR thử tổng hợp; không đưa ảnh hoặc dữ liệu thật vào Git/bàn giao.
5. Mở terminal log backend để đối chiếu endpoint cùng session_id.

## Các ca bắt buộc

- [ ] OTP → hai ảnh → review → `/id-card` → chuẩn bị mặt (không còn màn dừng
  checkpoint chặng 3). Chưa có `/id-card/confirm` hoặc `/media` tại đây.
- [ ] Quay hết lịch, đợi đóng MP4 → màn kiểm tra thông tin. Camera không chạy
  khi đọc/sửa. Trước khi xác nhận, log không có media/signals/finalize của lượt.
- [ ] Sửa tên và ngày sinh; số CCCD khóa. Bấm lưu: JSON confirm là tên đã sửa,
  ngày ISO YYYY-MM-DD, ID gốc. Không dùng giá trị hiển thị in hoa để ghi đè
  trường server chưa sửa. Log đúng confirm → media → signals → finalize.
- [ ] Bấm xác nhận nhanh hai lần: không tạo hai request confirm khi đang gửi,
  không tạo hai chuỗi upload. Confirm đã ack không gửi lại chỉ do tap trễ.
- [ ] Tắt cả Wi-Fi/dữ liệu di động trước confirm: lỗi tại màn hiện tại, giữ
  draft và bản quay, không có media. Bật lại và thử tiếp khi challenge còn hạn.
- [ ] Để quá hạn challenge nhưng chưa hết session: màn “Lượt quay đã hết hạn”,
  giữ thông tin, file cũ được dọn. Quay lại chuẩn bị phải nhận challenge/token
  mới; không đưa MP4 cũ vào lượt mới. Không dùng thời gian phỏng đoán: đối chiếu
  expires_at của challenge, đừng ghi token vào log/bàn giao.
- [ ] Hết session: màn “Phiên đã hết hạn”, yêu cầu bắt đầu lại từ ngân hàng.
  Không đánh đồng với hết một challenge.
- [ ] Home ở confirm/edit → trở lại trước deadline: giữ draft/bản quay, không
  tự gửi. Nếu đã quá hạn thì yêu cầu quay lại. Không tiếp tục recorder ngầm.
- [ ] Back ở confirm → hỏi dừng; Tiếp tục giữ lượt; Quay lại chuẩn bị bỏ file
  cũ/thu mới; Dừng xác minh về ngân hàng và Gallery báo file thu còn 0.
  Back ở edit chỉ về confirm, không xóa evidence/draft. Chụp lại CCCD từ edit
  bỏ bản quay cũ, giữ mặt CCCD còn lại; sau thẻ phải quay mới.
- [ ] Mất mạng sau media ack: retry chỉ signals/finalize chưa ack, không gửi
  media lần hai. File video local được dọn sau media ack nhưng signals còn giữ.
- [ ] genuine nhận pass → thành công, không bắt đọc câu. Scenario cần giọng →
  dùng prompt/ID server; lỗi/status lạ không ra success.
- [ ] low_quality → retry bằng challenge mới, token hiện hành; CCCD đã confirm
  còn hợp lệ thì không bắt confirm lại. Đối chiếu endpoint cùng phiên.
- [ ] Recovery/reauth không bị đòi CCCD hoặc fields giả; theo status server.
  Không coi mock là bằng chứng đăng nhập lại/account-bound thật đã hoàn chỉnh.

## Giới hạn kiểm chứng

MockURLProtocol test kiểm được thứ tự, expiry/rotation, mất mạng/ack và phản hồi
trễ; không chứng minh writer/camera/lifecycle thực tế trên iPhone. Thu file thật
vẫn cần các ca trên. Không ghi receipt HTTP 200 đã đạt nếu chỉ gặp 409 do backend
mock không đủ điều kiện enrollment. Theme mới nằm ở chặng 5, không thuộc lượt này.
