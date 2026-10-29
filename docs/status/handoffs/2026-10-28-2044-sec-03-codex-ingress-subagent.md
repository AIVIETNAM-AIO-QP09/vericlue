# Bàn giao · SEC-03 · Codex ingress subagent · 2026-10-28 20:44

**Nhánh:** `fix/SEC-03-preparse-auth`, base `73a25ab`.
**Trạng thái task sau phiên này:** review; parent tích hợp và cập nhật dòng SEC-03.

## Đã xong
- Thêm `SessionAPIRoute` kiểm bearer/current token hash trước khi FastAPI parse body.
  DB session chỉ đọc đóng trước receive, không `save_all` hoặc cập nhật hoạt động.
- Dependency cũ dùng chung helper và vẫn kiểm sau body: đổi token/hết hạn trong lúc
  parser nhận stream bị từ chối; thiếu/sai/trùng bearer không tạo file tạm.
- Multipart giới hạn vai trò/số file/field, trùng part, header, field byte và file
  byte ngay trong callback, giữ MAX_REQUEST_MB và MAX_UPLOAD_MB hiện có.
- Truncated multipart và lỗi parse/handler đóng file tạm; form cache không parse lại.
- Thêm `docs/architecture/session-ingress.md` và test tổng hợp; OpenAPI không đổi.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Chưa có quota tổng theo phiên/IP/worker, proxy deadline hoặc temp filesystem riêng;
  đây không phải bằng chứng chống DDoS. Phần đó thuộc tích hợp SEC-04/05/06.
- Chưa chạy PostgreSQL trực tiếp/thiết bị thật trong nhánh này. Bài race SQLite
  xác nhận mutation nằm sau khi parser bắt đầu, không phải trước preflight.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Parent cherry-pick commit, tích hợp với SEC-04/05/06 và cập nhật backlog/task card.
2. Chạy toàn bộ API/contract/CI, thêm PostgreSQL nếu có DB CI. Giữ test nonce rollback.
3. Các endpoint file mới phải khai báo UPLOAD_RULES tương ứng; parser subclass có
   callback/private cache Starlette cần regression test khi nâng framework.

## Quyết định, lưu ý, bẫy
- Không bắt exception từ handler gốc trong APIRoute rồi trả JSON: với yield
  dependency, việc nuốt exception có thể commit nonce của upload lỗi. Chỉ định
  dạng lỗi preflight/parser trước khi dependency bắt đầu; handler errors đi lên.
- Không đọc toàn body ở preflight và không giữ khóa DB trong lúc chờ client.
- max_part_size của Starlette hiện chỉ chặn field, nên callback kiểm byte file riêng.
- Filename/MIME vẫn không chứng minh định dạng; SEC-04 kiểm ảnh theo byte sau
  kiểm chữ ký, giữ nguyên bytes của upload trong SEC-03.
- Không sửa config.py, schema, threshold, ADR, UI hoặc bỏ guard model.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Không có quyết định nghiệp vụ mới. Hằng số ingress: header part8KiB, QR16KiB,
  challengeID256B, signature160B, audio_offset8B; file theo MAX_UPLOAD_MB.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
pytest test_session_ingress.py test_media_proof.py test_request_limits.py:
85 passed, 1 Starlette deprecation warning có sẵn, 24.63s
ruff check + format --check các file đã thay: pass
scripts/gen_openapi.py --check: openapi.json khớp code
git diff --check: pass
```
