# third_party — Ghi nhận mã nguồn dùng lại

Mọi đoạn code **chép** từ dự án khác phải được ghi vào bảng dưới đây, và file chép phải giữ nguyên dòng giấy phép ở đầu. Đây là điều kiện bắt buộc của giấy phép Apache-2.0 và MIT.

| Nguồn | Giấy phép | Chép vào đâu | Đã sửa gì | Task |
|---|---|---|---|---|
| aws-amplify/amplify-ui `packages/react-liveness` | Apache-2.0 | `apps/web/src/lib/capture/vendor/amplify/` | (điền khi chép) | CAP-04 |
| abrahamjuliot/creepjs `src/lies` | MIT | `apps/web/src/lib/capture/vendor/creepjs/` | (điền khi chép) | CAP-05 |

Văn bản giấy phép gốc lưu trong `third_party/licenses/<tên-dự-án>.txt`.

## Thư viện và mô hình dùng nguyên bản (không chép mã)

Không chép vào `src/`, nhưng vẫn ghi nhận để giữ đúng giấy phép. File tải bằng script, **không commit** (`apps/web/public/mediapipe/` nằm trong `.gitignore`).

| Nguồn | Giấy phép | Dùng ở đâu | Cách lấy | Task |
|---|---|---|---|---|
| `@mediapipe/tasks-vision` 1.1.0 (google-ai-edge/mediapipe) | Apache-2.0 (theo gói npm) | `apps/web/src/lib/capture/chromapulse/landmarker.ts`; wasm chép vào `apps/web/public/mediapipe/wasm/` | `npm ci`, rồi `uv run python scripts/fetch_web_assets.py` | CAP-03 |
| `face_landmarker.task` (float16, v1) | Apache-2.0 theo công bố của Google — **cần kiểm lại** model card và điều khoản dữ liệu huấn luyện | `apps/web/public/mediapipe/face_landmarker.task` | `scripts/fetch_web_assets.py` tải từ `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`, kiểm SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` (3.758.596 byte) | CAP-03 |
| `audioseal` 0.2.x (facebookresearch/audioseal) — thư viện pip và trọng số `detector_base.pth` | MIT (code và trọng số, theo README và LICENSE của repo; manifest: `audioseal-detector`) | `ml/src/vericlue_ml/forensic/provenance.py` | Dùng nguyên bản qua pip (extra `forensic`); nạp offline từ `MODELS_DIR` bằng đường dẫn file sau khi kiểm SHA-256, `nbits=16` | FOR-03 |
| `einops` 0.8, `omegaconf` 2.4 (kéo theo `audioseal`); `toml` 0.10, `cryptography` 50 (kéo theo `c2pa-python`) | giấy phép thoáng theo gói PyPI (MIT / BSD-3-Clause / Apache-2.0 hoặc BSD-3-Clause); kiểm lại khi nâng phiên bản | phụ thuộc gián tiếp của `ml/src/vericlue_ml/forensic/provenance.py` | Cài qua pip (extra `forensic`, `c2pa`), không chép mã | FOR-03 |
| `c2pa-python` 0.38.x (contentauth/c2pa-python) | MIT OR Apache-2.0 | `ml/src/vericlue_ml/forensic/provenance.py` | Dùng nguyên bản qua pip (extra `c2pa`); chỉ đọc manifest, chặn tải từ xa và OCSP | FOR-03 |

Giữ nguyên thông báo Apache-2.0 khi phân phối. Sau này gộp mô hình vào `models/manifest.yaml` (DATA-02).

## FACE-01

| Nguồn | Giấy phép | Chép vào đâu | Đã sửa gì | Task |
|---|---|---|---|---|
| [uniface](https://github.com/yakhyo/uniface) 4.0.0 — `spoofing/minifasnet.py` (tiền xử lý cắt theo `scale`, softmax), `detection/scrfd.py` và `common.py` (letterbox, giải mã anchor, NMS) | MIT, Copyright 2025-2026 Yakhyokhuja Valikhujaev | `ml/src/vericlue_ml/face/pad.py` (viết lại gọn; docstring giữ nguồn và giấy phép) | Chạy `onnxruntime` trực tiếp từ `MODELS_DIR`, kiểm SHA-256, không tải mạng; không phụ thuộc `uniface`. Điểm p_real đã đối chiếu với `uniface` gốc trên 4 khung hình, khớp tới 6 chữ số. Văn bản giấy phép: `third_party/licenses/uniface.txt` | FACE-01 |

## FACE-02

| Nguồn | Giấy phép | Chép vào đâu | Đã sửa gì | Task |
|---|---|---|---|---|
| [yermandy/GenD](https://github.com/yermandy/GenD) commit `387a42266dd385fbe8f7626c5d3aa03eea3bfaab` — `detector.py::align_face` (mốc đích, `estimateAffinePartial2D` LMEDS, `target_size=None`), `src/retinaface.py` (SCRFD: chia 128, đảo BGR→RGB), `src/hf/modeling_gend.py` (`pooler_output` → L2-normalize → Linear(1024, 2)), `app/run.py` (softmax, nhãn 1 = giả) | MIT, Copyright (c) 2025 Andy (`third_party/licenses/GenD-MIT.txt`) | `ml/src/vericlue_ml/face/gend.py` (viết lại gọn; docstring giữ nguồn) và `ScrfdFaceFinder` trong `face/pad.py` (thêm giải mã 5 mốc, tham số `scale`/`swap_rb`) | Nạp CLIP từ `config.json` cục bộ + trọng số GenD (không dùng `GenD.from_pretrained`, không tải mạng, không chạy mã từ xa); không phụ thuộc `peft`/`timm`. Chưa có script đối chiếu số học với mã gốc trong repo (xem bàn giao FACE-02) | FACE-02 |

Trọng số GenD `yermandy/GenD_CLIP_L_14` (MIT) và `openai/clip-vit-large-patch14` (MIT theo openai/CLIP, xem ghi chú trong `models/manifest.yaml`); `det_10g.onnx` vẫn là giấy phép nghiên cứu phi thương mại.

Trọng số (không commit, tải bằng `scripts/download_models.py`, theo `models/manifest.yaml`):

| Trọng số | Giấy phép | Ghi chú |
|---|---|---|
| `minifasnet_v2.onnx` (`yakhyo/uniface-weights`) | Apache-2.0 (verified trong manifest) | PAD |
| `det_10g.onnx` (SCRFD, cùng repo) | **Nghiên cứu phi thương mại** (`accepted-research`) | Chỉ dùng cho bản thi/nghiên cứu; GenD cũng dùng bộ tìm mặt này. Đưa vào sản phẩm thương mại thì phải thay |

## Giấy phép KHÔNG được chép vào sản phẩm

GPL, AGPL, LGPL (ví dụ Deep-Live-Cam, DeepFaceLive, pyVHR, heartbeat-js, Sherloq), và **repo không có giấy phép** (mặc định giữ mọi quyền). Những repo này chỉ được dùng để tham khảo ý tưởng hoặc làm công cụ thử tấn công.

## VOICE-04

Không chép mã nguồn thư viện vào repo:

| Thành phần | Giấy phép | Cách dùng |
|---|---|---|
| [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels/blob/release/LICENSE) | MIT wrapper; BSD-3-Clause WebRTC | Dependency optional voice; VAD CPU, không checkpoint |
| [Transformers](https://github.com/huggingface/transformers/blob/v4.57.1/LICENSE) | Apache-2.0 | Đọc PhoWhisper local, không remote code |
| [PhoWhisper](https://huggingface.co/vinai/PhoWhisper-small/blob/a86b604c346caf7148c37512eafe783a16420adb/README.md) | BSD-3-Clause | Weights ngoài repo, theo manifest DATA-02 |
| [eSpeak NG 1.52.0](https://github.com/espeak-ng/espeak-ng/blob/1.52.0/COPYING) | GPL-3.0-or-later | **Công cụ thử nghiệm độc lập**, chỉ tạo TTS nội bộ trong DATA_DIR; không chép/link/import vào sản phẩm và không phân phối binary/audio |

eSpeak GPL §2 cho phép chạy công cụ; không suy ra output có giấy phép CC/public
domain. Script chuẩn bị ghi phiên bản, SHA-256 và nguồn ở SOURCE.md cạnh fixture.

TTS thử nghiệm còn dùng [facebook/mms-tts-vie](https://huggingface.co/facebook/mms-tts-vie/blob/b58928d033932a49aa8e3d6cf11625b25fe928d2/README.md), weights **CC BY-NC 4.0**, chỉ nghiên cứu phi thương mại. Model ngoài repo trong MODELS_DIR; không chép code, không gọi ở inference sản phẩm. Script chuẩn bị ghim revision/SHA, không gán giấy phép Transformers cho weights.


## VOICE-01 — AntiDeepfake wrapper

| Nguồn ghim | Giấy phép code | Dùng ở đâu / thay đổi |
|---|---|---|
| [Transformers converter](https://github.com/huggingface/transformers/blob/09f9f566de83eef1f13ee83b5a1bbeebde5c80c1/src/transformers/models/wav2vec2/convert_wav2vec2_original_pytorch_checkpoint_to_pytorch.py) (v4.39.3, bảng MAPPING) | Apache-2.0, Copyright2021 HuggingFace | `ml/src/vericlue_ml/voice/antispoof.py`: ánh xạ lại Fairseq keys cho local checkpoint; thêm kiểm shape/coverage/allowlist, hỗ trợ weight_norm parametrizations. Không chép/import Fairseq runtime. |
| [AntiDeepfake W2V.py](https://github.com/nii-yamagishilab/AntiDeepfake/blob/0dea622bde8f064c8ee5a557f2598643123fc6b6/models/W2V.py#L69-L98) | BSD-3-Clause, Copyright2025 Yamagishi Lab/NII | `antispoof.py`: giữ temporal average-pooling và Linear head1024→2; backbone dùng Transformers với trọng số ánh xạ trong RAM. |

Giữ thông báo ở đầu file; nguyên văn license tại
`licenses/transformers-Apache-2.0.txt` và `licenses/antideepfake-BSD-3-Clause.txt`.
Trọng số `nii-yamagishilab/mms-300m-anti-deepfake` revision
`7928e119e09f616b2ce698892e00ca22dbaa40bf` là **CC-BY-NC-SA-4.0**, chỉ nghiên cứu
phi thương mại, khác giấy phép code. Không commit hay sửa file trong MODELS_DIR.
Fairseq chỉ là dependency môi trường Linux tham chiếu riêng cho parity; không nằm
trong pyproject.toml/uv.lock/runtime sản phẩm. Chưa chạy parity thì không được gọi
wrapper là đã tương đương số học với upstream hay sinh R3-baseline.

## VOICE-05 — Stable SyncNet

| Nguồn ghim | Giấy phép code | Dùng ở đâu / thay đổi |
|---|---|---|
| [LatentSync](https://github.com/bytedance/LatentSync/tree/a229c3948406bc2cf6eaf4873e662e70c6a04746), `latentsync/models/stable_syncnet.py`, lớp `Attention` trong `latentsync/models/attention.py`, `configs/syncnet/syncnet_16_pixel_attn.yaml` | Apache-2.0, Copyright 2024 Bytedance | `ml/src/vericlue_ml/voice/_syncnet_model.py`: giữ kiến trúc pixel-space 16 khung và tên khóa checkpoint; bỏ nhánh training, gộp attention, thay einops bằng tensor reshape, thêm encoder riêng để lưu embedding tạm. |
| [Diffusers v0.32.2](https://github.com/huggingface/diffusers/tree/560fb5f4d65b8593c13e4be50a59b1fd9c2d9992), `src/diffusers/models/attention.py` (`FeedForward`), `activations.py` (`GEGLU`) | Apache-2.0, Copyright 2024 HuggingFace | `_syncnet_model.py`: giữ nhánh GEGLU mặc định và tên `net.0.proj` / `net.2`; chỉ dùng Torch, không kéo dependency Diffusers hoặc mô hình sinh ảnh. |

Giữ thông báo gốc và ghi thay đổi ở đầu file. Nguyên văn giấy phép code tại
`licenses/latentsync-Apache-2.0.txt` và `licenses/diffusers-Apache-2.0.txt`.
Checkpoint `ByteDance/LatentSync-1.6` revision
`c42c7e6c8e9c213626389fa7d9a3c444b8536353`, file `stable_syncnet.pt`, dùng
**OpenRAIL++**, khác Apache-2.0 của code; tham chiếu `models/manifest.yaml`.
Không commit weights. Không chép evaluator SyncNet cổ điển hay mã Wav2Lip.

Căn chỉnh `voice/align.py` dùng triển khai Viterbi NumPy tự viết, không chép code
ctc-forced-aligner. Tham khảo recipe API tại
[ctc-forced-aligner@64293cc6](https://github.com/MahmoudAshraf97/ctc-forced-aligner/tree/64293cc6d711e57666c4a8b098e9fd93b381fd88)
(`alignment_utils.py`, `text_utils.py`; LICENSE upstream BSD-2-Clause, metadata cũ
có thể khác). Nhánh tiếng Việt dùng chuẩn hóa/bỏ dấu có sẵn, không chép uroman.
Weights `MahmoudAshraf/mms-300m-1130-forced-aligner` revision
`49402e9577b1158620820667c218cd494cc44486` dùng **CC-BY-NC-4.0**, chỉ nghiên cứu.
Wrapper đọc Transformers dependency Apache-2.0, không gọi mã remote hoặc mạng.
