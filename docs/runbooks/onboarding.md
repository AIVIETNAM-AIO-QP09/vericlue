# Ngày đầu tiên — checklist cho thành viên mới

Làm theo thứ tự, khoảng 2 giờ.

## 1. Hiểu dự án (30 phút)
- [ ] Đọc `docs/context/project-brief.md` (1 trang).
- [ ] Mở sơ đồ `docs/architecture/architecture.html` (hoặc link artifact trong STATUS.md).
- [ ] Lướt `docs/context/glossary.md`.
- [ ] Đọc `docs/context/team.md`: vai trò của mình, quy ước làm việc.

## 2. Cài máy (45 phút)
- [ ] Cài Git, uv, Node.js ≥ 20, Docker Desktop, VS Code (`docs/runbooks/dev-setup.md` §1).
- [ ] Clone repo, chạy `./scripts/setup.ps1` (Windows) hoặc `bash scripts/setup.sh`.
- [ ] Mở repo trong VS Code, cài các extension được gợi ý.
- [ ] Chạy `uv run pytest` → xanh.
- [ ] Chạy `uv run python scripts/plan_check.py` → đọc được bảng tải và đường găng.

## 3. Hiểu cách làm việc (30 phút)
- [ ] Đọc `CONTRIBUTING.md`: nhánh, commit, PR.
- [ ] Đọc `AGENTS.md`: luật chung; đặc biệt §6 (11 luật không được vi phạm).
- [ ] Đọc `docs/ai/working-with-ai.md` nếu dùng Codex hoặc Claude.
- [ ] Đọc `docs/plan/roadmap.md`: mốc, lịch của vai trò mình.

## 3b. Chạy thử toàn hệ thống (20 phút)
- [ ] Mở Docker Desktop. Trong thư mục repo: `copy .env.example .env`, đổi **cả hai** chỗ `change-me` (POSTGRES_PASSWORD và trong DATABASE_URL) thành cùng một mật khẩu. Không commit `.env`.
- [ ] `docker compose up -d --build --wait`, rồi mở http://localhost:3000/verify (luồng người dân), `/review` (bàn duyệt), http://localhost:8000/docs (API). Mặc định chạy **AI giả lập**, không cần GPU.
- [ ] Xong thì `docker compose down`. Báo lỗi "port is already allocated" nghĩa là đang có bộ Docker khác chạy: tắt nó trước.
- [ ] Dữ liệu và mô hình **không** nằm trong repo: tải bằng `scripts/download_models.py` và `scripts/download_data.py` (cần token Kaggle/Hugging Face riêng của bạn; xem `scripts/README.md`). Đặt `MODELS_DIR`, `DATA_DIR` trỏ ra thư mục ngoài repo.

## 4. Nhận việc đầu tiên (15 phút)
- [ ] Mở `docs/plan/backlog.md`, chọn task `todo` của vai trò mình mà phụ thuộc đã xong (`plan_check.py` in ra danh sách "Sẵn sàng làm").
- [ ] Ghi tên vào cột "Người", đổi trạng thái `doing`.
- [ ] Đọc task card, tạo nhánh `feat/<MÃ>-…`, bắt đầu.
- [ ] Cuối buổi: `uv run python scripts/new_handoff.py --task <MÃ> --who "<tên>"`.
- [ ] **Dùng AI:** mở Claude Code (`/start-task <MÃ>`) hoặc Codex với mẫu prompt ở `docs/ai/lead-playbook.md` §4 (có bước subagent). Bắt AI **tóm tắt kế hoạch trước**; gửi kế hoạch và PR cho trưởng nhóm duyệt (phiên điều phối dùng subagent `reviewer`).
- [ ] Trước khi mở PR chạm web luồng `/verify`: chạy `cd apps/web && npm run test:e2e` (trình duyệt thật với camera giả).

## Hỏi ai
- Kỹ thuật chung, hợp đồng, kiến trúc → tech lead.
- Tiến độ, phân công → trưởng nhóm.
- Mô-đun cụ thể → người phụ trách vai trò đó (`team.md`).
