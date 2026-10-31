# Đối chiếu số học Fairseq ↔ Transformers cho NES2Net-X (`VOICE-08` / `VOICE-09`)

Script `ml/scripts/parity_nes2net.py` đối chiếu trực tiếp nhánh chuyển đổi HuggingFace `Wav2Vec2Model` + `Nes2NetHead` (`vericlue_ml.voice.nes2net.Nes2NetBackend`, CPU float32) với mã gốc Fairseq của tác giả (`Liu-Tianchi/Nes2Net_ASVspoof_ITW` commit `c9fe1177f44040f002cb40def928332d2e261f1e`, file `model_scripts/wav2vec2_Nes2Net_X.py` SHA-256 `8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f`) trên cùng các cửa sổ PCM float32 64.000 mẫu (4,0 giây @ 16 kHz).

## 1. Quy tắc tiền xử lý và bất biến

- Tần số lấy mẫu: đúng `16000 Hz`, 1 kênh (mono), `float32` trong `[-1, 1]`.
- Không chuẩn hóa `layer_norm` trên sóng âm đầu vào và không cắt mẫu bằng VAD (khớp `easy_inference_demo.py --test_mode 4s`).
- Sóng âm ngắn hơn 64.000 mẫu được lặp (`np.tile`) rồi cắt đúng 64.000 mẫu; dài hơn 64.000 mẫu lấy 64.000 mẫu đầu (ở chế độ 4s đầu) hoặc các cửa sổ 64.000 mẫu theo `window_bounds` (ở chế độ timeline).
- Điểm thô: `score = logits[0] - logits[1]` (`0 = spoof`, `1 = bonafide`; điểm càng cao càng nghi giả).

## 2. Chạy kiểm tra phía chuyển đổi (Converted-side smoke trên Windows)

Khi chưa có runtime Linux Python 3.10 + `fairseq==0.12.2`, chạy kiểm tra tiền xử lý + ánh xạ 422 khóa frontend + 560 khóa head trên checkpoint thật:

```powershell
$env:PYTHONPATH = "ml/src"
& "D:\vericlue\tmp\nes2net-cpu\Scripts\python.exe" ml/scripts/parity_nes2net.py `
  --models-dir "D:\vericlue\models\selected-2026-10-24" `
  --synthetic-smoke `
  --output "tmp/nes2net-parity-smoke.json"
```

Kết quả trả mã thoát `2` và ghi `"status": "UNVERIFIED"` (không bao giờ tự đánh dấu `PASS` khi chưa chạy Fairseq).

## 3. Chạy đối chiếu đầy đủ với Fairseq trên Linux / WSL2 (Python 3.10)

Chuẩn bị môi trường tham chiếu tách biệt (chỉ dùng cho kiểm chứng nghiên cứu, không đưa vào `pyproject.toml` của sản phẩm):

1. Clone repo upstream tại đúng commit ghim:
   ```bash
   git clone https://github.com/Liu-Tianchi/Nes2Net_ASVspoof_ITW.git /tmp/Nes2Net_ASVspoof_ITW
   git -C /tmp/Nes2Net_ASVspoof_ITW checkout c9fe1177f44040f002cb40def928332d2e261f1e
   sha256sum /tmp/Nes2Net_ASVspoof_ITW/model_scripts/wav2vec2_Nes2Net_X.py
   # 8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f
   ```
2. Tạo venv Python 3.10 với `torch==2.2.2+cpu`, `fairseq==0.12.2`, `numpy<2`, `soundfile`:
   ```bash
   python3.10 -m venv /tmp/nes2net-fairseq-ref
   /tmp/nes2net-fairseq-ref/bin/pip install "pip<24.1" "setuptools<70" wheel
   /tmp/nes2net-fairseq-ref/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.2.2
   /tmp/nes2net-fairseq-ref/bin/pip install "numpy<2" soundfile fairseq==0.12.2
   ```
3. Chạy `parity_nes2net.py` với danh sách tối thiểu 32 file WAV 16 kHz mono:
   ```bash
   PYTHONPATH=ml/src python ml/scripts/parity_nes2net.py \
     --models-dir /path/to/models/selected-2026-10-24 \
     --audio-list /path/to/calib_audio_list.txt \
     --reference-python /tmp/nes2net-fairseq-ref/bin/python \
     --upstream-dir /tmp/Nes2Net_ASVspoof_ITW \
     --xlsr-checkpoint /path/to/xlsr2_300m.pt \
     --output /tmp/nes2net-parity-report.json
   ```

## 4. Tiêu chí đạt (`status == "PASS"`, exit code `0`)

- Số cửa sổ tiếng nói thật: `>= 32`.
- `max_abs_logit_diff <= 1e-4`.
- `max_abs_margin_diff <= 1e-4`.
- `sign_agreement == 1.0`.
