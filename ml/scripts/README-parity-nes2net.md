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

> Lưu ý: Script thực thi cả hai nhánh trong cùng một lần chạy qua `--reference-python` (tương tự `ml/scripts/parity_antideepfake.py`), **không có** cờ `--export-reference` hay `--compare-reference`.

## 2. Quy tắc tiền xử lý và bất biến

- Tần số lấy mẫu: đúng `16000 Hz`, 1 kênh (mono), `float32` trong `[-1, 1]`.
- Không chuẩn hóa `layer_norm` trên sóng âm đầu vào và không cắt mẫu bằng VAD (khớp `easy_inference_demo.py --test_mode 4s`).
- Sóng âm ngắn hơn 64.000 mẫu được lặp (`np.tile`) rồi cắt đúng 64.000 mẫu; dài hơn 64.000 mẫu lấy 64.000 mẫu đầu (ở chế độ 4s đầu) hoặc các cửa sổ 64.000 mẫu theo `window_bounds` (ở chế độ timeline).
- Điểm thô: `score = logits[0] - logits[1]` (`0 = spoof`, `1 = bonafide`; điểm càng cao càng nghi giả).
- Trong worker tham chiếu Fairseq, mô hình `wav2vec2_Nes2Net_no_Res_w_allT` được ép sang `cpu` + `torch.float32` trước khi nạp `state_dict` và đặt `.eval()` để ngăn `SSLModel.extract_feat` tự bật `.train()` khi thấy khác `dtype`.

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

Hiện trạng trên máy dev:
- Đã có: WSL2 `Ubuntu-24.04`, checkpoint `D:\vericlue\models\selected-2026-10-24\nes2net-x-xlsr\checkpoint.pth` (SHA-256 `3158d10c6fc3c58e452a33981b409f5a65ecf91d548931b4ffbd675462799685`), runtime chuyển đổi `D:\vericlue\tmp\nes2net-cpu`.
- Còn thiếu để chạy nhánh `--reference-python` đạt `PASS`:
  1. Venv Python 3.10 trong Linux/WSL2 có `fairseq==0.12.2` và `torch==2.2.2+cpu` (WSL2 hiện chỉ có `python3` 3.12.3).
  2. Checkout sạch của `Liu-Tianchi/Nes2Net_ASVspoof_ITW` tại commit `c9fe1177f44040f002cb40def928332d2e261f1e`.
  3. File Fairseq `xlsr2_300m.pt` cho `SSLModel.__init__` của upstream.
  4. Danh sách `>= 32` file WAV 16 kHz mono tiếng nói thật có phép (`calib_fit`).

Các bước cài đặt và chạy trên Linux / WSL2:

1. Clone repo upstream tại đúng commit ghim:
   ```bash
   git clone https://github.com/Liu-Tianchi/Nes2Net_ASVspoof_ITW.git /tmp/Nes2Net_ASVspoof_ITW
   git -C /tmp/Nes2Net_ASVspoof_ITW checkout c9fe1177f44040f002cb40def928332d2e261f1e
   sha256sum /tmp/Nes2Net_ASVspoof_ITW/model_scripts/wav2vec2_Nes2Net_X.py
   # 8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f
   ```
2. Tạo venv Python 3.10 với `torch==2.2.2+cpu`, `fairseq==0.12.2`, `numpy<2`, `soundfile` (chỉ dùng cho kiểm chứng nghiên cứu, không đưa vào `pyproject.toml` của sản phẩm):
   ```bash
   uv python install 3.10
   uv venv --python 3.10 /tmp/nes2net-fairseq-ref
   /tmp/nes2net-fairseq-ref/bin/pip install "pip<24.1" "setuptools<70" wheel "cython<3"
   /tmp/nes2net-fairseq-ref/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.2.2 torchaudio==2.2.2
   /tmp/nes2net-fairseq-ref/bin/pip install "numpy<2" soundfile fairseq==0.12.2
   ```
3. Chạy `parity_nes2net.py` với danh sách tối thiểu 32 file WAV 16 kHz mono:
   ```bash
   PYTHONPATH=ml/src python ml/scripts/parity_nes2net.py \
     --models-dir /mnt/d/vericlue/models/selected-2026-10-24 \
     --audio-list /path/to/calib_audio_list.txt \
     --reference-python /tmp/nes2net-fairseq-ref/bin/python \
     --upstream-dir /tmp/Nes2Net_ASVspoof_ITW \
     --xlsr-checkpoint /path/to/xlsr2_300m.pt \
     --output /tmp/nes2net-parity-report.json
   ```

## 5. Tiêu chí đạt (`status == "PASS"`, exit code `0`)

- Số cửa sổ tiếng nói thật (`--audio-list`, không phải `--synthetic-smoke`): `>= 32`.
- `max_abs_logit_diff <= 1e-4`.
- `max_abs_margin_diff <= 1e-4`.
- `sign_agreement == 1.0`.
