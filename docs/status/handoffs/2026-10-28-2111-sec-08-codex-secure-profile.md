# Bàn giao · SEC-08 · Codex+secure-profile · 2026-10-28 21:11

**Nhánh:** `feat/SEC-08-key-lifecycle`
**Trạng thái task sau phiên này:** review

## Đã xong
- CLI dry-run mặc định và apply có `--confirm-services-stopped`, đầu vào khóa
  qua tệp base64/biến môi trường có tên, URL DB chỉ qua biến môi trường có tên.
  Không tự sinh/ghi khóa, sửa `.env`, khởi tạo ApplicationState/model hoặc giải
  mã payload sinh trắc/định danh.
- Rewrap đúng định dạng AES-GCM/AAD hiện hành của DEK phiên và tài khoản;
  giữ nguyên payload, bỏ qua tombstone hợp lệ, từ chối trạng thái hủy không
  nhất quán. Một giao dịch toàn bộ; sai khóa/tag hoặc lỗi commit rollback.
- SQLite apply dùng `BEGIN IMMEDIATE`; CLI từ chối kho không tồn tại và sidecar
  WAL/journal, dry-run mở DB chỉ đọc. PostgreSQL apply khóa hai bảng với timeout
  5 giây; dry-run dùng giao dịch read-only.
- Output chỉ có số lượng, fingerprint có miền riêng, giới hạn và mã lỗi an
  toàn; không in SQL, URL DB, đường dẫn, khóa hay PII. CLI không lặp lại tham
  số lạ có thể chứa bí mật.
- Kiểm kê `_decoded` chỉ đọc, giới hạn 10.000 entry, từ chối symlink/junction;
  không đọc nội dung và không xóa. Không gọi candidate lease là orphan.
- Runbook hướng dẫn backup/restore, ACL, cấu hình sau apply, kết quả commit
  chưa rõ khi mất kết nối, và ranh giới crypto-shred/live data/backup.

## Đang dở
- Không chạy trên DB, dữ liệu hay khóa thật. PostgreSQL locking có code nhưng
  chưa được kiểm chứng với dịch vụ PostgreSQL chạy thực tế trong phiên này.
- Windows host không cho tạo symlink nên test symlink skip; code có kiểm tra
  symlink/junction nhưng chưa kiểm chứng tích hợp junction thực tế.
- Công cụ không có sổ lease bền vững để chứng minh tệp đã mồ côi; không cung
  cấp cleanup tự động vì có thể xóa tệp của phiên đang hoạt động.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Parent cherry-pick **commit code SEC-08 cuối cùng**, không cherry-pick
   `2c3ee33` (tương đương docs-only `3592bd7` parent đã có).
2. Parent cập nhật task card/backlog theo tích hợp, kiểm tra regression chung.
3. Khi triển khai, operator đọc runbook, kiểm tra trên bản sao tổng hợp trước;
   mọi apply thật phải do operator được phép thực hiện trong cửa sổ bảo trì.

## Quyết định, lưu ý, bẫy
- Cờ dừng dịch vụ là xác nhận của operator, không chứng minh các worker đã
  dừng. Table lock chỉ có hiệu lực trong giao dịch, không bảo vệ sau commit.
- Sau rotation, chỉ đổi cấu hình về khóa cũ không phải rollback hợp lệ;
  cần rewrap ngược trong cửa sổ bảo trì hoặc phục hồi đồng bộ từ backup.
- Fingerprint không phải khóa. Dù chỉ in fingerprint, vẫn kiểm soát log vận
  hành và không ghi thêm cấu hình/SQL/môi trường vào báo cáo.
- CLI chạy từ checkout host với môi trường API. Không thêm vào Dockerfile,
  không thực hiện npm audit/online install (metadata egress đã bị chặn trước).
- Không sửa config/state, schema, UI, ngưỡng hay backlog/task card trong nhánh
  này; parent quản lý trạng thái task và tích hợp các agent.

## Câu hỏi cho nhóm
- Nếu cần dọn temp tự động sau sự cố, cần thiết kế lease ownership bền vững
  trước; kiểm kê hiện tại không chứng minh lease hết hoạt động. Chưa triển khai
  thao tác xóa khi chưa có bằng chứng đó.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```text
pytest services/api/tests/test_key_rotation.py
       services/api/tests/test_session_privacy.py
       services/api/tests/test_accounts.py
  --basetemp <fresh workspace temp> --maxfail=1 --tb=short --disable-warnings
77 passed, 1 skipped, 1 warning in 22.30s

ruff check <4 Python files changed>: All checks passed
ruff format --check <4 Python files changed>: 4 files already formatted
git diff --check: passed
scripts/plan_check.py: 0 lỗi, 10 cảnh báo tải/phụ thuộc có sẵn
```

Test dùng migration SQLite hiện hành, secret ngẫu nhiên độc lập và payload
tổng hợp: dry-run không đổi hàng/hash DB; apply mở payload cũ bằng master mới;
key cũ không mở DEK sau đổi; lỗi tag account cuối rollback session đã flush;
lỗi before_commit rollback; tombstone giữ nguyên; lỗi đầu vào/URL/khóa không
bị lộ ra CLI; sidecar/missing DB bị từ chối; temp không bị xóa.
