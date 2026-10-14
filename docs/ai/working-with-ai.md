# Làm việc với AI (Codex, Claude Code…) trong dự án VeriClue

## Vấn đề cần giải quyết

AI không nhớ gì giữa các phiên chat. Phiên quá dài thì AI bắt đầu quên phần đầu, làm sai hoặc làm lệch thiết kế. Mỗi người trong nhóm lại dùng một AI khác nhau.

## Cách giải quyết: "trí nhớ nằm trong repo, không nằm trong phiên chat"

Mọi thứ AI cần biết đều được ghi thành file trong repo. Phiên mới, AI khác hay người mới chỉ cần đọc đúng các file đó là bắt kịp ngay.

| File | Vai trò | AI tự đọc? |
|---|---|---|
| `AGENTS.md` | Luật chung, bản đồ repo, quy trình | **Codex: tự đọc.** Claude: đọc qua `CLAUDE.md` |
| `CLAUDE.md` | Trỏ tới AGENTS.md + lệnh tắt của Claude | **Claude Code: tự đọc** |
| `docs/status/STATUS.md` | Dự án đang ở đâu, ai làm gì | Phải nhắc AI đọc |
| `docs/plan/epics/*.md` | **Task card**: mỗi việc có đủ mục tiêu, bước, tiêu chí xong | Phải chỉ đúng mã task |
| `docs/status/handoffs/` | Bàn giao giữa các phiên, **mỗi lần một file** | Phải nhắc AI đọc và ghi |
| `scripts/plan_check.py` | Bảng trạng thái, tải từng người, đường găng | AI chạy lệnh |
| `docs/architecture/architecture.md` | Thiết kế kỹ thuật | AI đọc khi task cần |

## Quy trình 1 task = 1 phiên

```
Mở phiên mới → giao 1 mã task → AI đọc bối cảnh, tóm tắt kế hoạch → bạn duyệt
→ AI làm → chạy test → AI ghi handoff → bạn review → commit/PR → đóng phiên
```

**Mẹo quan trọng:**

1. **Mỗi phiên chỉ làm 1 task** (hoặc 1 phần rõ ràng của task). Đừng dồn nhiều việc vào một phiên.
2. **Phiên dài thì dừng chủ động.** Khi thấy AI bắt đầu lặp lại hay quên, hoặc đã làm khoảng 1–2 giờ, bảo AI ghi handoff rồi mở phiên mới.
3. **Luôn bắt AI tóm tắt kế hoạch trước khi sửa code.** Kế hoạch sai thì sửa ngay, đỡ tốn công làm lại.
4. **Giao task theo mã** (`FACE-02`), không mô tả lại bằng lời. Task card đã đủ chi tiết và chính xác hơn lời nói.
5. **Không cho 2 AI sửa cùng một file cùng lúc.** Mỗi người, mỗi AI làm trên nhánh riêng.
6. **AI nói "xong" thì vẫn phải kiểm.** Bắt AI chạy test và đưa kết quả thật; tự mở app xem nếu là giao diện.
7. **Dùng AI thứ hai để review.** Ví dụ Codex viết code, Claude rà (`/review-pr`), hoặc ngược lại.

## Câu lệnh mẫu

### Bắt đầu một task (Codex, hoặc bất kỳ AI nào)

```
Bạn đang làm dự án VeriClue. Hãy đọc AGENTS.md và docs/status/STATUS.md.
Chạy `uv run python scripts/new_handoff.py --latest 5` và đọc các bàn giao
liên quan tới <MÃ-TASK>. Rồi đọc task card <MÃ-TASK> trong docs/plan/epics/. Tóm tắt cho tôi mục tiêu, kế hoạch các bước, các file
sẽ sửa và câu hỏi còn mở. CHƯA sửa code cho tới khi tôi đồng ý.
```

Với Claude Code chỉ cần gõ: `/start-task <MÃ-TASK>`

### Kết thúc phiên (bắt buộc)

```
Trước khi kết thúc: chạy `uv run python scripts/new_handoff.py --task <MÃ>
--who "<tên>+Codex"` rồi điền file vừa tạo. Cập nhật dòng của task trong
docs/plan/backlog.md, đánh dấu tiêu chí đã xong trong task card, chạy
`uv run python scripts/plan_check.py`. Bước tiếp theo phải ghi đủ rõ để người
khác làm tiếp không cần hỏi lại.
```

Với Claude Code: `/handoff <MÃ-TASK>`

### Tiếp tục việc dở dang ở phiên mới

```
Đọc AGENTS.md, rồi đọc file bàn giao mới nhất của task <MÃ> trong
docs/status/handoffs/ (tên file chứa mã task).
Tiếp tục từ "Bước tiếp theo" trong đó. Tóm tắt lại trước khi làm.
```

### Nhờ AI rà code

```
Rà thay đổi trên nhánh hiện tại so với main cho task <MÃ>. Đối chiếu với task
card, AGENTS.md §6 (luật) và §8 (Definition of Done). Liệt kê vấn đề theo mức
phải sửa / nên sửa / gợi ý, kèm file:dòng. Chạy test và báo kết quả thật.
Chưa tự sửa.
```

Với Claude Code: `/review-pr <MÃ>`

### Khi AI làm sai thiết kế

```
Dừng lại. Việc này trái với docs/architecture/architecture.md mục <X> (hoặc
AGENTS.md §6 luật số <N>). Đọc lại mục đó rồi đề xuất cách sửa.
```

## Dấu hiệu AI đang "lạc" — nên mở phiên mới

- Hỏi lại những điều đã nói.
- Sửa file không liên quan tới task.
- Tự đổi tên hàm, đổi schema, đổi ngưỡng mà không ai yêu cầu.
- Báo "đã xong" mà không chạy test.
- Code ngày càng dài và rối cho một việc đơn giản.

## Subagent và nhiều phiên song song

Claude Code có thể sinh **subagent** (một AI phụ chạy trong phiên). Nhóm cũng chạy nhiều phiên cùng lúc (Claude và Codex). Luật chung:

| Luật | Vì sao |
|---|---|
| **Mỗi task một phiên chính.** Chỉ phiên chính được commit và push. | Một người chịu trách nhiệm cho mỗi nhánh |
| Subagent chỉ dùng để **đọc, tra cứu, chạy test, duyệt**, hoặc viết vào **file riêng** được giao. | Tránh hai bên ghi đè nhau |
| **Hai subagent hoặc hai phiên không sửa cùng một file.** | Tránh xung đột và mất code |
| **Mỗi AI một git worktree**, đặt ngang hàng với `Data4Life` (ví dụ `D:\Projects\vericlue-claude`), không lồng vào trong. | pytest, ruff, tìm kiếm không quét trùng; tránh `git add .` nhầm |
| **Duyệt chéo:** PR của Codex do Claude duyệt, PR của Claude do Codex duyệt. | AI thứ hai dễ thấy lỗi mà AI thứ nhất bỏ qua |

Trong Claude Code có subagent `reviewer` (`.claude/agents/reviewer.md`): chỉ đọc và chạy test, trả về danh sách vấn đề. Phiên điều phối dùng nó để duyệt PR (xem `docs/ai/lead-playbook.md`).

### Dùng subagent để làm nhanh hơn

Phiên chính giữ phần **viết code và quyết định**. Những việc đọc nhiều, chờ lâu hoặc độc lập với nhau thì giao cho subagent **chạy song song**:

| Lúc | Giao cho subagent (chạy cùng lúc) | Phiên chính làm gì |
|---|---|---|
| Bắt đầu task | Mỗi subagent đọc một nhóm tài liệu và tóm tắt ngắn: (a) task card + ADR liên quan; (b) code hiện có ở thư mục sẽ sửa; (c) schema trong `packages/contracts/` và bàn giao gần nhất | Gộp các bản tóm tắt thành kế hoạch, chờ người dùng duyệt |
| Đang làm | Viết test vào **file test riêng**; tra cứu thư viện hoặc giấy phép; chạy `pytest`/`ruff`/`npm run build` rồi báo lỗi | Viết code chính |
| Trước khi mở PR | `reviewer` (Claude) hoặc một subagent chỉ đọc: rà theo task card và AGENTS.md §6, §8 | Sửa các mục "phải sửa", ghi bàn giao, mở PR |

Mẹo:

- Giao việc cho subagent phải **cụ thể**: đọc file nào, trả về gì, tối đa bao nhiêu dòng.
- Các subagent không phụ thuộc nhau thì **gọi cùng lúc** (Claude Code: nhiều lệnh gọi Agent trong một lượt).
- Không giao subagent việc nhỏ mà phiên chính tự làm nhanh hơn (đọc 1 file, sửa 1 dòng).
- **Codex:** nếu bản Codex đang dùng có subagent hoặc tác vụ song song thì áp dụng như bảng trên. Nếu không có thì làm tuần tự theo đúng thứ tự đó, và nhờ Claude duyệt chéo thay cho `reviewer`.

## Phân chia gợi ý giữa các AI

| Việc | Gợi ý |
|---|---|
| Viết code theo task card rõ ràng | Codex hoặc Claude Code |
| Thiết kế, gỡ lỗi khó, rà code | Claude Code |
| Việc lặp lại nhiều file (đổi tên, thêm test) | Codex |
| Viết tài liệu, báo cáo tiếng Việt | Claude |

Công cụ nào cũng được, miễn là **tuân theo cùng AGENTS.md và cùng quy trình bàn giao**.
