# Bàn giao · FLOW-01 · Ngọc Quang+Claude · 2026-10-26 17:50

**Nhánh:** `feat/FLOW-01-voice-on-suspicion`
**Trạng thái task sau phiên này:** review (PR mở, chờ người làm FLOW-05 duyệt phần ghi danh)

## Đã xong
- Đăng ký (`onboarding`) chỉ đọc câu khi điểm mặt lưng chừng (B < điểm < A); mặt rõ đạt thì đạt luôn ở `finalize`. Khôi phục (`recovery`) vẫn luôn đọc câu; `reauth` không đổi. Trưởng nhóm duyệt khi họp (Quang chuyển lời 26/10). Sửa ở `ml/src/vericlue_ml/router/flows.py` (`route_face`).
- Ghi danh tài khoản: `SessionFlow.finalize` ghi danh khi đăng ký đạt ngay (như `voice()` vẫn làm); client lấy biên nhận qua `GET /v1/sessions/{id}/account`, không đổi hợp đồng (`openapi.json` khớp).
- `AccountStore._validate_biometrics`: phiên **không** đọc câu bỏ đúng các kiểm tra về giọng (bước `voice`, `VOICE_CHALLENGE`/`LIPSYNC`/`VOICE_SPOOF`, face–voice continuity, chữ ký media giọng). "Có đọc câu" xác định theo lịch sử quyết định (`DecisionRow` có `voice_challenge`), không theo trạng thái client: đã từng được yêu cầu đọc câu thì phải đủ bằng chứng giọng. Mọi kiểm tra mặt, CCCD, OTP, chữ ký media mặt giữ nguyên.
- Tài liệu: ADR-0016 (mục cập nhật 26/10), ADR-0013 bảng giai đoạn C, `dynamic-session-api.md`, E9, README Android.

## Đang dở
- App Android chưa dùng biên nhận tài khoản ở đâu (việc của bên tích hợp UI, xem README Android); khi nối, đăng ký đạt ở `finalize` phải gọi `fetchAccountReceipt()`.

## Bước tiếp theo
1. Người làm FLOW-05 (ghi danh, `accounts.py`) duyệt phần nới điều kiện ghi danh.
2. Khi chạy chế độ thật: đo tỉ lệ ca rơi vào vùng lưng chừng (phải đọc câu) trên dữ liệu chia theo người, không dùng tập test.

## Quyết định, lưu ý, bẫy
- Bỏ đọc câu làm mất lớp chặn giọng nói với kẻ gian qua được cả ba lớp động ở giai đoạn B; chấp nhận cho demo (ghi ở ADR-0016).
- Kịch bản mock `voice_clone` cho điểm mặt lưng chừng, dùng để thử nhánh đọc câu của `onboarding`.

## Câu hỏi cho nhóm
- Không có câu chặn.

## Test đã chạy
```
uv run pytest                        # toàn bộ, xanh (26/10)
uv run ruff check ml services        # sạch
uv run python scripts/gen_openapi.py --check   # openapi.json khớp code
Test mới/sửa: ml/tests/test_router_flows.py (onboarding chỉ đọc khi lưng chừng, recovery luôn đọc),
services/api/tests/test_dynamic_flows.py (đăng ký mặt sạch đạt không đọc câu, /voice trả 409),
services/api/tests/test_accounts.py (ghi danh không đọc câu; đã từng được yêu cầu đọc câu mà bỏ qua thì không ghi danh),
test_media_proof.py, test_session_motion.py (đổi sang recovery hoặc kỳ vọng pass).
```
