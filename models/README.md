# models — Trọng số mô hình (KHÔNG commit)

Tải bằng `uv run python scripts/download_models.py` từ `models/manifest.yaml`
(DATA-02). Script không cài thư viện inference, không chạy mô hình và không chép
remote Python code vào sản phẩm. FACE/VOICE/FOR tiếp tục viết wrapper riêng.

## MODELS_DIR dùng chung

Script đọc biến môi trường **MODELS_DIR**, mặc định `./models`. Đường dẫn tương
đối được tính từ gốc checkout, không phụ thuộc thư mục đang đứng. Không cần sửa
`.env.example` hay dependency chung. PowerShell, máy nhóm này:

```powershell
$env:MODELS_DIR = 'D:\Projects\vericlue-store\models'
uv run python scripts/download_models.py
uv run python scripts/download_models.py --only minifasnet
uv run python scripts/download_models.py --verify
```

Bash: `export MODELS_DIR=/path/to/vericlue-store/models`. Mỗi checkout/worktree
đọc manifest riêng nhưng dùng chung weights; **không chạy hai downloader cùng
lúc ghi cùng model/file**. Biến trong `.env` chỉ có tác dụng khi được nạp vào môi
trường shell; downloader dùng `os.environ`, không tự sửa/nạp `.env` hay token.
Từ phiên sau mở Codex ngay tại `D:\Projects\vericlue-codex`.

Mỗi artifact lưu ở `MODELS_DIR/<id>/<path>` trong manifest. Trọng số, tokenizer,
config tải về đều không được commit. `.gitignore` giữ ngoại lệ duy nhất trong
`models/` là README và manifest; khi dùng store ngoài checkout, weights hoàn toàn
nằm ngoài cây Git. Bản tinh chỉnh riêng lưu dưới store `finetuned/<tên>/<ngày>/`
kèm card về dữ liệu/siêu tham số/kết quả/commit, không commit weights.

## Tải và kiểm toàn vẹn

- `--only NAME`: đúng id manifest, chỉ tải một mục, không tự tải dependencies.
  Tên sai trả mã khác 0. GenD cần thêm `clip-vit-large-patch14` và `scrfd-10g`; chạy
  mặc định tải cả các mục ready để chuẩn bị offline.
- `--verify`: chỉ đọc/hash local, không tải mạng, không điền checksum chưa có,
  không thay manifest. Thiếu file/hash, size sai hoặc SHA-256 lệch đều trả mã khác 0.
- `--manifest PATH`: cấu hình manifest riêng, dùng trong test/checkout khác.
- `--report PATH`: JSON thống kê lượt chạy thành công (bytes thực qua response,
  bytes các file hoàn chỉnh, thời gian tường); output nên ở store/gitignored.

Manifest ghi nguồn HF + **commit đầy đủ**, giấy phép kèm link/phạm vi, kích thước
**mỗi file**. `upstream_sha256` là hash LFS đã công bố nếu có; `sha256` là hash
đã đo bằng byte thực sau lần tải đủ. Git blob SHA-1 không được dùng làm SHA-256.
Script đối chiếu upstream hash ngay lần đầu nếu có. Không có checksum local thì
không tự tin file có sẵn là đúng: tải lại từ nguồn đã ghim. Đã có checksum thì
file hiện có phải đúng size/hash, sai báo lỗi, **không tự đổi hash hay ghi đè để
hợp thức hóa sai lệch**.

Tải streaming vào `.part`, kiểm Content-Length/size/SHA rồi atomic replace file;
manifest được ghi atomic sau mỗi file hoàn chỉnh. Bị ngắt thì chạy lại cùng lệnh:
file hoàn chỉnh/hash đã ghi được bỏ qua, file dở tải lại. Đây là tiếp tục **giữa
các file**, không hứa resume từng byte. Không chạy song song hai lệnh cùng target.
HTTP thật dùng HTTPS; HTTP loopback chỉ dành server test. Không giải nén archive
hay execute nội dung model; HTML/Drive login/confirmation bị từ chối, không lưu
nhầm làm weights và không ghi checksum cho trang lỗi.

## Nguồn và giấy phép

Xem đầy đủ file/revision/bytes/hash tại manifest. Các mục ready gồm MiniFASNet V2,
GenD CLIP L/14, AntiDeepfake MMS300M, PhoWhisper-small, stable_syncnet, SCRFD,
CTC aligner, AudioSeal detector và dependency CLIP nền.

- **MiniFASNet V2:** weights Apache-2.0 từ UniFace HF; code UniFace MIT là giấy
  phép khác. Không tải mọi model trong snapshot UniFace.
- **SCRFD:** nguồn UniFace `scrfd_10g.onnx`, lưu tên **det_10g.onnx**. Đã đối chiếu
  byte SHA-256 với entry chính thức buffalo_l InsightFace v0.7 và artifact GenD
  ghim: `5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91`,
  16.923.827 bytes. Giữ đúng tiền xử lý GenD ở FACE-02; không đổi detector vì tên
  class upstream là RetinaFace. Weights chỉ **nghiên cứu phi thương mại**.
- **stable_syncnet:** weights **OpenRAIL++**, không gán giấy phép Apache-2.0 của
  code LatentSync sang weights. Trưởng nhóm 15/10 chốt được dùng cho mục đích nhóm;
  vẫn phải tuân thủ hạn chế mục đích có hại của nguồn.
- **AntiDeepfake:** weights CC-BY-NC-SA-4.0, code BSD-3. **CTC:** weights CC-BY-NC-4.0,
  code BSD-2. Giữ mục đích nghiên cứu phi thương mại, trích dẫn và điều kiện nguồn.
- **PhoWhisper:** model card BSD-3-Clause. **AudioSeal detector:** model card MIT;
  chỉ tải detector_base, không tải generator không cần thiết.
- **CLIP nền:** ghi MIT theo nguồn repo/software `openai/CLIP` kèm link LICENSE
  đã pin trong manifest. Model card HF không công bố riêng license weights;
  giữ rõ phạm vi bằng chứng và quyết định trưởng nhóm 15/10 không chặn. GenD dùng
  backbone/processor này; downloader không xác nhận inference offline hay sửa
  wrapper, FACE-02 phải chọn đường dẫn local và cấm tự tải ngoài snapshot đã ghim.
- **PerTh:** `blocked`, **chờ xác minh quyền trọng số — FOR-03**, không tải.

Mục ready phải có giấy phép đã xác minh hoặc phạm vi nghiên cứu được chốt và
nguồn cụ thể; unknown/pending/GPL-family bị từ chối trước request. Chạy mặc định
báo rõ rồi bỏ qua SBI/PerTh theo ngoại lệ trưởng nhóm, không bỏ qua lỗi ở mục
ready. Chọn đích danh PerTh vẫn trả mã khác 0. Không coi license thư viện pip là
đương nhiên license mọi checkpoint ngoài thư viện.

## SBI: nguồn gốc, không mirror

**Không mirror SBI (điều khoản hạn chế chia sẻ) — mỗi máy tải từ nguồn gốc;
quyết định trưởng nhóm 15/10.** Private Hugging Face vẫn là phân phối lại, nên
không tạo repo/mirror/upload/token cho bước này.

1. Đọc README/LICENSE của SelfBlendedImages tại commit được ghi trong manifest;
   chỉ dùng đúng phạm vi nghiên cứu nội bộ phi thương mại.
2. Lấy link **FFc23.tar** từ README gốc: Drive file
   `1X0-NYT8KPursLZZdxduRQju6E52hauV0`, không dùng link mirror.
3. Có thể thử `uv run python scripts/download_models.py --only sbi-ffc23`.
   Nếu Drive trả trang HTML/quota/confirmation thì script báo lỗi rõ, không
   gán hash cho HTML; mỗi máy dùng trình duyệt tải từ chính link nguồn và FACE-03
   xác minh nội dung/size/hash trước dùng.
4. File Drive ID có thể bị thay nội dung; hiện **chưa pin revision/size/hash**.
   Mục SBI `deferred`, không tải mặc định, không chặn DATA-02 theo quyết định
   trưởng nhóm. Nếu script lấy được binary đủ từ nguồn gốc, nó ghi size/SHA-256
   thực; revision Drive vẫn ghi chưa pin nếu chưa có chứng cứ bất biến.
5. Không tự điền hash từ file thủ công chưa xác minh. FACE-03 ghi nguồn/ngày/hash
   thực và theo dõi riêng điều kiện tải/giấy phép; không sao chép sang HF kể cả private.

Tiêu chí DATA-02 tải đủ gồm 8 model ready và CLIP nền; SBI theo dõi FACE-03,
PerTh theo dõi FOR-03. Không diễn giải downloader thành đã thử inference thật.
