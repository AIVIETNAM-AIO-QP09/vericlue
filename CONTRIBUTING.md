# Quy trình làm việc nhóm

Áp dụng cho mọi thành viên và mọi AI agent. Mục tiêu: 5 người làm song song mà không giẫm chân nhau, và mọi thay đổi đều truy vết được.

## 1. Vòng đời một việc

```
backlog.md (todo) → nhận việc (doing) → nhánh riêng → commit nhỏ → PR → review (review) → merge (done)
```

1. **Nhận việc:** chọn task trong `docs/plan/backlog.md`, ghi tên mình vào cột "Người" và đổi trạng thái thành `doing`. Không nhận quá 2 task cùng lúc.
2. **Làm trên nhánh riêng**, không commit thẳng vào `main`.
3. **Mở PR sớm** (draft cũng được) để người khác thấy hướng đi.
4. **Review:** ít nhất 1 người khác duyệt. PR chạm `packages/contracts/` cần người của cả hai phía duyệt.
5. **Merge** bằng "Squash and merge". Xóa nhánh sau khi merge.

## 2. Đặt tên nhánh

```
<loại>/<MÃ-TASK>-<mô-tả-ngắn>
```

| Loại | Khi nào | Ví dụ |
|---|---|---|
| `feat` | Tính năng mới | `feat/CAP-04-chromapulse-renderer` |
| `fix` | Sửa lỗi | `fix/API-07-token-expiry` |
| `exp` | Thử nghiệm, có thể bỏ | `exp/FACE-03-gend-finetune-lr` |
| `docs` | Chỉ tài liệu | `docs/PLAN-update-status` |
| `chore` | Cấu hình, CI, dọn dẹp | `chore/PLAT-07-ci` |

## 3. Commit (Conventional Commits)

```
<loại>(<phạm-vi>): <mô tả ngắn, tiếng Anh, thì hiện tại> [MÃ-TASK]
```

- Ví dụ: `feat(face): add GenD inference wrapper [FACE-02]`, `fix(api): reject expired session token [PLAT-06]`.
- **Phạm vi:** `web`, `api`, `face`, `voice`, `presence`, `router`, `forensic`, `data`, `contracts`, `docs`, `ci`.
- Mỗi commit làm **một việc**. Không gộp "sửa đủ thứ".

## 4. Pull Request

- Tiêu đề giống commit chính, có mã task. PR đổi hợp đồng thì thêm `[contract]`.
- Điền đủ mẫu `.github/PULL_REQUEST_TEMPLATE.md`.
- **PR nhỏ:** cố gắng dưới 400 dòng thay đổi. Việc lớn thì chia thành nhiều PR.
- Có ảnh chụp hoặc GIF nếu đổi giao diện; có số liệu nếu đổi mô hình hoặc ngưỡng.
- CI phải xanh trước khi merge.

## 5. Người review kiểm tra gì

- Đúng mục tiêu task card? Đạt tiêu chí hoàn thành chưa?
- Khớp hợp đồng? Có vi phạm luật ở AGENTS.md §6 không?
- Có test? Dễ đọc? Có xử lý lỗi?
- Có lỡ commit dữ liệu, trọng số, bí mật không?
- Góp ý theo mức: **phải sửa** / **nên sửa** / **gợi ý**. Lịch sự, nói về code chứ không nói về người.

## 6. Thay đổi quan trọng cần ADR

Viết ADR (`docs/adr/`, theo mẫu `0000-template.md`) khi:
- đổi mô hình chính, đổi kiến trúc, đổi công nghệ;
- đổi cách tính ngưỡng hoặc quyết định;
- thêm thư viện hoặc dịch vụ lớn;
- thay đổi phạm vi so với proposal.

## 7. Giấy phép và dữ liệu

- Thêm thư viện mới: ghi giấy phép trong mô tả PR.
- Chép code từ dự án khác: chỉ MIT/Apache/BSD; giữ dòng giấy phép; ghi vào `third_party/README.md`.
- Không commit dữ liệu, trọng số, video, âm thanh. Mẫu nhỏ để test (< 1 MB) đặt trong `**/tests/fixtures/` và phải là dữ liệu tổng hợp hoặc của thành viên nhóm đã đồng ý.

## 8. Bàn giao

Cuối mỗi buổi làm việc (dù là người hay AI): `uv run python scripts/new_handoff.py --task <MÃ> --who "<tên>"` rồi điền file vừa tạo. Mỗi lần bàn giao là một file riêng nên không bao giờ xung đột. Xem `docs/status/handoffs/README.md`.
