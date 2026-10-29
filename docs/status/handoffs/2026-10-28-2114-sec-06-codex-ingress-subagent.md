# Bàn giao · SEC-06 · Codex-ingress-subagent · 2026-10-28 21:14

**Nhánh:** `feat/SEC-06-consent-api`
**Trạng thái task sau phiên này:** review (phần API; retention, wiring và UI do nhánh tích hợp xử lý)

## Đã xong
- Hợp đồng `privacy.schema.json`, ví dụ, Pydantic và router consent/withdrawal theo phiên; JSON ≤8 KiB.
- Migration 0010: ledger metadata append-only SQLite/PostgreSQL, không lưu bearer rõ hoặc PII nguồn.
- Chốt đồng ý theo phiên bản/nhóm dữ liệu trước parser và kiểm lại tại handler, mặc định tùy chọn để tương thích synthetic.
- Rút lại trong transaction khóa phiên: chốt xử lý và hủy DEK, sau commit mới xóa thư mục nguồn; retry idempotent với bearer hiện hành tại lúc rút lại.
- Đóng thêm bypass Content-Type upload urlencoded trước Request.form.
- Test đồng thời, rút lại giữa upload, token cũ/hết hạn, lỗi commit, lỗi xóa file, plaintext lease đang chạy và giới hạn metadata.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Không sửa main/config/state/session_store/storage để tránh giẫm việc agent khác; parent tích hợp router và retention.
- Không thay UI/UX; API ghi nhận quyền phiên, chưa chứng minh thao tác đồng ý của người thật.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Cherry-pick duy nhất commit SEC-06 mới sau `4167d67`; các commit profile gốc `3ad9936`, `1c79307` đã có ở nhánh tích hợp (local là `5200d9b`, `4167d67`), không cherry-pick trùng.
2. Parent include `vericlue_api.routers.privacy.router` cho cả chế độ eKYC, áp dụng migration0010 trước phục vụ request, sinh OpenAPI và TypeScript từ app đã tích hợp, bổ sung SDK nếu cần.
3. Kiểm tra luồng với retention/key lifecycle và ảnh thật đã chuẩn hóa ở SEC-04, chạy PostgreSQL trong CI.
4. Nhóm gắn màn thông báo/đồng ý rõ mục đích, đúng phiên bản; không tự gọi API khi chưa có lựa chọn. Backlog/epic do parent cập nhật.

## Quyết định, lưu ý, bẫy
- `scope=session`; không xóa mẫu tài khoản, phiên khác, bản giám định độc lập hoặc bản sao ngoài kho phiên.
- `SESSION_PRIVACY=false`: withdrawal trả503 vì không thể cam kết crypto-shred plaintext cũ.
- `processing_cleanup=not_verified` kể cả khi file nguồn đã xóa: lease plaintext đang xử lý có thể còn sống đến khi tác vụ giải phóng.
- Không thu hồi ngay BBS đã cấp; chốt API chỉ ngăn cấp mới/đọc nguồn từ phiên. Receipt nêu `credential_revocation=not_performed`.
- Bearer mới nhất được lưu hash+expiry tại withdrawal, không kéo dài TTL; bearer cũ sau refresh không đọc tombstone hay rút lại được.
- Không dùng SessionStore.save_all cho privacy API; exception handler gốc phải nhìn thấy lỗi để rollback nonce/DB.
- Consent metadata tối đa8 sự kiện/phiên +1 withdrawal +1 files_erased; append-only không chống DBA toàn quyền. Cần quyết định retention metadata riêng.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Quyết định văn bản/mục đích/cơ sở xử lý và retention metadata, quyền đại diện, xóa mẫu tài khoản là phạm vi sản phẩm/pháp lý tiếp theo, không thể suy ra từ boolean consent.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
pytest test_privacy_consent test_session_ingress test_media_proof test_request_limits test_contract_examples: 168 passed trước khi thêm3 ví dụ; 58 contract examples đã chạy lại xanh.
pytest test_db_storage test_migration_0002 test_session_privacy test_account_auth test_accounts: 113 passed,1 skipped (môi trường DB ngoài).
28 consent tests đã chạy lại cho thay đổi clock cuối cùng; xem báo cáo commit.
ruff check + format --check: sạch trên8 file Python thay đổi.
git diff --check: sạch.
scripts/plan_check.py:0 lỗi,10 cảnh báo tải/lịch sẵn có.
Không chạy npm install/audit online; không gửi dữ liệu/khóa hay fixture ngoài máy.
```
