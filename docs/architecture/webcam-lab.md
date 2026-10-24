# Webcam Lab — thử trực tiếp trên laptop

Công cụ **nội bộ cho người phát triển**, nằm trong `ml/eval`, không sửa giao
diện web/Android/iOS. Chạy model thật tại máy, không gọi API và không xác minh
đăng ký tài khoản. Không cần CCCD để thử các chức năng này.

## Mở cửa sổ

Tại gốc repo, dùng môi trường CPU đã cài theo
[`face-diagnostic-runtime.md`](face-diagnostic-runtime.md):

```powershell
tmp/face-diagnostic-runtime/Scripts/python.exe -m vericlue_ml.eval.webcam_lab --models-dir models/selected-2026-10-24
```

Camera **chưa mở** khi chương trình khởi động. Bấm **Bật camera** để cho phép
thu hình. Nếu webcam đang bị Camera/Teams/Zoom chiếm, đóng ứng dụng đó trước;
thử `--camera 1` khi laptop có nhiều thiết bị. Công cụ dùng Tkinter và bản
opencv-contrib-python có GUI trong runtime riêng, không thay OpenCV của API.

## Thử từng phần

1. **Bật camera:** thấy ảnh không lật gương, số mặt, yaw/pitch và tọa độ mống
   mắt tương đối cập nhật tối đa 10 Hz. Đây không phải tọa độ nhìn tuyệt đối
   trên màn hình. Chưa kiểm quy ước dấu trên từng webcam.
2. **Chụp tham chiếu:** nhìn thẳng, đủ sáng và chỉ một người trong khung.
   Ảnh nằm trong RAM, dùng làm mẫu để thử so mặt, không chứng minh danh tính CCCD.
3. **Bật AI liên tục:** LVFace so với mẫu; GenD và FS-VFM-L chấm một khung mới
   nhất theo lượt ở worker nền. Chỉ một lượt AI chạy cùng lúc, không xếp hàng
   vô hạn. Các model nạp một lần; lần đầu có thể lâu. CPU không chấm mọi khung
   hình, tốc độ cập nhật tùy máy. Có thể tạm dừng AI trong khi vẫn xem camera.
4. **Thử mắt + quay đầu:** AI phải chấm xong lượt đang chạy rồi mới bắt đầu.
   Trong khoảng 18 giây: giữ thẳng 0–5 s, chỉ đưa mắt theo chấm 5–12 s, quay
   theo thứ tự trái/phải ngẫu nhiên rồi về giữa 12–18 s. Cửa sổ giữ kích thước
   trong lượt thử. Nếu mắt và đầu đều `ok/pass`, chọn ba khung đúng tư thế
   trong RAM rồi chấm cả ba. Nếu thiếu/lỗi thì không chấm nhánh ba góc đó.
5. **Thử ánh sáng · 6–8 giây:** chỉ cần bật camera, không cần chụp tham chiếu.
   Tạm dừng AI và chờ lượt chấm hiện tại kết thúc, rồi bấm nút thử. Giữ đầu yên
   khi vùng lớn bên trái đổi màu theo bảng pastel/timing dùng chung của dự án.
   Một task MediaPipe trả đồng thời mắt/góc đầu và màu 5 vùng da + nền; không
   nạp thêm model. Hết lượt, worker đối chiếu số đo và hiển thị R² fit/lag biểu
   kiến nếu đủ dữ liệu. Thiếu mặt/vùng/nền hoặc gián đoạn thì không có kết quả
   khớp dùng được. Lượt luôn `degraded/unclear`, không kết luận người thật.
   Esc dừng camera; thu nhỏ hoặc chuyển sang cửa sổ khác hủy lượt màu.
6. **Dừng/Esc:** ngừng thu, bỏ tham chiếu/lượt thử và vô hiệu hóa kết quả cũ
   đang về. Lượt AI native đang chạy không thể cưỡng bức ngắt; hoàn tất rồi
   bỏ dữ liệu giữ trong worker. Camera được giải phóng sau lượt đọc hiện tại.
   Đóng cửa sổ để thoát cả tiến trình.

`face_match.score` là khoảng cách `1-min_cosine`, nhỏ hơn nghĩa gần tham chiếu
hơn. Thiếu ngưỡng hiệu chỉnh vẫn `degraded/unclear`, không phải xác minh đạt.
`face_pad` và `face_deepfake` là điểm tấn công thô chưa hiệu chỉnh, không dùng
ngưỡng 0,5 để tự kết luận. Có thể đọc từng module nhưng không hợp nhất thành
kết luận người thật. Mẫu tự chụp từ webcam không phải tham chiếu danh tính tin cậy.

## Dữ liệu, thời gian và giới hạn

Không thu âm, ghi video hoặc lưu ảnh ra đĩa. Pixel chỉ trong RAM: ảnh tham
chiếu, khung mới nhất và tối đa 75 khung cần cho lượt thử chuyển động. Bấm
**Lưu báo cáo JSON** mới ghi metadata/kết quả/hash vào `tmp/webcam-lab/`; không
ghi landmark thô, pixel hay embedding. Báo cáo là snapshot chẩn đoán mới nhất,
`sample_count=1`, không phải báo cáo độ chính xác từ nhiều người.
Lượt ánh sáng chỉ giữ tối đa 120 hàng số đo và 512 mốc yêu cầu vẽ, không giữ
video/khung màu riêng. JSON thêm `color` (ModuleResult), `color_plan` (lịch,
hash cấu hình, ID cục bộ, mốc yêu cầu vẽ). Bắt đầu lượt mới hoặc chụp tham chiếu
xóa kết quả ánh sáng cũ để không ghép nhầm lượt.

Thử thách sinh **cục bộ bằng CSPRNG** cho lab, không giả làm phản hồi server.
Timestamp là đồng hồ host khi lấy khung từ webcam, không phải timestamp cảm
biến hay bằng chứng chống camera ảo. Độ trễ đọc camera/hiển thị chưa được
nghiệm thu; không thay chữ ký media/SEC-02, kiểm chiều sâu hoặc kiểm giọng.
Lượt lab không được đưa vào API như bằng chứng xác minh.

ChromaPulse trong lab dùng version riêng `+local-host-clock-v1`: lịch sinh cục
bộ bằng CSPRNG, có đủ bốn màu và không lặp kề nhau. Mốc Tk chỉ là **yêu cầu vẽ**,
không phải thời điểm màn hình trình chiếu hoặc cảm biến chụp. Dùng lịch dự kiến
để fit; ghi log vẽ cho chẩn đoán, không tối ưu lệch đồng hồ để làm đẹp kết quả.
Khởi đầu vẽ trễ, thiếu cuối lịch hoặc gap >200 ms thì bỏ fit. Đây là quality
guard thử nghiệm, không phải ngưỡng độ trễ phát hiện deepfake. Lưới fit 5 ms,
mẫu camera ~100 ms không chứng minh đo chính xác 5 ms. R² là khớp trên cùng
mẫu để fit, không phải độ chính xác phân loại. Xem
[`chromapulse-diagnostic.md`](chromapulse-diagnostic.md) về các giới hạn còn lại.

GenD ảnh đơn có version riêng `+single-frame-v1`; ba góc giữ version cũ.
FS-VFM ảnh RAM đơn dùng cùng tiền xử lý/version ảnh đơn. LVFace nhận tham
chiếu RAM qua keyword nội bộ `reference_frame`, không đổi schema HTTP hoặc
resolver tham chiếu của sản phẩm. Không có mock fallback trong lab.

## Kiểm giao diện không mở camera

```powershell
tmp/face-diagnostic-runtime/Scripts/python.exe -m vericlue_ml.eval.webcam_lab --models-dir models/selected-2026-10-24 --ui-preview --close-after-ms 1000
```

Chế độ này vô hiệu hóa nút camera, dùng để kiểm layout; không được báo là test
mặt người thật. Bộ test `ml/tests/test_webcam_trial.py` dùng dữ liệu tổng hợp
và camera giả, kiểm timing, giới hạn RAM, chọn đúng pixel, dừng và lỗi đọc.
`test_webcam_color.py` kiểm lịch màu, số đo/đồng hồ tổng hợp, hủy/stop,
kết quả cũ, giới hạn RAM và export số liệu. Smoke opt-in
`test_webcam_color_real_smoke.py` dùng checkpoint thật trên một khung xám tự
sinh, không gọi camera và không có mẫu người thật. Các kiểm tra này không phải
nghiệm thu thiết bị, khả năng phản chiếu ánh sáng hoặc phát hiện tấn công.
