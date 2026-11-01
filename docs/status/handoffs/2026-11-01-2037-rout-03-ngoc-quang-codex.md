# Bàn giao · ROUT-03 · Ngoc Quang+Codex · 2026-11-01 20:37

**Nhánh:** codex/ROUT-03-offline-candidates
**Trạng thái task sau phiên này:** doing — phần công cụ offline; chưa chứng nhận ngưỡng thật

## Đã xong
- Core MAPIE 1.4.1 HB nhị phân: max-p qua các strata bắt buộc, Holm một lần qua toàn lưới. Voice t và face (B,A) giữ đúng biên inclusive, review/challenge tách riêng.
- Protocol khai báo trước lưới/strata/alpha/delta/quần thể/cách lấy quan sát, từ chối trùng thành phần người–nguồn trong cùng stratum. Tất cả output provisional, diagnostic_only, runtime_eligible=false.
- Core 48 test đạt và review thống kê/spec/chất lượng độc lập chấp thuận; không sửa thresholds.yaml, contracts, ADR hoặc STATUS.md.
- Consumer `eval.nes2net_candidate` + `scripts/fit_thresholds.py`: fit envelope/model/runtime/parity nghiêm ngặt, kiểm rò rỉ trên hợp mọi hàng kể cả hàng lỗi, xác suất candidate riêng và giữ ModuleResult degraded. Đánh giá test chỉ sau kiểm lại toàn artifact LTT/protocol, không refit/chọn ngưỡng trên test.
- Có commit thực thi riêng cho score/select/evaluate; báo cáo số loại/lớp thiếu và max APCER chỉ trên strata quan sát được. 54 test mới đạt; reviewer độc lập chấp thuận spec/chất lượng, không có Critical/Important.
- Công việc PostgreSQL độc lập nằm PR122/47f3209: **CI 8/8 đạt**, job Python **4749 passed, 78 skipped** trên DB vericlue_test. 333 test API liên quan đạt local; không đổi production API/migration/Android.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Full suite và smoke subprocess đang chạy/chuẩn bị ở commit code; chưa có phép fit hoặc LTT thật.
- Chưa có lớp TTS/VC đủ quyền/crosswalk nguồn–người. DNU chỉ bona fide; VIVOS32 chỉ parity, tuyệt đối không hiệu chỉnh. Không có artifact nhận diện/hiệu chỉnh đầy đủ để mở chốt sinh trắc.
- Chưa có điện thoại; demo AI thật toàn luồng chưa nghiệm thu, OTP vẫn mô phỏng.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Khi có dữ liệu hợp lệ, review quyền + protocol lấy một quan sát độc lập/nhóm/stratum trước khi đo. Chốt đủ train/calib_fit/calib_ltt/test theo mọi người/nguồn, không chọn lại bằng test.
2. Đo đúng version toàn câu/runtime đã ghim; fit chỉ calib_fit, kiểm envelope, LTT chỉ calib_ltt, khóa artifact rồi mới đánh giá test.
3. Chỉ đề xuất cài ngưỡng sau review kết quả thật và phạm vi áp dụng; không đưa artifact offline trực tiếp vào router. Cần consumer face đã gắn fusion/calibrator và dữ liệu mặt–giọng ghép trước bảo đảm cuối quy trình.
4. Khi có máy: cài đè giữ dữ liệu, thử CCCD/quay mặt/đọc câu, đăng ký → đăng nhập lại → khôi phục và consent/rút lại theo checklist.

## Quyết định, lưu ý, bẫy
- 59/60 clip không tự đủ: nhiều clip cùng người không độc lập; Holm qua lưới và nhiều strata cần ngân sách kiểm định chung. Không hạ alpha/đổi lưới/bỏ loại khó sau xem kết quả.
- Mục tiêu hiện là review ngay từng bước trên bona fide, chưa phải review cuối luồng; union bound cần sự kiện/quần thể tương thích và delta phân bổ chung.
- Metadata/attestation là tự khai báo, không phải chứng thực nguồn bên ngoài. Không xóa workspace/data/model/media, không khởi động API cleanup trên media thật, không merge main.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Cần nhóm xác nhận protocol lấy mẫu độc lập, quần thể triển khai, danh sách hệ TTS/VC/loại mặt bắt buộc, phân bổ delta, và nghĩa của review cuối luồng trước chứng nhận thực tế.
- ADR-0006/0010 và proposal có câu 59/60 mẫu dễ bị hiểu như đủ cho cả lưới; đề nghị task riêng sửa giải thích điều kiện độc lập/multiplicity, không tự sửa file được bảo vệ trong phiên này.

## Test đã chạy
<!-- lệnh + kết quả thật -->
- Core: RED thiếu module → 48 GREEN; root và reviewer độc lập chạy lại 48 đạt. Ruff core/test sạch.
- Candidate: 54 test mới đạt (có RED→GREEN); nhóm candidate/utterance/readiness đạt 67, 16 skip do thiếu SoundFile ở env test local. Root nhóm LTT/candidate/readiness/utterance/parity binding đạt **140 passed, 16 skipped**.
- API local: 333 passed, 42.04s; test PostgreSQL local skip do không DB. CI PR122 trên PostgreSQL16: 4749 passed, 78 skipped, 173.67s; 8/8 job đạt.
- plan_check tại core commit: 0 lỗi, 10 cảnh báo tải/đường găng hiện có.
- Ruff toàn repo sạch, 863 file đúng format; `uv lock --check` sạch. CLI module/wrapper --help exit0. Full suite/subprocess smoke chưa được tính vào kết quả trên.
