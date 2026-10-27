# Mục lục tài liệu

## Bắt đầu từ đây

| Nếu bạn… | Đọc |
|---|---|
| Mới vào dự án | `runbooks/onboarding.md` (checklist ngày đầu) |
| Sắp làm một task | `status/STATUS.md` → `plan/backlog.md` → task card trong `plan/epics/` |
| Đang dùng AI (Codex, Claude) | `ai/working-with-ai.md` và `../AGENTS.md` |
| Cần biết thiết kế | `architecture/architecture.md`, `adr/` |

Ghi danh, L0 và khôi phục tài khoản: [account-authentication.md](architecture/account-authentication.md).

Kết quả có chữ ký cho bên tích hợp: [signed-session-results.md](architecture/signed-session-results.md).

Thử nghiệm chứng nhận riêng tư BBS và đối chứng SD-JWT:
[hướng dẫn chạy](../services/credentials/README.md), [ADR-0018](adr/0018-chung-nhan-rieng-tu-bbs.md).
Cổng cấp từ backend: [private-credential-issuance.md](architecture/private-credential-issuance.md).
API kiểm proof, nonce DB: [private-credential-verifier.md](architecture/private-credential-verifier.md).
Xoay/thu hồi issuer key: [private-credential-keys.md](architecture/private-credential-keys.md).
SDK holder trình duyệt, không UI: [private-credential-holder.md](architecture/private-credential-holder.md).

Chữ ký và kiểm tệp báo cáo HTML: [forensic-report-signing.md](architecture/forensic-report-signing.md).

Gói PDF/JSON đã ký và runtime xuất: [forensic-pdf-bundle.md](architecture/forensic-pdf-bundle.md).
Ảnh/phổ minh họa từ vật chứng: [forensic-report-evidence.md](architecture/forensic-report-evidence.md).
Giám định độc lập/gắn hồ sơ và kiểm mốc nhật ký: [forensic-review-audit.md](architecture/forensic-review-audit.md).

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
