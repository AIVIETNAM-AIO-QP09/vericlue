# scripts — Script tiện ích

**Phụ trách:** M5 (setup), M3/M4 (dữ liệu, mô hình)

| Script (sẽ có) | Làm gì | Task |
|---|---|---|
| `setup.ps1` / `setup.sh` | Cài Python qua uv, cài thư viện, cài npm, tạo `.env` từ `.env.example` | PLAT-01 |
| `fetch_external.py` | Clone các repo trong `external/repos.yaml` về `external/` | PLAT-01 |
| `download_models.py` | Tải trọng số trong `models/manifest.yaml` về `models/`, kiểm tra SHA-256 | DATA-02 |
| `download_data.py` | Tải bộ dữ liệu công khai theo `docs/data/data-plan.md` | DATA-01 |
| `make_splits.py` | Chia train / calibration / test **theo người** | DATA-03 |
| `synth_vn_deepfakes.py` | Tạo deepfake mặt và giọng người Việt từ nguồn công khai | DATA-04 |
| `compress_variants.py` | Tạo 3 mức nén kiểu mạng xã hội bằng ffmpeg | DATA-05 |
| `gen_keys.py` | Sinh khóa ký token và khóa Ed25519 ký báo cáo | PLAT-06 |

**Quy tắc:**
- Script phải chạy được trên cả Windows và Linux. Ưu tiên viết bằng Python, chạy bằng `uv run python scripts/...`.
- Có `--help`.
- Chạy lại nhiều lần không hỏng gì (idempotent).
