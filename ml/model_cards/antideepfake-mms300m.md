# AntiDeepfake MMS-300M — wrapper VOICE-01

**Parity CPU với Fairseq upstream đã đạt trên bốn file / chín window; xem bằng chứng bên dưới.**
Task chỉ làm wrapper; chưa huấn luyện/tinh chỉnh, chưa có R3 hay calibrator thật.

| Mục | Giá trị |
|---|---|
| Module | voice_spoof |
| Checkpoint | nii-yamagishilab/mms-300m-anti-deepfake @7928e119e09f616b2ce698892e00ca22dbaa40bf |
| SHA-256 weights | 9bd5d9785bf72f91dfca8508651354946c4b307921cb358505e1b94035102224 |
| License weights | CC-BY-NC-SA-4.0 — chỉ nghiên cứu phi thương mại |
| License code dùng lại | BSD-3-Clause (NII head/pooling), Apache-2.0 (Transformers mapping); third_party/README.md |
| Runtime | Transformers Wav2Vec2Model + temporal average pooling + Linear1024→2, eval/inference_mode |
| Loading | Chỉ local; xác minh SHA config/weights; ánh xạ trong RAM, strict=True, không sửa file gốc |
| Model version | mms-300m-antideepfake@7928e119e09f616b2ce698892e00ca22dbaa40bf+voice01-v1-vad1-ln-win4-hop1-tail-meanlogits |
| Calibration | Chưa có; raw score không phải prob_attack. TrustRouter thiếu calibrator đúng version sẽ error/review |

## Tiền xử lý và gộp

Mean kênh → resample16k bằng torchaudio như upstream → WebRTC VAD mode1 cắt lặng
ngoài (VOICE-04; giữ gap trong, đệm200ms), kiểm đủ1s trước/sau trim. Cổng VAD và
4s/hop 1 s là quy ước VeriClue được trưởng nhóm duyệt, không tự nhận là recipe
đánh giá upstream. Không thêm Silero, không dùng augmentation/crop ngẫu nhiên.
Audio 1–4 s giữ độ dài thật; file dài dùng window 4 s / hop 1 s và1 window neo cuối để phủ
đuôi. Mỗi window chuẩn hóa kiểu layer_norm toàn waveform, eps=1e-5, không affine.
Gộp meanlogits rồi softmaxfake; evidence window_scores ghi offset theo file gốc,
logits và raw score từng window. Không pad/repeat thành tiếng nói giả.

Class order xác minh từ [model card ghim](https://huggingface.co/nii-yamagishilab/mms-300m-anti-deepfake/blob/7928e119e09f616b2ce698892e00ca22dbaa40bf/README.md):
phần inference in `real prob=prob[1]`, `fake prob=prob[0]`; không đoán nhãn.
Head/pooling theo [W2V.py ghim](https://github.com/nii-yamagishilab/AntiDeepfake/blob/0dea622bde8f064c8ee5a557f2598643123fc6b6/models/W2V.py#L69-L98).

## Kiểm loading / smoke, không phải R3

Checkpoint thật:424 mapped,0 missing,0 unexpected; chỉ7tensor pretraining bỏ qua
(quantizer.vars/weight_proj.weight/bias, project_q.weight/bias, final_proj.weight/bias).
Không cho phép bỏ qua backbone/head hay ghi đè khóa ánh xạ trùng.

Smoke được chạy bằng ml/scripts/smoke_antideepfake.py trên4 file đã chọn trước,
Windows11/MSI, CPU float32, Python 3.12.14, sourcecommit
4aa0da47b1c867629fae787f15a3b400bc4b635c-dirty. Không chọn lại mẫu/ngưỡng bằng kết quả.
| File công khai | Nhãn nguồn | Raw fake score |
|---|---|---:|
| correct.wav | MMS-TTS | 0.998591652 |
| wrong.wav | MMS-TTS | 0.971673030 |
| 00000.wav | VSASV bona fide | 0.000402755 |
| 00001.wav | VSASV bona fide | 0.000500161 |

Cả4 status=ok, min(TTS)>max(real). Đây chỉ là kiểm chiều và loader, không có EER,
độ chính xác đại diện, ngưỡng ra quyết định hay bảo đảm thống kê. Report cục bộ
tmp/voice01-smoke-cpu.json lưu modelversion/commit/hash/audioevidence và mọi kết quả.

## Parity thực chạy — PASS

`ml/scripts/parity_antideepfake.py` so cả hai raw logits trên đúng bốn file smoke,
9 normalized windows giống hệt byte, CPU float32/1 thread. **Max abs error =
2.956390380859375e-05 ≤ 1e-4**, không chọn lại mẫu hoặc tinh chỉnh theo kết quả.
Wrapper Windows11/Python 3.12.14/Torch 2.14.1/Transformers 4.57.6/NumPy 2.5.4;
reference Docker Linux WSL2/Python 3.10.22/Fairseq 0.12.2/Torch 2.2.2+cpu/
torchaudio 2.2.2+cpu/NumPy 1.23.5/safetensors 0.5.3. Reference gọi trực tiếp W2V.py
upstream sạch, commit0dea622bde8f064c8ee5a557f2598643123fc6b6, strict load: 0 missing / 0 unexpected.
Wrapper commit4aa0da47b1c867629fae787f15a3b400bc4b635c-dirty; checkpoint giữ nguyên SHA.
Image tham chiếu `vericlue-antideepfake-reference:py310-pinned`, ID
`sha256:e3aa000d0c2e2f920bb0bc3bf986cfb3f5e21060fe1e57ef5278feb7105f376d`.
Container chỉ mount checkpoint/script read-only, dữ liệu cửa sổ tạm ngoài Git;
chạy --rm/--network none, không Fairseq trong runtime Windows hay uv.lock.

| File | Số window | Max abs error logits |
|---|---:|---:|
| correct.wav | 1 | 2.52723693848e-05 |
| wrong.wav | 1 | 2.95639038086e-05 |
| 00000.wav | 1 | 9.53674316406e-07 |
| 00001.wav | 6 | 2.55107879639e-05 |

Báo cáo do code sinh: tmp/voice01-parity.json (ignored), chứa từng cặp logits,
SHA audio/window/checkpoint, môi trường, nguồn và thời điểm. Phép kiểm chứng minh
backend ánh xạ trên những window này; không chứng minh EER hay calibration/R3.

## Giới hạn / phần phải làm tiếp

- Parity đã đạt cho checkpoint/pipeline/version này; phải kiểm lại khi đổi mapping hoặc backend trước công bố baseline.
- Môi trường nghiệm thu hiện cài Torch CPU. Code hỗ trợ CUDA fp16, từng window, batch 1;
  chưa có phép đo VRAM/latency trên RTX 4050 6 GB trong smokeCPU này. Cần Torch CUDA
  phù hợp và đặt DEVICE=cuda để chạy GPU, không tự rơi về CPU nếu CUDA lỗi.
  Thử tải wheel CUDA trong môi trường tách riêng bị gián đoạn nhiều lần; đã dừng
  và giữ phần tải hoàn tất để tiếp tục sau. Không coi hỗ trợ code là GPU đã nghiệm thu.
- Decoder giới hạn120 s mỗi predict để chặn input quá lớn; FOR-01 chia đoạn dài.
- CPU chậm, file dài/queue có thể vượt budget API 4 s; timeout do orchestrator xử lý,
  không dùng kết quả muộn để pass. API đã truyền Settings.models_dir vào preload; mixed cần cả extra face và voice.
- Thiếu/corrupt model, thiếu dependency, lỗi/OOM hoặc outputNaN → error, không mockfallback.
- Im lặng/<1s → not_applicable. Không sinh R3, không fit/chọn trên calib_ltt/test.

## Latency CPU của smoke (không phải SLA)

Sau preload, mỗi file chạy một lần; gồm decode/VAD/window inference, không gồm nạp mô hình:

| File | Window | Latency ms |
|---|---:|---:|
| correct.wav | 1 | 3141.531 |
| wrong.wav | 1 | 2121.565 |
| 00000.wav | 1 | 2012.300 |
| 00001.wav | 6 | 19747.897 |

Máy/môi trường/commit như smoke ở trên; file dài trên CPU vượt budget API. Đây là phép đo từng mẫu, không phải percentile hay benchmark đại diện.
