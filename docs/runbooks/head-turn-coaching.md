# Thử hướng dẫn quay đầu Android — APP-01

Phần tập nằm sau xác nhận CCCD, trước chuẩn bị challenge và ghi hình; đăng nhập
lại thụ động không thêm phần tập. Có thể tập lại hoặc bỏ phần tập; không có nút
bỏ qua thử thách thật. Phần tập không phải kết quả xác minh.

1. Để điện thoại ngang mắt, giữ cả mặt trong camera; không cố áp mặt sát oval.
2. Quay nhẹ theo mũi tên/lời nhắc. Khi nghe “Dừng, giữ yên” hoặc hai bíp ngắn,
   dừng quay. Mũi tên biến mất, khung xanh là hướng dẫn local.
3. Khi nghe “Nhìn thẳng” hoặc một bíp dài, quay về giữa. Nếu nghe “Quay nhẹ lại”,
   giảm góc quay; nếu nhắc giữ đầu thẳng, giảm nghiêng/cúi/ngẩng.
4. Sau phần tập mới bắt đầu lượt xác minh. Vẫn theo thứ tự/thời gian server;
   app không kéo dài lịch, ép đạt hay dùng điểm local thay quyết định API.

Giọng đọc chỉ dùng câu cố định, không đọc thông tin cá nhân. Tìm giọng Việt
offline đã cài trong các engine có sẵn trước; nếu không có thì thử giọng cần
mạng. Không tự tải giọng hoặc thay engine mặc định hệ thống. Bíp dự phòng dùng
âm lượng thông báo của máy; lời đọc dùng luồng hỗ trợ tiếp cận. Có thể chỉnh
âm lượng hệ thống. Cả hai tuân theo trạng thái tắt âm của thiết bị.

Sau khi khởi động máy/engine, câu đầu có thể chưa kịp đọc trong thời hạn lời
nhắc. App hủy câu đã cũ để tránh đọc sai hướng, dùng bíp ngay cho giữ/nhìn thẳng/
cảnh báo. Kiểm tra native ngày31/10: có giọng offline, callback lần đầu không
hoàn tất trong thời gian chờ, chạy lại có callback thành công; chưa kết luận
mọi lần khởi động engine đều đọc kịp hoặc âm nghe được trên máy.

## Kiểm tra sau khi khởi động lại laptop

- Chạy `D:\vericlue\tmp\full-demo-setup\VeriClue.cmd start` và chờ API sẵn sàng.
- Kết nối lại ADB USB/Wi-Fi; cổng Wi-Fi có thể đổi, không dùng lại mã pairing cũ.
- `adb devices`, sau đó `adb -s <serial> reverse tcp:8421 tcp:8421`.
- APK: `D:\vericlue\tmp\full-demo-setup\apk\VeriClue-demo-debug.apk`.
  Cài đè bằng `adb -s <serial> install -r <apk>`, không gỡ app/xóa dữ liệu.
- Thử một lượt mới: lời quay → giữ → nhìn thẳng, cảnh báo quay quá/đầu nghiêng;
  thử đưa app ra nền rồi trở lại. Âm cũ phải dừng, không phát sang màn giọng nói.

Native probe tùy chọn không mở camera hay phát âm nghe được:
`adb -s <serial> shell am instrument -w vn.vericlue.app.test/vn.vericlue.app.HeadSpeechProbe`.
Cần cài APK androidTest trước; callback im lặng không chứng minh người dùng nghe
rõ hoặc thao tác quay đạt trên toàn luồng.

## Giới hạn nghiệm thu

Khung xanh/giữ đủ chỉ giúp thao tác, không phải quyết định đạt. Model và ngưỡng
server giữ nguyên. Thiếu artifact hiệu chỉnh/đánh giá video-v2 PAD/GenD/danh tính
và quyền lưu mẫu SEC-09 vẫn chặn kết luận toàn bộ demo AI thật đã hoàn tất.
Lượt 23:36 ngày 30/10 chỉ dùng chẩn đoán: mắt đạt, có 126 mẫu đầu hợp lệ,
yaw tối đa 57,1°; app đã cảnh báo. Không dùng lượt đó làm bằng chứng bản mới đạt.
