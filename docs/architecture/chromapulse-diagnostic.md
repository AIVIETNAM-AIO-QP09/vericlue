# ChromaPulse — đo phản hồi màu phía server

PRES-02 đã có phần **đo và đối chiếu**, chưa có cổng xác minh được hiệu chỉnh.
ADR-0016 đưa ChromaPulse trở lại lớp 1 của thử thách động; quyết định đó không
thay thế dữ liệu kiểm chứng. Factory diagnostic riêng không thay module mock
hiện hành, profile full/MVP hay chốt 503 của luồng dynamic ở real/mixed.

## Đầu vào và cách chạy

Dùng runtime MediaPipe đã hướng dẫn trong
[presence/README.md](../../ml/src/vericlue_ml/presence/README.md). Không cần tải
thêm model: dùng lại `face_landmarker.task`, đường dẫn/hash từ models.yaml.
Không mở camera, tự nháy màu hoặc sửa UI sản phẩm. Cần video chưa lật gương và
bản phản hồi tạo phiên **dynamic do server của nhóm cấp**, cùng đầu bản ghi.
Phản hồi này phải được giữ từ nguồn đáng tin; CLI không xác thực chữ ký của
một JSON tùy ý và không coi hash là bằng chứng xác thực nguồn.

```powershell
tmp/liveness-runtime/Scripts/python.exe -m vericlue_ml.eval.gaze_video --module chromapulse --video tmp/capture.mp4 --server-response tmp/session-response.json --models-dir models/selected-2026-10-24 --output tmp/color-diagnostic.json
```

Đầu vào chứa token/dữ liệu riêng tư chỉ để ở thư mục ignored. Không chép token
vào báo cáo. Artifact xuất commit/dirty, phiên bản thuật toán, hash model,
hash cấu hình màu, hash video, runtime và `sample_count=1` clip. Kết quả này
là diagnostic, không phải một mẫu benchmark có nhãn người thật/tấn công.
Không xuất ảnh, video, landmark hay embedding; chỉ có số đo và đường khớp màu.

Dùng Python trực tiếp: `registry.get_chromapulse_diagnostic()` trả detector
cache; `get_chromapulse_diagnostic(mock=True)` trả mock hiện có. Có thể truyền
`ColorObservationReader(existing_face_reader)` để dùng chung task MediaPipe với
mắt/quay đầu. Nạp một lần, gọi tuần tự dưới khóa, đóng reader khi hết phiên làm việc.

## Đo và khớp

1. Kiểm challenge/session/version và thử thách hiện tại bằng metadata do server
   cung cấp. Dựng lịch từ `baseline_ms`, 8 bước màu và cấu hình dùng chung ở
   `packages/contracts/chromapulse.json`; kiểm mốc bắt đầu dò mắt khớp cuối màu.
   Theo CAP-03, mỗi bước **chuyển màu trước rồi giữ**, nội suy và làm tròn sRGB.
2. Tính lại median RGB 5 vùng da và nền từ video, không dùng `region_means`,
   `color_events` hay kết quả client làm số đo server. Hộp landmark co 20%,
   hai ô nền góc trên rộng 12% khung hình; bỏ ô chạm mặt cộng lề 10%.
   Bỏ pixel có luma `0.299R+0.587G+0.114B <=55` hoặc `>=200`, cùng quy tắc CAP-03.
3. Đổi sRGB sang tuyến tính, lấy log vùng da trừ log nền. Khớp từng vùng bằng
   biến đổi affine của log màu dự kiến. Quét lag 0–300 ms, bước lưới 5 ms,
   trên **cùng các mẫu** với mọi lag; không chọn vùng/thời đoạn đẹp nhất.
4. Trả R² khớp **trên chính mẫu dùng để fit**, lag biểu kiến, biên độ biến thiên,
   độ phủ, mức loại pixel, condition number và khoảng lag gần nghiệm tốt nhất.
   Chuỗi bằng chứng chứa phản hồi trung bình 5 vùng và đường đã fit.

Reader dùng timestamp decoder, lấy khoảng 10 Hz; không sửa timestamp bằng FPS.
Giữ giới hạn 30 giây, 1800 khung, 1920×1080, kiểm ngân sách đọc 15 giây giữa các
khung; thêm giới hạn file 64 MiB và hash trước/sau đọc. Ngân sách không ngắt được
một native call đang treo. Thiếu vùng/nền, mất mặt, nhiều mặt, clip quá ngắn,
timestamp lỗi, khoảng trống lớn, phản hồi hằng hoặc thiết kế thiếu hạng đều
không tạo một kết quả đạt. Hằng số độ phủ và numerical guard chưa hiệu chỉnh.

## Giới hạn cần giữ khi trình bày

- Mọi kết quả detector thật đều `degraded/unclear` hoặc lỗi; không có score
  phân loại hay `prob_attack`, không thể dùng `is_usable` để cấp pass.
- `apparent_lag_ms` là lệch so với **lịch dự kiến và mốc video**, chưa phải độ trễ
  vật lý. Thiếu liên kết draw/capture có kiểm chứng và đồng bộ nguồn thời gian.
  Lưới 5 ms không có nghĩa độ chính xác đo 5 ms khi lấy mẫu khoảng 100 ms.
- R² cao không chứng minh da thật, chống ảnh in/màn hình/deepfake hay giải mã
  đúng 8 ký hiệu. Một biến đổi màu học lại trên cùng clip có thể khớp nhiều
  ánh xạ; vì vậy chưa báo số ký hiệu đúng và chưa có tỷ lệ phát hiện tấn công.
- Chưa so client/server để bật cờ mismatch: cần chốt định dạng/mốc thời gian,
  dung sai dựa trên dữ liệu và kiểm parser trước. Client stats hiện được bỏ qua.
- Chưa có dữ liệu CAP-03 thật, ngưỡng, đo APCER/BPCER hay kết quả R5. Không sửa
  thresholds.yaml. Chưa chứng minh mục tiêu <500 ms/video 6 giây của task.

Trước khi bật cổng cần thu dữ liệu có đồng ý, chia theo người, kiểm timestamp,
đánh giá khả năng phân biệt tấn công và chọn ngưỡng trên calib. Khóa cấu hình
rồi mới đánh giá test và nối API với quy tắc fail-closed. Tiêu chí cũ “trễ 100 ms
là fail” trong PRES-02 cần được nhóm xem lại theo đồng hồ và số đo thực tế.

## Kiểm tra

`ml/tests/test_chromapulse.py` dùng số đo tổng hợp có đáp án biết trước và pixel
giả lập, không dùng người hoặc video tấn công. Test hồi quy reader/mắt/quay đầu
kiểm việc chia sẻ decoder. Smoke opt-in dưới đây chạy checkpoint thật và CLI
trên video xám tự sinh, xác nhận không có mặt luôn unclear; **0 mẫu người thật**.

```powershell
$env:GAZE_MODELS_DIR = "D:/Projects/Data4Life/models/selected-2026-10-24"
tmp/liveness-runtime/Scripts/python.exe -m pytest ml/tests/test_chromapulse_real_smoke.py -m slow -ra
```
