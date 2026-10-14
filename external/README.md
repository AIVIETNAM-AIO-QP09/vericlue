# external — Repo bên ngoài cần clone để chạy (KHÔNG commit)

Thư mục nằm trong `.gitignore`. Danh sách repo và phiên bản cố định nằm trong `repos.yaml`. Lệnh clone: `uv run python scripts/fetch_external.py` (task PLAT-01).

## Quy tắc

- Chỉ clone những repo **không có gói pip/npm** mà cần code của nó để chạy mô hình hoặc công thức huấn luyện.
- Luôn ghim (pin) một commit cụ thể trong `repos.yaml` để mọi người chạy giống nhau.
- **Không sửa code trong `external/`.** Cần sửa thì viết lớp bọc (wrapper) trong `ml/src/`.
- **Công cụ tấn công (Deep-Live-Cam, FaceFusion, tiện ích giả camera, VieNeu-TTS…) KHÔNG để ở đây.** Chúng chỉ được cài trên máy red-team riêng (xem `docs/runbooks/red-team.md`). Deep-Live-Cam dùng giấy phép AGPL.
