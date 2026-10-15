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
$env:DATA_DIR = 'E:\shared\vericlue\data'
uv run --group data python scripts/download_data.py --dry-run
uv run --group data python scripts/download_data.py --only vn_celeb_faces vivos --subset small
```

`DATA_DIR` mặc định `./data`, đường dẫn tương đối tính từ gốc worktree; biến môi
trường ưu tiên hơn `.env`. Mọi worktree nên trỏ cùng kho để chạy lại không tải trùng.
Mặc định `--subset small`, seed 42, ngân sách toàn danh mục 28,6 GB gồm
archive/cache. Trước media download, script in tổng và kiểm tra ổ đích phải còn
ít nhất 10 GB sau tải; kiểm tra lại khi giải nén. `--subset full` tính byte nguồn,
chi phí giải nén được tính thêm trong adapter; luôn kiểm tra dung lượng ổ đích trước tải.
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
small chạy hết trong một đêm, tải tiếp được sau ngắt, tổng <30 GB sau khi chạy đủ danh mục và xem cả các bộ bị bỏ qua.


Review DATA-01 ngày 15/10: FAS-VN small = full, một gói ZIP dataset ghim phiên bản,
không tải 11.376 request file lẻ; giữ ZIP gốc để tránh nhân đôi dung lượng.
ViSpoofDB dự phòng small 2,6 GB. ViCocktail/WildDeepfake được duyệt chọn theo
shard/archive; `index.csv` cạnh SOURCE ghi từng clip/frame, video nguồn, speaker
nếu nguồn có (rỗng khi chưa biết), cùng archive/member để DATA-03 nối nhóm.
Wild ghi kết quả kiểm tra video xuất hiện xuyên archive, chỉ trong phạm vi đã tải.

Tiêu chí small: chạy hết trong một đêm, tải tiếp được sau ngắt, tổng <30 GB;
ghi tốc độ MB/s và thời gian thực. Báo cáo/log tách `network_seconds` (HTTP có
hoạt động, không cộng trùng request song song), `processing_seconds` (phần còn
lại: hash/index/giải nén/ghi file), `network_bytes` và `network_mbps` (MB thập phân/s).
Lượng byte Range ViMD truyền qua mạng có thể lớn hơn WAV giữ trên đĩa; không có
cache parquet trên đĩa. Small giữ toàn bộ clip của tối đa bốn người mỗi miền, output
bị giới hạn và xác minh trước khi ghi. Giọng thật ViSpoofDB có nguồn VIVOS:
DATA-03 phải nối danh tính xuyên hai bộ để chống rò rỉ người nói.
CelebA/LAV-DF hiện luôn báo skipped; LAV-DF còn cần triển khai cho đánh giá khớp môi S2.

Kích thước HEAD được checkpoint trong `$DATA_DIR/.metadata/head_sizes.json` (24 giờ),
chỉ lưu hash URL/kích thước/thời điểm, không lưu token hoặc URL ký. HTTP 5xx và
ngắt luồng tải được retry tối đa ba lần; .part vẫn giữ để chạy lại khi hết retry.
Bộ đếm byte không gồm metadata HTTP nội bộ gdown; thời gian discovery gdown
được tính vào phần mạng, cùng một ít thời gian parse HTML bên trong thư viện.

### Sửa metadata MLAAD-vi và VSASV (16/10)

MLAAD giữ các WAV có `original_file` hợp lệ, nhóm câu nguồn xuyên TTS; thiếu một
phần metadata không làm bỏ cả bộ. SOURCE ghi số file bị bỏ theo lý do/hệ TTS.
`reference_speaker` giữ đường dẫn gốc, không được coi là subject ID tự tạo.

VSASV có `label` là **ID người**, `utt_type` mới là loại mẫu. Adapter riêng chỉ
lấy bonafide/replay và giữ nguyên nhóm người qua mọi shard; VC/AA bị loại vì thiếu
mapping người nguồn (quyết định trưởng nhóm 16/10), kể cả khi chạy full. Manifest
đổi `label` thành 0=thật/1=phát lại, giữ `source_label`, `subject_id`, `source_group`
là ID công bố; không dùng tên shard làm ID người. WAV IEEE float32 giữ nguyên
sampling rate và giá trị trong độ chính xác float32, không resample/clipping.

Prepare đọc đúng footer và các cột metadata qua HTTP Range, không đọc audio.
Sau preflight, execute chỉ đọc các rowgroup cần thiết, giữ waveform trong Arrow
và đổi từng mẫu được chọn sang NumPy; không tạo danh sách Python cho cả shard.
Biên nhận identity/SHA-256 cho từng WAV giúp bỏ qua audio đã xác minh khi chạy lại;
file hỏng được tạo lại. Không cache Parquet trên đĩa; metadata vẫn được khảo sát lại.

```powershell
$env:DATA_DIR = 'E:\shared\vericlue\data'
uv run --group data python scripts/download_data.py --only mlaad_vi --subset small
uv run --group data python scripts/download_data.py --only vsasv --subset small
```

Dùng HF_TOKEN đã chấp nhận điều khoản hai bộ; không ghi token trong lệnh literal,
log, SOURCE hoặc bàn giao. DATA-03 phải đối chiếu người xuyên bộ qua reference
MLAAD và VSASV ↔ VIVOS/ViMD; không mặc định ID namespace khác nhau là người khác.
