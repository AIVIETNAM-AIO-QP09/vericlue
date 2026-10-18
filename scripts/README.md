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
Mặc định `--subset small`, seed 42, ngân sách toàn danh mục 29,9 GB gồm
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

Review PR #17: nhóm `data` khai báo trực tiếp NumPy/SciPy để adapter VSASV chạy
độc lập, không dựa vào dependency gián tiếp của ML. MLAAD kiểm đủ hệ TTS theo
các thư mục có `meta.csv`, không lấy danh sách từ chính records còn hợp lệ.
VSASV SOURCE đo max |x| và số WAV vượt [-1,1] trên file float32 đã lưu; không clipping.

Quy ước byte: `manifest_data_bytes` là tổng size của media được chọn;
`outcomes.<bộ>.stored_bytes` là toàn bộ file trong thư mục bộ đó, gồm SOURCE,
manifest và biên nhận. `stored_bytes` ở đầu báo cáo cộng thêm cache `.metadata`
dùng chung, không phải chỉ media. Dòng “Số byte lưu” trong SOURCE gồm media,
metadata/archive và manifest, loại SOURCE.md, biên nhận `.verified.json` và file part.

## Chia tập âm thanh local (DATA-03)

```powershell
uv sync --all-packages --group data
$env:DATA_DIR = 'E:\shared\vericlue\data'
uv run --group data python scripts/make_splits.py --seed 42 --audit-hashes
```

Script cần `raw/<bộ>/selected_manifest.json` và audio của MLAAD-vi, VSASV,
ViMD, VIVOS, ViSpoofDB đã tải. Không gọi mạng, không decode/chỉnh audio.
`DATA_DIR` đọc từ môi trường rồi `.env`, mặc định `./data` tính từ gốc worktree;
`--data-dir` ưu tiên cao nhất. Thiếu dotenv khi có `.env` sẽ cảnh báo rõ.
Chạy lại ghi cùng 20 CSV và `splits/SUMMARY.md` khi input/seed/commit không đổi;
đường dẫn audio trong CSV tương đối với DATA_DIR: `raw/<bộ>/...`, UTF-8,
nhãn `0` thật / `1` giả. Thành viên ghép `Path(DATA_DIR) / row["path"]` khi đọc;
validate và audit hash cũng ghép như vậy, từ chối absolute/traversal và file thiếu.
Ngoài cột task card có `source_group`, `reference_group`, `tts`, `group_id` để
kiểm toán liên kết; hai cột group không phải ID người. `subject_id` trống khi
nguồn không công bố. Không commit CSV/SUMMARY/audio; chỉ chép thống kê bàn giao.

ViSpoofDB + VIVOS giữ test-only do bằng chứng chung nguồn. VSASV/ViMD **giả định
độc lập**, không phải đã chứng minh khác người xuyên bộ (quyết định trưởng nhóm
16/10). ViMD small giữ một người mỗi miền trong mỗi tập. MLAAD nối câu nguồn
và giọng tham chiếu; mẫu thiếu reference chỉ nhóm theo câu nguồn, không gom
vixTTS. Mục tiêu nhóm train/fit/LTT/test 60/10/10/20; phân tầng TTS theo nhóm,
nhóm lớn ưu tiên train nên tỷ lệ mẫu có thể lệch lớn. Không hứa test TTS chưa thấy.
Mọi loại tấn công chính thiếu 60 LTT được dồn nguyên component từ train;
nhóm nhỏ ưu tiên, hòa chọn bằng seed 42, không lấy test/calib_fit. Sau đó fit
thiếu 100 mẫu/lớp được dồn từ train theo cùng quy tắc, không lấy test/LTT.
Giữ nguyên người ViMD để không phá cân bằng miền; component liên kết chứa
ViMD cũng không được dồn. Chỉ báo thiếu sau khi đã thử các nhóm train hợp lệ.
Tỷ lệ calib thực tế theo mẫu/người ghi trong SUMMARY, không chỉ tỷ lệ nhóm:
ViMD 50% số người; VSASV ban đầu 25% người, có thể tăng sau dồn quota fit/LTT.

**Rủi ro cho VOICE-01/03:** vixTTS thiếu reference có thể dùng chung giọng mặc
định, nên nhóm theo câu nguồn có thể để cùng giọng tổng hợp qua cả bốn tập.
Test MLAAD chỉ có vixTTS; bốn TTS còn lại đều ở train. Không coi đây là test
hệ TTS chưa thấy hay bằng chứng độc lập người nói đã xác minh.
Quota là số đếm báo cáo, không phải chứng nhận chất lượng/độc lập. Thiếu quota
không làm mã thoát lỗi và không đánh dấu đạt task; đọc SUMMARY trước khi dùng.

Khi có đối chiếu danh tính **đã xác minh**, cung cấp CSV local qua
`--identity-links <file.csv>` với cột `source,kind,identity,canonical_id`.
`kind` là `subject_id` hoặc `reference_group`; các dòng chung `canonical_id`
liên kết cùng người/nhóm nguồn. `identity` phải khớp nguyên giá trị metadata.
Toàn component theo cùng tập; có VIVOS/ViSpoofDB thì bắt buộc test, còn lại theo
đa số mẫu của assignment ban đầu. Liên kết thật ưu tiên tỷ lệ/cân bằng miền.
SOURCE chưa có crosswalk MLAAD tới bộ Việt; không tự suy người từ tên đường dẫn.
`--audit-hashes` lọc size rồi SHA-256, ghi số file/byte đã hash và số mẫu trùng
ViSpoofDB; phát hiện audio trùng byte ở tập khác test sẽ dừng để bổ sung crosswalk.
Hash bằng 0 không chứng minh khác người: có thể đổi định dạng/cắt audio.

Mã thoát `0`: đã xuất split và cảnh báo quota; `1`: metadata/file/nhóm không hợp lệ.
Các quota còn thiếu được ghi trong bàn giao và SUMMARY; xem luồng ảnh bên dưới.

## Chia tập ảnh local (DATA-03)

```powershell
uv sync --all-packages --group data --group data-image
$env:DATA_DIR = 'D:\Projects\vericlue-store\data'
$env:MODELS_DIR = 'D:\Projects\vericlue-store\models'
uv run python scripts/download_models.py --only arcface-mnet
uv run --group data --group data-image python scripts/make_splits.py --only zalo2022
uv run --group data --group data-image python scripts/make_splits.py --only wilddeepfake
uv run --group data --group data-image python scripts/make_splits.py --only rtfs10k vicocktail vn_celeb_faces
uv run python scripts/audit_image_splits.py --data-dir $env:DATA_DIR
```

`--only` chọn bộ ảnh; không truyền vẫn chạy năm bộ âm thanh như trước.
`--models-dir` ưu tiên hơn MODELS_DIR. `zalo2022` và `fas_vn` phải xử lý cùng
nhau để giữ mọi liên kết xuyên bộ ở test; `vicocktail` và `vn_celeb_faces` cũng
chạy cùng nhau. Không tải mạng trong bước chia tập. Cần weights ArcFace/SCRFD
đúng SHA-256 manifest. Loader dùng ONNX trực tiếp, tiền xử lý tham chiếu UniFace
4.0.0 (MIT, ghi nhận tại third_party/); không import UniFace/SciPy. Trọng số
ArcFace chỉ dùng nghiên cứu phi thương mại.

- **Zalo:** nhãn gốc `liveness_score=1` là thật (`label=0`), `0` là giả (`label=1`).
  Lấy 3 khung ở 15/50/85% mỗi video, SCRFD tìm mọi mặt, ArcFace căn chỉnh và
  chuẩn hóa embedding. Union mọi cặp cosine ≥0,30; nếu component lớn nhất chứa
  >30% video Zalo thì thử 0,35/0,40/0,45/0,50/0,55/0,60 theo thứ tự và báo mọi
  lần thử. Nếu vẫn lớn thì giữ nguyên component, báo `oversized_after_tightening`;
  không tách nhóm để ép tỷ lệ. Chỉ xem phân bố component, không xem điểm PAD/GenD hoặc
  kết quả test để chọn ngưỡng. Component liên kết FAS hoặc video không tìm được
  mặt buộc test. Các nhóm còn lại chia 60/10/10/20 theo nhóm, rồi dồn nguyên nhóm
  train cho LTT ≥60/attack và fit ≥100/lớp. `subject_id` luôn trống; nhóm tự động
  có thể bỏ sót cùng người, không coi là danh tính đã xác minh.
  Video lỗi mở/đếm khung hoặc lỗi ở bất kỳ khung lấy mẫu nào bị bỏ toàn bộ
  embedding của video và buộc test; SUMMARY ghi path/lý do lỗi decode.
- **FAS-VN:** lấy nhãn thư mục live/not_live, không suy từ chữ trong filename.
  Lọc ứng viên trùng bằng CRC/size rồi xác nhận SHA-256; mọi bản trùng byte
  mang nhãn đối lập bị cách ly khỏi CSV. Báo danh sách/path/hash/lý do trong
  SUMMARY. Phần hợp lệ chỉ test. ZIP gốc được giữ nguyên.
- **WildDeepfake (ADR-0012):** dùng `video_groups.jsonl`, union `video_origin_id`
  xuyên archive. Không train. Dành nguyên nhóm cho LTT ≥60/lớp rồi fit ≥100/lớp,
  mục tiêu khoảng 10% nhóm mỗi phần; phần chưa gán mới được chốt thành test.
  Có thể vượt quota do không bẻ nhóm. Subject chưa có để trống; cùng người ở
  video khác vẫn là rủi ro. Quota khung không tương đương video/người độc lập.
  Khi LTT đã đạt tối thiểu, không dồn thêm nhóm chỉ để đạt tỷ lệ nếu làm fit
  còn dưới 100 mẫu/lớp.
  Nếu lựa chọn ban đầu vẫn làm fit thiếu dù cả hai quota khả thi, tìm tổ hợp
  nguyên nhóm khác cho LTT để giữ đủ 100 mẫu fit; không đổi cách chọn đã đủ quota.
- **RTFS-10k:** test-only, union video YouTube gốc ∪ ảnh donor xuyên generator.
- **DATA-04:** giữ nguyên mọi clip cùng video gốc ViCocktail và mọi ảnh cùng
  nhãn người vn_celeb; ArcFace union thêm liên kết xuyên hai bộ (0,30).
  Lấy ảnh/clip đầu, giữa, cuối theo path trong mỗi nhóm; mỗi clip lấy 3 khung.
  Đây là nhóm rủi ro có lấy mẫu, không chứng minh khác người. DATA-04 chỉ ghép
  mặt/video trong **cùng tập** và kế thừa tập của cả hai nguồn; không ghép xuyên tập.

Các media trong archive/Parquet được giải nén dưới `raw/<bộ>/extracted/`,
CSV tham chiếu file thật tương đối DATA_DIR, không dùng đường dẫn `zip::member`.
Cần thêm dung lượng cho media giải nén bên cạnh archive. Không lưu embedding,
không sửa/xóa nguồn gốc. Chạy lại giữ file giải nén có cùng size và xuất CSV
theo seed 42. Summary ảnh riêng `SUMMARY-<bộ>.md` liên kết từ `SUMMARY.md`, giữ
phần âm thanh. Không commit CSV, thống kê local hoặc media.

Audit là script độc lập đọc lại CSV: rò người/nhóm, nhóm toàn cục xuyên bộ,
file trùng, path/label/source, test-only/no-train và quota. Mã thoát 1 nếu có
lỗi; quota bất khả thi chỉ cảnh báo kèm số nhóm train còn lại. Lưu ý: số đếm
đủ không chứng minh điều kiện độc lập của Learn-then-Test.

GPU tùy chọn: `DATA_SPLIT_DEVICE=cuda` yêu cầu ONNX Runtime GPU thực sự khởi
tạo CUDA, lỗi thì dừng; mặc định `cpu`. Dùng **môi trường riêng**, không cài
đồng thời bản CPU và GPU của ONNX Runtime vào cùng môi trường. Theo
[hướng dẫn ONNX Runtime](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html),
cài `onnxruntime-gpu[cuda,cudnn]` và gọi `preload_dlls`; script đã gọi preload khi
chọn CUDA. Bản thực chạy DATA-03 dùng ORT 1.31.0, OpenCV 5.0.0,
NumPy ghi trong SUMMARY. CUDA tắt TF32, dùng deterministic compute; không hứa
bit-identical giữa CPU/GPU hoặc giữa các phiên bản thư viện. CSV/seed cùng môi
trường phải giữ ổn định. CPU dùng một worker, bốn luồng ONNX, OpenCV một luồng.

### Zalo 2022 whole ZIP và phục hồi HTTP 416 (17/10)

Zalo `small = full`: tải **một ZIP toàn dataset**, ghim Kaggle version, không tải
file video/CSV lẻ. Chỉ giải nén `train/train/label.csv` và video được `fname`
tham chiếu; giữ nguyên đường dẫn và `liveness_score` gốc. Test không nhãn và
video không có dòng nhãn không được giải nén. Không suy ID người từ filename.
ZIP gốc giữ trong `.cache/` để resume/xác minh; dữ liệu dùng ở ngoài cache chỉ
là train có nhãn. `selected_manifest.json` liệt kê video/nhãn gốc, không tính
label.csv hay ZIP là mẫu. Giấy phép: MIT theo mirror, điều khoản Zalo gốc chưa rõ;
chỉ nghiên cứu, không phân phối lại.

Preflight tính **ZIP + train giải nén**; ngân sách Zalo 4,8 GB, toàn danh mục small
29,9 GB, vẫn chừa ít nhất 10 GB trống. Archive và file giải nén phải qua kiểm
path traversal, symlink/junction, kiểu file đặc biệt; CRC kiểm cả file đã tồn tại
để sửa bản lỗi dù đủ byte. Không dùng `extractall` trên ZIP chưa kiểm.

```powershell
uv sync --all-packages --group data
$env:DATA_DIR = 'E:\shared\vericlue\data'
uv run --group data python scripts/download_data.py --only zalo2022 --subset small
```

HTTP download chung: nếu `.part` lớn hơn nguồn, bỏ partial và tải từ đầu. Gặp
HTTP 416 cũng bỏ `.part`/biên nhận partial rồi GET mới không Range; tối đa ba
lần, không nối sai hoặc lặp vô hạn. Sau gián đoạn mạng hợp lệ vẫn giữ Range
resume và kiểm kích thước/SHA trước rename. Trước chuyển Zalo từ file lẻ sang ZIP,
xóa riêng `.part`/`.part.json` cũ trong `raw/zalo2022`, không xóa dữ liệu bộ khác.

Dự phòng ViMD small giảm từ 800 xuống 300 MB dựa trên bản đã tải ~63 MB;
không đổi seed, bốn người/miền, không bỏ clip của người được chọn. Giải phóng
0,5 GB dự phòng cho ZIP + train Zalo để tổng small vẫn dưới 30 GB.

Review PR #24: `safe_extract_zip(..., max_total_bytes=...)` giới hạn tổng byte
file được chọn, kể cả file có sẵn; Zalo truyền đúng ngân sách train đã preflight.
Header ZIP vượt trần bị từ chối trước ghi; byte thực được kiểm tiếp trong stream.
Lỗi CRC/zlib/phương thức nén không hỗ trợ trả thông báo giải nén rõ, dọn file tạm
bị lỗi. Đầu lượt tải và đầu giải nén dọn `*.extract.part` thường, từ chối link;
thống kê mẫu bỏ qua các đường dẫn này. `safe_path` cũng chặn tên dành riêng
Windows (CON/NUL/COM...) và dấu chấm/khoảng trắng cuối thành phần đường dẫn.
SOURCE Zalo ghi **Video nguồn** thay cho nhóm người chưa xác minh; hai biên nhận
file lẻ cũ đã được xóa khỏi kho chung, giữ biên nhận ZIP hiện tại.
