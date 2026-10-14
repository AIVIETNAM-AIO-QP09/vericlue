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


## Tải dữ liệu công khai (DATA-01)

Cài nhóm tùy chọn `data` (không thuộc phụ thuộc chính API/ml):

```powershell
uv sync --all-packages --group data
$env:DATA_DIR = 'D:\Projects\vericlue-store\data'
uv run --group data python scripts/download_data.py --dry-run
uv run --group data python scripts/download_data.py --only vn_celeb_faces vivos --subset small
```

`DATA_DIR` mặc định `./data`, đường dẫn tương đối tính từ gốc worktree; biến môi
trường ưu tiên hơn `.env`. Mọi worktree nên trỏ cùng kho để chạy lại không tải trùng.
Mặc định `--subset small`, seed 42, ngân sách toàn danh mục 28,4 GB gồm
archive/cache. Trước media download, script in tổng và kiểm tra ổ đích phải còn
ít nhất 10 GB sau tải; kiểm tra lại khi giải nén. `--subset full` tính byte nguồn,
chi phí giải nén được tính thêm trong adapter; ổ khoảng 119 GB không đủ full.
`--only` nhận một hoặc nhiều tên. Dry-run chỉ in danh mục/ngân sách, không tạo file,
không gọi mạng; byte thực và danh sách chọn được ghi khi chạy thật.

Sau khi có quyền truy cập, đặt credentials trong PowerShell (nhập khóa được che):

```powershell
$env:KAGGLE_USERNAME = Read-Host 'Kaggle username'
$env:KAGGLE_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Kaggle API key' -AsSecureString)).Password
$env:HF_TOKEN = [System.Net.NetworkCredential]::new('', (Read-Host 'HF Read token' -AsSecureString)).Password
uv run --group data python scripts/download_data.py --only zalo2022 fas_vn rtfs10k mlaad_vi vsasv lavdf --subset small
uv run --group data python scripts/download_data.py --subset small
```

Kaggle: tạo API credentials tại <https://www.kaggle.com/settings/account>;
có thể dùng `~/.kaggle/kaggle.json` hoặc `$env:KAGGLE_CONFIG_DIR` thay hai biến.
HF: token Read tại <https://huggingface.co/settings/tokens>, đồng ý điều khoản trên
trang MLAAD/VSASV/LAV-DF bằng tài khoản đó trước khi chạy. Drive dùng `gdown`,
không cần khóa API; quota hoặc yêu cầu cookie sẽ được báo và bỏ qua riêng bộ.
Không chép token vào lệnh literal, SOURCE.md hoặc file tracked.

File `.part` có identity của nguồn để tải tiếp an toàn; file đủ byte được bỏ qua,
checksum được kiểm tra khi nguồn công bố hoặc khi đã có biên nhận SHA-256.
Server bỏ Range thì download thường bắt đầu lại; đọc chọn lọc Range sẽ từ chối
ngay, không âm thầm tải full. Không thay đổi/di chuyển `.part.json` khi muốn resume.

Mỗi bộ có `raw/<tên>/SOURCE.md`: nguồn, revision, ngày giờ Việt Nam, giấy phép,
seed, nhóm nguồn, danh sách/số byte file, trạng thái complete/skipped/error.
Archive lưu nguyên vẹn vẫn là dữ liệu gốc; không coi số archive là số mẫu.
ViMD giữ trọn người nói và số người bằng nhau ba miền; MLAAD giữ nhóm câu nguồn
xuyên hệ TTS; RTFS giữ video gốc và fake liên quan. Metadata không có identity thì
không tự tạo subject_id. DATA-03 phải nối danh tính trước chia theo người.

CelebA-Spoof/LAV-DF small chỉ khả dụng khi xác minh HTTP Range và mapping người/
video nguồn; nếu chưa đủ điều kiện, script báo skipped và không tải full thay thế.
Bộ chưa rõ giấy phép vẫn dùng nghiên cứu; không phân phối lại. ViMD ND không
phân phối bản phái sinh, gồm các biến thể nén của DATA-05.

Mã thoát: `0` hoàn thành lựa chọn/dry-run; `2` có bộ skipped; `1` có lỗi.
Thiếu token không chặn những bộ khác và không được coi là hoàn thành danh mục.
Báo cáo thực chạy nằm ở `$DATA_DIR/runs/*.json`, gồm commit, seed, thời gian,
số byte lưu (kể cả cache), revision và outcome từng bộ. Chỉ xác nhận tiêu chí
small <30 phút/<30 GB sau khi chạy đủ danh mục và xem cả các bộ bị bỏ qua.
