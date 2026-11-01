# Offline LTT và kiểm artifact — Implementation Plan

> For agentic workers: dùng subagent-driven-development; người điều phối tích hợp và tổ chức review độc lập. Không xóa workspace hay dữ liệu.

**Goal:** hoàn thiện công cụ có thể chạy trước nghiệm thu điện thoại, không biến dữ liệu thiếu thành kết quả đạt.

**Architecture:** công cụ nghiên cứu offline tách khỏi router chạy thật; candidate probability không sửa ModuleResult. LTT dùng MAPIE 1.4.1, Hoeffding–Bentkus nhị phân, max-p qua các strata rồi Holm qua toàn lưới. Báo cáo luôn không đủ điều kiện triển khai.

**Tech Stack:** Python 3.12, Pydantic, MAPIE, pytest; PostgreSQL regression trên DB test riêng hoặc CI.

**Spec:** E6-router ROUT-03; ADR-0006; ADR-0010; nes2net-utterance-calibration runbook; API migration 0011.

## Global Constraints

- Không sửa thresholds.yaml, contracts, ADR, proposal hoặc STATUS.md. Không merge main.
- Không fit dữ liệu thật khi chưa có lớp tấn công có quyền sử dụng và chia người/nguồn; VIVOS parity nằm ngoài hiệu chỉnh.
- Mỗi stratum chỉ tối đa một quan sát được định trước trên mỗi thành phần phụ thuộc người/nguồn. Không tự khử trùng sau khi xem điểm.
- Protocol phải khai báo trước lưới, strata, alpha, delta riêng cho mặt/giọng, quần thể, phương pháp lấy mẫu và tiêu chí chọn. Khai báo là bằng chứng tự mô tả, không phải chứng thực bên ngoài.
- Điểm candidate là chẩn đoán; kết quả degraded/error không đổi thành ok/pass.
- Không dùng test để chọn mô hình, calibrator hay ngưỡng. Đánh giá test chỉ sau artifact LTT đã khóa và kiểm lại liên kết.
- Không xóa dữ liệu/model/media, khởi động API có cleanup trên media thật, đăng nhập hay đồng ý điều khoản thay người dùng.

## Review Focus

Độc lập thống kê khác với chia tập; multiplicity qua toàn lưới; ràng buộc runtime/model/calibrator; rò rỉ người và nguồn xuyên báo cáo; thay đổi input trong khi chạy; output không thể ghi đè input/config; không tuyên bố bảo đảm thực tế từ fixture.

## Task 1: LTT core và kiểm toán thống kê

Thêm router/ltt.py và test. Hỗ trợ lưới giọng một ngưỡng và mặt (B,A), inclusive pass; ba trạng thái mặt đếm riêng. Dùng MAPIE đã pin, kiểm p-value bằng oracle độc lập trong test. Missing strata, trùng component trong stratum, lỗi score/protocol phải fail closed. Kết quả không có candidate hợp lệ trả selected=null. Candidate hợp lệ chỉ là kết quả thống kê có điều kiện, luôn runtime_eligible=false.

## Task 2: Candidate artifact và đường đánh giá khóa

Thêm eval/nes2net_candidate.py và test; dùng validator measurement hiện có. Kiểm fit envelope nghiêm ngặt, counts/exclusions/dataset/commit, runtime và parity binding. Gộp mọi hàng từ mọi measurement riêng biệt để kiểm người/nguồn/file/PCM xuyên tập; không bỏ cầu nối do lỗi. Candidate probability là trường riêng. Chấm điểm không refit; không đánh giá test trước LTT hợp lệ. Thêm CLI offline và smoke fixture có nhãn synthetic rõ ràng.

## Task 3: PostgreSQL consent regression

Test riêng cho migration 0011: grant đồng thời trả cùng receipt và một hàng; UPDATE/DELETE bị P0001; FK receipt sai bị 23503; rollback giữ receipt/link hợp lệ. Dùng fixture test PostgreSQL hiện có; nếu không có DB local thì báo skip và xác nhận bằng CI, không dùng DB sản phẩm.

## Task 4: Tích hợp, review và bàn giao

Chạy test liên quan, lint, plan_check, kiểm dữ liệu/bí mật trong diff; reviewer độc lập kiểm spec + chất lượng. Cập nhật task card/backlog đúng phần đã làm, giữ phần chứng nhận dữ liệu thật chưa xong. Ghi bàn giao và Draft PR riêng dựa trên PR121; không merge.

## Task 5: Ghép điểm mặt từ producer hiện có (bổ sung sau audit)

**Goal:** hoàn thiện phần code nhỏ còn tự làm được trước dữ liệu/điện thoại:
consumer chấm điểm PAD/GenD trên calib_fit, không chọn ngưỡng hay coi các gate
chưa đo là đạt. Spec: session_calibration.SessionReport/fit_report và max fusion
hiện tại của ROUT-02. File mới eval/face_candidate.py và test_face_candidate.py.

- Nhận --pad-report/--gend-report/--pad-calibrator/--gend-calibrator/--output.
  Chỉ xuất calib_fit. Không fit hoặc tự chọn model/fusion; giữ max hiện tại.
- Hai report hợp lệ, cùng dataset/manifest; exact modules/versions; không inner
  join. Mọi hàng khớp ID/người/split/label/video/challenge hash, kể cả hàng lỗi
  hoặc split không xuất; kiểm phân vùng theo khả năng producer hiện có.
- Calibrator fitted nonidentity/nonprovisional đúng module/version, counts,
  commit và metadata dataset JSON do session.fit_report tạo: exact reporthash,
  manifest/modelmanifest/sourcecommit/selected/usable/excluded/groups.
- Hàng lỗi vẫn xuất cả hai measurement nguyên bản; xác suất ứng viên chỉ tính
  từ module có status ok, max chỉ khi cả hai module đủ điều kiện. Không tạo
  ModuleResult ok thay dữ liệu lỗi; không xuất quyết định pass/review.
- Hash snapshot bounded và kiểm input không đổi trước output mới; cấm output
  input/config/model/data. Ghi executioncommit thực và mọi binding nguồn.
- Luôn diagnostic_only=true/deployed=false/runtime_eligible=false/ltt_ready=false,
  source_crosswalk_verified=false/prior_gates_measured=false. Producer hiện
  thiếu strata/alias/donor/source và quality/presence/OOD; không suy độc lập từ
  subject_id hoặc tuyên bố router đầy đủ được mô phỏng.
- TDD: chấm max đúng, sai liên kết/phiên bản/metadata/count bị chặn, thiếu/mất
  hàng hoặc video/challenge khác bị chặn, lỗi giữ nguyên và max null, thay input
  khi predict không output, output bảo vệ, không refit, CLI chỉ calib_fit.
- Root tổ chức review độc lập, chạy test phù hợp, handoff và Draft riêng sau
  PR123. Không sửa producer hay tự thiết kế metadata thu thập thay nhóm.

## Rulings và tiến độ

- Ruling: thực hiện thiết kế đã được chấp thuận trong ADR/task card, giới hạn đầu ra offline; không phát hành ngưỡng thật khi thiếu dữ liệu — tránh suy diễn bảo đảm thống kê hoặc thay đổi runtime.
- Ruling: mục tiêu mặt là tỷ lệ review ngay bước mặt, đếm voice_challenge riêng; chưa có dữ liệu ghép mặt–giọng để chứng minh tỷ lệ review cuối luồng.
- Ruling: không chứng nhận độc lập chỉ từ mã người duy nhất; protocol thu thập và phạm vi áp dụng vẫn cần nhóm xác nhận trước phép đo thật.
- Task 1: complete — 48 test đạt, reviewer độc lập chấp thuận spec/chất lượng; không chứng nhận dữ liệu thật.
- Task 2: complete về code/review — 54 test mới đạt; consumer/CLI/đánh giá khóa không mở chốt runtime.
- Task 3: complete — CI PR122 8/8 đạt, job Python 4749 passed/78 skipped với PostgreSQL16. Nhóm 333 test API khác đạt local.
- Task 4: complete về review/kiểm thử/bàn giao — full Python 4810 đạt/119 skip; smoke subprocess 4 thành công + 2 từ chối dự kiến. Draft riêng xếp sau PR122; không merge, không chứng nhận ngưỡng thật.
- Task 5: code/review complete — 54 test mới, nhóm chung 637 đạt/17 skip;
  đã sửa guard CALIBRATORS_DIR cho cả mặt/giọng sau review. Smoke và CI cuối
  đang thực hiện. Audit xác nhận định dạng producer cho phép consumer score
  nhỏ mà không cần bịa strata hoặc gate; các producer metadata để LTT mặt cần
  đặc tả/thu thập riêng. Nhánh codex/ROUT-03-face-candidate-score dựa PR123.
