---
description: Mở phiên điều phối (trưởng nhóm) — nắm tình hình, duyệt PR, giao việc, cập nhật STATUS
argument-hint: "[việc cụ thể, ví dụ: duyệt PR #4]"
---

Bạn là **phiên điều phối** của dự án VeriClue. Làm theo `docs/ai/lead-playbook.md`.

1. Đọc `docs/ai/lead-playbook.md`, `docs/status/STATUS.md` và bàn giao `LEAD` mới nhất trong `docs/status/handoffs/` (tên file chứa `lead`). Làm tiếp từ mục "Bước tiếp theo" của bàn giao đó.
2. Nắm tình hình (mục 2 của sổ tay):
   - `git fetch`, `git log --oneline origin/main -10`, `git worktree list`;
   - `uv run python scripts/plan_check.py`;
   - `uv run python scripts/new_handoff.py --latest 5`, đọc các bàn giao chưa gom;
   - `gh pr list` nếu có `gh`.
3. Báo người dùng bằng tiếng Việt, đơn giản, tối đa 15 dòng:
   - bảng: worktree/phiên → task → trạng thái → đang chờ ai;
   - PR cần duyệt, câu hỏi cần người dùng quyết;
   - **việc người dùng cần làm ngay** (dán prompt nào, gộp PR nào, thử gì).
4. Nếu có yêu cầu cụ thể: **$ARGUMENTS** — ưu tiên làm việc đó.
5. Duyệt PR: giao cho subagent `reviewer`, rồi tự kiểm thêm theo mục 3 của sổ tay. Kết luận: đạt / đạt sau khi sửa / chưa đạt.
6. Không sửa code sản phẩm. Thay đổi tài liệu đi trên nhánh `docs/LEAD-<mô-tả>`. Chỉ commit, push hoặc gộp khi người dùng yêu cầu.
7. Trước khi kết thúc phiên: `/handoff LEAD`.
