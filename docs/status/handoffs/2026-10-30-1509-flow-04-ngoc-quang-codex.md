# Bàn giao · FLOW-04 · Ngoc Quang+Codex · 2026-10-30

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Adapter PAD/GenD chỉ dùng calibrator fitted non-provisional đúng module và full session-video version. Không nâng error/degraded thành đạt; thiếu artifact tiếp tục diagnostic.
- Công cụ collect/fit dùng session_views, kiểm nguồn/hash, nhóm người và split trước lọc lỗi; chỉ fit calib_fit. Giữ mọi mẫu lỗi, không xuất media/embedding, không chọn ngưỡng.
- Review độc lập phát hiện lỗi hash manifest tùy chỉnh. Hai regression test tái hiện đỏ; sửa dùng đúng ML_MODELS_MANIFEST và chặn manifest đổi trong lúc đo.
- Test tích hợp classifier fitted vẫn không vượt qua mandatory motion lỗi; các guard real/mixed/account-bound giữ nguyên.
- Hướng dẫn: docs/runbooks/session-face-calibration.md.

## Đang dở
- Chưa có tập video/lịch/nhãn phù hợp trong các nguồn đã kiểm; chưa fit artifact thật, số mẫu thật đo trong phiên này = 0. Không có số liệu độ chính xác mới.
- Chưa hoàn thiện hiệu chỉnh/đánh giá ChromaPulse, danh tính/continuity và giọng. Chưa mở ghi danh thật hoặc nghiệm thu điện thoại.
- SEC-09 quyền lưu mẫu tài khoản là phần kế tiếp, chưa được giải quyết bởi consent xử lý phiên.

## Bước tiếp theo
1. Chuẩn bị dữ liệu được phép sử dụng, snapshot lịch server cùng lượt, nhãn và nhóm người/nguồn; chia calib_fit/calib_ltt/test không giao nhóm.
2. Trên commit sạch, chạy collect riêng face_pad/face_deepfake rồi fit theo runbook. Kiểm các mẫu bị loại và provenance; đánh giá độc lập trước khi cấu hình CALIBRATORS_DIR và restart.
3. Thiết kế riêng SEC-09 lưu mẫu tài khoản và protocol giọng/danh tính; người dùng tự nghiệm thu Android sau.

## Quyết định, lưu ý, bẫy
- Collector gọi session_views + backend trực tiếp để đo raw score khi chưa có calibrator; kiểm identity/hash trước khi gán full session version. Nếu interface thay đổi phải sửa collector và adapter cùng nhau.
- Guard vốn đã đúng nên dùng regression hiện có và bổ sung integration test; không làm yếu policy để tạo vòng test đỏ giả.
- OTP mô phỏng giữ nguyên. Không sửa thresholds, hợp đồng, STATUS hoặc API guard. Không dùng fixture tổng hợp làm artifact production.
- Giữ local, không push/PR.

## Câu hỏi cho nhóm
- Tập dữ liệu đúng protocol video phiên, quyền sử dụng và nhãn/nhóm nguồn đang nằm ở đâu? Chưa tìm thấy trong các nguồn local/GitHub đã kiểm, không kết luận nhóm không có dữ liệu.

## Test đã chạy
- Suite ML adapter/collector/calibration/router + API motion/video identity/voice/account/guards: 533 passed, 0 failed/errors/skipped (JUnit integration.xml).
- CLI collect/fit --help chạy được; toàn bộ fixture trong test là tổng hợp, không phải nghiệm thu model trên người thật.
- plan_check.py: 0 lỗi, 10 cảnh báo tải công việc/đường găng hiện có.
