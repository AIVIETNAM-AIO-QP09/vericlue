# Đối chiếu số học Fairseq ↔ Transformers cho NES2Net-X (`VOICE-08` / `VOICE-09`)

Script `ml/scripts/parity_nes2net.py` đối chiếu trực tiếp nhánh chuyển đổi HuggingFace `Wav2Vec2Model` + `Nes2NetHead` (`vericlue_ml.voice.nes2net.Nes2NetBackend`, CPU float32) với mã gốc Fairseq của tác giả (`Liu-Tianchi/Nes2Net_ASVspoof_ITW` commit `c9fe1177f44040f002cb40def928332d2e261f1e`, file `model_scripts/wav2vec2_Nes2Net_X.py` SHA-256 `8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f`, lớp `wav2vec2_Nes2Net_no_Res_w_allT`) trên cùng các cửa sổ PCM float32 64.000 mẫu (4,0 giây @ 16 kHz).

## 1. Các tùy chọn CLI thực tế

`ml/scripts/parity_nes2net.py` nhận đúng các tham số sau:

- `--models-dir <PATH>`: thư mục gốc chứa `nes2net-x-xlsr/checkpoint.pth` (mặc định đọc `MODELS_DIR` hoặc `./models`).
- `--audio-list <PATH>`: file văn bản chứa danh sách đường dẫn file WAV 16 kHz mono (mỗi dòng một file; cần `>= 32` mẫu tiếng nói thật để xét `PASS`).
- `--synthetic-smoke`: chạy 4 sóng âm tổng hợp tất định 16 kHz (loại trừ tương hỗ với `--audio-list`; trạng thái luôn giữ `UNVERIFIED`, exit code `2`).
- `--reference-python <PATH>`: đường dẫn tới trình thông dịch Python 3.10 đã cài `fairseq==0.12.2` và `torch==2.2.2+cpu`.
- `--upstream-dir <PATH>`: thư mục checkout `Liu-Tianchi/Nes2Net_ASVspoof_ITW` tại commit `c9fe1177f44040f002cb40def928332d2e261f1e` (bắt buộc khi truyền `--reference-python`).
- `--xlsr-checkpoint <PATH>`: đường dẫn tới file gốc Fairseq `xlsr2_300m.pt` mà `SSLModel.__init__` trong `model_scripts/wav2vec2_Nes2Net_X.py` gọi qua `fairseq.checkpoint_utils.load_model_ensemble_and_task` để khởi tạo kiến trúc trước khi `load_state_dict` nạp `checkpoint.pth` (bắt buộc khi truyền `--reference-python`; nhánh chuyển đổi Transformers không cần file này).
- `--output <PATH>`: đường dẫn file JSON mới để ghi báo cáo (script từ chối ghi đè nếu file đã tồn tại).
- `--source-commit <40-hex>`: tùy chọn cung cấp commit đã kiểm bằng Git Windows
  khi `.git` của worktree chứa đường dẫn Windows mà Git WSL không đọc được.
  Chỉ truyền commit đã xác minh, chạy trên source sạch; báo cáo còn giữ hash script.

> Lưu ý: Script thực thi cả hai nhánh trong cùng một lần chạy qua `--reference-python` (tương tự `ml/scripts/parity_antideepfake.py`), **không có** cờ `--export-reference` hay `--compare-reference`.

## 2. Quy tắc tiền xử lý và bất biến

- Tần số lấy mẫu: đúng `16000 Hz`, 1 kênh (mono), `float32` trong `[-1, 1]`.
- Không chuẩn hóa `layer_norm` trên sóng âm đầu vào và không cắt mẫu bằng VAD (khớp `easy_inference_demo.py --test_mode 4s`).
- Sóng âm ngắn hơn 64.000 mẫu được lặp (`np.tile`) rồi cắt đúng 64.000 mẫu; dài hơn 64.000 mẫu lấy 64.000 mẫu đầu (ở chế độ 4s đầu) hoặc các cửa sổ 64.000 mẫu theo `window_bounds` (ở chế độ timeline).
- Điểm thô: `score = logits[0] - logits[1]` (`0 = spoof`, `1 = bonafide`; điểm càng cao càng nghi giả).
- Trong worker tham chiếu Fairseq, mô hình `wav2vec2_Nes2Net_no_Res_w_allT` được ép sang `cpu` + `torch.float32` trước khi nạp `state_dict` và đặt `.eval()` để ngăn `SSLModel.extract_feat` tự bật `.train()` khi thấy khác `dtype`.
- Worker cấp `AudioPretrainingTask(AudioPretrainingConfig())` cho loader để không
  merge các trường dataset/training cũ (`multiple_train_files`, `eval_wer`, ...)
  trong checkpoint XLS-R vào dataclass Fairseq0.12.2. Graph lấy từ cấu hình model
  của checkpoint và mọi trọng số giữ nguyên; không gọi dataset/task preprocessing.
  Hai nhánh vẫn nhận cùng PCM và chỉ được công nhận khi số học thực sự khớp.
- Cả hai nhánh dùng cùng số CPU threads từ `nes2net.yaml` (hiện4). Không ép
  reference1 thread trong khi converted4; vẫn giữ nguyên giới hạn sai lệch1e-4.

## 3. Chạy kiểm tra phía chuyển đổi (Converted-side smoke trên Windows)

Khi chưa có runtime Linux Python 3.10 + `fairseq==0.12.2`, chạy kiểm tra tiền xử lý + ánh xạ 422 khóa frontend + 560 khóa head trên checkpoint thật:

```powershell
$env:PYTHONPATH = "ml/src"
& "D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe" ml/scripts/parity_nes2net.py `
  --models-dir "D:\vericlue\models\selected-2026-10-24" `
  --synthetic-smoke `
  --output "tmp/nes2net-parity-smoke.json"
```

Kết quả trả mã thoát `2` và ghi `"status": "UNVERIFIED"`. **Tuyệt đối không coi smoke Transformers hoặc việc nạp checkpoint thành công là `PASS`**; `Nes2NetDetector` và `Nes2NetTimelineDetector` giữ nguyên `status="degraded"`, `gate="unclear"`, `prob_attack=None` cho tới khi đủ bằng chứng parity và hiệu chỉnh.

## 4. Chạy đối chiếu đầy đủ với Fairseq trên Linux / WSL2 (Python 3.10)

Hiện trạng trên máy dev (cập nhật 01/11/2026):
- Đã có:
  1. WSL2 `Ubuntu-24.04` với `uv` (`/home/ngocquang/.local/bin/uv`) và venv Python 3.10.22 tại `/home/ngocquang/nes2net-fairseq-ref` đã cài `torch==2.2.2+cpu`, `torchaudio==2.2.2+cpu`, `numpy==1.26.4`, `soundfile==0.14.0`, `fairseq==0.12.2` (từ tag gốc `v0.12.2` commit `4a388e64cd646ed7d7ad8de8fae55df2b8eea91d`).
  2. Checkout sạch của `Liu-Tianchi/Nes2Net_ASVspoof_ITW` tại `/home/ngocquang/Nes2Net_ASVspoof_ITW` (commit `c9fe1177f44040f002cb40def928332d2e261f1e`, `model_scripts/wav2vec2_Nes2Net_X.py` SHA-256 `8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f`).
  3. Checkpoint `D:\vericlue\models\selected-2026-10-24\nes2net-x-xlsr\checkpoint.pth` (SHA-256 `3158d10c6fc3c58e452a33981b409f5a65ecf91d548931b4ffbd675462799685`) và runtime chuyển đổi `D:\vericlue\tmp\nes2net-cpu`.
- Đã có `xlsr2_300m.pt` và 32 WAV VIVOS publisher pin revision, chín speaker.
  Lượt cùng4threads đạt parity trên WSL và Windows; báo cáo tổng hợp ở
  `docs/status/results/VOICE-09-parity-2026-11-01.json`. Đây là dữ liệu parity,
  **không phải calib_fit**; VIVOS vẫn test-only cho việc chọn model/ngưỡng.
- Binding marker opt-in, các biến môi trường và điều kiện runtime/source/config:
  [hướng dẫn detector](../../docs/architecture/nes2net-diagnostic.md).

> Lưu ý trên WSL2 có `systemd`: không đặt venv hoặc repo ở `/tmp` vì WSL2 tự xóa `/tmp` khi máy ảo tắt sau vài giây nghỉ giữa các lệnh `wsl`. Đặt cố định trong `$HOME` (`/home/ngocquang/...`).

Các bước cài đặt và chạy trên Linux / WSL2:

1. Clone repo upstream tại đúng commit ghim:
   ```bash
   git clone https://github.com/Liu-Tianchi/Nes2Net_ASVspoof_ITW.git "$HOME/Nes2Net_ASVspoof_ITW"
   git -C "$HOME/Nes2Net_ASVspoof_ITW" checkout c9fe1177f44040f002cb40def928332d2e261f1e
   sha256sum "$HOME/Nes2Net_ASVspoof_ITW/model_scripts/wav2vec2_Nes2Net_X.py"
   # 8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f
   ```
2. Tạo venv Python 3.10 với `torch==2.2.2+cpu`, `fairseq==0.12.2`, `numpy<2`, `soundfile` (chỉ dùng cho kiểm chứng nghiên cứu, không đưa vào `pyproject.toml` của sản phẩm; cài `numpy<2` trước bước `--no-build-isolation` và dùng tag `v0.12.2` của `facebookresearch/fairseq` vì bản sdist trên PyPI thiếu `fairseq/clib/libbase/balanced_assignment.cpp`):
   ```bash
   uv python install 3.10
   uv venv --seed --python 3.10 "$HOME/nes2net-fairseq-ref"
   "$HOME/nes2net-fairseq-ref/bin/python" -m pip install "pip<24.1" "setuptools<70" wheel "cython<3" "numpy<2" soundfile
   "$HOME/nes2net-fairseq-ref/bin/python" -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.2.2 torchaudio==2.2.2
   "$HOME/nes2net-fairseq-ref/bin/python" -m pip install --no-build-isolation "git+https://github.com/facebookresearch/fairseq.git@v0.12.2"
   "$HOME/nes2net-fairseq-ref/bin/python" -c "import torch, fairseq, soundfile, numpy; print(torch.__version__, fairseq.__version__, numpy.__version__)"
   ```
3. Tạo môi trường **chuyển đổi** Python 3.12 riêng. Gói `vericlue_ml` dùng `StrEnum`
   và không import được trên Python 3.10 của Fairseq. Không dùng interpreter hệ thống
   chưa cài Transformers để chạy script cha:
   ```bash
   uv venv --seed --python 3.12 "$HOME/nes2net-hf-parity"
   uv pip install --python "$HOME/nes2net-hf-parity/bin/python" \
     torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
   uv pip install --python "$HOME/nes2net-hf-parity/bin/python" \
     transformers==4.57.6 pydantic pyyaml scipy==1.15.3 numpy==1.26.4 soundfile webrtcvad-wheels
   ```
4. Chạy `parity_nes2net.py` bằng môi trường chuyển đổi; worker Fairseq vẫn chạy bằng
   Python 3.10. Danh sách gồm tối thiểu 32 file WAV 16 kHz mono độc lập:
   ```bash
   PYTHONPATH=ml/src "$HOME/nes2net-hf-parity/bin/python" ml/scripts/parity_nes2net.py \
     --models-dir /mnt/d/vericlue/models/selected-2026-10-24 \
     --audio-list /path/to/calib_audio_list.txt \
     --reference-python "$HOME/nes2net-fairseq-ref/bin/python" \
     --upstream-dir "$HOME/Nes2Net_ASVspoof_ITW" \
     --xlsr-checkpoint /path/to/xlsr2_300m.pt \
     --output "$HOME/nes2net-parity-report.json"
   ```

## 5. Tiêu chí đạt (`status == "PASS"`, exit code `0`)

- Số cửa sổ tiếng nói thật (`--audio-list`, không phải `--synthetic-smoke`): `>= 32`.
- Tất cả mẫu độc lập (`diversity.all_unique == true` và `independent_sample_count >= 32`; các bản lặp file hoặc cửa sổ PCM trùng SHA-256 không được tính gộp thành nhiều mẫu).
- `max_abs_logit_diff <= 1e-4`.
- `max_abs_margin_diff <= 1e-4`.
- `sign_agreement == 1.0`.

PASS chỉ là đối chiếu số học trên các input/runtime đã ghi, không chứng minh
độ chính xác chống giả giọng hoặc cho phép đổi trạng thái detector thành đạt.
Đổi Torch/thiết bị/recipe cần kiểm chứng lại; không suy từ kết quả WSL sang
runtime Windows khác phiên bản.

Report canonical `docs/status/results/VOICE-09-parity-2026-11-01.json` là bằng
chứng gắn theo byte. Các phép đo native đã bind SHA-256
`669bf62e4db134a46e8a0dd8f3d5b6a72bba90a984c3a7901fa8e866e8f21a48` của bản CRLF
đã sử dụng. `.gitattributes` giữ nguyên byte của riêng artifact này khi checkout;
không tự định dạng hoặc đổi xuống dòng rồi coi hash khác là cùng binding.
Test kiểm cả hash cố định và `verify_parity`. Nếu thay dữ liệu bằng chứng,
cần report/binding mới được review; không tắt kiểm SHA để dùng lại cache cũ.
