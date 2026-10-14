# CLAUDE.md

Toàn bộ luật và bối cảnh của dự án nằm trong AGENTS.md (dùng chung cho Codex, Claude Code và thành viên mới):

@AGENTS.md

## Riêng cho Claude Code

- Lệnh tắt có sẵn trong `.claude/commands/`:
  - `/start-task <MÃ>` — nạp bối cảnh và bắt đầu một task.
  - `/handoff` — ghi bàn giao trước khi kết thúc phiên.
  - `/status` — tóm tắt tình trạng dự án.
  - `/review-pr` — tự rà một thay đổi theo Definition of Done.
  - `/lead` — mở phiên điều phối (trưởng nhóm): nắm tình hình, duyệt PR, giao việc. Xem `docs/ai/lead-playbook.md`.
- Subagent `reviewer` (`.claude/agents/reviewer.md`): duyệt PR, chỉ đọc. Luật subagent: `docs/ai/working-with-ai.md`.
- Khi phiên chat đã dài, chạy `/handoff` rồi mở phiên mới và chạy `/start-task <MÃ>`. Bối cảnh sẽ được nạp lại từ file, không phụ thuộc trí nhớ của phiên cũ.
- Chỉ commit hoặc push khi người dùng yêu cầu.
