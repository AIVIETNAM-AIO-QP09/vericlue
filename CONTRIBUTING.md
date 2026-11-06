# Phát triển VeriClue

Một thay đổi tốt cần làm rõ **hành vi sản phẩm, bằng chứng kiểm tra và tác động
đến dữ liệu**. Hướng dẫn này giúp thành viên và cộng tác viên được phép đóng
góp theo cùng một quy trình.

[Chuẩn bị](#trước-khi-viết-code) · [Quy trình](#quy-trình-đóng-góp) ·
[Kiểm tra](#kiểm-tra-và-bằng-chứng) · [Dữ liệu](#dữ-liệu-và-quyền-sử-dụng) ·
[Bàn giao](#bàn-giao-và-review)

## Trước khi viết code

1. Đọc [AGENTS.md](AGENTS.md), ngày cập nhật của [STATUS](docs/status/STATUS.md)
   và các [bàn giao gần đây](docs/status/handoffs/).
2. Chọn task trong [backlog](docs/plan/backlog.md), đọc task card, kiểm phụ
   thuộc và thống nhất với người phụ trách. Không nhận quá hai task đồng thời.
3. Đọc [kiến trúc](docs/architecture/architecture.md), README và AGENTS của
   khu vực cần sửa. Xác định profile và cấu hình liên quan.

Với yêu cầu mới chưa có task card, ghi phạm vi và câu hỏi trong bàn giao;
không dùng việc đó để đánh dấu hoàn thành task khác. Không sửa STATUS thay
trưởng nhóm. Quy trình này không cấp quyền sử dụng code hoặc chuyển quyền sở
hữu; xem [LICENSE](LICENSE).

## Quy trình đóng góp

### Xác định hành vi trước khi triển khai

Mô tả ngắn tác nhân, tình huống gây lỗi, hành vi mong muốn và điều kiện hoàn
thành. Với xác minh danh tính, nêu rõ tác động lên trạng thái phiên, lỗi,
thử lại, quyền truy cập và vòng đời dữ liệu.

Nếu đổi giao tiếp, task phải cho phép thay hợp đồng: sửa schema trước, cập
nhật các phía trong cùng PR và thêm `[contract]` vào tiêu đề. Việc sửa ngưỡng,
proposal hoặc ADR tuân theo phạm vi ủy quyền trong AGENTS, không thực hiện
kèm một thay đổi giao diện hay chỉnh tài liệu thông thường.

### Làm trên nhánh có phạm vi rõ

```text
<loại>/<MÃ-TASK>-<mô-tả-ngắn>
fix/SEC-02-reject-expired-proof
```

Mã task trong ví dụ phải được thay bằng mã của việc đã nhận khi áp dụng.
Loại thường dùng: `feat`, `fix`, `docs`, `chore`, `exp`.
Không commit trực tiếp vào `main`.

Commit theo Conventional Commits:

```text
fix(api): reject expired media proof [SEC-02]
```

Mỗi commit nên có một mục đích. Giữ nguyên công việc của người khác, không tự
reset nhánh, xóa file untracked hoặc stage toàn workspace để làm sạch Git.

### Giữ các bất biến an toàn

| Bất biến | Yêu cầu khi thay đổi |
|---|---|
| **Lỗi không trở thành đạt** | Giữ `ModuleResult`, mock và xử lý `error`/`degraded`; không fallback thành công |
| **Bằng chứng có ngữ cảnh** | Không bỏ kiểm tra session, challenge, nonce, hash hoặc chữ ký để luồng đi qua |
| **Quyền truy cập có kiểm soát** | Kiểm token, consent và trạng thái hiện hành, kể cả trường hợp hết hạn/thử lại |
| **Trải nghiệm người dân phù hợp** | Không hiển thị điểm AI, không gán nhãn “giả mạo”; hướng dẫn thử lại rõ ràng |
| **Kết quả có thể truy vết** | Ghi phiên bản, nguồn và phạm vi kiểm tra; tách nghiên cứu khỏi luồng đã tích hợp |

Thay đổi thiết kế cần quyết định tương ứng theo quy trình repo. Không đổi
nhãn mô hình, trạng thái lịch sử hoặc kết quả cũ để khớp cấu hình mới.

## Kiểm tra và bằng chứng

### Workspace Python

```powershell
uv sync --frozen --all-packages
uv run pre-commit install
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python scripts/plan_check.py
```

### Theo thành phần

| Thành phần | Bằng chứng cần cân nhắc | Hướng dẫn |
|---|---|---|
| Android | Test logic, lint/build, ảnh giao diện, thử thiết bị khi cần | [README](apps/android/README.md) |
| iOS | Xcode test/build và điều kiện thiết bị | [README](apps/ios/README.md) |
| API | Quyền, validation, hết hạn, transaction và trường hợp đồng thời | [README](services/api/README.md), [AGENTS](services/api/AGENTS.md) |
| ML | Nhãn, chia tập, phiên bản, tiền xử lý, lỗi và số mẫu | [README](ml/README.md), [AGENTS](ml/AGENTS.md) |
| Web | Lint, typecheck, test và kiểm giao diện liên quan | [README](apps/web/README.md), [AGENTS](apps/web/AGENTS.md) |
| BBS | Kiểm mật mã, sai ngữ cảnh, phát lại, holder và runtime | [README](services/credentials/README.md) |
| Tài liệu | Link, lệnh, encoding, nguồn hình và `git diff --check` | [Mục lục](docs/README.md) |

Chạy check phù hợp thay đổi và check CI bắt buộc. Không viết test chỉ lặp lại
implementation. Báo chính xác lệnh đã chạy, kết quả và check chưa chạy/bị chặn.
Test mock hoặc fixture mật mã không thay thế đánh giá sinh trắc trên dữ liệu thật.

### Khi báo cáo mô hình

- Khóa phiên bản model, preprocessing và cách gộp trước đánh giá cuối.
- Chia theo người/nguồn; không chọn ngưỡng hoặc model trên test.
- Ghi commit, checkpoint, protocol và số mẫu; báo cả lỗi/timeout, không chỉ
  tập con có điểm thành công.
- Tách số liệu paper khỏi kết quả tự chạy; không đổi AUC, EER hoặc HTER thành
  “độ chính xác toàn hệ thống”.

## Dữ liệu và quyền sử dụng

**Không đưa dữ liệu riêng vào Git hoặc artifact công khai:** căn cước, mặt,
giọng, bản ghi thật, DB, `.env`, token, khóa riêng hoặc trọng số. Kiểm cả log,
screenshot, PR và file đính kèm. Quyền quay demo không tự bao gồm quyền huấn
luyện hoặc hiệu chỉnh bằng bản ghi đó.

Ưu tiên fixture tổng hợp nhỏ và ảnh từ UI thật với dữ liệu minh họa. Với ảnh
tài liệu, kiểm bằng mắt, ghi nguồn/commit/checksum như [bộ ảnh app](docs/assets/app/README.md).

Dependency mới cần nêu giấy phép. Code sao chép giữ notice và được ghi vào
[third_party](third_party/README.md). Không chép GPL/AGPL/LGPL hoặc nguồn không
có giấy phép theo luật repo. Tách điều khoản code, trọng số và dataset; giấy
phép nguồn không tự chuyển thành giấy phép thương mại cho toàn sản phẩm.

Kiểm thử tấn công chỉ nhắm môi trường nhóm kiểm soát và được phép, không dùng
hệ thống ngân hàng hoặc dịch vụ thật bên ngoài làm mục tiêu.

## Bàn giao và review

Tạo [PR theo mẫu](.github/PULL_REQUEST_TEMPLATE.md), gồm vấn đề cụ thể, hành
vi sau thay đổi, kiểm tra và rủi ro còn lại. Với UI kèm ảnh phù hợp; với model
kèm nguồn kết quả; với migration nêu yêu cầu chuyển đổi. Có thể mở draft sớm.

Với task có mã, cập nhật tiêu chí task card và đúng dòng backlog, rồi tạo bàn giao:

```powershell
uv run python scripts/new_handoff.py --task <MA-TASK> --who "Ten+AI"
```

Ghi việc đã làm, cách chạy tiếp, giới hạn và câu hỏi cho nhóm. Trưởng nhóm cập
nhật STATUS; chỉnh tài liệu không tự chứng nhận nghiệm thu tính năng.

Trước review, xác nhận:

- [ ] Diff chỉ chứa phạm vi đã nhận, không có dữ liệu riêng hoặc file thừa.
- [ ] Hợp đồng và các bất biến an toàn được giữ hoặc thay đúng quyết định.
- [ ] Check phù hợp đã đạt; check chưa chạy và giới hạn được nêu rõ.
- [ ] Tài liệu, nguồn upstream, task và bàn giao được cập nhật khi áp dụng.
- [ ] PR mô tả implementation cuối cùng, không giữ nội dung của cách làm đã bỏ.

Cần ít nhất một người khác review; đổi hợp đồng cần người hai phía. CI đạt
trước khi merge, nhóm dùng squash merge. Góp ý theo mức phải sửa/nên sửa/gợi
ý, tập trung vào hành vi và bằng chứng.
