---
description: Ghi bàn giao trước khi kết thúc phiên (để phiên/AI sau làm tiếp được)
argument-hint: "<MÃ-TASK>"
---

Kết thúc phiên làm việc hiện tại cho task **$ARGUMENTS** một cách có thể bàn giao:

1. Xem lại những gì đã làm trong phiên: file đã sửa (`git status`, `git diff --stat`), test đã chạy và kết quả **thật**.
2. Tạo file bàn giao:

   ```bash
   uv run python scripts/new_handoff.py --task $ARGUMENTS --who "<tên người>+Claude"
   ```

   Điền đủ các mục trong file vừa tạo:
   - đã xong;
   - đang dở (file:dòng);
   - **bước tiếp theo**, viết đủ rõ để người khác làm ngay mà không cần hỏi lại;
   - quyết định, lưu ý, bẫy;
   - test đã chạy.
3. Cập nhật **dòng của task** trong `docs/plan/backlog.md` (trạng thái, người) và đánh dấu các tiêu chí đã đạt trong task card.
4. Chạy `uv run python scripts/plan_check.py`. Nếu có lỗi, sửa trước khi kết thúc.
5. Nếu có vướng mắc cần cả nhóm quyết, ghi vào mục "Câu hỏi cho nhóm" trong file bàn giao. Trưởng nhóm sẽ gom vào `STATUS.md`.
6. Báo lại cho người dùng 3–5 dòng tóm tắt bằng tiếng Việt. Không commit nếu người dùng chưa yêu cầu.
