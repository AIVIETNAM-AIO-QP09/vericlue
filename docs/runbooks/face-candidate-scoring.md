# Ghép điểm PAD–GenD offline trên calib_fit

Consumer `eval.face_candidate` dùng report `session_calibration.SessionReport`
và calibrator fitted do `session_calibration.fit_report` tạo. Mục đích là kiểm
liên kết artifact và tính max(PAD, GenD) theo phép gộp hiện tại của ROUT-02.
Không tạo quyết định xác minh hoặc chọn ngưỡng mặt.

```powershell
# Python workspace, PYTHONPATH tuyệt đối đến ml/src của checkout hiện tại.
python -m vericlue_ml.eval.face_candidate --pad-report <pad-measurements.json> --gend-report <gend-measurements.json> --pad-calibrator <pad-fitted.json> --gend-calibrator <gend-fitted.json> --output <face-candidates-moi.json>
```

Hai report phải cùng dataset/manifest; mỗi module đúng tên và exact version
session. Calibrator phải fitted, nonprovisional, đúng module/version và metadata
dataset JSON gắn với đúng byte report, manifest/model-manifest, commit đo, số
mẫu fit/usable/loại theo lớp và số nhóm như producer đã ghi. Không refit hoặc
lấy artifact identity làm thay thế. Source checkout cần sạch để ghi commit
thực thi thật; output mới và không nằm trên input/config/model/data.

Kiểm mọi hàng của cả hai report, kể cả hàng lỗi và split không xuất. Các hàng
khớp một-một theo sample ID, người, split, nhãn, hash video/challenge. Không
inner join rồi bỏ hàng thiếu. Trật tự hai report có thể khác nhau. Phân vùng
theo subject/video hiện có của producer vẫn được kiểm, nhưng chưa có crosswalk
đủ nguồn/alias/donor để chứng minh độc lập cho LTT.

Chỉ xuất **calib_fit**. Mỗi hàng giữ nguyên cả hai measurement. Chỉ module
status=ok mới có xác suất candidate; max chỉ có khi cả hai module đủ điều kiện.
Module lỗi/degraded không bị nâng trạng thái và không bị bỏ khỏi báo cáo.
Không tự đổi phép gộp thành logistic hoặc dùng test để chọn mô hình/threshold.

## Giới hạn bắt buộc

Report hiện không có stratum tấn công, mọi danh tính/nguồn/derivative/alias,
runtime số học đã đo, hoặc kết quả quality/presence/OOD trước router. Consumer
không điền giả các trường này. Output luôn diagnostic_only, không triển khai,
không LTT-ready; runtime/source crosswalk/gate chưa được chứng thực. Max ở đây
chỉ là candidate của hai module, không phải kết quả chính sách eKYC đầy đủ.

Để thêm select/evaluate cho mặt, cần đặc tả/thu thập metadata còn thiếu, kiểm
người–nguồn xuyên train/calib_fit/calib_ltt/test, khóa mô hình/calibrator/fusion,
chốt protocol quan sát độc lập/strata/quần thể rồi mới dùng core LTT đã có.
Không nối score CSV PAD/GenD khác tập theo số dòng hoặc suy loại tấn công từ
điểm. Chưa có dữ liệu/artifact thật đủ điều kiện cho bước này trên laptop.

Các JSON có ID/hàng thật để ngoài Git; chỉ công bố tổng hợp đã review. Metadata
và hash cục bộ giúp kiểm tính nhất quán, không phải chứng thực nguồn/quyền có
chữ ký. Unit/CLI fixture không phải phép đo accuracy hoặc nghiệm thu điện thoại.
