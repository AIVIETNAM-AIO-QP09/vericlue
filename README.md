# VeriClue

**Phát hiện khuôn mặt và giọng nói giả mạo bằng AI cho định danh điện tử tại Việt Nam.**

Data for Life 2026 · Đội **DS@AInSec4E** · Đề bài **BTL86-16** (Bộ Tư lệnh 86) · Hạn nộp vòng 2: **trước 06/11/2026**

VeriClue gồm **một bộ não phát hiện giả mạo** được kiểm tra trên dữ liệu người Việt, dùng cho **hai chế độ**:
1. **Kiểm tra tức thời khi mở tài khoản (eKYC):**
   - màn hình nháy màu để chắc có người thật trước camera;
   - phát hiện camera ảo;
   - quyết định *cho qua / chụp lại / đọc câu tiếng Việt / chuyển nhân viên* với ngưỡng có bảo đảm thống kê.
2. **Giám định cho điều tra viên:** tải video lên, hệ thống chỉ ra đoạn nào nghi bị làm giả, dò thủy vân AI, và xuất báo cáo có chữ ký số.

> Sơ đồ dễ hiểu: [`docs/architecture/architecture.html`](docs/architecture/architecture.html) · Yêu cầu đầy đủ: [`docs/proposal/proposal.md`](docs/proposal/proposal.md)

---

## Bắt đầu nhanh

| Bạn là… | Đọc gì |
|---|---|
| **Thành viên mới** | [`docs/runbooks/onboarding.md`](docs/runbooks/onboarding.md) — checklist ngày đầu, khoảng 2 giờ |
| **AI agent** (Codex, Claude…) | [`AGENTS.md`](AGENTS.md) — đọc trước mọi việc |
| **Người giao việc cho AI** | [`docs/ai/working-with-ai.md`](docs/ai/working-with-ai.md) |
| **Muốn biết đang làm tới đâu** | [`docs/status/STATUS.md`](docs/status/STATUS.md) · `uv run python scripts/plan_check.py` |

## Cài đặt

> Công cụ đã sẵn sàng; web, API, cơ sở dữ liệu đang được dựng (PLAT-02…05). Xem [`docs/runbooks/dev-setup.md`](docs/runbooks/dev-setup.md).

```powershell
./scripts/setup.ps1                       # cài Python 3.12 (qua uv), thư viện, git hooks, tạo .env
uv run pytest                             # kiểm tra
docker compose up                         # (sau PLAT-05) chạy web :3000, API :8000, PostgreSQL
```

Mặc định hệ thống chạy với **mô-đun giả lập** (`USE_MOCK_MODELS=true`), chưa cần tải mô hình.

## Cấu trúc repo

```
apps/web/             Next.js — /verify (người dân), /review (nhân viên), /forensic (điều tra viên)
services/api/         FastAPI — phiên eKYC, bàn duyệt, giám định
ml/                   gói vericlue_ml — face, presence, voice, router, forensic, eval, mock
packages/contracts/   JSON Schema — hợp đồng dữ liệu giữa các phần
scripts/              setup, tải dữ liệu, tải mô hình
data/ models/ external/   không commit — tải bằng script
third_party/          ghi nhận mã nguồn dùng lại và giấy phép
notebooks/            thử nghiệm
docs/                 toàn bộ tài liệu — mục lục: docs/README.md
```

## Làm việc nhóm

- **Quy trình:** nhận task trong [`backlog.md`](docs/plan/backlog.md) → nhánh `feat/<MÃ>-…` → PR → review → merge. Chi tiết: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Mỗi task có task card** trong [`docs/plan/epics/`](docs/plan/epics/), ghi đủ mục tiêu, bước làm và tiêu chí xong.
- **Cuối mỗi phiên** tạo file bàn giao trong [`docs/status/handoffs/`](docs/status/handoffs/) (`uv run python scripts/new_handoff.py`) để người sau hoặc AI sau làm tiếp.
- **Kế hoạch và mốc:** [`docs/plan/roadmap.md`](docs/plan/roadmap.md).

| Mốc | Ngày |
|---|---|
| M0 — khung chạy được | 17/10 |
| M1 — hình ảnh chạy thật | 25/10 |
| M2 — đủ tính năng | 01/11 |
| M3 — đóng băng | 04/11 |
| Nộp | 05/11 |

## Giấy phép và dữ liệu

- Chỉ dùng dữ liệu công khai cho nghiên cứu ([`docs/data/data-plan.md`](docs/data/data-plan.md)). Không thu dữ liệu sinh trắc học của người ngoài nhóm.
- Một số mô hình và bộ dữ liệu **chỉ dùng phi thương mại**. Xem [`models/manifest.yaml`](models/manifest.yaml) và [`third_party/README.md`](third_party/README.md).
