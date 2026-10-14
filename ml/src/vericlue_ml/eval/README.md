# Khung đánh giá chung (EVAL-01)

Đọc/sinh kết quả R1–R4 qua `vericlue_ml.eval`, không tự viết lại công thức ở
notebook hay script mô hình. `metrics.py` nhập **ECE/Brier** từ
`vericlue_ml.common.calibration`; `report.py` đọc CSV, bootstrap và sinh Markdown.
Chạy trên CPU, không tải ảnh/âm thanh hoặc trọng số. Nghiệm thu khung bằng dữ liệu
tổng hợp có đáp án biết trước; kết quả R1–R4 thật kiểm tại FACE-01/VOICE-01/ROUT-05.

## predictions.csv

Một dòng là một lần dự đoán; UTF-8, có header. **Tám cột bắt buộc:**

| Cột | Ý nghĩa |
|---|---|
| `sample_id` | ID mẫu, không trùng trong cùng module/phiên bản/compression |
| `subject_id` | ID người nhất quán qua các mẫu và tập chia; đơn vị bootstrap |
| `label` | `0` = bona fide/người thật, `1` = tấn công |
| `attack_type` | Strip khoảng trắng; label=1 cần loại tấn công, label=0 chỉ chấp nhận rỗng hoặc bona_fide |
| `prob_attack` | Xác suất đã hiệu chỉnh, hữu hạn trong [0,1]; bắt buộc có giá trị khi status=ok |
| `status` | `ok`, `error`, `degraded`, `not_applicable` theo ModuleResult |
| `module` | Module hợp lệ theo hợp đồng, ví dụ face_pad/face_deepfake/voice_spoof/lipsync |
| `model_version` | Phiên bản cụ thể, không được trống |

Giữ thêm các cột từ file chia tập nếu có: `path`, `source`, `region`; các cột tùy
chọn khác: `score`, `compression`. Score chỉ là metadata, không thay prob_attack
và không được diễn giải như xác suất cho ECE/Brier. Nếu chỉ có score, caller phải
áp calibrator đã khóa của ROUT-01 **trước khi xuất CSV**; thiếu calibrator là lỗi.
CSV không có status hoặc chứa cột không hỗ trợ, NaN/Inf, nhãn sai, dòng thiếu cột,
ID trống/trùng đều bị từ chối. Header trùng bị từ chối. `path` chỉ là metadata,
không dùng để đọc media. Không commit CSV dữ liệu thật hay kết quả tổng hợp giả
làm thực nghiệm.

Mặc định **bất kỳ dòng khác ok gây lỗi**, không xem error/degraded là pass.
Bật tay `exclude_non_ok=True` hoặc CLI `--exclude-non-ok` để loại các dòng đó;
prob_attack của dòng không ok có thể để trống. Báo cáo luôn có tổng đầu vào, số
mẫu dùng, và **số/tỷ lệ bị loại trên tổng đầu vào** của bona_fide cùng từng
attack_type, kể cả nhóm bị loại hoàn toàn. Chỉ số khi loại là kết quả có điều kiện
trên các dòng ok, không phải hiệu năng của toàn hệ thống. Không tạo xác suất giả
cho lỗi. Nếu mọi dòng bị loại, vẫn sinh báo cáo số mẫu/cảnh báo, chỉ số không khả dụng.

Các module/model_version được báo cáo riêng. Compression có thể phân nhóm bằng
cách lọc đầu vào trước khi gọi (không chọn cấu hình bằng kết quả lọc). Các mẫu
nén của cùng người vẫn dùng cùng subject_id để bootstrap giữ sự phụ thuộc.

## Quy ước chỉ số

`prob_attack >= threshold` là dự đoán tấn công/từ chối, bằng ngưỡng cũng từ chối.
Ngưỡng đánh giá không tối ưu theo CSV đánh giá. Nếu không truyền threshold/--threshold, báo cáo ghi rõ "mặc định 0.5, không do caller cung cấp"; ngưỡng truyền tường minh được ghi nguồn caller.
APCER là tỷ lệ tấn công lọt, theo từng loại; APCER max là lớn nhất theo loại.
BPCER là tỷ lệ người thật bị từ chối. AUC ROC dùng 1=tấn công. EER nội suy tuyến
tính tại giao BPCER/APCER gộp trên ROC. Không có lớp cần thiết thì chỉ số và CI
liên quan là **không khả dụng**, không điền 0 hay bịa mẫu.

Hai dòng **BPCER@APCER 5%** phải đọc riêng:

1. **Ngưỡng khóa từ calib_fit, APCER max:**
   `select_reference_threshold(calib_fit, dataset=..., split="calib_fit")` chọn
   ngưỡng benchmark lớn nhất để APCER của từng loại <=5%. Với n mẫu của loại,
   lấy score ở vị trí floor(0,05*n) của dãy tăng; lấy min qua các loại. Vì quyết
   định dùng >=, tie không bị chia. Calib_fit cần hai lớp, tất cả status=ok và
   đúng một module/phiên bản. Hàm từ chối split test/calib_ltt. Reference lưu
   commit Git, dataset, subject_ids, danh sách attack_types của calib_fit, module/version và target. JSON reference cũ thiếu attack_types bị từ chối, cần sinh lại từ calib_fit. Khi đánh giá,
   kiểm đúng phiên bản và **không giao người** giữa calib_fit và tập đánh giá. Nếu tập đánh giá có attack_type ngoài danh sách calib_fit thì in cảnh báo tên loại đó, không coi ngưỡng đã được kiểm trên loại mới.
   Reference chỉ là benchmark; không viết vào thresholds.yaml, không thay LTT.
   Thiếu reference cho nhóm thì ghi không khả dụng. Báo cả **APCER max thực đạt
   trên tập đánh giá** tại ngưỡng đó; không khẳng định nó vẫn <=5%.
2. **Mô tả, theo đường cong trên tập đánh giá, APCER gộp:**
   Nội suy BPCER trên ROC tại APCER gộp=5%, tương tự EER, để so công bố. Chỉ giữ
   giá trị chỉ số; **không trả, lưu hoặc dùng ngưỡng mô tả** trong API, reference,
   bootstrap hay Markdown. Các góc ROC được giữ nguyên; tại đúng APCER trùng
   lấy BPCER nhỏ nhất. Nội suy có thể tương ứng pha trộn quyết định ở nhóm tie,
   không phải một ngưỡng khả thi để vận hành. Chỉ số này không chứng nhận rủi ro.

Đánh giá không fit calibrator, không chọn mô hình. Theo ADR-0010, calib_fit dùng
cho thành phần học; calib_ltt là phần riêng ROUT-03/04. **EVAL-01 không dùng
calib_ltt/test để chọn cấu hình hoặc ngưỡng**, chỉ có phép đo ROC mô tả được chốt
ở trên. Caller chịu trách nhiệm lấy đúng dữ liệu đã chia theo người, không đổi
tên tập test/calib_ltt thành calib_fit; CSV không tự chứng minh được nguồn split.

## Khoảng tin cậy và truy vết

CI mặc định **95%, percentile, 2.000 lần, seed=42**; có thể cấu hình số lần/seed.
Lấy mẫu có hoàn lại theo **subject_id**, mỗi lần lấy người giữ tất cả dòng của
người đó và số lần người lặp lại. Chỉ số dòng của mỗi người được tính sẵn một lần trước vòng lặp, không quét lại vector subject ở mỗi lượt. Giữ nguyên ngưỡng đánh giá và ngưỡng tham chiếu
trong từng lượt, không chọn lại. Các chỉ số mô tả vẫn chỉ trả giá trị.

Lượt thiếu một lớp/loại tấn công không có chỉ số tương ứng, không thay bằng 0.
Báo số lượt bootstrap hợp lệ của từng chỉ số; APCER max cần đủ các loại tấn công
ban đầu còn có mẫu. Nếu không có lượt hợp lệ thì CI không khả dụng. Dưới **10
subject còn lại**, vẫn sinh báo cáo nhưng in cảnh báo CI không đáng tin. Bootstrap
percentile có thể suy biến ở tỷ lệ quan sát 0/1; không diễn giải CI [0,0] như
chứng minh rủi ro bằng 0.

Clopper–Pearson hai phía 95% bổ sung cho APCER từng loại và BPCER (kể cả BPCER
khóa). CP dùng số dòng và **giả định thử nhị thức độc lập**; không thay thế CI
bootstrap theo người và không áp trực tiếp cho APCER max hay chỉ số nội suy.

Commit báo cáo/Reference được lấy bằng **git rev-parse HEAD** trong repo được
chỉ định (mặc định suy ra repo chứa gói), thêm **-dirty** nếu git status có thay
đổi tracked/untracked. Không cho caller nhập commit báo cáo tùy ý. Repo Git thiếu
hoặc không có HEAD gây lỗi rõ. Báo cáo luôn có dataset, module/model_version, số
mẫu/người, ngưỡng được chốt, seed/số lần bootstrap. Kết quả phát sinh trước commit
code sẽ mang -dirty; chạy lại sau commit để có báo cáo truy vết phiên bản sạch.

## Chạy

```powershell
uv run python -m vericlue_ml.eval.report predictions.csv --dataset "dataset/test" --output outputs/evaluation.md --threshold 0.5 --seed 42 --n-bootstrap 2000
```

Có calib_fit riêng (không giao người với predictions.csv):

```powershell
uv run python -m vericlue_ml.eval.report predictions.csv --dataset "dataset/test" --output outputs/evaluation.md --calib-fit calib_fit.csv --calib-dataset "dataset/calib_fit"
```

Hoặc `--reference reference.json` có nguồn gốc được tạo trước bằng
`ReferenceThreshold.model_dump_json()`; không dùng cùng `--calib-fit`. Reference
chỉ áp cho đúng nhóm module/phiên bản; các nhóm khác ghi không khả dụng. Dùng
`--repo <repo>` khi gói cài ngoài checkout. Không cần GPU/matplotlib.

```python
from pathlib import Path
from vericlue_ml.eval.report import evaluate, read_predictions, write_report

rows = read_predictions(Path(predictions_path))
report = evaluate(
    rows, dataset=dataset_name, seed=42, n_bootstrap=2000, exclude_non_ok=True, repo=Path(repo_path)
)
write_report(report, Path(output_path))
```

Output ở đường dẫn caller cung cấp; mặc định ví dụ dùng outputs/ (gitignored).
R1–R4 thật chỉ được công bố sau khi code chạy trên dữ liệu đúng phiên bản; không
điền số liệu để hoàn thành task khung.
