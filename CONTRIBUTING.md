# Đóng góp cho VeriClue

**Giữ hành trình xác minh rõ ràng, bằng chứng có thể kiểm tra và dữ liệu được bảo vệ.**

Tài liệu dành cho thành viên/cộng tác viên được chủ sở hữu cho phép đóng góp.
Đọc [LICENSE](LICENSE) về quyền sử dụng; quy trình này không cấp giấy phép mới,
không mặc định chuyển quyền sở hữu hoặc tái cấp phép mã của tác giả khác.

[Bắt đầu](#bắt-đầu) · [Quy trình](#từ-task-đến-pull-request) ·
[Kiểm tra](#kiểm-tra-theo-phạm-vi) · [Dữ liệu](#dữ-liệu-hình-ảnh-và-bên-thứ-ba)

## Bắt đầu

1. Đọc [AGENTS.md](AGENTS.md), các [bàn giao gần đây](docs/status/handoffs/)
   và ngày cập nhật của [STATUS](docs/status/STATUS.md).
2. Xác định task trong [backlog](docs/plan/backlog.md), đọc task card và phụ
   thuộc; phối hợp người phụ trách, không nhận quá hai task đồng thời.
3. Đọc README/AGENTS của khu vực sửa và [kiến trúc](docs/architecture/architecture.md).
   Tài liệu lịch sử không thay việc đối chiếu source/profile.

Việc mới chưa có task card cần ghi phạm vi và câu hỏi trong bàn giao; không
đánh dấu hoàn thành một task không liên quan.

## Từ task đến pull request

| Bước | Kết quả cần có |
|---|---|
| Xác định phạm vi | Vấn đề, hành vi mong muốn, tiêu chí hoàn thành |
| Nhánh riêng | `<loại>/<MÃ-TASK>-<mô-tả-ngắn>`, không commit thẳng `main` |
| Thay đổi nhỏ | Commit có thể review, không trộn thay đổi người khác |
| Kiểm tra | Lệnh đã chạy, kết quả và giới hạn rõ ràng |
| Bàn giao | Cập nhật đúng task, ghi cách chạy tiếp và câu hỏi còn lại |
| Review | PR theo mẫu, ít nhất một người khác duyệt và CI đạt |

Loại nhánh/commit thường dùng: `feat`, `fix`, `docs`, `chore`, `exp`.

```text
fix(api): reject expired media proof [SEC-02]
```

Dùng [mẫu PR](.github/PULL_REQUEST_TEMPLATE.md), mô tả vấn đề và hành vi cuối
cùng. PR nhỏ, có thể mở draft sớm. Thay hợp đồng cần người hai phía review;
nhóm dùng squash merge. Không tự reset nhánh, xóa file untracked hoặc commit
cả workspace để làm sạch Git.

## Những nguyên tắc cần giữ

### Hợp đồng và quyết định xác minh

- Giao tiếp khớp `packages/contracts/`. Khi task cho phép đổi hợp đồng, sửa
  schema trước, cập nhật hai phía trong cùng PR và thêm `[contract]` vào tiêu đề.
- Bộ phát hiện trả `ModuleResult` và có mock; không đổi lỗi/suy giảm thành đạt.
- Không fallback ngầm sang thành công, không tắt consent, chữ ký, nonce hoặc
  kiểm danh tính để demo hoàn tất.
- Người dân không thấy điểm AI hoặc nhãn “giả mạo”; gợi ý thử lại phải phù hợp.
- Tuân thủ luật AGENTS về ngưỡng, schema, proposal và ADR. Thay đổi thiết kế
  cần quyết định tương ứng; không tự viết lại yêu cầu hoặc lịch sử.

### Truy vết và đánh giá

- Tách benchmark paper, kiểm thử phần mềm và đánh giá toàn hệ thống.
- Báo cáo ghi commit, model/checkpoint, protocol, số mẫu, lỗi và timeout.
- Chia theo người/nguồn; không chọn mô hình, ngưỡng hoặc tiền xử lý trên test.
- Không mô tả chữ ký là bằng chứng camera thật, Keystore luôn có phần cứng,
  hoặc chuyển động đầu là phép đo chiều sâu 3D.

## Kiểm tra theo phạm vi

Từ gốc repo, sau khi cài theo [README](README.md):

```powershell
uv sync --frozen --all-packages
uv run pre-commit install
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python scripts/plan_check.py
```

| Khu vực | Tài liệu và kiểm tra |
|---|---|
| Android | [README](apps/android/README.md): Gradle test/lint/build, ký APK và thử thiết bị |
| iOS | [README](apps/ios/README.md): Xcode, backend và nghiệm thu riêng |
| API | [README](services/api/README.md), [AGENTS](services/api/AGENTS.md): migration, quyền, transaction |
| ML | [README](ml/README.md), [AGENTS](ml/AGENTS.md): extras và đánh giá |
| Web | [README](apps/web/README.md), [AGENTS](apps/web/AGENTS.md): npm và giao diện |
| BBS | [README](services/credentials/README.md): Node, lint/test, holder SDK |

Chạy check phù hợp thay đổi và các check bắt buộc của CI. Với tài liệu thuần
túy, kiểm liên kết, encoding, lệnh và `git diff --check`. Không báo đã test
ứng dụng hoặc AI nếu chỉ sửa Markdown. Ghi rõ check chưa chạy hoặc bị chặn.

## Dữ liệu, hình ảnh và bên thứ ba

- Không commit `.env`, token, khóa riêng, DB, dữ liệu sinh trắc, bản ghi thật
  hoặc trọng số. Không đưa chúng vào log, screenshot, PR hoặc artifact công khai.
- Dùng fixture tổng hợp nhỏ, có quyền rõ ràng. Quyền quay demo không tự cho
  phép huấn luyện/hiệu chỉnh bằng dữ liệu đó.
- Ảnh tài liệu ưu tiên snapshot tổng hợp từ UI thật; kiểm bằng mắt, ghi nguồn,
  commit và checksum. Xem [bộ ảnh README](docs/assets/app/README.md).
- Kiểm thử tấn công chỉ trên môi trường được phép, không nhắm hệ thống thật
  của ngân hàng hoặc bên ngoài.
- Dependency mới phải ghi giấy phép. Code sao chép giữ notice và ghi vào
  [third_party](third_party/README.md); không chép GPL/AGPL/LGPL hoặc nguồn
  không có giấy phép theo luật repo.
- Code, trọng số và dữ liệu có thể có giấy phép khác nhau. Kiểm quyền nghiên
  cứu, thương mại và phân phối; giữ license upstream, không tự thay bằng LICENSE gốc.

## Bàn giao và hoàn tất

Với task có mã, cập nhật tiêu chí task card và đúng dòng backlog, rồi tạo bàn giao:

```powershell
uv run python scripts/new_handoff.py --task <MA-TASK> --who "Ten+AI"
```

Ghi việc đã làm, check thực sự đã chạy, giới hạn, bước tiếp và câu hỏi cho nhóm.
Không sửa `docs/status/STATUS.md`; trưởng nhóm tổng hợp file này. Cập nhật tài
liệu không tự chứng nhận hoàn thành tính năng.

Trước khi gửi review, kiểm diff chỉ chứa phạm vi được giao, không có dữ liệu
riêng hoặc artifact thừa. Cập nhật PR theo kết quả cuối cùng, tránh giữ mô tả
cũ của cách làm đã bỏ.
