# Kiểm parity AntiDeepfake (VOICE-01)

Script này so **logits gốc**, không hiệu chỉnh, học ngưỡng hoặc công bố kết quả
R3. Chỉ `PASS` khi đã chạy cả hai backend trên cùng mọi cửa sổ và sai khác tuyệt
đối lớn nhất không quá **1e-4**. `UNVERIFIED` là **CHƯA kiểm parity**, không phải
đạt, dù kiểm kê checkpoint không thiếu/thừa key hoặc bốn mẫu có chiều điểm hợp lý.

## Hai môi trường tách biệt

- **Runtime VeriClue:** Python 3.12, Transformers/PyTorch và extra voice đã được
  nhóm chốt; không cài/import Fairseq vào runtime, pyproject hoặc uv.lock.
- **Reference ngoại vi:** Linux, Python 3.10, Fairseq 0.12.2 cùng các phụ thuộc của
  upstream (`torch`, `torchaudio`, `safetensors`, `numpy`; `models/W2V.py` còn
  import `models/oc_softmax.py`). Môi trường này do người chạy chuẩn bị riêng,
  không phải dependency của workspace. Script không tự cài package hay gọi mạng.
- Checkout AntiDeepfake **đã chuẩn bị sẵn** phải sạch và đúng commit
  `0dea622bde8f064c8ee5a557f2598643123fc6b6`. Script từ chối branch/commit khác
  hoặc checkout có thay đổi; không tự clone, checkout hay sửa external source.
- Hai Python process chạy trên **cùng máy Linux**, đọc cùng checkpoint/audio và
  script. Không chạy reference Fairseq trên Windows. Dùng Python 3.12 gọi script,
  truyền `--reference-python` tới executable Python 3.10 riêng. Không cài gói
  VeriClue vào Python 3.10; reference process chỉ nhập source upstream.

Fairseq/Python 3.10 vẫn cần kiểm tương thích với phiên bản torch/NumPy trong môi
trường reference; không khẳng định môi trường đã chạy được khi chưa có báo cáo.
Nếu import/load/strict-key check hoặc reference subprocess lỗi, report giữ
`UNVERIFIED`, exit 2. Không sửa dataclass thư viện hay tải checkpoint khác để né lỗi.

## Nguồn và giấy phép

- [Custom model upstream](https://github.com/nii-yamagishilab/AntiDeepfake/blob/0dea622bde8f064c8ee5a557f2598643123fc6b6/models/W2V.py):
  `Model("mms_300m")`, Fairseq features, temporal average pooling, Linear1024→2.
  Reference gọi trực tiếp source external đã pin, **không chép implementation**.
- [LICENSE-CODE](https://github.com/nii-yamagishilab/AntiDeepfake/blob/0dea622bde8f064c8ee5a557f2598643123fc6b6/LICENSE-CODE):
  BSD-3-Clause. Checkpoint có giấy phép riêng
  [CC-BY-NC-SA-4.0](https://huggingface.co/nii-yamagishilab/mms-300m-anti-deepfake/blob/7928e119e09f616b2ce698892e00ca22dbaa40bf/README.md).
- Checkpoint HF revision `7928e119e09f616b2ce698892e00ca22dbaa40bf`, file
  `MODELS_DIR/antideepfake-mms300m/model.safetensors`, SHA-256
  `9bd5d9785bf72f91dfca8508651354946c4b307921cb358505e1b94035102224`.
  Script đọc/hash, không tải, chuyển đổi trên đĩa hoặc ghi lại file này.
- Không mặc định config HF `Wav2Vec2ForPreTraining` là classifier hoàn chỉnh;
  reference nạp full custom `m_ssl.*` + `proj_fc.*` bằng `strict=True`.

## Cách chạy sau khi chuẩn bị môi trường

Đặt bốn file đã chọn trước (hai TTS, hai giọng thật); không chọn lại file hoặc
ngưỡng dựa trên kết quả parity. File nằm ngoài Git. Truyền đường dẫn tuyệt đối
và dùng báo cáo JSON trong DATA_DIR hoặc tmp ignored:

```bash
python3.12 ml/scripts/parity_antideepfake.py \
  --models-dir /srv/vericlue-store/models \
  --upstream-dir /srv/vericlue-external/AntiDeepfake \
  --reference-python /srv/venvs/antideepfake-reference/bin/python \
  --audio /srv/vericlue-store/data/parity/tts-one.wav \
  --audio /srv/vericlue-store/data/parity/tts-two.wav \
  --audio /srv/vericlue-store/data/parity/real-one.wav \
  --audio /srv/vericlue-store/data/parity/real-two.wav \
  --report /srv/vericlue-store/data/parity/result.json
```

Python 3.12 phải tìm được gói `vericlue_ml` của checkout đang kiểm tra (môi trường
workspace đã sync hoặc PYTHONPATH tới `ml/src`). Đường dẫn ví dụ chỉ minh họa,
không là đường dẫn hard-code trong script. Script không tự đọc `.env`;
`--models-dir` ưu tiên, sau đó biến môi trường MODELS_DIR, mặc định `models`.

Nếu chưa có reference, có thể ghi nhận trung thực tình trạng chưa kiểm:

```bash
python3.12 ml/scripts/parity_antideepfake.py --report /tmp/parity-unverified.json
```

Lệnh này exit **2**, không import model/Fairseq và không chạy inference.
Không đổi nó thành exit0 để vượt CI hoặc đánh dấu parity đạt.

## Đối chiếu và nội dung báo cáo

1. Kiểm commit Git runtime/reference, kiểm SHA checkpoint đúng pin. Model nạp
   một lần mỗi process, CPU FP32/eval/inference mode; không có calibrator.
2. Dùng chính `preprocess_audio`, `make_windows`, `normalized_window` của wrapper:
   decode/resample/trim và quy ước cửa sổ/tail như runtime. Layer-norm đúng một lần
   trước khi chia dữ liệu cho hai backend. Không dùng lại padding/VAD khác ở reference.
3. Lưu mỗi normalized float32 window tạm thành NumPy NPZ (`allow_pickle=False`
   khi đọc). Converted runtime nhận array gốc, reference nhận đúng array đã lưu;
   hash normalized bytes được ghi để kiểm chứng đầu vào. File tạm xóa khi xong.
4. Reference gọi `Model("mms_300m")` upstream, không augmentation, strict state dict;
   runtime dùng backend Transformers đã chuyển key. Report lưu missing/unexpected
   keys của hai phía và ignored keys có chủ đích do runtime báo, không âm thầm
   bỏ qua mismatch hoặc thay classifier ngẫu nhiên.
5. So cả hai logits `[fake, real]` cho từng cửa sổ, không chỉ softmax/argmax.
   `PASS`/exit0 nếu mọi cửa sổ có max abs error ≤1e-4; lệch lớn hơn → `FAIL`/exit1.
   Không chạy xong đủ bốn file/reference lỗi → `UNVERIFIED`/exit2.
6. JSON ghi thời gian UTC, Git commit/dirty của wrapper và reference, Python/OS,
   phiên bản package, checkpoint/source/audio hashes, thời lượng/số mẫu, từng
   cửa sổ và logits/sai số. Không chứa transcript hoặc token. Không commit audio,
   checkpoint, NPZ hay JSON phát sinh như kết quả thực nghiệm trong task wrapper.

Kết quả bốn mẫu kiểm chiều điểm là kiểm riêng, không chứng minh numerical parity.
Nếu môi trường reference chưa chạy được, PR có thể ghi **CHƯA kiểm parity** theo
phạm vi đã được trưởng nhóm duyệt; không tuyên bố conversion tương đương upstream.

## Cách đã kiểm trên máy Windows qua Docker Linux

Không cài Fairseq lên Windows. Python 3.12 của workspace chạy phần converted;
worker Python 3.10 chạy trong image riêng. Lưu Dockerfile sau vào thư mục tmp
ignored rồi build image tham chiếu (không dùng Dockerfile sản phẩm):

```dockerfile
FROM python:3.10-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pip==24.0 'setuptools<70' wheel numpy==1.23.5 Cython==0.29.37
RUN pip install --no-cache-dir torch==2.2.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir fairseq==0.12.2 safetensors==0.5.3 scipy==1.10.1
RUN git clone --no-checkout https://github.com/nii-yamagishilab/AntiDeepfake.git /reference && git -C /reference checkout --detach 0dea622bde8f064c8ee5a557f2598643123fc6b6
ENV OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /reference
```

Build cần mạng; inference/parity không dùng mạng. Không đưa weights/audio vào
build context/image. Checkout trực tiếp trong Linux tránh tên file chỉ khác hoa/thường
của upstream bị collision khi clone trên Windows. Sau khi build:

```powershell
docker build -t vericlue-antideepfake-reference:py310-pinned tmp/voice01-reference-build
uv run --no-sync python ml/scripts/parity_antideepfake.py `
  --reference-docker-image vericlue-antideepfake-reference:py310-pinned `
  --models-dir $env:MODELS_DIR `
  --audio $ttsOne --audio $ttsTwo --audio $realOne --audio $realTwo `
  --report tmp/voice01-parity.json
```

Các biến audio là đường dẫn bốn file đã chọn trước; MODELS_DIR phải được export
vào process (script không đọc .env). Không truyền --upstream-dir ở chế độ image
có /reference; worker kiểm commit/sạch ngay trong image. Script resolve image ID
rồi chạy --pull=never/--network=none/--rm, mount model/script read-only và thư mục
tạm cửa sổ/report riêng. Không truyền secret/token hay mount thư mục .env.

Kết quả thực chạy 17/10/2026: **PASS**,4 file/9 window,max abs logits
2.956390380859375e-05. Môi trường, SHA và giới hạn ở
[model card](../model_cards/antideepfake-mms300m.md). Kết quả này không thay R3.
