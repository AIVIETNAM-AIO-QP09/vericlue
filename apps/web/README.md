# apps/web — Giao diện web (Next.js)

**Phụ trách:** M1 (web xác minh), M2 (bàn duyệt, cổng giám định)
**Trạng thái:** đã khởi tạo ở **PLAT-02** (Next.js 16, App Router, TypeScript strict, Tailwind 4, Vitest, Prettier).

## Ba khu vực

| Đường dẫn   | Người dùng                | Task chính |
| ----------- | ------------------------- | ---------- |
| `/verify`   | Người dân trên điện thoại | E2 (CAP-*) |
| `/review`   | Nhân viên duyệt           | E7 (REV-*) |
| `/forensic` | Điều tra viên             | E7 (FOR-*) |

## Quy ước

- TypeScript strict, App Router, thư mục `src/`.
- Logic camera, cổng chất lượng, ChromaPulse, CamProbe nằm trong `src/lib/capture/`, **không** viết trong component.
- Gọi API qua `src/lib/api/` (type sinh từ OpenAPI). Không gọi `fetch` rải rác.
- Code chép từ AWS Amplify hay CreepJS để trong `src/lib/capture/vendor/`, giữ nguyên dòng giấy phép ở đầu file và ghi vào `third_party/README.md`.
- Chữ hiển thị tiếng Việt để trong `src/i18n/vi.ts`.
- Người dân **không bao giờ** thấy điểm số hay chữ "giả mạo".
- Không tải phông từ mạng (demo chạy offline): dùng phông hệ thống.

## Lệnh

```bash
cp .env.local.example .env.local   # lần đầu; chỉnh NEXT_PUBLIC_API_URL nếu API chạy chỗ khác
npm ci                             # hoặc npm install
npm run dev                        # http://localhost:3000
npm run lint
npm run test
npm run typecheck
npm run gen:api                    # sinh lại type API từ ../../packages/contracts/openapi.json
npm run format:check               # npm run format để tự sửa
npm run build
```

## Gọi API

- Chỉ qua `src/lib/api/client.ts` (`createApiClient`): tự gắn `Authorization: Bearer` cho các bước của phiên, lỗi thành `ApiError` có `errorCode`.
- Type nằm ở `src/lib/api/schema.d.ts`, **sinh tự động**, đừng sửa tay. Khi API đổi: `uv run python scripts/gen_openapi.py` rồi `npm run gen:api`, commit cả hai file (CI kiểm chạy lại không lệch).
- `NEXT_PUBLIC_API_URL` trỏ tới API (mặc định `http://localhost:8000`). Khi API chạy mock, `createSession("print")` chọn kịch bản qua header `X-Mock-Scenario`.

## Thử trên điện thoại

1. Cùng mạng Wi-Fi với máy tính. Chạy `npm run dev -- -H 0.0.0.0`, mở `http://<IP-máy>:3000` (xem IP bằng `ipconfig`). Cách này đủ để xem giao diện; Windows Firewall có thể hỏi quyền cho Node.
2. **Camera cần HTTPS** (trừ `localhost`). Chọn một trong hai:
   - `npm run dev -- --experimental-https -H 0.0.0.0` rồi mở `https://<IP-máy>:3000` (chấp nhận cảnh báo chứng chỉ);
   - hoặc `cloudflared tunnel --url http://localhost:3000` (hoặc ngrok).

Xem thêm `docs/runbooks/dev-setup.md` §4.
