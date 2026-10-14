# Mục lục tài liệu

## Bắt đầu từ đây

| Nếu bạn… | Đọc |
|---|---|
| Mới vào dự án | `runbooks/onboarding.md` (checklist ngày đầu) |
| Sắp làm một task | `status/STATUS.md` → `plan/backlog.md` → task card trong `plan/epics/` |
| Đang dùng AI (Codex, Claude) | `ai/working-with-ai.md` và `../AGENTS.md` |
| Cần biết thiết kế | `architecture/architecture.md`, `adr/` |

## Cấu trúc

```
docs/
├── context/        tóm tắt dự án, thuật ngữ, đội
├── proposal/       proposal.md (đang dùng) · archive/ (bản cũ, KHÔNG dùng để triển khai)
├── architecture/   architecture.md (kỹ thuật) · architecture.html (sơ đồ cho người không chuyên)
├── adr/            quyết định thiết kế và lý do (0001–0009)
├── plan/           roadmap · backlog · epics/ (task card)
├── status/         STATUS.md · handoffs/ (bàn giao, mỗi lần một file) · results/ (R1–R7)
├── data/           data-plan.md — dữ liệu công khai sẽ dùng
├── research/       sources.md · github-references.md
├── conventions/    coding-standards.md
├── runbooks/       onboarding · dev-setup · red-team · demo-day
├── templates/      mẫu: bàn giao, thẻ mô hình, báo cáo kết quả, tổng kết sprint
└── ai/             working-with-ai.md — làm việc với nhiều AI, nhiều phiên · lead-playbook.md — sổ tay trưởng nhóm
```

## Quy tắc tài liệu

- **Tên file:** chữ thường, nối bằng gạch ngang, tiếng Anh. **Nội dung:** tiếng Việt.
- **Một sự thật, một chỗ.** Không chép cùng một nội dung ra nhiều file; trỏ link tới chỗ gốc.
- **Đổi thiết kế:** viết ADR mới, không sửa ADR cũ (chỉ đổi trạng thái thành "thay thế bởi").
- **Sửa code làm tài liệu sai:** sửa tài liệu trong cùng PR.
