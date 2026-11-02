# Bàn giao · ROUT-03 · Ngoc Quang+Codex · 2026-11-01 20:53

**Nhánh:** codex/ROUT-03-face-candidate-score, dựa PR123/f085806
**Trạng thái task sau phiên này:** doing — công cụ offline; chưa có ngưỡng mặt/giọng thật được chứng nhận

## Đã xong
- `eval.face_candidate.score_report` và CLI ghép max(PAD, GenD) trên calib_fit bằng calibrator frozen, đúng metadata producer `session_calibration.fit_report`.
- Kiểm exact module/version/reporthash/manifest/modelmanifest/commit/count/exclusions/groups. Mọi hàng khớp một-một người/split/label/video/challenge kể cả lỗi/unused; không inner join mất mẫu.
- Giữ measurement nguyên bản; probability chỉ cho module ok, max chỉ khi cả hai module đủ điều kiện. Lỗi/degraded vẫn còn và max null; không sinh quyết định xác minh hoặc nâng trạng thái.
- Snapshot bounded/recheck input, output mới ngoài input/config/model/data và commit thực thi sạch. Luôn diagnostic_only, undeployed, runtime_eligible=false/ltt_ready=false; runtime/crosswalk/gate/external attestation chưa kiểm chứng.
- PR122 và PR123 đã xanh CI 8/8. PR123 f085806: Python PostgreSQL16 **4851 passed,78 skipped**,240.11s. Không thay ngưỡng hoặc chạy trọng số mới.
- Review phát hiện output còn ghi được vào CALIBRATORS_DIR tùy chỉnh ngoài repo. Đã tái hiện RED rồi chặn cho cả face_candidate và nes2net_candidate, thêm regression thực qua score_report; review lại chấp thuận spec/chất lượng, không còn Critical/Important.
- Smoke subprocess từ source sạch **a47151e31311aee646855627853eb8979eb9dfa7** hoàn tất: 1 lệnh chấm synthetic thành công, 3 lệnh sai calibrator/ghi đè input/ghi vào CALIBRATORS_DIR bị từ chối đúng, không đổi input hoặc tạo output lỗi. 10 hàng calib_fit giữ nguyên, 8 đủ max và 2 thiếu max do module lỗi. Không nạp trọng số hay giải mã video.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Còn metadata producer mặt: stratum, crosswalk mọi người/nguồn/alias/derivative, runtime số học và gate quality/presence/OOD. Consumer score không thể suy chúng từ điểm; chưa select/evaluate LTT mặt.
- Thiếu dữ liệu tấn công có quyền/crosswalk, protocol độc lập/quần thể/strata/delta đã review và fitted artifacts thật. DNU chỉ bona fide, VIVOS32 chỉ parity. Chưa nghiệm thu Android ba luồng, OTP mô phỏng.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Nhóm chốt metadata/protocol cho producer mặt và bổ sung dữ liệu có nguồn/quyền đúng. Không ghép PAD/GenD CSV khác quần thể theo số dòng, không bịa attack type hoặc source IDs.
2. Khi có dữ liệu/artifact, chạy đúng phiên bản model/runtime, fit chỉ calib_fit, LTT chỉ calib_ltt, test sau artifact khóa. Chỉ đề xuất cài vào router sau review phép đo thật; không đổi các cờ false offline để ép đạt.
3. Khi có điện thoại, nghiệm thu CCCD/quay mặt/đọc câu và đăng ký→đăng nhập lại→khôi phục/consent theo checklist; không reset dữ liệu.

## Quyết định, lưu ý, bẫy
- Score calib_fit phục vụ kiểm artifact/chẩn đoán, không là ước lượng hiệu năng heldout. Max phản ánh ROUT-02 hiện tại, không giả là logistic fusion đã học.
- Mã người đơn trong SessionReport chưa đủ chứng minh nguồn/độc lập. Hash/metadata cục bộ là tự khai báo, không phải attestation có chữ ký. Không có API/Android/contract/threshold/migration thay đổi.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Cần chốt metadata producer v2 trước LTT mặt: loại tấn công đúng hệ, mọi danh tính và nguồn gốc/alias, quyền và usage, runtime, gate/phiên bản fusion; chốt mapping nguồn thực tế và quần thể/độc lập. Đây là thiết kế/thu thập cần review, không điền giả để hoàn tất code.

## Test đã chạy
<!-- lệnh + kết quả thật -->
- TDD consumer: RED→GREEN; **54 test mới đạt** sau bổ sung guard CALIBRATORS_DIR. Lỗi --help Windows cp1252 được tái hiện bằng subprocess rồi sửa description ASCII, regression đạt.
- Root nhóm face_candidate/session_calibration/calibration/router_fusion/router_policy/router_flows/router_profiles: **494 passed,1 skipped**,19.10s. Ca skip là tùy chọn có điều kiện, không tính là đã kiểm.
- Root nhóm chung face/voice candidates, calibration, router, LTT, readiness, utterance/parity sau sửa guard: **637 passed,17 skipped**,35.17s. Các skip là tùy chọn; reviewer độc lập chạy riêng 13 output-guard test đạt.
- Ruff toàn repo sạch, 868 file đúng format; plan_check0lỗi/10cảnh báo hiện có; diff --check sạch.
- Review cuối toàn diff f085806..a47151e chấp thuận Draft, không Critical/Important. Bằng chứng CLI chỉ số tổng hợp: `docs/status/results/ROUT-03-face-candidate-smoke-2026-11-01.json`; source/runtime/gate vẫn không được chứng nhận. CI nhánh mặt sẽ ghi trên Draft PR sau push; không lấy CI parent thay thế.
