# Sổ tay trưởng nhóm (người hoặc AI điều phối)

> Dành cho **phiên điều phối**: phiên không viết code sản phẩm, chỉ giao việc, duyệt PR, gom bàn giao và cập nhật `STATUS.md`.
> Với Claude Code: gõ `/lead`. Với AI khác: dán mục "Câu lệnh mở phiên" ở cuối file.

## 1. Phiên điều phối làm gì và không làm gì

| Làm | Không làm |
|---|---|
| Đọc bàn giao, gom vào `STATUS.md` | Sửa code trong `apps/`, `services/`, `ml/` |
| Viết prompt giao task cho Claude/Codex | Commit thay cho phiên của task khác |
| Duyệt PR theo task card và AGENTS.md §6, §8 | Tự gộp PR khi người dùng chưa đồng ý |
| Viết ADR, sửa tài liệu cho khớp quyết định | Đổi ngưỡng, hợp đồng, proposal mà không có ADR hoặc task |
| Theo dõi đường găng, tải từng người, câu hỏi mở | Sửa dòng backlog của task đang có phiên khác làm |

Phiên điều phối chạy ở thư mục chính `D:\Projects\Data4Life`. Thay đổi tài liệu của nó đi trên nhánh `docs/LEAD-<mô-tả>`.

## 2. Vòng lặp mỗi lần mở phiên

1. **Nắm tình hình** (5 phút):
   - `git fetch` rồi `git log --oneline origin/main -10`, `git worktree list`;
   - `uv run python scripts/plan_check.py`;
   - `uv run python scripts/new_handoff.py --latest 5`, đọc các file mới;
   - `gh pr list` (nếu có `gh`).
2. **Báo người dùng** bằng bảng ngắn: mỗi phiên/worktree đang làm task gì, trạng thái, việc cần người dùng làm (thử điện thoại, gộp PR, dán prompt).
3. **Xử lý theo thứ tự ưu tiên:**
   1. PR đang chờ duyệt (đừng để người khác chờ quá 12 giờ);
   2. phiên bị chặn hoặc có câu hỏi trong bàn giao;
   3. giao task kế tiếp cho phiên vừa rảnh (theo đường găng trong `plan_check.py`);
   4. cập nhật `STATUS.md`.
4. **Kết thúc phiên:** `/handoff LEAD`. Mục "Bước tiếp theo" phải ghi rõ đang chờ ai.

## 3. Duyệt PR

Giao cho subagent `reviewer` (chỉ đọc) hoặc chạy `/review-pr <MÃ>` trong worktree của PR. Trưởng nhóm tự kiểm thêm:

- PR làm đúng task card, không làm lan sang task khác;
- tiêu đề có `[contract]` nếu sửa `packages/contracts/`;
- không chạm `thresholds.yaml`, `proposal.md`, `docs/adr/` ngoài phạm vi task;
- có file bàn giao và dòng backlog đã đổi trạng thái;
- con số trong bàn giao/README chạy ra từ code (AGENTS.md §6 luật 9).

Kết luận gửi người dùng: **đạt / đạt sau khi sửa (liệt kê) / chưa đạt**. Người dùng là người bấm gộp.

**Duyệt chéo:** PR của Codex do Claude duyệt và ngược lại.

## 4. Giao task cho một phiên AI

Prompt giao việc gồm đủ 6 phần. **Luôn có phần 4 (subagent)**:

```
Bạn là phiên <Claude|Codex> ở worktree <đường dẫn>, làm task <MÃ>.
1. git fetch && git switch -c <loại>/<MÃ>-<mô-tả> origin/main
2. Đọc AGENTS.md, STATUS.md, bàn giao mới nhất của <MÃ>, task card <MÃ>.
3. Lưu ý riêng: <ADR liên quan, bẫy đã biết, quyết định tạm thời>.
4. Dùng subagent cho nhanh (docs/ai/working-with-ai.md, mục "Dùng subagent để làm nhanh hơn"):
   - đầu task: song song (a) tóm tắt task card + ADR, (b) tóm tắt code hiện có ở <thư mục>,
     (c) tóm tắt schema/bàn giao liên quan;
   - đang làm: subagent viết test ở file riêng / chạy test + lint; bạn viết code chính;
   - trước PR: subagent chỉ đọc rà theo task card + AGENTS.md §6, §8 (Claude: dùng `reviewer`);
   - chỉ bạn (phiên chính) commit; hai subagent không sửa cùng file.
   Codex: nếu không có subagent thì làm tuần tự theo đúng các bước trên.
5. Tóm tắt kế hoạch, CHỜ tôi duyệt rồi mới sửa code.
6. Xong: test + lint xanh, cập nhật backlog, /handoff <MÃ>, mở PR theo mẫu.
```

Trước khi giao, kiểm task đã `todo` và các task phụ thuộc đã `done` (`plan_check.py`).

## 5. Cập nhật STATUS.md

Chỉ trưởng nhóm sửa. Mỗi lần cập nhật:

- dòng đầu: ngày, sprint, số ngày còn lại tới 06/11;
- "Đang làm": mã, người · AI (worktree), trạng thái;
- "Bị chặn", "Câu hỏi mở": gom từ mục "Câu hỏi cho nhóm" của các bàn giao;
- "Quyết định gần đây": chỉ quyết định đã ghi ở ADR, PR hoặc bàn giao.

## 6. Luật subagent và phiên song song

- **Mỗi task một phiên chính.** Chỉ phiên chính commit và push.
- **Subagent** dùng để: đọc, tra cứu, chạy test, duyệt PR, hoặc viết vào **file riêng** được giao.
- **Hai subagent (hoặc hai phiên) không sửa cùng một file.**
- **Mỗi AI một worktree**, đặt ngang hàng với `Data4Life` (ví dụ `D:\Projects\vericlue-claude`), không lồng bên trong. **Mở phiên AI ngay tại thư mục worktree đó**; `Data4Life` chỉ dành cho phiên điều phối.
- Tạo worktree mới: `git worktree add -b <nhánh> ../vericlue-<tên> origin/main` (chạy trong `Data4Life`), rồi nhắc người dùng mở phiên AI ở thư mục mới.
- Hook pre-commit dùng chung `.venv` của `Data4Life`: không xóa `.venv` đó.

Chi tiết cho thành viên: `docs/ai/working-with-ai.md` mục "Subagent và nhiều phiên song song".

## 7. Nói chuyện với người dùng

- Câu ngắn, ít thuật ngữ; dùng bảng khi có nhiều phiên hoặc nhiều PR.
- Luôn nói rõ **người dùng cần làm gì tiếp** (dán prompt nào vào đâu, bấm gộp PR nào, thử gì trên điện thoại).
- Nếu người dùng "không thấy code": thường do code ở worktree khác hoặc chưa `git pull` trên `main`. Chỉ đường dẫn cụ thể.

## 8. Câu lệnh mở phiên (cho AI không có `/lead`)

```
Bạn là phiên điều phối (trưởng nhóm) của dự án VeriClue ở D:\Projects\Data4Life.
Đọc AGENTS.md, docs/ai/lead-playbook.md, docs/status/STATUS.md và bàn giao
LEAD mới nhất trong docs/status/handoffs/. Làm mục 2 của sổ tay rồi báo tôi
bảng tình hình và việc tôi cần làm. Không sửa code sản phẩm.
```
