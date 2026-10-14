# apps/web — Giao diện web (Next.js)

**Phụ trách:** M1 (web xác minh), M2 (bàn duyệt, cổng giám định)
**Trạng thái:** chưa khởi tạo — làm ở task **PLAT-02** (`docs/plan/epics/E0-platform.md`).

## Ba khu vực

| Đường dẫn | Người dùng | Task chính |
|---|---|---|
| `/verify` | Người dân trên điện thoại | E2 (CAP-*) |
| `/review` | Nhân viên duyệt | E7 (REV-*) |
| `/forensic` | Điều tra viên | E7 (FOR-*) |

## Quy ước

- TypeScript strict, App Router, thư mục `src/`.
- Logic camera, cổng chất lượng, ChromaPulse, CamProbe nằm trong `src/lib/capture/`, **không** viết trong component.
- Gọi API qua `src/lib/api/` (type sinh từ OpenAPI). Không gọi `fetch` rải rác.
- Code chép từ AWS Amplify hay CreepJS để trong `src/lib/capture/vendor/`, giữ nguyên dòng giấy phép ở đầu file và ghi vào `third_party/README.md`.
- Chữ hiển thị tiếng Việt để trong `src/i18n/vi.ts`.
- Người dân **không bao giờ** thấy điểm số hay chữ "giả mạo".

## Lệnh (sau khi khởi tạo)

```bash
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run test
```
