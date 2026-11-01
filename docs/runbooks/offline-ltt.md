# LTT offline: phạm vi và điều kiện

Công cụ ROUT-03 triển khai thiết kế ADR-0006/0010 để chuẩn bị phép đo trước khi
có artifact/dữ liệu đầy đủ. Đây là đường nghiên cứu; không cài ngưỡng vào router,
không thay `thresholds.yaml`, không biến ModuleResult degraded/error thành đạt.

## Khóa trước phép đo

Khai báo trước lưới, loại tấn công bắt buộc, alpha, delta, quần thể áp dụng,
quy trình lấy quan sát độc lập và mục tiêu chọn. Không sửa các mục này sau khi
xem kết quả để tìm một cấu hình đạt. Chỉ `calib_ltt` được chọn ngưỡng; test chỉ
đánh giá sau khi artifact ngưỡng đã khóa. Model, phép gộp, calibrator và fusion
phải được cố định bằng `train`/`calib_fit` trước bước LTT.

Chia theo người ngăn rò rỉ xuyên tập, nhưng không làm các clip cùng người trở
thành độc lập. Phiên bản này yêu cầu tối đa một quan sát được chọn trước cho mỗi
thành phần phụ thuộc trong mỗi stratum. Thành phần nối mọi người liên quan,
nguồn gốc, derivative và alias đã biết. Không tự chọn clip tốt nhất hay khử
trùng sau khi thấy điểm. Mã người/nguồn độc nhất vẫn chưa chứng minh độc lập;
khai báo trong JSON không thay xác nhận quyền và quy trình thu thập bên ngoài.

Các mẫu lỗi vẫn phải có trong báo cáo đo và kiểm rò rỉ. Đường chọn/đánh giá
candidate từ chối khi split cần dùng có mẫu không đủ điểm/parity; không âm thầm
đổi tập đo thành tập con chỉ gồm mẫu thành công.

## Kiểm định

Dùng MAPIE **1.4.1** đã khóa: p-value Hoeffding–Bentkus dành cho biến nhị phân.
Mỗi candidate có một p-value trên mỗi loại tấn công. Lấy max qua các rủi ro bắt
buộc rồi chạy Holm **một lần trên toàn lưới**. Một stratum không đạt thì candidate
không đạt. Không chạy mỗi stratum tại toàn bộ delta rồi tuyên bố bảo đảm chung.
Nếu kiểm thêm BPCER thì rủi ro này cũng thuộc max-p của candidate.

Phân bổ delta mặt và giọng trước, tổng không vượt delta toàn bộ. Công thức 59
quan sát không lỗi tại alpha=5%, delta=5% chỉ là ví dụ một kiểm định đơn; không
được thay số clip vào đó để chứng nhận cả lưới hoặc nhiều clip cùng người.

Mặt: score <= B là pass, score >= A là review, giữa hai ngưỡng là voice_challenge.
Giọng: score <= t là pass, lớn hơn là review. Mục tiêu ở công cụ này là tỷ lệ
review ngay bước đó trên bona fide; challenge được đếm riêng. Nó chưa đo tỷ lệ
review cuối quy trình mặt–giọng. Chọn trong tập candidate hợp lệ theo mục tiêu
đã khai báo và thứ tự lưới để phá hòa, không theo test.

Nếu không có candidate hợp lệ, `selected=null`. Fixture có thể cho candidate
hợp lệ để kiểm chương trình nhưng không chứng nhận dữ liệu thật. Artifact luôn
`diagnostic_only=true`, `provisional=true`, `runtime_eligible=false`. Các giả
định độc lập, phạm vi quần thể và quyền dữ liệu vẫn cần review trước phép đo thật.

## Trạng thái dữ liệu hiện có

DNU đã đo chỉ có giọng thật; chưa fit calibrator và không thể kiểm rủi ro TTS/VC.
VIVOS32 là bộ parity, không được dùng hiệu chỉnh. Thiếu nguồn tấn công có quyền
sử dụng/crosswalk người–nguồn và các artifact nhận diện vẫn là chốt triển khai.
Không có kết quả R4 hay bảo đảm toàn luồng được nghiệm thu từ công cụ này.

## Nguồn phương pháp

- [MAPIE 1.4.1 BinaryClassificationController](https://github.com/scikit-learn-contrib/MAPIE/blob/v1.4.1/mapie/risk_control/binary_classification.py).
- [MAPIE 1.4.1 Holm](https://github.com/scikit-learn-contrib/MAPIE/blob/v1.4.1/mapie/risk_control/fwer_control.py).
- [Learn then Test: giả định và p-value](https://arxiv.org/html/2110.01052v5).

Không chép mã MAPIE vào repo. Dependency đã pin; không dựa vào default có thể
thay đổi giữa phiên bản. Báo cáo đo thật cần ghi commit, model/runtime, số mẫu
và số quan sát độc lập mỗi stratum; synthetic test không phải accuracy thật.
