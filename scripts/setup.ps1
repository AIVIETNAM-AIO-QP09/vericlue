# Cài môi trường phát triển VeriClue trên Windows.
# Chạy từ thư mục gốc repo:   ./scripts/setup.ps1
# Chạy lại nhiều lần không sao.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Step "Kiểm tra công cụ"
foreach ($tool in @("git", "uv", "node", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "Thiếu '$tool'. Xem docs/runbooks/dev-setup.md mục 1." -ForegroundColor Red
        exit 1
    }
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Chưa có Docker (cần từ task PLAT-05). Bỏ qua bước này." -ForegroundColor Yellow
}

Step "Cài Python 3.12 và thư viện (uv)"
uv -q python install 3.12
uv sync --all-packages

Step "Cài git hooks (pre-commit)"
uv run pre-commit install

Step "Tạo .env từ .env.example (nếu chưa có)"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Đã tạo .env — nhớ điền giá trị." }
else { Write-Host ".env đã có, giữ nguyên." }

if (Test-Path "apps/web/package.json") {
    Step "Cài thư viện web (npm)"
    Push-Location apps/web; npm install; Pop-Location
}

Step "Kiểm tra nhanh"
uv run ruff check .
uv run python scripts/plan_check.py --board

Write-Host "`nXong. Đọc tiếp: AGENTS.md và docs/status/STATUS.md" -ForegroundColor Green
