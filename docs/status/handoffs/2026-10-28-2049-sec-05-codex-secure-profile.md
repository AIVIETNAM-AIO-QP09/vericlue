# Bàn giao · SEC-05 · Codex+secure-profile · 2026-10-28 20:49

**Nhánh:** `fix/SEC-05-safe-profile`, base `73a25ab` / main `caf4469`.
**Trạng thái task sau phiên này:** review kỹ thuật; parent cập nhật backlog sau tích hợp.

## Đã xong
- Profile `synthetic|protected`; `create_app` kiểm protected trước tạo DB/model state.
  Protected yêu cầu mode eKYC, consent bắt buộc, privacy, ký media, model real;
  master 32 byte base64 chuẩn, HMAC/token >=32 byte, từ chối dev/placeholder/lặp
  một ký tự và dùng lại vật liệu giữa ba vai trò. Không tự tạo hoặc đổi khóa.
- Helper OTP gọi đầu cả send/verify: chỉ exact mock `True` + synthetic được dùng
  kênh mô phỏng. Real/mixed/protected trả 503 trước thay đổi trạng thái; OTP mock
  cũ không thể được xác nhận sau đổi mode. Guard model/nguồn thật vẫn giữ.
- Preflight `scripts/check_security_profile.py` chỉ xuất tên check/boolean,
  không nối DB, nạp model, sinh khóa, ký hoặc in bí mật/path cấu hình.
- Overlay protected, bind API loopback mặc định có cấu hình, temp tmpfs 256 MiB,
  Docker image chứa CLI và runbook nêu giới hạn. Overlay kết hợp BBS hợp lệ.
- Settings dùng chung cho SEC-04/06 đã thêm theo phối hợp; fixture test dùng
  synthetic/tools và consent=false để tách môi trường operator khỏi kiểm thử.

## Đang dở
- Parent triển khai receipt/withdraw/retention và bỏ route tools khi product_mode
  là ekyc ở SEC-06. Profile chỉ kiểm cấu hình, không tự có UI consent.
- Chưa có SMS thật, chưa nghiệm thu app/AI/TLS/quyền tệp/backup trên máy demo.

## Bước tiếp theo
1. Nhận commit OTP `3ad9936` rồi commit profile. Không nhận lại `97d351b` (cùng
   nội dung OTP do subagent file tách); SEC-04 không lặp guard này.
2. Tích hợp SEC-03/04/06, chạy lại kiểm thử/hợp đồng và đánh dấu backlog/card.
3. Operator làm preflight bằng khóa riêng, app ký media và consent đúng phiên bản.

## Quyết định, lưu ý, bẫy
- `config.py` có `max_id_card_scans=5`, `max_id_card_total_mb=128`,
  `product_mode=tools|ekyc` mặc định tools, `media_ttl_unverified_hours=24`,
  `require_privacy_consent=false`, `privacy_policy_version=demo-v1` pattern ASCII.
- Synthetic là môi trường lab tương thích, không là profile bảo vệ dữ liệu thật.
  Người vận hành phải chọn protected overlay; model real không chứng minh cấu
  hình nền đã bảo vệ đúng hoặc cho phép mở các guard sinh trắc.
- Chưa có SMS thật; luồng cần chứng minh số điện thoại vẫn đóng. Không dùng
  mock receipt để nói đã xác minh số ngoài đời.
- Độ dài/placeholder không chứng minh entropy; khóa phải từ CSPRNG, giữ bền,
  ACL/backup kiểm riêng. Tmpfs không thay lease/orphan cleanup hoặc backup.
- Không sửa schema/ADR/ngưỡng/UI, không chạy npm audit BBS đã bị chặn egress.

## Câu hỏi cho nhóm
- Không có câu hỏi mới ngoài các quyết định workflow/thiết bị parent đang chốt.
  Không đánh dấu nghiệm thu app hoặc toàn bộ bảo mật đã hoàn thành.

## Test đã chạy
```
pytest test_security_profile.py test_identity_steps.py test_account_auth.py test_accounts.py:
121 passed, 1 cảnh báo Starlette/httpx có sẵn, 32.10 s; dữ liệu tổng hợp.
Ruff check và format --check sáu file Python thay đổi: pass.
Compose base+protected config --quiet: pass; base+protected+BBS: pass với giá trị tổng hợp.
plan_check.py --board và git diff --check: pass.
Chưa build/chạy container hoặc nghiệm thu TLS/thiết bị thật.
```
