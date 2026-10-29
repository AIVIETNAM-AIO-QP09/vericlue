# Bản lưu các thay đổi cục bộ — 29/10/2026

Nhánh `backup/local-drafts-2026-10-29` lưu các file chưa commit khi người dùng
đề nghị push toàn bộ code. Đây là bản nháp, chưa nghiệm thu để tích hợp.

- Nền snapshot: `fix/SEC-04-image-rescan`, commit `377f45e`.
- `core/config.py` và `core/security_profile.py`: sao nguyên trạng từ worktree
  `security-files`; chưa tích hợp hoặc kiểm chứng như một tính năng hoàn chỉnh.
- Báo cáo kiểm tra model ngày 24/10: bản tài liệu cục bộ được giữ nguyên.
- Bàn giao DATA-03 ngày 18/10: bản nháp từ worktree `vericlue-data`, phản ánh
  thời điểm ghi tài liệu, không phải xác nhận trạng thái dữ liệu hiện tại.

Kiểm tra cho bản lưu này: cú pháp Python, cấu trúc JSON, bản sao khớp byte,
và rà mẫu khóa/token thông dụng. Không chạy lại kiểm thử chức năng cho các bản
nháp; không tuyên bố chúng sẵn sàng sử dụng. Không thay đổi bản app/server đang
chạy. Các file gốc và worktree gốc được giữ nguyên.

Code Android mới nhất nằm trên `fix/APP-10-qr-responsiveness` (PR #115),
phụ thuộc PR #114 và #112. Không dùng nhánh backup này thay bản Android đó.
