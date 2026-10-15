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

## Cổng chất lượng ảnh (CAP-02)

Bước xem trước camera (`framing`) đo từng khung ngay trong trình duyệt và **chưa gửi gì lên máy chủ** cho tới khi đủ `QUALITY_REQUIRED_FRAMES` khung đạt liên tục. Logic thuần ở `src/lib/capture/quality.ts` (số khuôn mặt, oval/IoU, khoảng cách, nghiêng đầu, độ nét, thiếu sáng, **quá sáng**, độ yên); `pickGuidance` chọn **một** chỉ dẫn theo `GUIDANCE_PRIORITY`. Máy trạng thái giữ bộ đếm (`flow.ts`); vòng đo ở `app/verify/useQualityGate.ts` (MediaPipe chạy offline từ `public/mediapipe/`). Chỉ dẫn là chỉ dẫn cục bộ của web, **không** phải `retry_hint` của API (hợp đồng không đổi).

- FPS dưới 15, độ phân giải dưới 640×480 hoặc trình duyệt thiếu `requestVideoFrameCallback`: màn "Thiết bị hoặc trình duyệt chưa đáp ứng", không phải lỗi của người dùng, không gửi gì đi.
- Ngưỡng có số trong tài liệu: 1 mặt, IoU ≥ 0,6, nghiêng ≤ 20°, mặt chiếm 35–60% chiều rộng, ≥ 15 fps, ≥ 640×480. Các ngưỡng còn lại là **TẠM** (ghi `TẠM — chỉnh khi thử máy thật` cạnh từng hằng số).
- Thử: `npm run dev`, mở `/verify`, đi qua màn đồng ý; che bớt đèn để thấy "Ra chỗ sáng hơn", chiếu đèn pin sát mặt để thấy "Tránh nắng chiếu thẳng vào mặt".

## Bài thử trình duyệt thật (Playwright)

Test Vitest chạy trong Node, không có DOM, camera hay React thật nên **không bắt được lỗi nối giao diện** (một lỗi so sánh trạng thái từng làm luồng kẹt ở bước xin camera mà mọi test đơn vị vẫn xanh). Vì vậy có bài thử tự động trên Chromium thật, dùng camera giả:

```bash
cd apps/web
npm ci
npx playwright install chromium             # lần đầu (khoảng 150 MB, lưu ngoài repo)
uv run python ../../scripts/fetch_web_assets.py   # MediaPipe offline (nếu chưa có)
npm run test:e2e
```

- Tự khởi động **API mock** (cổng 8002, SQLite tạm trong thư mục tạm, chạy migration; không cần Docker hay PostgreSQL) và **web dev** (cổng 3202), không tranh cổng 3000/8000/5432. Cần `uv` và Node như khi phát triển.
- Chromium chạy với `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`: tự cấp camera, hình giả không có khuôn mặt nên cổng chất lượng báo "chưa thấy mặt" (không thể vượt cổng bằng camera giả). Bài thử kiểm: đồng ý không tích sẵn; camera được cấp và **không kẹt** ở bước xin camera; xin camera đúng một lần dù React StrictMode chạy effect hai lần; bị từ chối rồi thử lại; trình duyệt thiếu `requestVideoFrameCallback` ra màn "thiết bị chưa đáp ứng"; màn người dân không lộ điểm số.
- Không có dev server `next dev` nào khác đang chạy trong `apps/web` (Next khóa thư mục `.next`). Mất khoảng 1–2 phút (lần đầu lâu hơn do biên dịch).
- **Chưa chạy trong CI** (cần cài trình duyệt và tải mô hình, dễ vượt 3 phút); chạy tay trước khi gộp thay đổi ở `app/verify/` hay `lib/capture/`.

## Luồng /verify (CAP-01)

Máy trạng thái là logic thuần ở `src/lib/capture/flow.ts` (reducer, test bằng Vitest); `runner.ts` gọi API qua `src/lib/api/client.ts` và trả sự kiện cho reducer; `VerifyFlow.tsx` chỉ nối giao diện. Chỉ `status = pass` của API mới thành "xác minh thành công"; mọi lỗi (mạng, 401, 409, 413, 422, 5xx, phản hồi lạ) thành màn hình lỗi.

- **Thử với API mock:** chạy API (`uv run uvicorn vericlue_api.main:app --app-dir services/api/src`) và web (`npm run dev`), mở `http://localhost:3000/verify?scenario=<tên>`. `scenario` chỉ hoạt động khi không phải bản build production. Kịch bản: `genuine` (đạt), `low_quality` (thử lại, 2 lần rồi chuyển duyệt), `voice_clone` (đọc câu rồi chuyển duyệt), `print`/`replay`/`virtual_cam`/`faceswap`/`error` (chuyển duyệt).
- **Test với API thật:** khởi động API mock rồi `E2E_API_URL=http://localhost:8000 npx vitest run src/lib/capture/runner.e2e.test.ts` (CI bỏ qua).
- **Thử trên điện thoại qua IP LAN:** API chỉ cho phép origin `http://localhost:3000` theo mặc định. Đặt `API_CORS_ORIGINS` (phân cách bằng dấu phẩy) trước khi chạy API, ví dụ `API_CORS_ORIGINS=http://localhost:3000,https://192.168.1.23:3000`, và đặt `NEXT_PUBLIC_API_URL` trong `apps/web/.env.local` trỏ tới địa chỉ API mà điện thoại truy cập được (ví dụ `http://192.168.1.23:8000`; trang HTTPS gọi API HTTP có thể bị chặn nội dung hỗn hợp, khi đó chạy API sau một đường hầm HTTPS). Camera cần HTTPS (xem bên dưới).
- **Chỗ giữ chỗ:** `quality_check` (CAP-02), nháy màu chưa lấy mẫu (CAP-04), ảnh gửi lên là ảnh giữ chỗ (CAP-06), đọc câu (CAP-07). Mỗi chỗ có chú thích `TẠM — CAP-0x thay` trong code.

## Trang thử ChromaPulse (CAP-03, nội bộ)

`/lab/chromapulse` thu số liệu phản chiếu màu cho PRES-01. Không gọi API phiên, không lưu ảnh hay khung hình; kết quả là file JSON tải về máy. Bảng màu và nhịp lấy từ `packages/contracts/chromapulse.json` (cùng file với API). MediaPipe chạy offline từ `public/mediapipe/`, chuẩn bị bằng `uv run python scripts/fetch_web_assets.py` (sau `npm ci`). Hướng dẫn thu dữ liệu từng bước: `docs/runbooks/chromapulse-lab.md`.

## Thử trên điện thoại

1. Cùng mạng Wi-Fi với máy tính. Chạy `npm run dev -- -H 0.0.0.0`, mở `http://<IP-máy>:3000` (xem IP bằng `ipconfig`). Cách này đủ để xem giao diện; Windows Firewall có thể hỏi quyền cho Node.
2. **Camera cần HTTPS** (trừ `localhost`). Chọn một trong hai:
   - `npm run dev -- --experimental-https -H 0.0.0.0` rồi mở `https://<IP-máy>:3000` (chấp nhận cảnh báo chứng chỉ);
   - hoặc `cloudflared tunnel --url http://localhost:3000` (hoặc ngrok).

Xem thêm `docs/runbooks/dev-setup.md` §4.
