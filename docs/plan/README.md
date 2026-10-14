# Kế hoạch triển khai — cách dùng

| File | Nội dung |
|---|---|
| `roadmap.md` | Mốc, lịch theo ngày, đường găng, phân bổ công việc, nghi thức nhóm |
| `backlog.md` | **Bảng tất cả task** với trạng thái — nơi cập nhật hằng ngày |
| `epics/E0-platform.md` … `E8-eval-demo.md` | **Task card** chi tiết của từng task |

## Mã task

`<EPIC>-<số>`:

| Mã | Phần |
|---|---|
| PLAT | Nền tảng |
| DATA | Dữ liệu |
| CAP | Web thu nhận |
| PRES | Hiện diện (ChromaPulse, CamProbe phía server) |
| FACE | Khuôn mặt |
| VOICE | Giọng nói |
| ROUT | TrustRouter |
| REV | Bàn duyệt |
| FOR | Giám định |
| REDT | Red-team |
| EVAL | Đánh giá |
| DEMO | Demo và nộp bài |

## Trạng thái

| Trạng thái | Nghĩa |
|---|---|
| `todo` | Chưa ai nhận |
| `doing` | Đang làm (có tên người) |
| `review` | Đã mở PR, chờ duyệt |
| `done` | Đã merge, đạt tiêu chí |
| `blocked` | Bị chặn; ghi lý do vào STATUS.md |
| `cut` | Bỏ khỏi phạm vi; ghi lý do |

## Mức ưu tiên

| Mức | Nghĩa |
|---|---|
| **P0** | Bắt buộc cho demo |
| **P1** | Nên có |
| **P2** | Nếu còn thời gian |

## Mẫu task card

```markdown
### <MÃ> · <Tên task>
| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M? | ? ngày công | S? | P0/P1/P2 | MÃ, MÃ |

**Mục tiêu:** 1–2 câu.
**Đọc trước:** file cần đọc.
**Đầu vào:** …
**Đầu ra:** file/hàm/endpoint cụ thể.
**Các bước:** 1. 2. 3.
**Tiêu chí hoàn thành:**
- [ ] …
**Lưu ý / bẫy:** …
```

## Definition of Ready — task được phép bắt đầu khi

- [ ] Có task card đủ: mục tiêu, đầu ra, tiêu chí hoàn thành đo được.
- [ ] Mọi task phụ thuộc đã `done`. Lệnh `plan_check.py` liệt kê các task "Sẵn sàng làm".
- [ ] Biết dữ liệu, mô hình hay hợp đồng cần dùng, và chúng đã có.
- [ ] Người làm đã ghi tên vào cột "Người".

Task chưa đạt các điều trên thì **chưa bắt đầu**: báo trưởng nhóm, hoặc làm task khác.

## Kiểm tra kế hoạch tự động

```bash
uv run python scripts/plan_check.py            # đầy đủ
uv run python scripts/plan_check.py --board    # chỉ bảng trạng thái
uv run python scripts/plan_check.py --notes    # kèm các cặp phụ thuộc cùng sprint
```

Script kiểm tra:
- phụ thuộc tồn tại, không có vòng lặp;
- thứ tự sprint hợp lệ;
- **backlog và task card khớp nhau** (người, ngày công, sprint, ưu tiên, phụ thuộc);
- tải từng vai trò theo sprint so với sức chứa;
- đường găng và các chuỗi gần găng.

CI chạy lệnh này trên mọi PR: kế hoạch sai thì CI đỏ.

## Quy tắc

- Muốn đổi phạm vi, thêm hoặc bỏ task: sửa `backlog.md` + task card trong cùng PR, ghi lý do vào STATUS.md.
- Ước lượng tính bằng **ngày công** (1 người làm tập trung 1 ngày). Nếu thực tế vượt 50%, báo ngay trong buổi họp nhanh.
