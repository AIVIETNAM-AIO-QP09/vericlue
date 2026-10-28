# Bàn giao · SEC-06 · Codex-integration · 2026-10-28 21:26

**Nhánh:** `fix/SEC-03-security-hardening`
**Trạng thái task sau phiên này:** SEC-03/04/05/06/08 review; SEC-07 doing vì dependency web chưa vá.

## Đã xong

- Ghép ba subagent: kiểm quyền/consent trước parser, multipart bounded, kiểm/chuẩn hóa ảnh theo nội dung, rescan/quota bền, profile fail-closed và chặn OTP mô phỏng ở real/mixed/protected.
- Consent/rút lại theo phiên có contract/Pydantic/router/migration 0010; OpenAPI, TypeScript và SDK đồng bộ. Kiểm consent hiện hành cả khi dùng lại CCCD/liên hệ/giọng đã lưu, không đòi giọng chỉ vì có prompt cấp trước.
- Mode eKYC ẩn route review/forensic, không tạo ca chờ nhân viên. Retention hữu hạn và độc lập polling; kiểm trước giải mã, trước ghi quyết định và commit để tác vụ hoàn tất muộn không gia hạn dữ liệu.
- Rà chéo và sửa race cleanup SQLite/upload bằng BEGIN IMMEDIATE. Hủy DEK không phụ thuộc unlink; file lỗi vẫn retry. Audit phân biệt khóa/file và không nhận hủy khóa thành công khi DB rollback.
- Công cụ offline rewrap DEK phiên/tài khoản nguyên tử, dry-run và kiểm kê temp chỉ đọc; không gọi trên kho thật.
- Protected Compose không tự chạy Next.js cũ; API mặc định loopback, multipart tmpfs riêng. Không thay layout, ngưỡng ML, ADR, proposal hoặc STATUS.md.
- [Bảng kết quả theo AUD-01…14](../../research/2026-10-28-security-remediation.md), runbook và task card/backlog cập nhật đúng phạm vi.

## Đang dở

- SEC-07/Next.js: npm registry bị auto-review chặn vì egress metadata dependency; user mới hỏi web dùng để làm gì, chưa cấp quyền kết nối. Thử offline thiếu package, manifest/lockfile giữ nguyên đồng bộ 16.4.0; bản đề xuất 16.4.3 chưa áp dụng. Không chuyển tải package qua CI để né chốt này.
- Nhóm app phải nối lựa chọn consent/rút lại và thông báo đúng phiên bản/phạm vi. Chưa có SMS provider thật, không mở các guard sinh trắc thật.
- PostgreSQL/container/TLS/app/ACL/backup/crash/load test cần môi trường triển khai. Docker daemon local chưa chạy; ba bài hồi quy PostgreSQL mới sẽ được CI thu thập, local skip có ghi rõ.

## Bước tiếp theo

1. Review PR tích hợp và CI, đặc biệt migration 0010 và các test PostgreSQL; không merge thay nhóm.
2. Nhóm app đọc [consent](../../architecture/session-privacy-consent.md), nối lựa chọn chủ động trước thu dữ liệu; giữ voice theo nhu cầu và không hứa có nhân viên đang duyệt.
3. Operator đọc [protected profile](../../runbooks/protected-profile.md) và [master key lifecycle](../../runbooks/master-key-lifecycle.md), kiểm kho/backup trước đổi mode. Không bật protected rồi coi đó là nghiệm thu sinh trắc.
4. Khi user quyết định tiếp tục dùng web và cho phép npm registry, cập nhật cả Next/eslint-config-next/lockfile rồi kiểm lại. Không ghi đè dependency root checkout hoặc tuyên bố advisory đã khắc phục chỉ vì service bị tắt.

## Quyết định, lưu ý, bẫy

- API consent dùng bearer hiện hành, không chứng minh ý chí con người; withdrawal chỉ xóa kho **phiên**, không xóa tài khoản/backup hay thu hồi ngay BBS đã cấp. Lease plaintext đang chạy có thể còn tới khi tác vụ thực kết thúc.
- Biên nhận withdrawal giữ hash/hạn token hiện hành để gọi lại tối thiểu sau hủy DEK; không nhận token trước refresh, không kéo dài TTL. Nhật ký append-only không chống DBA toàn quyền và chưa có chính sách xóa metadata riêng.
- Mặc định ca chưa xác minh 24h, trần rescan 5 lượt, CCCD 128 MiB và tổng media 256 MiB là cấu hình demo cần đo capture. Counter cũ mặc định 0, không dựng lại lịch sử byte trước bản vá.
- Không catch lỗi handler trong APIRoute wrapper: yield dependency phải thấy exception để rollback nonce. Privacy transaction không gọi SessionStore.save_all sau hủy khóa.
- Test quota phải giữ CCCD trước: nếu face thắng trước, flow chặn quét CCCD bằng 409 là hợp lệ và không chứng minh đã chạm quota. Bài kiểm tra hiện điều khiển thứ tự bằng event và kiểm face nhận 413.
- `test_eval_report[not_repository]` cần thư mục tạm ngoài cây Git. Chạy toàn scripts/ML với basetemp dưới repo đã gây một lỗi môi trường; không sửa logic/test chỉ để nhận thư mục con Git là ngoài repo.

## Câu hỏi cho nhóm

- Chốt thông báo consent, đầu mối yêu cầu xóa, thời hạn metadata/backup, mất bearer và xóa mẫu tài khoản; không tự đặt pháp nhân hoặc kết luận tuân thủ.
- Có tiếp tục dùng web dự phòng không, và có cho phép npm registry để hoàn tất bản vá dependency không? Câu hỏi quyền kết nối đã được gửi, chưa được trả lời bằng chấp thuận.

## Test đã chạy

- Python Ruff toàn repo và format: đạt (741 file sau bổ sung test PG).
- OpenAPI `--check`, `uv lock --check --offline`, Compose protected `config --quiet`: đạt; không chạy container hoặc DB thật.
- Web: typecheck, ESLint SDK và Prettier file đổi đạt; Vitest toàn bộ **1319 passed, 10 skipped**.
- Parent retention/orchestrator: **38 passed**; subagent cleanup+privacy/storage **51 passed, 1 skipped**; repeat quota/refresh concurrency **2 passed**. Các nhóm này có thể trùng nhau, không cộng làm số lượng mẫu độc lập.
- Scripts/ML: lượt rộng **2635 passed, 42 skipped**, một test not_repository lỗi vì basetemp nằm dưới Git; nhóm eval-report được chạy lại với TEMP riêng ngoài repo, kết quả bổ sung dưới đây.
- Nhóm `ml/tests/test_eval_report.py` chạy lại với TEMP riêng ngoài repo: **42 passed**. Không sửa source ML hoặc thay kỳ vọng test để xử lý lỗi môi trường.
- API toàn bộ cuối: **1800 passed, 29 skipped**, một warning, 441,80 giây; có worker BBS thật bằng Node cục bộ. PostgreSQL/trình duyệt/điều kiện ngoài được skip đúng fixture; không gọi đây là toàn bộ đường triển khai đã đạt.
- `plan_check.py`: **0 lỗi, 10 cảnh báo** tải/lịch sẵn có. Hooks kiểm secrets/merge/JSON/YAML/kích thước/lint đạt trước commit.

Số test kiểm logic phần mềm và mật mã trên fixture tổng hợp; không phải số người,
mẫu sinh trắc, accuracy hoặc kết quả R của cuộc thi. Không chạy npm install/audit
online, không tải mô hình hoặc gửi khóa/dữ liệu sinh trắc ra ngoài máy.
