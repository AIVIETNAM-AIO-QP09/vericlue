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

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
