# STATUS — Tình trạng dự án

> **Cập nhật:** 15/10/2026 · **Sprint:** S0 (15/10 → 17/10) · **Mốc kế tiếp:** M0 — 17/10 · **Hạn nộp:** trước 06/11 (còn 21 ngày)
> **Chỉ trưởng nhóm sửa file này** (tránh xung đột git). Người khác ghi vào file bàn giao, trưởng nhóm gom lại.
> Số liệu task luôn mới nhất: `uv run python scripts/plan_check.py --board`.

## Tổng quan

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Proposal | ✅ Chốt bản 3 | `docs/proposal/proposal.md` |
| Kiến trúc | ✅ Bản nháp | `docs/architecture/architecture.md`; API và DB chốt ở PLAT-04, PLAT-05 |
| Kế hoạch | ✅ 56 task, đã kiểm tự động | `plan_check.py`: 0 lỗi, 0 cảnh báo; không ai vượt 70% sức chứa ở sprint nào |
| Công cụ và quy trình | ✅ PLAT-01 xong | `setup.ps1` chạy được trên Windows; CI, pre-commit; test trên `main` `4456711`: 255 đạt, 2 bỏ qua. Phiên điều phối: `/lead`, `docs/ai/lead-playbook.md` |
| Web / API / ML | 🟡 Đang làm | PLAT-03 xong (API + mock). ROUT-01 xong (PR #3). PLAT-02 xong (PR #4: Next.js 3 khu vực, đã thử trên điện thoại). EVAL-01 xong (PR #5: khung đánh giá chung). PLAT-04 chờ sửa sau review (PR #7) |
| Dữ liệu | 🟡 Đang viết script | DATA-01 (dữ liệu), DATA-02 (mô hình). Lưu chung ngoài worktree: `D:\Projects\vericlue-store\{data,models}`. Ổ D: còn ~119 GB |

## Đang làm

| Mã | Người | Bắt đầu | Ghi chú |
|---|---|---|---|
| PLAT-04 | M5 (+M1) · Claude (thư mục `vericlue-claude`) | 15/10 | `review` — PR #7; đang sửa lỗi đi tắt tới `pass` qua `/voice`; nằm trên đường găng |
| DATA-02 | M2 · Codex (thư mục `vericlue-codex`) | 15/10 | `doing` — script tải mô hình + SHA-256; chờ duyệt bảng mô hình (giấy phép) |
| DATA-01 | M3 + M4 · Codex (thư mục `vericlue-data`) | 15/10 | `doing` — script tải dữ liệu công khai, `--subset small` < 30 GB |

## Bị chặn

| Mã | Lý do | Cần ai giải quyết |
|---|---|---|
| — | | |

## Câu hỏi mở

| # | Câu hỏi | Ai hỏi / trả lời | Hạn |
|---|---|---|---|
| Q1 | Vòng 2 phải nộp những gì (bản chạy, báo cáo, video, slide, link repo)? | M2 hỏi BTC/mentor | 16/10 |
| Q2 | Có được nêu Đề 62 và DA940-02 là đề liên quan ngoài BTL86-16 không? | M2 hỏi BTC | 16/10 |
| Q3 | Điều khoản gốc của Zalo AI 2022 về việc dùng dữ liệu? | M3 | 17/10 |
| Q4 | Gán tên thật cho M1–M5; chọn trưởng nhóm và tech lead; điền `team.md` và `CODEOWNERS` | Cả nhóm | 15/10 |
| Q5 | Máy nào làm máy demo (có GPU)? Máy nào làm máy red-team? | Cả nhóm | 17/10 |
| Q6 | Tra lại Google Scholar cho tuyên bố "lần đầu áp dụng Learn-then-Test" | M5 | trước khi nộp |
| Q7 | Kênh liên lạc chính của nhóm (Zalo/Discord/…)? Giờ họp nhanh 21:00 có hợp không? | Cả nhóm | 15/10 |

## Quyết định gần đây

| Ngày | Quyết định | Tham chiếu |
|---|---|---|
| 14/10 | Chốt proposal v3: 1 bộ não + 2 chế độ; chỉ dữ liệu công khai; GenD, AntiDeepfake, MAPIE, mã nháy màu AWS Amplify, quét thủy vân | `docs/adr/0001`–`0009` |
| 14/10 | Monorepo, mock trước, AGENTS.md làm luật chung cho mọi AI | ADR-0001 |
| 14/10 | Cân lại kế hoạch theo tải từng sprint: SBI và tinh chỉnh GenD sang S2; PLAT-06/07 → M2; FOR-01 → M5; FOR-03 → M3; thêm PLAT-09 (kiểm thử đầu–cuối) và EVAL-03 (đánh giá giám định, R7) | `docs/plan/roadmap.md` |
| 14/10 | Tách tập calib theo người thành `calib_fit` (hiệu chỉnh, hợp nhất, chọn mô hình) và `calib_ltt` (chỉ chọn ngưỡng); calibrator lưu trong `ml/configs/calibrators/` | ADR-0010 |
| 14/10 | Token theo phiên (~5 phút), mỗi bước nhận một lần (409), thử thách sống 120 giây; nhịp nháy màu ≥ 550 ms/bước | ADR-0011 |
| 14/10 | Chạy song song 2 AI bằng git worktree: Claude ở `D:\Projects\vericlue-claude` (PLAT-02 → PLAT-04), Codex ở `D:\Projects\vericlue-codex` (ROUT-01 → EVAL-01) | `docs/ai/working-with-ai.md` |
| 14/10 | Gộp PR #2 (ADR-0010, ADR-0011) và PR #3 (ROUT-01: hiệu chỉnh xác suất, GroupKFold theo người, thiếu calibrator thì báo lỗi) | PR #2, #3 |
| 15/10 | PLAT-04: phiên đã ra `review` là trạng thái cuối (gọi lại → 409); xác thực nhân viên cho `/review`, `/forensic` giao PLAT-06 | Bàn giao LEAD 15/10, thẻ PLAT-06 |
| 15/10 | Mở phiên AI ngay tại thư mục worktree của nó; dữ liệu và mô hình để chung ngoài worktree (`DATA_DIR`, `MODELS_DIR`) | `docs/ai/working-with-ai.md` |
| 15/10 | Gộp PR #5 (EVAL-01) và PR #6 (bộ công cụ trưởng nhóm) | PR #5, #6 |
| 14/10 | Gộp PR #4 (PLAT-02). `npm audit`: 5 lỗi mức cao chỉ nằm trong công cụ lint (`eslint-config-next`); bản chạy thật báo 0. Không chạy `audit fix --force` | PR #4 |
| 14/10 | EVAL-01: BPCER@APCER 5% chính lấy ngưỡng từ `calib_fit` rồi khóa, kèm dòng "mô tả" theo đường cong; cột `status` bắt buộc, không âm thầm bỏ mẫu lỗi | Bàn giao LEAD, bàn giao EVAL-01 |
| 14/10 | Phiên điều phối riêng (`/lead`); luật subagent: mỗi task một phiên chính, chỉ phiên chính commit, không hai bên sửa cùng file, duyệt chéo Claude ↔ Codex | `docs/ai/lead-playbook.md`, `docs/ai/working-with-ai.md` |
| 14/10 | Bàn giao mỗi lần một file (`docs/status/handoffs/`) để tránh xung đột git | `docs/status/handoffs/README.md` |

## Kết quả đã có

Chưa có. Kết quả lưu ở `docs/status/results/` (R1–R7).

## Liên kết nhanh

- Sơ đồ kiến trúc (artifact): https://claude.ai/artifact/EmX1EhHPH6DrKeLxCHDmuo — nguồn: `docs/architecture/architecture.html`
- Repo GitHub: https://github.com/AIVIETNAM-AIO-QP09/vericlue (private)
