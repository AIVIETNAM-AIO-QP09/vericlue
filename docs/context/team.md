# Đội, vai trò và quy ước làm việc

> **Việc cần làm ngay:** điền tên thật và tài khoản GitHub vào bảng dưới, rồi thay `@TODO-M*` trong `.github/CODEOWNERS`.

## 1. Vai trò chuyên môn

| Vai trò | Người | GitHub | Phụ trách chính | Task (xem `docs/plan/backlog.md`) |
|---|---|---|---|---|
| **M1 — Web thu nhận** | _(điền)_ | _(điền)_ | `apps/web` phần `/verify`: camera, chất lượng, ChromaPulse và CamProbe phía trình duyệt; kiểm thử đầu–cuối | PLAT-02, CAP-01…08, PRES-04, PLAT-09, DEMO-02 |
| **M2 — Bàn duyệt, giám định UI, bảo mật API** | _(điền)_ | _(điền)_ | `apps/web` phần `/review`, `/forensic`; API bàn duyệt; bảo mật phiên; CI; máy red-team; kịch bản demo; báo cáo nộp | PLAT-06, PLAT-07, DATA-02, DATA-04, REDT-01, REV-01/02, FOR-02, FOR-04, DEMO-01, DEMO-03 |
| **M3 — AI khuôn mặt** | _(điền)_ | _(điền)_ | `ml/src/vericlue_ml/face`, `presence`; quét thủy vân | DATA-01/03 (ảnh), PRES-01/02/03, FACE-01…05, FOR-03 |
| **M4 — AI giọng nói** | _(điền)_ | _(điền)_ | `ml/src/vericlue_ml/voice`; dữ liệu âm thanh; đánh giá chế độ giám định | DATA-01/03 (âm thanh), DATA-05, VOICE-01…06, EVAL-03 |
| **M5 — Nền tảng và quyết định** | _(điền)_ | _(điền)_ | `services/api`, `ml/src/vericlue_ml/router`, `eval`, `forensic/segment`; Docker | PLAT-01/03/04/05/08, ROUT-01…05, FOR-01, EVAL-01/02, DEMO-04 |

Tải công việc từng người theo sprint: chạy `uv run python scripts/plan_check.py`.

## 2. Vai trò điều phối (kiêm nhiệm)

| Vai trò | Ai | Trách nhiệm |
|---|---|---|
| **Trưởng nhóm / điều phối** (scrum master) | _(điền — gợi ý: người đăng ký đội)_ | Chủ trì họp nhanh hằng ngày; **người duy nhất cập nhật `docs/status/STATUS.md`** (tránh xung đột); theo dõi đường găng; liên lạc BTC/mentor |
| **Tech lead** | _(gợi ý: M5)_ | Duyệt PR chạm `packages/contracts/`, `docs/architecture/`, `docs/adr/`; quyết định kỹ thuật khi nhóm không thống nhất |
| **Người giữ ngưỡng** | _(gợi ý: M5 + người của mô-đun)_ | Duyệt mọi thay đổi `ml/configs/thresholds.yaml` |
| **Người giữ máy demo** | _(điền)_ | Máy demo luôn chạy được bản `main` mới nhất từ M2 (01/11) |

## 3. Quy ước làm việc (working agreement)

| Mục | Quy ước |
|---|---|
| **Họp nhanh** | 21:00 mỗi ngày, 15 phút, online. Mỗi người: hôm qua xong gì / hôm nay làm gì / đang vướng gì |
| **Kênh liên lạc** | Nhóm chat _(điền: Zalo/Discord/Messenger)_ cho trao đổi nhanh. **Quyết định quan trọng phải ghi lại** trong `STATUS.md`, ADR hoặc PR — không để chỉ nằm trong chat |
| **Thời gian phản hồi** | Câu hỏi ghi tên mình: trả lời trong 12 giờ. PR được nhờ duyệt: duyệt trong 12 giờ |
| **Bị chặn quá 2 giờ** | Báo ngay trong nhóm chat, ghi vào STATUS "Bị chặn". Không ngồi im chờ |
| **Ước lượng sai** | Thực tế vượt 50% so với ước lượng thì báo trong họp nhanh để điều chỉnh kế hoạch |
| **Nhánh `main`** | Luôn chạy được. Không push thẳng; chỉ gộp qua PR có CI xanh và 1 người duyệt |
| **Đóng băng** | Từ 02/11 chỉ sửa lỗi; mọi thay đổi khác cần trưởng nhóm đồng ý |
| **Dùng AI** | Theo `docs/ai/working-with-ai.md`. Người giao việc cho AI chịu trách nhiệm về code AI viết |
| **Dữ liệu sinh trắc** | Mặt và giọng của thành viên chỉ dùng khi chính người đó đồng ý; xóa sau dự án |

## 4. Nghi thức

| Khi nào | Việc | Kết quả lưu ở |
|---|---|---|
| Mỗi ngày 21:00 | Họp nhanh | Trưởng nhóm cập nhật STATUS.md |
| 21/10, 29/10 | Buổi tích hợp (2 giờ) | Bàn giao chung |
| 17/10, 25/10, 01/11 | Demo nội bộ cuối sprint (1 giờ) | `docs/status/sprints/` (mẫu `docs/templates/sprint-review.md`) |
| Cuối mỗi phiên làm việc | Bàn giao | `docs/status/handoffs/` |
