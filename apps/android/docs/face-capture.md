# Capture khuôn mặt và hướng dẫn chuyển động

## Khung hình

Mặt trước dùng `PreviewView.ScaleType.FIT_CENTER`, tránh crop để lấp một màn
hình dài. Mặt sau chụp thẻ vẫn dùng `FILL_CENTER`. Zoom phần cứng đặt lại 1×
khi mở camera; không tự thay đổi zoom giữa các pha khuôn mặt.

`FaceCaptureSurface` dùng oval chính tối đa 82% chiều rộng/320dp, thu lại theo
không gian đọc chữ và nút trên màn thấp/chữ lớn. Căn mặt, baseline, đổi màu và
quay đầu dùng cùng oval. Gaze thu preview vào góc phải trên bằng transform lớp
vẽ 360ms, không đổi layout/bind CameraX; khi quay đầu trở lại đúng khung chính.
Không yêu cầu người dùng căn lại theo thumbnail. Chấm giữ nguyên tọa độ toàn
màn hình và thời gian do server cấp; viền navy/tâm sáng giúp nhìn rõ trên nền.

## Điều kiện bắt đầu và hoàn tất

- Một mặt, đủ bounding box trong ảnh, mắt/mũi/miệng nhìn thấy, tư thế nhìn thẳng,
  đủ sáng và kích thước phù hợp. Mặt bị cắt, nhiều người hoặc tín hiệu thiếu
  không được coi là sẵn sàng.
- `CameraSession.previewBounds()` ánh xạ bounding box ML Kit bằng
  `ImageProxyTransformFactory` và `CoordinateTransform` tới PreviewView thực,
  gồm crop/xoay/phản chiếu. Chưa có transform thì chưa bắt đầu.
- `StableFaceGate` yêu cầu nằm trong oval qua nhiều frame khác nhau, mới và
  liên tục trong một giây. Poll UI hoặc một frame Good bị treo không đủ.
  Độ mới kiểm cả timestamp cảm biến và lúc analyzer trả kết quả; thời gian
  giữ/gap tính theo cảm biến, không cộng độ trễ xử lý thành bằng chứng giữ mặt.
- Căn mặt chấp nhận từ 24% chiều rộng ảnh nhưng ít nhất 100×100 pixel; giữ
  nguyên kiểm tra mặt trọn trong ảnh và đủ landmarks. Oval có dung sai 6%,
  tăng tối đa 10% khi đã căn ổn định để tránh rung mép làm mất tiến độ.
  Dung sai không cho phép ảnh bị cắt mất mặt. Gợi ý phân biệt quá gần với
  lệch tâm; chưa có transform thì báo đang chuẩn bị camera.
- JPEG chỉ lấy từ frame mới đã qua kiểm tra mặt nhìn thẳng. Request hủy/timeout
  được xóa; route hủy coroutine nên ảnh cũ không ghi sang lượt thử mới.
- App mới gửi `head_mode=adaptive` khi tạo phiên đăng ký/khôi phục. Server
  trả `head_timeout_ms` giới hạn phần quay đầu tới mốc 30 giây của toàn video;
  màu và đường chấm giữ nguyên lịch. `AdaptiveHeadCapture` giữ từng hướng
  đến khi quan sát đúng tư thế qua nhiều frame mới trong 650ms, xác nhận ngắn
  rồi mới chuyển. Quay sai/chưa quay/khó quan sát được nhắc ngay tại chỗ và
  chỉ đặt lại tiến độ giữ tư thế hiện tại. Kết thúc cần đang nhìn chính diện.
- `FaceAttemptGuard` vẫn chặn thay tracking identity/nhiều người. Mất dữ liệu
  ở phần màu/gaze vẫn không được bỏ qua. Hết giới hạn thu hoặc thiếu ảnh
  frontal hợp lệ thì không upload/đánh dấu hoàn tất. Server cũ không cấp
  adaptive vẫn dùng lịch cũ; client không tự kéo dài lịch chưa được cấp.
  Timed v1/v2 giữ hướng dẫn và kiểm mặt/identity hiện có, không nhận thêm chốt
  hoàn tất động tác của adaptive. Lời nhắc adaptive dùng cùng bộ chống lặp;
  xác nhận một bên không nhắc nhìn giữa trước khi controller chuyển bước.
- Server adaptive đọc tới EOF, tự tìm đủ hướng theo thứ tự và giữ giữa ở
  cuối video; không tin thời điểm hoàn tất do client khai. Video quá hạn,
  thiếu coverage, nhiều mặt hoặc chỉ chuyển động sai không được coi là đạt.
- Thoát tới xác nhận dừng sẽ ngừng recording ngay, mở AE/AWB và dọn lượt bỏ.
- Callback recording cũ không được ghi đè đồng hồ của lượt mới; file lượt đã
  bỏ được dọn cả khi CameraX báo Finalize trễ.

Giá trị trên là chốt chất lượng client cho demo, không phải ngưỡng mô hình đã
hiệu chỉnh. `trackingId` là theo dõi frame, không chứng minh danh tính.
Nguồn: [ML Kit về landmarks/pose](https://developers.google.com/ml-kit/vision/face-detection/face-detection-concepts),
[ánh xạ CameraX](https://developer.android.com/media/camera/camerax/transform-output).
Kích thước ảnh mặt tham khảo: [ML Kit Android](https://developers.google.com/ml-kit/vision/face-detection/android).

## Chuyển động

`HeadMotionGuide` minh họa đầu xoay, mũi tên cong, rồi giữ tư thế; đổi về giữa
thì hình quay lại chính diện. Đây là hướng dẫn native nhẹ, không tạo WebView
trong camera. Khi tắt chuyển động, vẫn có hướng và tiến độ bằng hình tĩnh/chữ.
Thumbnail chuyển vị trí mượt nhưng không làm chậm chấm hoặc thay thời điểm màu.
Không thêm nhấp nháy hay vòng sáng trang trí vào thử thách đổi màu.

## Giới hạn cần nghiệm thu

Chế độ adaptive chờ từng hướng trong ngân sách còn lại của video tối đa
30 giây, không phải chờ vô hạn. Cần cập nhật cả API và app; phiên đã tạo ở
bản cũ giữ lịch cũ. Server real vẫn phải chứng minh gaze, danh tính và các
mô-đun bắt buộc; hướng dẫn local không tự đưa ra kết quả eKYC.
Phép đo adaptive có version riêng, không mượn artifact của timed. Chế độ
chuẩn vẫn đóng khi thiếu artifact đúng version; demo ngưỡng tạm vẫn ghi rõ
chưa hiệu chỉnh và giữ nguyên chính sách ngưỡng. Tài khoản cũ dùng lại embedding
đã lưu, không cần xóa/ghi danh lại chỉ vì cập nhật giao diện.

Client kiểm độ đầy đủ của mặt trong bước gaze, chưa suy được mắt có theo đúng
chấm. Kiểm gaze và quyết định danh tính phải dựa trên bằng chứng server. Server
mock không chứng minh PAD/liveness; kiểm frame/camera ở client không thay thế
chính sách server. Phương thức không đổi màu cho người nhạy cảm ánh sáng vẫn
chưa có ở backend, xem bàn giao trước.

Cần thử trên máy thật: khoảng cách cầm máy tự nhiên, thấy trọn mặt, trái/phải
đúng chiều, giữ nguyên điện thoại, quay sai rồi chỉnh đúng trong cùng lượt; thử che/cắt mặt, hai
người, camera mất frame, thoát giữa recording, thử lại nhanh và chữ 200%.
Diện tích nền màu thay đổi theo oval; cần đánh giá ánh sáng/capture riêng.
