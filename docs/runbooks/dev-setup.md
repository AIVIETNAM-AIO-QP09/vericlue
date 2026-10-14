# Cài đặt môi trường phát triển

> Phần công cụ (PLAT-01) **đã chạy được**. Phần chạy web, API, cơ sở dữ liệu sẽ có sau PLAT-02…05.

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

## 3. Chạy hằng ngày (sau PLAT-03…05)

```powershell
docker compose up -d db                                                        # PostgreSQL
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
