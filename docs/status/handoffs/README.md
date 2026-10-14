# Bàn giao giữa các phiên làm việc

**Mỗi lần bàn giao là một file riêng**, đặt tên `YYYY-MM-DD-HHMM-<mã-task>-<người>.md`. Nhờ vậy nhiều người hoặc nhiều AI ghi cùng lúc cũng không bị xung đột khi gộp nhánh.

## Tạo bàn giao mới (cuối mỗi phiên)

```bash
uv run python scripts/new_handoff.py --task FACE-02 --who "Quoc+Codex"
```

Lệnh tạo file từ mẫu `docs/templates/handoff.md`. Mở file đó và điền: đã xong, đang dở, **bước tiếp theo**, lưu ý, test đã chạy.

## Đọc bàn giao gần nhất (đầu mỗi phiên)

```bash
uv run python scripts/new_handoff.py --latest 3
```

Lệnh in đường dẫn 3 file mới nhất. Để xem riêng một task, lọc theo tên file, ví dụ tìm các file có `face-02`.

## Quy tắc

- Viết sao cho **người khác (hoặc AI khác) đọc xong là làm tiếp được ngay**, không cần hỏi lại.
- Không sửa file bàn giao của người khác. Muốn bổ sung thì tạo file mới.
- Commit file bàn giao cùng với code của phiên đó.
