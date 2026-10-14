# AGENTS.md — apps/web/ (Next.js)

Bổ sung cho `AGENTS.md` ở gốc repo. Đọc thêm `apps/web/README.md`.

- **Logic camera, chất lượng, ChromaPulse, CamProbe** nằm trong `src/lib/capture/`, không viết trong component.
- **Đo thời gian bằng `performance.now()`**, `requestAnimationFrame` và `requestVideoFrameCallback`. **Không** dùng `Date.now()` hay MediaRecorder để đo độ trễ.
- **Nháy màu an toàn:** tối đa 2,5 lần đổi màu/giây, không dùng đỏ bão hòa, có cảnh báo và nút "Bỏ qua". Không đổi bảng màu khi task không yêu cầu.
- **Người dân không bao giờ thấy điểm số** hay chữ "giả mạo". Gợi ý chụp lại chỉ nói về chất lượng.
- **Gọi API chỉ qua `src/lib/api/`** (type sinh từ OpenAPI: `npm run gen:api`).
- **Code chép từ Amplify hay CreepJS** để trong `src/lib/capture/vendor/`, giữ dòng giấy phép, ghi `third_party/README.md`.
- **Chữ hiển thị tiếng Việt** đặt trong `src/i18n/vi.ts`.
- **Camera trên điện thoại cần HTTPS** — xem `docs/runbooks/dev-setup.md` §4.
