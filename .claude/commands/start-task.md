---
description: Nạp bối cảnh và bắt đầu một task theo mã (ví dụ /start-task FACE-02)
argument-hint: <MÃ-TASK>
---

Bắt đầu task **$ARGUMENTS** của dự án VeriClue.

1. Đọc `docs/status/STATUS.md`. Chạy `uv run python scripts/new_handoff.py --latest 5` và đọc các bàn giao liên quan tới $ARGUMENTS (tên file chứa mã task).
2. Tìm task card `$ARGUMENTS` trong `docs/plan/epics/` và đọc kỹ toàn bộ: mục tiêu, phụ thuộc, đầu vào/đầu ra, các bước, tiêu chí hoàn thành.
3. Kiểm tra các task phụ thuộc trong `docs/plan/backlog.md` đã `done` chưa. Nếu chưa, dừng lại và báo.
4. Đọc các file được liệt kê ở mục "Đọc trước" của task card, cùng `docs/architecture/architecture.md` nếu task chạm tới API, mô-đun hoặc dữ liệu.
5. Tóm tắt lại cho người dùng bằng tiếng Việt, ngắn gọn:
   - mục tiêu;
   - kế hoạch các bước;
   - file sẽ tạo hoặc sửa;
   - rủi ro hoặc câu hỏi còn mở.
6. Chờ người dùng xác nhận rồi mới sửa code. Khi làm, tuân thủ AGENTS.md §6–§8.
