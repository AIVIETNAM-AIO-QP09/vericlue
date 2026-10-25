# FLOW-03/FLOW-05 — cầu nối OCR/QR và AdaFace vào Android

Yêu cầu người dùng: UI trên main, quét CCCD rồi kiểm tra/sửa hoặc dùng QR; so mặt
ngưỡng 0.40. Đã merge main 59f16f9 vào nhánh feat/FLOW-05-identity-lab.

Server opt-in `IDENTITY_LAB_URL`: đọc QR từ ảnh, fallback detector/VietOCR pretrained,
không tin QR client. Lưu bản quét và xác nhận riêng, ID dạng HMAC; ghi thay đổi,
rescan hủy xác nhận, không thay thẻ sau nhận media. AdaFace so với still đầu tiên,
ngưỡng cosine 0.40 configurable, lỗi/thiếu/xung đột không tự đạt. Không trả điểm cho app.

Android: không dùng mẫu khi OCR thiếu ID, sửa được số ID, validate đủ trường/ngày,
không cho live flow thiếu ảnh/fields nhảy qua bước thẻ. Có test Kotlin mới.

Runtime riêng localhost Python3.10 giữ weights nạp một lần, API Python3.12 gọi HTTP.
Không đổi JSON contract công khai, OpenAPI check đạt. Không sửa LVFace registry,
thresholds.yaml hoặc gỡ chặn real/mixed dynamic flow. Chế độ demo có OCR/face thật
và các detector còn lại mock; không đạt nghiệm thu production.

Kiểm tra: full services/api/tests exit0 (có test skipped theo môi trường); 103 lab tests
cũ pass, test scanner QR mới pass; Ruff sạch. Runtime thực HTTP200 đọc QR/so mặt.
Chưa build APK/chạy Kotlin tests vì máy thiếu Android SDK và JDK17 (người dùng xác nhận).
Chưa thử hai mặt thẻ thật qua camera Android; chưa hiệu chỉnh FAR/FRR ngưỡng0.40.

Runbook: docs/runbooks/identity-integration.md. FLOW-03/05 giữ doing; không đổi STATUS.
Nhóm cần kiểm tra Android build/camera và hoàn tất security/retention, các detector
còn thiếu trước khi bật real eKYC. Không public cổng runtime /internal.
