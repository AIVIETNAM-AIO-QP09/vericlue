# Thử hướng dẫn quay đầu Android — APP-01

Từ bản sửa sáng31/10, app không tự mở phần tập nữa. Các composable tập còn
trong mã/ảnh thử, không nằm trong điều hướng xác minh. Không có nút bỏ qua thử
thách thật; đăng nhập lại thụ động giữ nguyên.

1. Để điện thoại ngang mắt, giữ cả mặt trong camera; không cố áp mặt sát oval.
2. Quay nhẹ theo mũi tên/lời nhắc. Khi nghe “Dừng, giữ yên” hoặc hai bíp ngắn,
   dừng quay. Mũi tên biến mất, khung xanh là hướng dẫn local.
3. Khi nghe “Nhìn thẳng” hoặc một bíp dài, quay về giữa. Nếu nghe “Quay nhẹ lại”,
   giảm góc quay; nếu nhắc giữ đầu thẳng, giảm nghiêng/cúi/ngẩng.
4. Lượt xác minh vẫn theo thứ tự/thời gian server;
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

Nếu người thử đang sẵn sàng, thêm `-e audible true` trước tên runner để phát
một câu cố định ở âm lượng app. Không chạy nếu điện thoại đang bận. Probe có
thể dừng app đang mở; không quay camera, không thu âm hoặc gửi lượt xác minh.
Trace debug tag `VeriClueHeadSpeech` chỉ ghi cue cố định, accepted/ready,
start/done/error và stale callback; không ghi lời người dùng, token hay định danh.

## Chất lượng góc và làm lại

Head rules0.2 giữ yaw20–50°, tilt15°, giữ300ms, coverage80%, gap300ms và
biên cửa sổ200ms. Mẫu yaw quá50° không được tính giữ hướng; một khoảng thoáng
qua không còn phủ quyết cả video. Quá góc kéo dài vẫn không đạt; mẫu bị loại
vẫn ngắt đoạn giữ, không ghép các mẩu tư thế ngắn. Baseline và kiểm lại tư thế
trên pixel khung được chọn vẫn giữ nguyên. Chưa có bằng chứng chống tấn công.

Khi các kiểm tra chất lượng/mắt/presence đều đạt và chỉ vướng pose_out_of_range,
API cho chụp lại phần mặt một lần bằng challenge/nonce mới, hint HOLD_STILL.
Kết quả/error hiệu chỉnh sau router, gate fail, xác suất vượt chốt, lỗi model,
lượt hết hạn hoặc reauth không được chuyển thành retry theo nhánh này. Retry
không phải pass và không giải quyết thiếu artifact hiệu chỉnh.

## Giới hạn nghiệm thu

Khung xanh/giữ đủ chỉ giúp thao tác, không phải quyết định đạt. Model và ngưỡng
server giữ nguyên. Thiếu artifact hiệu chỉnh/đánh giá video-v2 PAD/GenD/danh tính
và quyền lưu mẫu SEC-09 vẫn chặn kết luận toàn bộ demo AI thật đã hoàn tất.
Lượt 23:36 ngày 30/10 chỉ dùng chẩn đoán: mắt đạt, có 126 mẫu đầu hợp lệ,
yaw tối đa 57,1°; app đã cảnh báo. Không dùng lượt đó làm bằng chứng bản mới đạt.
