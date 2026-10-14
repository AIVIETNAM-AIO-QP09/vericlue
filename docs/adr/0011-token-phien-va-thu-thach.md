# ADR-0011: Token theo phiên, mỗi bước nhận một lần; thử thách sống 120 giây; nhịp nháy màu an toàn

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-14

## Bối cảnh

Ba tài liệu cùng ghi token "dùng một lần" (proposal §2.7(a), thẻ PLAT-06, `session.schema.json`), trong khi `architecture.md` §4 gắn token vào **mọi** lần gọi trong phiên: media, signals, finalize, voice. Hai điều này mâu thuẫn. Ngoài ra, hạn 120 giây cho cả token là quá ngắn khi phiên có tới 2 lần chụp lại và bước đọc câu.

Schema cũng cho phép `hold_ms` = 300 và `transition_ms` = 0, tức 3,3 lần đổi màu/giây — vượt giới hạn 2,5 lần/giây an toàn cho người nhạy cảm ánh sáng (proposal Phụ lục A, WCAG 2.3.1).

## Quyết định

**Token và chống phát lại:**
1. **Token theo phiên:** ký HMAC (`SESSION_SIGNING_SECRET`), gắn `session_id`, hết hạn sau khoảng **5 phút** (`SESSION_TTL_SECONDS`, mặc định 300). Gửi trong header `Authorization: Bearer` ở mọi lần gọi của phiên.
2. **Chống phát lại bằng máy trạng thái phía server:** trong mỗi lượt, mỗi bước (media, signals, finalize, voice) chỉ được nhận **một lần**. Gọi lại một bước đã nhận → **409**. Token sai chữ ký hoặc hết hạn → **401**.
3. **Mỗi thử thách (chuỗi màu) sống 120 giây** kể từ lúc cấp. Chụp lại thì server **cấp thử thách mới** (cách cấp do PLAT-04 thiết kế; đề xuất: kèm trong phản hồi `finalize` khi `status = retry`). Media gắn thử thách cũ hoặc hết hạn bị từ chối.

**Nhịp nháy màu:**
4. `hold_ms` 400–650 (ngẫu nhiên), `transition_ms` = 150 cố định. Mỗi bước ≥ 550 ms, tức **≤ 1,8 lần đổi màu/giây**, an toàn với giới hạn 2,5.
5. Bảng màu **không** cứng trong schema, vì có thể đổi sau thử nghiệm PRES-01. Thay vào đó, bộ sinh chuỗi màu phải có test kiểm:
   - đúng 8 màu, hai màu liền kề khác nhau;
   - ≤ 2,5 lần đổi màu/giây;
   - chênh độ chói tương đối giữa các màu ≤ 0,064;
   - không màu nào có R/(R+G+B) ≥ 0,8.
6. Tổng thời gian nháy: 8 bước × 550–800 ms ≈ **4,4–6,4 giây**, chưa tính 1 giây nền đầu và 0,5 giây nền cuối.

## Hệ quả

- PLAT-04 sửa mô tả trong `session.schema.json` và siết `hold_ms`/`transition_ms` (PR có `[contract]`).
- PLAT-06 cài đặt token, máy trạng thái chống phát lại, giới hạn lượt, kèm test 401 / 409 / 429.
