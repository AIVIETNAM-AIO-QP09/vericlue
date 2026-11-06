# Bàn giao — README, CONTRIBUTING và LICENSE

**Ngày:** 06/11/2026. **Người thực hiện:** Codex, theo yêu cầu trực tiếp.
**Task:** bảo trì tài liệu gốc, chưa có task card riêng; không đổi trạng thái
task tính năng trong backlog và không sửa STATUS.

## Đã làm

- Viết lại README theo trọng tâm Android/eKYC, bảo mật và tích hợp đa dịch vụ.
  Tách thành phần đang có với ví/BBS chưa tích hợp hoàn chỉnh; loại tuyên bố
  nháy màu bảo đảm người thật, phát hiện camera ảo và ngưỡng thống kê đã đạt.
- Thay hướng dẫn nền tảng đang xây dựng bằng các entrypoint cài đặt, README
  thành phần và launcher runtime có sẵn. Giữ cảnh báo runbook có mốc lịch sử.
- Cập nhật CONTRIBUTING: quy trình review, hợp đồng, check theo phạm vi, dữ
  liệu/consent, giấy phép và bàn giao; không cấp quyền sở hữu hoặc license mới.
- Giữ nguyên phần độc quyền/bảo lưu quyền của LICENSE, thêm phân định quyền
  upstream, trọng số, dữ liệu và tài sản ngoài code nhóm.
- Lượt tiếp theo theo yêu cầu trình bày sản phẩm: bổ sung phần đầu README,
  gallery bốn snapshot Compose, hành trình, Mermaid kiến trúc và bảng cơ chế
  bảo mật. Hướng dẫn chạy, điều kiện nghiệm thu và giới hạn ở phần dưới.
- Thêm `docs/assets/app/` với PNG nguyên byte, README nguồn và provenance JSON.
  Kiểm bằng mắt cả bốn ảnh, không có dữ liệu cá nhân thật; tổng PNG 391.240 byte.
  Nguồn UI ngày 04/11, commit `24fe76d`, không gọi là ảnh của build mới nhất.
- Phát hiện lỗi encoding do truyền tiếng Việt qua stdin PowerShell ở lượt
  trước. Đã viết lại README/CONTRIBUTING bằng apply_patch và kiểm nội dung
  tiếng Việt; bản cuối không dùng file bị lỗi đó.

## Kiểm tra

- Tất cả liên kết local trong README/CONTRIBUTING tồn tại, UTF-8 hợp lệ.
- Đối chiếu SHA-256 của bốn PNG với manifest nguồn, kiểm lại file đích.
- Kiểm ảnh không bị gitignore; link ảnh có alt text và kích thước hiển thị.
- `git diff --check`: đạt.
- `.venv/Scripts/python.exe scripts/plan_check.py`: 0 lỗi, 10 cảnh báo lịch
  tải công việc/đường găng; không đổi backlog trong lượt này.
- Không chạy test ứng dụng hoặc mô hình: chỉ sửa tài liệu.

## Phạm vi và câu hỏi cho nhóm

- Không đổi API, ngưỡng, runtime, schema, proposal, ADR hoặc AGENTS.
- STATUS và một số runbook vẫn có mô tả lịch sử; README trỏ rõ để người đọc
  đối chiếu. Cần task riêng nếu đồng bộ toàn bộ tài liệu thiết kế.
- Nếu nhóm muốn phát hành nguồn mở, cần chốt giấy phép và quyền của các chủ
  sở hữu; lượt này không đổi chính sách cấp phép hiện có.
- Chưa commit/push. Giữ nguyên file nghiên cứu untracked của người dùng.
