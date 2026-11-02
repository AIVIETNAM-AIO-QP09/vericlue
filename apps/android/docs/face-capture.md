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
- JPEG chỉ lấy từ frame mới đã qua kiểm tra mặt nhìn thẳng. Request hủy/timeout
  được xóa; route hủy coroutine nên ảnh cũ không ghi sang lượt thử mới.
- `FaceAttemptGuard` giữ kiểm tra mặt trong lượt thu, kiểm hướng trái/phải/giữa
  bằng `HeadActionGate`. Hướng phải đúng và giữ ít nhất 350ms qua ít nhất ba
  frame mới. Thanh tiến độ là phần giữ tư thế đã quan sát, không phải điểm AI.
- Nếu thiếu thao tác ở ranh giới pha, mất mặt/tín hiệu lâu hoặc thay tracking
  identity, dừng thu, mở AE/AWB, xóa media tạm và không upload/đánh dấu thu xong.
  Người dùng chủ động thử lại; API cấp challenge mới. Chưa có ảnh frontal hợp
  lệ cũng không được hoàn tất. Thoát tới xác nhận dừng sẽ ngừng recording ngay.
- Callback recording cũ không được ghi đè đồng hồ của lượt mới; file lượt đã
  bỏ được dọn cả khi CameraX báo Finalize trễ.

Giá trị trên là chốt chất lượng client cho demo, không phải ngưỡng mô hình đã
hiệu chỉnh. `trackingId` là theo dõi frame, không chứng minh danh tính.
Nguồn: [ML Kit về landmarks/pose](https://developers.google.com/ml-kit/vision/face-detection/face-detection-concepts),
[ánh xạ CameraX](https://developer.android.com/media/camera/camerax/transform-output).

## Chuyển động

`HeadMotionGuide` minh họa đầu xoay, mũi tên cong, rồi giữ tư thế; đổi về giữa
thì hình quay lại chính diện. Đây là hướng dẫn native nhẹ, không tạo WebView
trong camera. Khi tắt chuyển động, vẫn có hướng và tiến độ bằng hình tĩnh/chữ.
Thumbnail chuyển vị trí mượt nhưng không làm chậm chấm hoặc thay thời điểm màu.
Không thêm nhấp nháy hay vòng sáng trang trí vào thử thách đổi màu.

## Giới hạn cần nghiệm thu

Lịch head của server hiện cố định 6 giây; app không tự kéo dài để chờ người
dùng. Khi chưa làm đủ, lượt thu được dừng để thử lại, không coi hết giờ là đạt.
Muốn từng hướng chờ tùy tốc độ người dùng cần cập nhật contract/server/ML đồng
bộ; không thay thời gian ở client riêng lẻ.

Client kiểm độ đầy đủ của mặt trong bước gaze, chưa suy được mắt có theo đúng
chấm. Kiểm gaze và quyết định danh tính phải dựa trên bằng chứng server. Server
mock không chứng minh PAD/liveness; kiểm frame/camera ở client không thay thế
chính sách server. Phương thức không đổi màu cho người nhạy cảm ánh sáng vẫn
chưa có ở backend, xem bàn giao trước.

Cần thử trên máy thật: khoảng cách cầm máy tự nhiên, thấy trọn mặt, trái/phải
đúng chiều, giữ nguyên điện thoại, bỏ thao tác thì retry; thử che/cắt mặt, hai
người, camera mất frame, thoát giữa recording, thử lại nhanh và chữ 200%.
Diện tích nền màu thay đổi theo oval; cần đánh giá ánh sáng/capture riêng.
