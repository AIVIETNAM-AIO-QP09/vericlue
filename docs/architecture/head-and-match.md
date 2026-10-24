# FLOW-04/FLOW-05 — Diagnostic quay đầu và so mặt

Hai module backend có thể chạy độc lập trước khi FLOW-03/CAP-06 hoàn thành.
Không sửa UI. Chưa nối vào quyết định xác minh: full/MVP vẫn giữ 9/7 module;
luồng purpose mới vẫn bị chặn ở real/mixed cho đến khi đủ các gate bắt buộc.

## 1. Quay đầu: `head_turn`

Dùng cùng mã reader MediaPipe với gaze; có thể truyền **cùng một instance
reader** cho `GazeDetector` và `HeadTurnDetector` để chỉ nạp task một lần.
Reader không giữ trạng thái theo phiên. Detector mặc định tạo reader riêng;
lớp tích hợp có trách nhiệm chia sẻ/đóng reader. `image` mode chạy trên CPU.

Chỉ tin lịch `metadata.expected_challenge` do server lấy từ phiên, kiểm
`session_id/challenge_id/version`. Đọc video theo timestamp, yêu cầu đủ cửa sổ
500 ms trước thử thách và toàn bộ 6 giây thử thách. Cần tư thế giữa lúc bắt đầu;
sau đó đúng thứ tự server chọn (trái/phải hoặc phải/trái, cuối cùng về giữa),
giữ mỗi tư thế tối thiểu 300 ms. Thiếu dữ liệu, sai thứ tự, nhiều/không có mặt
không được đạt. Các hằng góc, chất lượng và thời gian giữ là **thử nghiệm**.

`view_times_ms` ghi thời điểm chính diện theo lịch và trung điểm hai đoạn nghiêng
được chấp nhận; chưa tự trích ảnh và chưa kiểm chất lượng khung chính diện.
Chiều dương yaw đang hiểu là trái của người dùng trên **video không lật**;
cần quay kiểm tra trên điện thoại trước khi dùng cho quyết định.

**Giới hạn:** góc đầu suy từ ma trận landmark không chứng minh chiều sâu hay
chống ảnh/video giả. Mọi kết quả ghi `depth_verified=false`; pass chỉ có nghĩa
chuỗi chuyển động khớp, không phải người thật. Chưa có kiểm tra homography.

```powershell
# Dùng runtime MediaPipe riêng như presence/README.md.
tmp/liveness-runtime/Scripts/python.exe -m vericlue_ml.eval.gaze_video --module head_turn --video <video.mp4> --server-response <session-response.json> --models-dir <models-root> --output <report.json>
```

File phản hồi phải là phản hồi tạo phiên thực sự lưu từ server. CLI đọc tệp
cục bộ để diagnostic, không xác thực tính nguyên bản của file JSON này.
HTTP tương lai phải lấy lịch từ kho phiên, không tin lịch client gửi.

## 2. So mặt: `face_match`

Nhận ảnh chân dung tham chiếu đã cắt + một ảnh front hoặc đủ front/left/right.
Đường dẫn và nhãn ảnh do server quản lý qua `DetectorInput`; không cho client
trỏ đường dẫn server. Chưa có endpoint mới hay OCR CCCD trong lát cắt này.

SCRFD dùng session ONNX chung với các module mặt hiện có. Mỗi ảnh phải có đúng
một mặt đủ lớn và 5 landmark. Căn bằng phép đồng dạng 2D về 112×112, RGB/CHW
float32 và chuẩn hóa về [-1,1]. LVFace-B ONNX gốc trả 512 chiều; chuẩn hóa L2,
so cosine với tham chiếu và **mọi cặp ảnh**: ba ảnh tạo 6 phép so, lấy giá trị
nhỏ nhất để xét ngưỡng. Ảnh query trùng byte pixel bị từ chối để bắt lỗi lấy
lặp một khung. Embedding chỉ ở RAM, không xuất vào report.

Nhãn left/right chưa được module này xác thực; khi tích hợp phải lấy khung do
server chọn từ video sau kiểm quay đầu. So mặt chỉ kiểm danh tính; không thay
PAD, GenD, chứng minh chiều sâu hay tính thật của CCCD.

```powershell
.venv/Scripts/python.exe -m vericlue_ml.eval.face_match --reference <portrait.png> --front <front.png> --left <left.png> --right <right.png> --models-dir <models-root> --device cpu --output <report.json>
# Chỉ so một ảnh: bỏ đồng thời --left và --right.
```

Không có ngưỡng mặc định. Chưa có artifact → vẫn trả cosine, nhưng
`status=degraded`, `gate=unclear`, `prob_attack=null`. Điểm thô `score=1-min_cosine`
là khoảng cách, **không phải xác suất giả mạo**. Cosine/diagnostic chỉ dành cho
người phát triển/người duyệt; không gửi cho màn hình người dân.

Artifact tin cậy do server cấp qua `--calibration` hoặc `FACE_MATCH_CALIBRATION`
là JSON gồm: `model_version` đúng `MATCH_VERSION`, `preprocessing` đúng
`arcface112-rgb-minus1to1-v1`, `threshold` trong [-1,1], `split=calib_ltt`,
`dataset`, `pairs` > 0, `subjects` ≥ 2, `source_commit` (40 hex) và
`predictions_sha256` (64 hex). Chưa có công cụ hiệu chỉnh/threshold thực trong
PR này. Artifact phải sinh từ dữ liệu chia theo người và không dùng tập test
để chọn ngưỡng. Kiểm schema chỉ kiểm metadata, không chứng nhận dữ liệu đúng
hay chứng minh đạt chỉ tiêu thống kê. Cần nghiệm thu trước khi bật API.
Khi đánh giá phải đo cả phiên có nhiều phép so; ngưỡng chọn trên cặp ảnh đơn
không tự bảo đảm cùng tỷ lệ lỗi cho quy tắc lấy min của 6 phép so.

CLI ghi commit/trạng thái dirty, version/hash mô hình, hash đầu vào và artifact,
runtime, một trường hợp chẩn đoán và số phép so trong ModuleResult; không phải
báo cáo độ chính xác. Không commit ảnh, video, embedding hay trọng số.

## 3. Nguồn và giấy phép

- [LVFace inference chính thức, commit cố định](https://github.com/bytedance/LVFace/blob/80bd20c8bb78e56eb708941180d800a27c396a6b/inference_onnx.py): tiền xử lý RGB/112/[-1,1].
- [Mốc landmark ArcFace](https://github.com/deepinsight/insightface/blob/master/python-package/insightface/utils/face_align.py): dùng các tọa độ đích; phép fit least-squares viết riêng, không chép implementation.
- [Giấy phép tác giả LVFace](https://github.com/bytedance/LVFace/blob/80bd20c8bb78e56eb708941180d800a27c396a6b/README.md#license): code MIT, trọng số nghiên cứu phi thương mại. Giữ giới hạn này dù thẻ Hugging Face gắn MIT.
- [Nguồn trọng số LVFace-B đã pin](https://huggingface.co/bytedance-research/LVFace/tree/b12702ab1f5c721748e054a66dc90e1edd1f0724): SHA-256 và kích thước byte ở `models/manifest.yaml`; runtime kiểm hash trước nạp, không tải ngầm.

## 4. Phần còn lại

Kiểm tra chiều yaw/khả dụng trên điện thoại, người thật và video giả; kiểm
chiều sâu/homography; chọn khung và nối GenD; FLOW-03 trích chân dung CCCD;
hiệu chỉnh ngưỡng so mặt trên dữ liệu chia người; kiểm VRAM/latency cả bộ;
quản lý mã hóa/xóa mẫu 24 giờ; cuối cùng mới nối gate vào API và retry.
