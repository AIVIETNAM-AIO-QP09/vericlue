# ml — Bộ não phát hiện giả mạo (gói `vericlue_ml`)

**Phụ trách:** M3 (face/, presence/), M4 (voice/, forensic/provenance), M5 (router/, eval/)
**Trạng thái:** PLAT-03 đã khởi tạo giao diện, registry và mock; ROUT-01 bổ sung hiệu chỉnh xác suất.

## Cấu trúc

| Thư mục | Nội dung | Epic |
|---|---|---|
| `src/vericlue_ml/common/` | `ModuleResult`, hiệu chỉnh xác suất, đọc video/âm thanh | E0 |
| `src/vericlue_ml/mock/` | Mô-đun giả lập cho mọi bộ phát hiện | E0 |
| `src/vericlue_ml/face/` | PAD (MiniFASNet), GenD, SBI, gộp điểm theo khung | E4 |
| `src/vericlue_ml/presence/` | Phân tích ChromaPulse (độ trễ, mức khớp), chấm điểm CamProbe | E3 |
| `src/vericlue_ml/voice/` | AntiDeepfake, PhoWhisper, căn chỉnh câu, kiểm tra câu đọc, SyncNet | E5 |
| `src/vericlue_ml/router/` | Hợp nhất, cổng ngoài phạm vi, Learn-then-Test (MAPIE), chính sách | E6 |
| `src/vericlue_ml/forensic/` | Chia đoạn, quét nguồn gốc (thủy vân, C2PA), báo cáo | E7 |
| `src/vericlue_ml/eval/` | Script sinh kết quả R1–R6 | E8 |
| `configs/models.yaml` | Mô hình nào, phiên bản nào, đường dẫn trọng số | |
| `configs/thresholds.yaml` | **Ngưỡng đã khóa** — chỉ sửa qua PR có kết quả đánh giá kèm theo | |
| `tests/` | Test (pytest) | |

## Quy ước bắt buộc

1. Mọi bộ phát hiện kế thừa giao diện `Detector` và trả `ModuleResult` (`docs/architecture/architecture.md` §3).
2. Mọi bộ phát hiện **phải có bản mock** cùng tên trong `mock/`.
3. Không hard-code đường dẫn: dùng `MODELS_DIR`, `configs/models.yaml`.
4. Tiền xử lý **đúng như repo gốc** của từng mô hình (ví dụ GenD: SCRFD, căn chỉnh 5 điểm, tỷ lệ 1,3, 224 px). Ghi rõ nguồn trong docstring.
5. Notebook chỉ để thử; code dùng thật phải chuyển vào `src/` và có test.
6. Kết quả đánh giá ghi kèm: commit, phiên bản mô hình, bộ dữ liệu, số mẫu.


## Hiệu chỉnh xác suất (ROUT-01)

`common/calibration.py` dùng nhãn **0 = người thật, 1 = tấn công**; điểm thô càng
cao càng giống tấn công. AUC < 0,5 trên dữ liệu fit gây `CalibrationError` để phát
hiện nhầm chiều; không tự đảo dấu điểm.

Tập calib được chia **theo người**, không giao nhau, thành:
- **calib_fit:** chỉ để hiệu chỉnh xác suất và học trọng số hợp nhất.
- **calib_ltt:** chỉ để chọn ngưỡng LTT; ROUT-01 không đọc hay fit trên phần này.

`fit(calib_fit, ...)` nhận `CalibFit` có `scores`, `labels`, `subject_ids`, `dataset`
và `split="calib_fit"`. Caller phải lấy đúng phần đã chia, không truyền calib_ltt
hay test dưới tên calib_fit. Tiền xử lý ảnh/âm thanh do detector thực hiện trước;
calibration chỉ nhận điểm, không đổi tiền xử lý và không tải trọng số.

Chọn phương pháp bằng **GroupKFold theo subject**, mặc định 5 phần (ít người hơn
thì dùng số phần bằng số người, tối thiểu 2). Mỗi phần fit phải có cả hai lớp,
không đủ thì báo lỗi để bổ sung dữ liệu hoặc chọn số phần phù hợp. So sánh log-loss
trên toàn bộ dự đoán ngoài fold (OOF, trọng số theo số mẫu). Chỉ thử/chọn isotonic
khi toàn calib_fit có **ít nhất 100 mẫu mỗi lớp**, và chỉ chọn khi log-loss OOF
thấp hơn Platt **ít nhất 2% tương đối**. Trường hợp còn lại dùng Platt. Sau khi
chọn, fit lại phương pháp thắng trên **toàn bộ calib_fit** được đưa vào.

Platt dùng logistic một chiều, chuẩn hóa score lúc fit, không cân bằng lớp để giữ
tiền nghiệm quan sát. JSON lưu slope/intercept đã quy đổi về score gốc. Isotonic
đơn điệu tăng, nội suy tuyến tính và chặn ngoài miền score. Mọi xác suất hiệu chỉnh
được cắt trong **[1e-4, 1-1e-4]**, epsilon cố định cũng được ghi vào JSON.

Artifact ở `ml/configs/calibrators/<module>/<version>.json` (không dùng `models/`).
`CalibrationStore(root=...)` nhận root tùy cấu hình; hoặc dùng `CALIBRATORS_DIR`,
mặc định suy ra thư mục configs từ vị trí gói. Khi đóng gói/triển khai cần chuyển
artifact cùng cấu hình và truyền root tương ứng. Ký tự phiên bản không hợp lệ
trong tên file được percent-encode (ví dụ `v1:a/b` → `v1%3Aa%2Fb.json`). Store cache
calibrator theo module/version; dùng store mới khi triển khai artifact thay thế.

JSON có module, model_version, method, parameters, epsilon, n_pos, n_neg,
log-loss/ECE/Brier trước và sau, bảng reliability trước và sau, ngày UTC, commit,
dataset, split, số fold và log-loss của các phương pháp. `prior_attack` tính
**π = n_pos / (n_pos + n_neg)** từ calib_fit cho FOR-04, không phải tỷ lệ tấn công
trong dân số. Caller cung cấp commit thật của phiên chạy và tên bộ dữ liệu;
không ghi số liệu tổng hợp như kết quả trên dữ liệu thật.

Chỉ số trước/sau trong artifact đều trên cùng mẫu: trước là **điểm thô cắt vào
[epsilon, 1-epsilon]**, sau là dự đoán **OOF**, không phải dự đoán fit lại trên dữ
liệu học. Khi score là logit hay thang điểm khác [0,1], số đo trước chỉ là baseline
`clipped_raw_score`, không có nghĩa điểm thô vốn đã là xác suất. ECE dùng 10 bin
đều, bin trái đóng/phải mở, bin cuối gồm 1; bin rỗng có giá trị None. Brier là
trung bình `(p-y)^2`. EVAL-01 nhập `ece` từ đây, không định nghĩa lại.

```python
from vericlue_ml.common.calibration import CalibFit, CalibrationStore, fit, reliability_markdown

# scores, labels, subject_ids chỉ lấy từ calib_fit của cùng module/version.
data = CalibFit(scores=scores, labels=labels, subject_ids=subject_ids, dataset=dataset_name)
artifact = fit(data, module="face_pad", model_version=model_version, commit=git_commit)
store = CalibrationStore()  # Khởi tạo/nạp ở lifespan, tái dùng giữa các request.
store.save(artifact)
print(reliability_markdown(artifact.after_reliability))
calibrated_result = store.apply(module_result)
```

Bắt buộc calibrator cho **face_pad, face_deepfake, voice_spoof, lipsync**. Miễn
**quality, chromapulse, camprobe, voice_challenge, provenance**, và mọi phiên bản
bắt đầu bằng `mock@` (fixture kịch bản PLAT-03). `store.apply` giữ score và các
trường hợp đồng, chỉ thay prob_attack trên bản sao. Kết quả không `ok` của module
bắt buộc được giữ nguyên status và xóa prob_attack. Thiếu/hỏng/sai phiên bản
calibrator hoặc thiếu score → **ném CalibrationError**, không fallback sang điểm
thô hay prob_attack có sẵn. **Lớp gọi phải bắt lỗi và trả ModuleResult status=error**
(với error_code hiện có, ví dụ E_INTERNAL); không được chuyển lỗi thành pass.
ROUT-01 cung cấp hàm dùng chung, không thay registry hay mock hiện tại; detector
thật/lớp orchestration phải gọi hàm này khi được triển khai.

`reliability_table` trả dữ liệu bin; `reliability_markdown` sinh bảng Markdown.
PNG chỉ dùng `plot_reliability(rows, destination)` khi cài extra tùy chọn:
`uv sync --all-packages --extra eval`. Matplotlib import lười, CI/test mặc định
không cần matplotlib. Không commit dữ liệu, trọng số hay PNG phát sinh; artifact
calibrator số và metadata có thể được review trong configs.

## Định dạng predictions.csv cho EVAL-01

Mỗi dòng giữ các cột của file chia tập:
`path,label,attack_type,subject_id,source,region`, bổ sung `module,model_version`
và **score hoặc prob_attack** (có thể có cả hai); `compression` là cột tùy chọn.
Nhãn 0 = người thật, 1 = tấn công; score càng cao càng giống tấn công;
prob_attack nằm trong [0,1]. Không trộn module/phiên bản khi hiệu chỉnh. Giữ
subject_id nhất quán để chia tập và bootstrap theo người, không theo dòng.
Điểm thô chưa có calibrator không được diễn giải như xác suất để tính ECE.

EVAL-01 được nghiệm thu bằng dữ liệu tổng hợp có đáp án biết trước. Việc xác nhận
R1–R4 thật được sinh bằng khung chung thực hiện ở FACE-01/VOICE-01/ROUT-05;
không tạo hay tuyên bố kết quả thực nghiệm khi các task đó chưa chạy.
