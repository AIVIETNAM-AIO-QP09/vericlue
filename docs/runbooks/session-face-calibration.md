# Đo và hiệu chỉnh PAD/GenD cho video phiên

FLOW-04 dùng đúng ba khung từ `session_views`, video và lịch server. Đây là công
cụ nghiên cứu local, không mở guard eKYC. Chưa có dữ liệu/artifact thực cho
protocol này trên laptop; chưa có số liệu accuracy mới.

## Manifest và dữ liệu

Mỗi video đi với snapshot lịch của chính lượt đó, chỉ giữ `session_id` và
`challenge`, bỏ bearer/token. Không dựng lại lịch để hợp thức hóa video cũ.
Công cụ tin file lịch local; không chứng minh chữ ký server hoặc nguồn camera.

Đặt media/lịch/manifest trong data root ignored, không commit. `subject_id` là
mã opaque nối cùng người/nguồn liên quan, không gán mỗi clip một người khác.
Cùng nhóm không được giao giữa calib_fit/calib_ltt/test. Nhãn 0 là thật, 1 là
tấn công theo protocol mô-đun. Ví dụ dưới chỉ là định dạng, không đủ dữ liệu fit:

Từ 30/10, lượt mới là dynamic v2/12000 ms; v1/6000 ms vẫn được nhận. Mỗi
manifest/report chỉ được chứa một protocol, kể cả các mẫu lỗi. Không gán lịch
v2 cho video cũ; giữ snapshot lịch thực sự đã dùng. Hai lượt thử điện thoại
được dùng để chẩn đoán UX, không tự đưa vào kho dữ liệu hiệu chỉnh.

```json
{
  "schema_version": 1,
  "dataset": "session-study-v1",
  "samples": [{
    "sample_id": "capture-001", "subject_id": "person-group-001",
    "split": "calib_fit", "label": 0,
    "video": "videos/capture-001.mp4",
    "server_response": "challenges/capture-001.json"
  }]
}
```

Đường dẫn phải tương đối và resolve trong data root; video tối đa 64 MiB.
Giới hạn decoder/lịch/pose hiện có không được nới. Trùng mã/nội dung video và
giao nhóm giữa split, kể cả mẫu không chấm được, đều bị từ chối.

## Đo và fit

Commit code trước khi đo để giữ provenance. Dùng dữ liệu có quyền sử dụng, đúng
protocol và nhãn; không cần mở camera từ công cụ này.

```powershell
$py = 'D:\vericlue\tmp\session-api-runtime\Scripts\python.exe'
& $py -m vericlue_ml.eval.session_calibration collect `
  --manifest '<data-root>\manifest.json' --data-root '<data-root>' `
  --models-dir 'D:\vericlue\models\selected-2026-10-24' `
  --module face_pad --device cpu --output '<reports>\session-pad.json'
# GenD chạy riêng với --module face_deepfake và output mới.
& $py -m vericlue_ml.eval.session_calibration fit `
  --report '<reports>\session-pad.json' --output-dir '<output-calibrators>' `
  --n-splits 5
```

Báo cáo giữ mọi mẫu: trạng thái/lỗi, raw score khi chấm được, nhãn/nhóm/split,
hash video/lịch/manifest model, module/version/commit. Không xuất ảnh, vector
hoặc CCCD. Lỗi khởi tạo model/manifest làm lệnh thất bại; lỗi từng lượt giữ
trong rows, không bịa score. Output phải mới, không ghi đè input/kho model.

Fit chỉ dùng calib_fit chấm được, đủ hai lớp và nhóm cho cross-validation;
Platt/isotonic chọn bằng GroupKFold hiện có. Không dùng nhãn test/calib_ltt để
fit/chọn phương pháp/ngưỡng. Artifact giữ số mẫu/lớp/nhóm/loại trừ và hash báo
cáo/manifest/commit. Kết quả group OOF không thay đánh giá test độc lập. Lệnh
không chọn LTT hoặc sửa thresholds.yaml.

Kho output riêng, không ghi đè artifact đang dùng. Kiểm nguồn dữ liệu, nhãn,
split, loại trừ và đánh giá độc lập trước khi sử dụng thực tế. JSON local
không tự chứng minh provenance; không sửa metadata để hợp thức hóa số đo.

## Nối API và giới hạn

Cấu hình `CALIBRATORS_DIR=<output-calibrators>` rồi restart. Store tìm đúng
`<module>/<full-version được encode>.json`. Không đổi tên artifact ảnh tĩnh/
video cũ để dùng cho phiên. Chỉ `Calibrator` fitted non-provisional đúng module
và full version `...+session-video-v1` (v1/6000) hoặc `...+session-video-v2`
(v2/12000) mới tạo xác suất. Không mượn artifact giữa hai protocol. Thiếu/hỏng/sai hoặc
identity/provisional vẫn degraded/unclear, không có xác suất. Nạp/cache một lần;
thêm/sửa file cần restart. Backend lỗi/score sai/video thay đổi không được nâng
thành đạt; gate vẫn unclear, router giữ quyền quyết định.

Đối chiếu nhiều góc LVFace v2 có hậu tố `+head12s-v2`; artifact ngưỡng đối
chiếu và consistency phải khớp đúng version đó. Đối chiếu chỉ khung chính diện
không thay lịch lấy khung; không tự dùng ngưỡng nhiều góc v1 cho v2. Thiếu bằng
chứng ghi danh/continuity hoặc guard chưa cho phép thì account vẫn không tạo.

Hiệu chỉnh xác suất không chứng minh chiều sâu/crop parity hay chất lượng ngoài
tập đánh giá. Guard real/mixed/account-bound giữ nguyên, OTP demo không đổi.
ChromaPulse, LVFace/consistency/continuity và giọng có protocol riêng. Chưa bật
ghi danh thật. Người dùng tự thử điện thoại sau; các test phần mềm dùng fixture
tổng hợp trong tmp, không đưa chúng vào kho calibrator của demo.
