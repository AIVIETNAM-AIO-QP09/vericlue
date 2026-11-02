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

Stratum thật phải ghi đúng hệ TTS/VC hoặc loại tấn công cần kiểm soát; không
gom các hệ khó vào một nhãn TTS chung chỉ để tỷ lệ trung bình đẹp hơn. Các nhãn
`tts`/`vc` trong unit test chỉ là fixture, không phải bộ loại đã nghiệm thu.

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

## Đường artifact NES2Net toàn câu

`python -m vericlue_ml.eval.nes2net_candidate` có ba lệnh offline. Dùng Python
đã cài workspace theo `uv.lock`; không cần nạp trọng số/Torch để chấm lại các
report đo đã có. Runtime ghi trong report là runtime lúc đo, không phải runtime
của lệnh này. Giữ report, protocol và artifact chứa hàng/ID ở thư mục riêng
ngoài Git; chỉ công bố số tổng hợp đã review.

```powershell
# PYTHONPATH trỏ tuyệt đối đến ml/src của checkout hiện tại.
python -m vericlue_ml.eval.nes2net_candidate score --report <measurements.json> --fit-report <fit.json> --fit-measurement <fit-measurements.json> --split calib_fit --output <scores-moi.json>
python -m vericlue_ml.eval.nes2net_candidate select --report <ltt-measurements.json> --fit-report <fit.json> --fit-measurement <fit-measurements.json> --protocol <protocol.json> --output <ltt-moi.json>
python -m vericlue_ml.eval.nes2net_candidate evaluate --report <test-measurements.json> --fit-report <fit.json> --fit-measurement <fit-measurements.json> --ltt-report <ltt.json> --ltt-measurement <ltt-measurements.json> --output <test-moi.json>
```

`scripts/fit_thresholds.py` là entry point chọn candidate giọng với cùng input
như lệnh `select`; tên script không có nghĩa ghi vào thresholds.yaml. Core mặt
có trong Python API; [consumer ghép điểm mặt](face-candidate-scoring.md) chỉ
chấm calib_fit, chưa chọn/đánh giá ngưỡng mặt do thiếu metadata bắt buộc.
Không coi phần mặt đã chứng nhận từ một file điểm rời.

Protocol JSON khớp `LTTProtocol`: `mode`, `grid` (giọng: `[[t], ...]`),
`expected_attack_types`, `alpha`, `delta`, `total_delta`,
`family_delta_allocations` (cả `face` và `voice`), `sampling_protocol`,
`target_population`, `independence_attestation`,
`one_observation_per_group_per_stratum=true`, `grid_predeclared=true`,
`independent_of_training_and_calibration=true`,
`objective="immediate_review_rate"`, `tie_break="grid_order"`,
`fixture_kind="research"` hoặc `"synthetic"`; `bpcer_alpha` tùy chọn. Không có
lưới mặc định hay danh sách hệ tấn công mặc định để dùng nhầm cho dữ liệu thật.

Consumer kiểm envelope calibrator fitted, số lớp/mẫu loại, commit/dataset và hash
report nguồn; model/checkpoint/code/protocol/parity/runtime phải khớp. Kiểm
người/nguồn/file/PCM trên hợp của mọi hàng, kể cả hàng lỗi. Cùng report đầy đủ
có thể cung cấp các split khác nhau; báo cáo khác trùng dữ liệu bị từ chối.
Artifact và input phải còn nguyên lúc ghi output mới. Scoring test trực tiếp
bị chặn; evaluate kiểm lại toàn bộ kết quả LTT với protocol/report liên kết
trước khi tính xác suất test. Không fit lại hoặc tìm ngưỡng trên test.

`candidate_probability` nằm riêng; `module_result` gốc vẫn degraded/unclear,
prob_attack=null. Hash/provenance giúp phát hiện nhầm lẫn/thay đổi đầu vào;
artifact cục bộ không phải chứng thực có chữ ký về nguồn hoặc quyền dữ liệu.

## Nguồn phương pháp

- [MAPIE 1.4.1 BinaryClassificationController](https://github.com/scikit-learn-contrib/MAPIE/blob/v1.4.1/mapie/risk_control/binary_classification.py).
- [MAPIE 1.4.1 Holm](https://github.com/scikit-learn-contrib/MAPIE/blob/v1.4.1/mapie/risk_control/fwer_control.py).
- [Learn then Test: giả định và p-value](https://arxiv.org/html/2110.01052v5).

Không chép mã MAPIE vào repo. Dependency đã pin; không dựa vào default có thể
thay đổi giữa phiên bản. Báo cáo đo thật cần ghi commit, model/runtime, số mẫu
và số quan sát độc lập mỗi stratum; synthetic test không phải accuracy thật.
