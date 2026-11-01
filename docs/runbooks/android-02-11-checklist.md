# Thử VeriClue trên điện thoại ngày 02/11

Gói trên laptop: `D:/vericlue/tmp/phone-demo-2026-11-02/`.
Đây là **model thật, ngưỡng tạm chưa hiệu chỉnh, OTP mô phỏng**.
Chưa nghiệm thu ba luồng trên điện thoại; một lượt có thể bị từ chối.

## Mở bộ demo

1. Mở `START-DEMO.cmd`, đợi `READY` (cold start tối đa 5 phút).
2. Cắm một điện thoại bằng USB; mở khóa, bật và cho phép USB debugging.
3. Mở `CONNECT-PHONE.cmd`. Công cụ kiểm chứng chỉ nếu đã có app, cài đè `-r`,
   nối cổng8421 và mở app. Giữ USB kết nối. Nếu khác chứng chỉ thì dừng, không
   gỡ app hoặc xóa dữ liệu để vượt lỗi.
4. Cho phép camera/micro và tự chọn đồng ý trong app. Mã OTP hiển thị trong
   SMS mô phỏng của lượt gửi, không có mã cố định. Giữ laptop hoạt động khi thử.

`STATUS-DEMO.cmd` kiểm tiến trình và đúng instance/mode/policy, không chỉ thấy
cổng mở. `STOP-DEMO.cmd` dừng đúng tiến trình của gói kể cả khi HTTP bị lỗi.
Source và APK được kiểm hash trước khi chạy; DB/media/khóa mới riêng, không
khởi động launcher cũ. Không gửi `.env`, CCCD, video mặt hoặc giọng lên GitHub.

## Phiếu thử thực tế — chưa điền kết quả

Tất cả mục dưới đây hiện là **not_run**, không được đánh dấu từ unit test.
Dùng người tham gia đã đồng ý và CCCD của họ.

- [ ] Đăng ký: hai lựa chọn đồng ý chủ động, OTP, QR/chân dung, xác nhận thông
  tin, nhìn chấm/quay đầu; đọc câu nếu app yêu cầu. Kết quả có nhãn demo; thiếu
  consent bị chặn. Nếu phiên đạt nhưng thiếu receipt/lưu lỗi, phải báo tài
  khoản chưa lưu, không mở tài khoản hoặc tự nhận đã sẵn sàng đăng nhập lại.
- [ ] Đóng/mở lại app: nhận đúng tài khoản và vẫn hiện nhãn demo.
- [ ] Đăng nhập lại: ký thiết bị/L0 và các bước app yêu cầu; không đổi tài khoản
  hoặc mất khóa sau restart.
- [ ] Khôi phục trên cùng app đang giữ tài khoản: app tạo alias mới, thực hiện
  OTP/CCCD/mặt/giọng theo luồng; tài khoản giữ nguyên, binding mới chỉ thay khi
  kết quả và receipt đã lưu. Đóng/mở rồi đăng nhập lại. Không cần máy thứ hai.
- [ ] Sai câu, giọng nhỏ, lệch mặt, từ chối camera/micro, mất kết nối và lượt
  bị model từ chối: không tự chuyển sang kết quả đạt hoặc xóa tài khoản cũ.
- [ ] Dừng/mở lại server rồi kiểm đăng nhập lại; xác nhận độ trễ CPU thực tế.

Ghi giờ, bước, chữ lỗi và kết quả từng mục. Ảnh màn hình gửi nhóm phải che thông
tin cá nhân. Lỗi kỹ thuật xem `server/server.err.log`; không sửa ngưỡng theo
người thử. Xem [policy và smoke](manual-face-demo.md).

## Các điểm còn chưa hoàn thiện

1. Nghiệm thu điện thoại: ba luồng, quyền camera/micro, CCCD/QR, clock audio–video,
   giữ/đổi khóa và tài khoản, gián đoạn/restart, độ trễ. Chưa cài APK mới lên máy.
2. SyncNet: đã nạp trọng số và forward tensor hữu hạn; chưa có video mặt–giọng
   hợp lệ để xác nhận crop, offset và pipeline lipsync thực tế.
3. Chất lượng AI: ngưỡng demo là hằng số minh họa; chưa có bộ hiệu chỉnh/đánh giá
   đủ giọng thật + TTS/VC và mặt/tấn công, quyền sử dụng, nhóm người/nguồn. Chưa
   fit/chọn LTT hoặc báo cáo FAR/FRR/APCER/BPCER trên tập độc lập. VIVOS parity
   không được đưa vào hiệu chỉnh. Chế độ standard/protected vẫn giữ chốt.
4. OTP là mô phỏng; chưa có SMS thật, chip/NFC hoặc đối chiếu CSDL nhà nước.
5. HTTPS/phát hành và nghiệm thu sản phẩm không nằm trong gói USB demo này;
   signer debug laptop được giữ, khác signer phát hành trong repo.

APP-01/FLOW-04/SEC-09 vẫn `doing`; sẵn sàng bắt đầu thử máy không đồng nghĩa
đã hoàn thành nghiệm thu hay chứng minh hệ thống chống giả mạo đạt yêu cầu.
