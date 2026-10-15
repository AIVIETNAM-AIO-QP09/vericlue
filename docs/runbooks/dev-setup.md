# Cài đặt môi trường phát triển

> PLAT-05: chạy web/API/PostgreSQL bằng Docker Compose; mặc định dùng mock, không cần GPU/trọng số.

## 1. Cài một lần trên máy

| Công cụ | Cách cài (Windows) | Kiểm tra |
|---|---|---|
| Git | https://git-scm.com | `git --version` |
| uv (quản lý Python) | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `uv --version` |
| Node.js ≥ 20 | https://nodejs.org (LTS) | `node --version` |
| Docker Desktop | https://www.docker.com/products/docker-desktop | `docker --version` |
| VS Code | https://code.visualstudio.com, mở repo rồi cài các extension được gợi ý | |

Python **không cần cài riêng**: `uv` tự cài Python 3.12.

## 2. Lấy code và cài đặt

```powershell
git clone <url-repo> Data4Life
cd Data4Life
./scripts/setup.ps1                       # cài Python 3.12, thư viện, git hooks, tạo .env
uv run python scripts/fetch_external.py   # clone repo phụ cần thiết (khi làm task mô hình)
```

Kiểm tra cài đặt thành công:

```powershell
uv run pytest                             # các test đều xanh
uv run python scripts/plan_check.py       # in bảng trạng thái, "0 lỗi"
```

Nếu PowerShell chặn chạy script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, rồi chạy lại.

## 3. Chạy hằng ngày (native API/web)

```powershell
docker compose up -d db                                                        # PostgreSQL
uv run alembic -c services/api/alembic.ini upgrade head                       # DB trống cần migration
uv run uvicorn vericlue_api.main:app --reload --app-dir services/api/src       # API :8000
cd apps/web; npm run dev                                                       # Web :3000
```

Mặc định `USE_MOCK_MODELS=true`: chạy được ngay, chưa cần tải mô hình.

## 4. Thử trên điện thoại

Camera trên trình duyệt điện thoại **bắt buộc HTTPS**. Chọn một trong hai cách:
- `npm run dev -- --experimental-https -H 0.0.0.0` rồi mở `https://<IP-máy>:3000` (chấp nhận cảnh báo chứng chỉ);
- hoặc tạo tunnel bằng `cloudflared tunnel --url http://localhost:3000`.

## 5. Lỗi thường gặp

| Lỗi | Cách sửa |
|---|---|
| `python` không tìm thấy | Dùng `uv run python …`, không gọi `python` trực tiếp |
| `make` không có | Repo không dùng `make`; dùng script trong `scripts/` |
| Camera không mở trên điện thoại | Kiểm tra đang dùng HTTPS |
| Xuống dòng CRLF làm lệch diff | Repo đã có `.gitattributes`; chạy `git add --renormalize .` một lần |


## 6. Docker Compose (PLAT-05, Windows + Docker Desktop)

Mở PowerShell **tại worktree của mình**, ví dụ `D:\Projects\vericlue-codex`.
Docker Desktop phải đang chạy Linux containers; kiểm `docker info` trước.

1. Tạo `.env` từ `.env.example` nếu chưa có. Điền mật khẩu DB riêng trong `.env`,
   không commit hoặc đưa file này vào build. `DATABASE_URL` cho lệnh native dùng
   `127.0.0.1:5432` (khớp binding IPv4); Compose truyền các trường DB riêng, API dùng SQLAlchemy URL.create để encode mật khẩu đúng và dùng hostname `db`.
   Nếu mật khẩu có ký tự đặc biệt của URL, percent-encode khi điền `DATABASE_URL`;
   Compose tự encode các ký tự đặc biệt từ POSTGRES_PASSWORD; ví dụ demo vẫn nên dùng chuỗi ngẫu nhiên URL-safe. Đổi mật khẩu env không tự đổi
   mật khẩu trong volume PostgreSQL đã khởi tạo.
2. Đặt `MODELS_DIR`, `DATA_DIR`, `MEDIA_DIR` là đường dẫn host. Windows nên dùng
   dạng `D:/Projects/vericlue-store/models`, `.../data`, `.../media`. Model/data
   chỉ đọc; media ghi được. Linux cần cấp quyền ghi thư mục media cho UID10001
   của API; Docker Desktop quản lý chia sẻ đường dẫn Windows.
3. Chạy các lệnh từ gốc worktree:

```powershell
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
uv run python scripts/smoke_compose.py --restart-api
```

Kết quả mong đợi: db/api/web healthy; web `http://localhost:3000`, API
`http://localhost:8000/docs`. Migration chạy trước Uvicorn. Smoke tạo phiên genuine,
upload bytes giả, gửi signals, finalize pass, kiểm sessions/module_results/decisions
trong PostgreSQL, restart API rồi xác minh token/trạng thái còn; báo cáo tại
`tmp/plat-05-smoke.json`, không chứa token/mật khẩu. Script yêu cầu mock bật và
`DATABASE_URL` trong `.env` truy cập được từ host.

Dừng bằng `docker compose down` (giữ volume DB); không xóa volume DB khi cần giữ
phiên/kết quả. `docker compose logs api` có log startup và audit dọn file.
Giám định mặc định **không tự xóa** (`FORENSIC_TTL_DAYS=`); xem chính sách trong README API.

### MediaPipe và nội dung image

Không model/dataset/media/.env nào được đưa vào build context/image. Dockerfile
web chỉ chứa standalone app; `public/mediapipe` được mount read-only từ
`WEB_ASSETS_DIR` trên host. Chuẩn bị assets theo CAP-03 trước khi dùng camera lab:
`npm.cmd --prefix apps/web ci`, `uv run python scripts/fetch_web_assets.py`, rồi
`uv run python scripts/fetch_web_assets.py --check`. Trên Linux dùng `npm`.
Mặc định assets ở `apps/web/public/mediapipe` (ignored); không tải model trong Docker build.
Chưa chuẩn bị assets thì web/mock API vẫn khởi động, nhưng không thể chạy MediaPipe lab.
Bản smoke HTTP không chứng minh camera trên điện thoại đã hoạt động; điện thoại cần HTTPS.

`NEXT_PUBLIC_API_URL` được chốt lúc build web. Dùng URL trình duyệt truy cập được
(localhost trên cùng máy hoặc địa chỉ LAN/HTTPS), không dùng hostname nội bộ `api`.
Nếu đổi URL, rebuild web. API image copy `chromapulse.json` và đặt đường dẫn tuyệt đối;
kiểm container khởi động là một phần nghiệm thu, không chỉ build thành công.
