# AGENTS.md — Hướng dẫn cho mọi AI agent (Codex, Claude Code, Cursor, …) và thành viên mới

> File này được Codex tự đọc; Claude Code đọc qua `CLAUDE.md`. Giữ file **ngắn và đúng**. Chi tiết nằm trong `docs/`.

## 1. Dự án trong 30 giây

**VeriClue** — hệ thống phát hiện khuôn mặt và giọng nói bị làm giả bằng AI cho định danh điện tử (eKYC) tại Việt Nam.

- **Cuộc thi:** Data for Life 2026, đội DS@AInSec4E (5 người), đề bài **BTL86-16** của Bộ Tư lệnh 86.
- **Hạn nộp vòng 2:** trước **06/11/2026**. Mục tiêu là một **bản demo chạy được**, không phải sản phẩm thương mại.
- **Cấu trúc:** **1 bộ não** phát hiện giả mạo dùng chung cho **2 chế độ**:
  1. kiểm tra tức thời khi người dân xác minh trên điện thoại (web);
  2. giám định video/âm thanh cho điều tra viên.

## 2. Đọc gì trước khi làm (theo thứ tự)

1. `docs/status/STATUS.md` — dự án đang ở đâu, ai làm gì, đang vướng gì.
2. **Task card** của việc được giao: `docs/plan/epics/E*-*.md`, tìm theo mã (ví dụ `FACE-02`).
3. `docs/architecture/architecture.md` — cấu trúc code, API, giao diện mô-đun.
4. README của thư mục sắp sửa (`apps/web/`, `services/api/`, `ml/`, …).
5. Khi cần lý do của một quyết định: `docs/adr/`. Khi cần yêu cầu gốc: `docs/proposal/proposal.md`.

**Không đọc** `docs/proposal/archive/` để lấy yêu cầu — đó là bản cũ.

Mỗi khu vực code có `AGENTS.md` riêng (`apps/web/`, `services/api/`, `ml/`) với luật bổ sung — đọc khi làm ở khu vực đó.

## 3. Nguồn sự thật

| Câu hỏi | Xem ở đâu |
|---|---|
| Làm cái gì, vì sao | `docs/proposal/proposal.md`, `docs/context/project-brief.md` |
| Làm như thế nào (thiết kế) | `docs/architecture/architecture.md`, `docs/adr/` |
| Dữ liệu trao đổi giữa các phần | `packages/contracts/schemas/` |
| Việc cần làm, thứ tự, tiêu chí xong | `docs/plan/` |
| Tình trạng hiện tại | `docs/status/STATUS.md` |
| Dùng dữ liệu nào | `docs/data/data-plan.md` |
| Thuật ngữ (APCER, LTT, ChromaPulse…) | `docs/context/glossary.md` |
| Mẫu tài liệu (bàn giao, thẻ mô hình, kết quả) | `docs/templates/` |
| Ai làm gì, quy ước nhóm | `docs/context/team.md` |

## 4. Bản đồ repo

```
apps/web/            Next.js: /verify (người dân), /review (nhân viên), /forensic (điều tra viên)
apps/android/        App Kotlin cho người dân (ADR-0014); hiện có phần giao diện
services/api/        FastAPI: phiên eKYC, bàn duyệt, giám định
ml/                  gói vericlue_ml: face/ presence/ voice/ router/ forensic/ eval/ mock/
packages/contracts/  JSON Schema — hợp đồng giữa các phần
scripts/             setup, tải dữ liệu, tải mô hình
data/ models/ external/   KHÔNG commit (tải bằng script)
third_party/         ghi nhận code chép từ dự án khác
docs/                tài liệu (mục lục: docs/README.md)
```

## 5. Lệnh thường dùng

```bash
./scripts/setup.ps1                            # (Windows) cài mọi thứ lần đầu; Linux/macOS: bash scripts/setup.sh
uv run pytest                                  # chạy test Python
uv run ruff check . && uv run ruff format .    # kiểm tra và định dạng Python
uv run python scripts/plan_check.py            # bảng trạng thái, tải từng người, đường găng, kiểm tra backlog
uv run python scripts/new_handoff.py --latest 5                          # 5 bàn giao mới nhất
uv run python scripts/new_handoff.py --task <MÃ> --who "<tên>+<AI>"      # tạo bàn giao
cd apps/web && npm run dev                     # chạy web (sau PLAT-02)
docker compose up -d db                        # PostgreSQL (sau PLAT-05)
```

## 6. Luật bắt buộc (KHÔNG được vi phạm)

1. **Hợp đồng trước, code sau.** Mọi dữ liệu qua lại giữa web ↔ API ↔ ml phải khớp `packages/contracts/`. Đổi schema thì sửa schema trước, rồi sửa cả hai phía trong cùng PR.
2. **Mọi bộ phát hiện trả `ModuleResult`** và có **bản mock** trong `ml/src/vericlue_ml/mock/`.
3. **Người dân không bao giờ thấy điểm số hay chữ "giả mạo".** API chỉ trả `pass | retry | review | voice_challenge`. Gợi ý chụp lại chỉ nói về chất lượng (ánh sáng, khoảng cách…).
4. **`status` = `error` hoặc `degraded` không bao giờ được coi là đạt.**
5. **Không commit** dữ liệu, trọng số mô hình, video, âm thanh, file `.env`, khóa bí mật.
6. **Không chép code GPL/AGPL/LGPL hoặc repo không có giấy phép** vào sản phẩm. Code MIT/Apache chép về thì giữ dòng giấy phép và ghi vào `third_party/README.md`.
7. **Không sửa** `ml/configs/thresholds.yaml`, `packages/contracts/`, `docs/proposal/proposal.md` hay `docs/adr/` **trừ khi** task yêu cầu rõ. Nếu cần đổi, ghi đề xuất vào mục "Câu hỏi cho nhóm" trong file bàn giao.
8. **Tập test không được dùng** để chọn ngưỡng hay chọn mô hình. Chia dữ liệu **theo người**.
9. **Không bịa số liệu.** Mọi con số trong báo cáo phải chạy ra từ code trong repo, ghi kèm commit, phiên bản mô hình và số mẫu (thể lệ cuộc thi cấm làm giả kết quả).
10. **Không tuyên bố "đầu tiên/duy nhất"** ngoài những gì đã ghi trong `proposal.md` §2.10.
11. Không thử tấn công vào hệ thống thật của ngân hàng hay bất kỳ bên nào. Công cụ tấn công chỉ chạy trên máy red-team, nhắm vào hệ thống của chính nhóm.

## 7. Quy trình làm một task

1. Đọc mục 2. Xác nhận task có trạng thái `todo`, không bị chặn bởi task khác.
2. Tạo nhánh `<loại>/<MÃ-TASK>-<mô-tả-ngắn>`, ví dụ `feat/FACE-02-gend-baseline`.
3. Làm từng bước nhỏ. Commit theo Conventional Commits và có mã task: `feat(face): add GenD inference wrapper [FACE-02]`.
4. Viết hoặc cập nhật test. Chạy lint và test trước khi báo xong.
5. Đánh dấu các tiêu chí đã xong trong task card. Đổi trạng thái **dòng của task** trong `docs/plan/backlog.md`, chạy `uv run python scripts/plan_check.py`. **Không sửa `docs/status/STATUS.md`** — trưởng nhóm cập nhật file đó.
6. **Ghi bàn giao:** `uv run python scripts/new_handoff.py --task <MÃ> --who "<tên>+<AI>"` rồi điền file vừa tạo trong `docs/status/handoffs/`.
7. Mở PR theo mẫu `.github/PULL_REQUEST_TEMPLATE.md`.

## 8. Định nghĩa "XONG" (Definition of Done)

- [ ] Đạt hết tiêu chí trong task card.
- [ ] Có test cho logic mới; `uv run pytest` / `npm run test` xanh.
- [ ] Lint sạch (`ruff`, `eslint`).
- [ ] Khớp hợp đồng trong `packages/contracts/`.
- [ ] Không có bí mật, dữ liệu hay trọng số trong commit.
- [ ] README hoặc tài liệu liên quan đã cập nhật nếu hành vi thay đổi.
- [ ] Đã thêm file bàn giao trong `docs/status/handoffs/` và cập nhật dòng của task trong `backlog.md`; `scripts/plan_check.py` không báo lỗi.

## 9. Khi không chắc chắn

- **Không đoán.** Nếu yêu cầu mơ hồ, mâu thuẫn, hoặc cần đổi thiết kế: dừng lại, ghi câu hỏi vào mục "Câu hỏi cho nhóm" trong file bàn giao, và báo người giao việc. Trưởng nhóm gom các câu hỏi vào `STATUS.md`.
- Nếu phát hiện tài liệu sai hoặc lỗi thời, sửa trong cùng PR và ghi rõ trong mô tả PR.
- Ưu tiên giải pháp **đơn giản, chạy được cho demo** hơn giải pháp hoàn hảo.

## 10. Phong cách

- **Python:** 3.12, type hints, `ruff` (format + lint), docstring ngắn cho hàm công khai, `pytest`.
- **TypeScript:** strict, ESLint + Prettier, component nhỏ, logic tách khỏi UI.
- **Ngôn ngữ:** tên biến và code bằng tiếng Anh; chữ hiển thị cho người dùng và tài liệu bằng tiếng Việt; comment bằng tiếng Anh hoặc tiếng Việt đều được, nhưng ngắn.
- **Đầy đủ:** `docs/conventions/coding-standards.md`.
