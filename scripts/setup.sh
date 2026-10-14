#!/usr/bin/env bash
# Cài môi trường phát triển VeriClue trên macOS/Linux (hoặc Git Bash).
# Chạy từ thư mục gốc repo:   bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n==> %s\n' "$1"; }

step "Kiểm tra công cụ"
for tool in git uv node npm; do
  command -v "$tool" >/dev/null || { echo "Thiếu '$tool'. Xem docs/runbooks/dev-setup.md mục 1."; exit 1; }
done
command -v docker >/dev/null || echo "Chưa có Docker (cần từ task PLAT-05)."

step "Cài Python 3.12 và thư viện (uv)"
uv -q python install 3.12
uv sync --all-packages

step "Cài git hooks"
uv run pre-commit install

step "Tạo .env (nếu chưa có)"
[ -f .env ] || { cp .env.example .env; echo "Đã tạo .env — nhớ điền giá trị."; }

if [ -f apps/web/package.json ]; then
  step "Cài thư viện web (npm)"
  (cd apps/web && npm install)
fi

step "Kiểm tra nhanh"
uv run ruff check .
uv run python scripts/plan_check.py --board

echo "Xong. Đọc tiếp: AGENTS.md và docs/status/STATUS.md"
