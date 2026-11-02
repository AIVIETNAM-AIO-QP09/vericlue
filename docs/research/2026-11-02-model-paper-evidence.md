# Số liệu công bố cho các mô hình tích hợp trong VeriClue

**Đối chiếu ngày 02/11/2026; tài liệu bổ trợ DEMO-03.** Phạm vi chính là gói
Android/API `manual_full_demo` có source thực thi `7904d70`; mã ML/API khớp
nhánh tích hợp `06c9a7f`. Đây là **kết quả từ paper/model card/benchmark bên
ngoài**, không phải kết quả đánh giá của VeriClue.

## Phần có thể đưa vào báo cáo

VeriClue lựa chọn các thành phần nhận diện và phát hiện giả mạo dựa trên các
nghiên cứu công bố. Bảng dưới tổng hợp kết quả của tác giả cho đúng biến thể
mô hình liên quan, kèm bộ dữ liệu và giao thức. Các kết quả này cung cấp cơ sở
tham khảo khi lựa chọn thành phần; đánh giá pipeline VeriClue trên dữ liệu
tiếng Việt và thiết bị thực được trình bày riêng. Không lấy benchmark của mô
hình thành phần để công bố độ chính xác của toàn hệ thống.

### Mô hình chính trong gói demo hiện tại

Mọi giá trị ở cột kết quả đều là **phần trăm**; ↑ càng cao càng tốt, ↓ càng thấp
càng tốt. TAR phải đi kèm FAR; AUC không phải tỷ lệ lượt xác minh đạt.

| Mô hình và vai trò | Dữ liệu, thiết lập công bố | Kết quả tác giả báo cáo | Nguồn và vị trí |
|---|---|---|---|
| **FS-VFM ViT-L/16**, PAD | OCI→M: fine-tune trên OULU-NPU, CASIA-FASD, Idiap Replay-Attack; test MSU-MFSD; trung bình 5 runs | **HTER 2,00% ↓; AUC 99,50% ↑** | [P1, Table III, tr.12; §VI-C](https://arxiv.org/pdf/2510.10663v1#page=12) |
| **GenD CLIP ViT-L/14**, deepfake mặt | Train FF++ c23; video-level, 32 frames và trung bình softmax; hàng GenD (CLIP) | **AUROC ↑:** CDFv2 **96,0%**; DFD **97,0%**; DFDC **87,1%**; FFIW **92,8%** | [P2, Table 2, tr.5](https://arxiv.org/pdf/2508.06248v4#page=5) |
| **LVFace-B, Glint360K**, đối chiếu danh tính | IJB-C và IJB-B; **FAR = 10⁻⁴** | **TAR ↑:** IJB-C **97,70%**; IJB-B **96,51%** | [P3, Table 2, tr.8, hàng LVFace-B](https://arxiv.org/pdf/2501.13420v3#page=8) |
| **AntiDeepfake MMS-300M + RawBoost**, giọng giả | Zero-shot sau post-training; chưa fine-tune theo tập đích; ITW và Deepfake-Eval-2024 | **EER ↓:** ITW **2,90%**; DE-2024 **32,80%** theo paper; model card ghi DE-2024 **32,84%**, xem ghi chú dưới | [P4, Table II, tr.4, giá trị bên trái mỗi ô](https://arxiv.org/pdf/2506.21090v2#page=4); [card checkpoint ghim](https://huggingface.co/nii-yamagishilab/mms-300m-anti-deepfake/blob/7928e119e09f616b2ce698892e00ca22dbaa40bf/README.md#-performance-metrics) |
| **Qwen3-ASR-0.6B**, kiểm nội dung câu đọc | Tiếng Việt `vi`; FLEURS và MLC-SLM, đúng cột **0.6B** | **WER ↓:** FLEURS **8,52%**; MLC-SLM **17,67%** | [P5, Table A.2(b)/(a), tr.16](https://arxiv.org/pdf/2601.21337v1#page=16) |
| **StableSyncNet**, khớp môi–âm | Tác giả train trên VoxCeleb2, test ngoài miền trên HDTF | **Accuracy 94% ↑** của bài toán đồng bộ trong paper | [P6, §4, đoạn Discussions, tr.6](https://arxiv.org/pdf/2412.09262v2#page=6) |

**Giới hạn ánh xạ sang bản tích hợp:**

- FS-VFM hiện giữ một checkpoint **OCI→M `run_0`**. Số trong bảng là trung bình
  5 runs, không phải điểm riêng file đó. Tiền xử lý VeriClue dùng SCRFD thay
  MTCNN; chưa chứng minh tương đương benchmark. Không lấy trung bình nhiều
  giao thức FAS để gán cho một checkpoint.
- GenD model card nối checkpoint phát hành với **Table 2**. VeriClue chọn khung
  và gộp điểm phiên riêng, khác trung bình 32 frames; chưa tái hiện AUROC đó.
- LVFace dùng bản **B/Glint360K**, không lấy kết quả bản L/WebFace42M. TAR trên
  IJB không phải độ chính xác đối chiếu CCCD hoặc continuity mặt–giọng.
- AntiDeepfake có khác biệt giữa hai nguồn chính thức: **paper 32,80 / card
  32,84**. Giữ đúng nguồn khi trích, chưa có giải thích xác minh cho chênh lệch.
  Bản local chưa fine-tune DE-2024; không dùng số của bản đã fine-tune.
  Runtime thêm VAD, cửa sổ4 giây/hop1 giây và gộp mean logits, khác test nguyên
  thời lượng trong paper; đây cũng là lý do chưa coi EER paper là số local.
- Qwen dùng bản **0.6B HF-native**; số paper là của biến thể 0.6B. Thông báo
  tác giả cho biết HF-native phát hành sau technical report; chưa có bằng chứng
  benchmark/parity nối chính xác revision local với weights đã đo trong paper.
  WER không đo khả năng chống giọng giả.
- Gói dùng `stable_syncnet.pt` từ LatentSync1.6, không chạy bộ sinh video
  LatentSync. **94% không phải tỷ lệ phát hiện deepfake/eKYC** hoặc benchmark đã
  tái hiện cho checkpoint local. Crop, offset và luật gate của VeriClue khác.

### NES2Net là nhánh chẩn đoán, không phải bộ chấm giọng của manual demo

| Nguồn và biến thể | Dữ liệu/giao thức | EER công bố ↓ | Vị trí |
|---|---|---|---|
| **NES2Net-X/XLS-R-300M**, paper gốc, **single model, CKPT Avg.=N/A** | Train ASVspoof2019; ASVspoof2021 DF; best/mean qua các seed | **1,65% best; 1,91% mean** | [P7, Table V, tr.9](https://arxiv.org/pdf/2504.05657v2#page=9) |
| **Nes2NetX**, đánh giá độc lập Speech DF Arena | 14 tập/điều kiện; average theo benchmark và pooled với ngưỡng chung | **Average 16,11%; pooled 17,04%** | [P8, Table 3, tr.3](https://arxiv.org/pdf/2509.02859v1#page=3) |

README tác giả nối link **DF 1,65** với nguồn checkpoint single-model đang ghim.
Paper còn có cấu hình gộp checkpoint; không lấy số ITW **5,52%** của cấu hình
gộp 5 checkpoint để gán cho file single local. Arena không pin hash chứng minh
dùng đúng file local. Không so trực tiếp các EER trên hai tập/giao thức khác
nhau như một bảng xếp hạng chung. Pipeline cửa sổ/toàn câu của VeriClue vẫn
diagnostic; parity số học không xác nhận các EER này.
Đường `first4s` dùng64.000 mẫu, còn benchmark gốc64.600 mẫu; quy tắc gộp toàn
câu offline của nhóm cũng cần đánh giá riêng.

### Mô hình hỗ trợ và phần không có benchmark tương ứng

| Thành phần | Số công bố có thể dẫn | Phạm vi chính xác |
|---|---|---|
| **SCRFD-10GF**, paper | WIDER FACE validation, ảnh bị giới hạn kích thước640: **AP Easy/Medium/Hard = 95,16 / 93,87 / 83,05% ↑** | [P9, Table 4, tr.7](https://arxiv.org/pdf/2105.04714v1#page=7), hàng không KPS; không mặc định là số của file ONNX local |
| **SCRFD_10G_KPS**, repo tác giả | VGA: **AP Easy/Medium/Hard = 95,40 / 94,01 / 82,80% ↑** | [repo gốc, bảng Pretrained-Models](https://github.com/deepinsight/insightface/tree/master/detection/scrfd#pretrained-models); `_KPS` có dự đoán 5 điểm. Không trộn hai hàng |
| **MediaPipe Face Mesh V2** trong Face Landmarker | **IOD-normalized MAE ↓:** tracking **2,62%**, reacquisition **3,24%**, bộ đánh giá Google1.700 ảnh/17 vùng | [model card Google, tr.4 định nghĩa, tr.5 bảng tổng](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf#page=5). Đây là sai số landmark, không phải accuracy nhìn-chấm/quay-đầu/liveness |
| **MMS-300M forced aligner** | Chưa xác minh số sai số timestamp cho đúng checkpoint/giao thức tiếng Việt hiện dùng | [P10: MMS](https://arxiv.org/abs/2305.13516) là nguồn nền; [model card aligner](https://huggingface.co/MahmoudAshraf/mms-300m-1130-forced-aligner) mô tả bản chuyển từ TorchAudio. Không lấy WER ASR của MMS làm chất lượng căn chỉnh |
| **ML Kit Face Detection** trên Android | Không đưa một tỷ lệ accuracy chưa có nguồn cho đúng SDK vào bảng | [tài liệu Google](https://developers.google.com/ml-kit/vision/face-detection): hỗ trợ phát hiện/đặc trưng mặt, không phải xác minh danh tính |
| **CamProbe, luật gaze/head, ChromaPulse, router/LTT** | Không có benchmark paper nào được xác nhận là kết quả của các luật/pipeline VeriClue | Đo riêng bằng code/eval của nhóm; không gán độ chính xác landmark hoặc của detector khác cho các bước này |

File SCRFD local đã được đối chiếu byte với `buffalo_l/det_10g.onnx` trong
manifest. Chưa nối hash checkpoint với chính xác hàng benchmark KPS hay không
KPS nêu trên; các số đó chỉ mô tả **họ SCRFD**, không phải kết quả tái hiện.
Không lấy latency GPU trong paper để ghi tốc độ CPU/laptop hoặc thời gian toàn
phiên của VeriClue.

## Checkpoint và nguồn ánh xạ

Revision dưới đây xác định tài nguyên đang dùng, **không tự chứng minh tái hiện
benchmark**. Các prefix được giữ ngắn để đọc; SHA đầy đủ nằm ở file cấu hình liên kết.

| Thành phần | Tài nguyên/revision | Chỗ kiểm trong repo hoặc nguồn tác giả |
|---|---|---|
| FS-VFM-L | `Wolowolo/fsfm-3c@59f7b50a`, FAS `OCI2M/...run_0.pth.tar` | [manifest](../../models/manifest.yaml); [card ghim](https://huggingface.co/Wolowolo/fsfm-3c/blob/59f7b50a1865d53b0cc1c80ec620022c39b11c9a/README.md) |
| GenD CLIP L/14 | `yermandy/GenD_CLIP_L_14@891ce014` | [manifest](../../models/manifest.yaml); [card ghim nối Table 2](https://huggingface.co/yermandy/GenD_CLIP_L_14/blob/891ce014a0308386c4d7d25b3dcf436a22db5504/README.md) |
| LVFace-B | `bytedance-research/LVFace@b12702ab`, `LVFace-B_Glint360K.onnx` | [manifest](../../models/manifest.yaml); [README tác giả](https://github.com/bytedance/LVFace/blob/80bd20c8bb78e56eb708941180d800a27c396a6b/README.md#lvface-pretrained-models) |
| AntiDeepfake | `nii-yamagishilab/mms-300m-anti-deepfake@7928e119` | [model card local](../../ml/model_cards/antideepfake-mms300m.md); [cấu hình](../../ml/configs/models.yaml) |
| Qwen3-ASR-0.6B-hf | `Qwen/Qwen3-ASR-0.6B-hf@7f1569a4` | [cấu hình](../../ml/configs/qwen3_asr.yaml); [card ghim](https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf/blob/7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c/README.md); [news HF-native](https://github.com/QwenLM/Qwen3-ASR#news) |
| StableSyncNet | `ByteDance/LatentSync-1.6@c42c7e6c`, `stable_syncnet.pt` | [manifest](../../models/manifest.yaml); [card ghim](https://huggingface.co/ByteDance/LatentSync-1.6/blob/c42c7e6c8e9c213626389fa7d9a3c444b8536353/README.md) |
| CTC aligner | `MahmoudAshraf/mms-300m-1130-forced-aligner@49402e95` | [manifest](../../models/manifest.yaml), [căn chỉnh](../../ml/src/vericlue_ml/voice/align.py) |
| NES2Net-X/XLS-R | upstream `c9fe1177`, weights SHA `3158d10c…` | [cấu hình](../../ml/configs/nes2net.yaml); [README tác giả ghim](https://github.com/Liu-Tianchi/Nes2Net_ASVspoof_ITW/blob/c9fe1177f44040f002cb40def928332d2e261f1e/README.md) |
| SCRFD / Face Landmarker | SCRFD `bfcc7d48`; Landmarker task SHA `64184e22…` | [manifest](../../models/manifest.yaml), [cấu hình](../../ml/configs/models.yaml) |

`ml/configs/models.yaml` có cả đường mặc định, diagnostic và opt-in; cần đọc
cùng orchestrator/chế độ phiên. Trong manual full demo, AntiDeepfake thay đường
NES2Net diagnostic. MiniFASNet/PhoWhisper/AudioSeal còn có trong repo cho cấu hình
khác; không được ghi rằng chúng cùng chạy trong gói Android này. Bảng trên
không coi CLIP/XLS-R/MMS là các detector độc lập ngoài mô hình sử dụng chúng.

## GitHub đã có gì và chỗ cần cập nhật khi trích

Đã kiểm trực tiếp GitHub `main` tại commit
`7fc2ce9e9bb4e493f46e00cc103b75fab5d46cf3`:

- [Nghiên cứu server18/10](https://github.com/AIVIETNAM-AIO-QP09/vericlue/blob/7fc2ce9e9bb4e493f46e00cc103b75fab5d46cf3/docs/research/2026-10-18-models-server-sota.md#L80)
  đã có bảng GenD, LVFace, AntiDeepfake, Arena và nguồn paper.
- [Nghiên cứu on-device18/10](https://github.com/AIVIETNAM-AIO-QP09/vericlue/blob/7fc2ce9e9bb4e493f46e00cc103b75fab5d46cf3/docs/research/2026-10-18-models-on-device.md),
  [github-references](https://github.com/AIVIETNAM-AIO-QP09/vericlue/blob/7fc2ce9e9bb4e493f46e00cc103b75fab5d46cf3/docs/research/github-references.md)
  và [sources](https://github.com/AIVIETNAM-AIO-QP09/vericlue/blob/7fc2ce9e9bb4e493f46e00cc103b75fab5d46cf3/docs/research/sources.md)
  là nguồn tham khảo đã lên main, không chỉ nằm local. `sources` phục vụ bản
  proposal cũ, không dùng làm yêu cầu hiện hành.
- Lịch sử xác nhận tài khoản `AIVIETNAM-AIO-QP09` đưa hai file18/10 lên tại
  [commit baa2034](https://github.com/AIVIETNAM-AIO-QP09/vericlue/commit/baa2034773c55375bf03ad3be85309c647f1a864),
  có dòng đồng tác giả Claude. Chưa đủ căn cứ ánh xạ tài khoản thành người bạn
  cụ thể nào. [PR126](https://github.com/AIVIETNAM-AIO-QP09/vericlue/pull/126)
  chứa cập nhật demo mới hơn, vẫn Draft và chưa ở main tại lúc kiểm.

| Điểm trong tài liệu cũ | Cách dùng sau đối chiếu |
|---|---|
| GenD **91,2 / 94,6 / 86,4** | Đúng cho **Table 4**, kết quả trung bình5 seeds; không đổi thành số riêng checkpoint Table 2. Table S3 bổ sung độ lệch chuẩn. [P2, tr.6/15](https://arxiv.org/pdf/2508.06248v4#page=6) |
| AntiDeepfake **32,84** | Giữ được khi ghi nguồn **model card**; nếu ghi theo paper Table II dùng **32,80**, nêu khác biệt nguồn |
| Qwen trong nghiên cứu cũ là **1.7B** | Thay bằng hàng **0.6B** ở bảng chính khi mô tả runtime hiện tại; không lấy kết quả bản lớn hơn |
| Khoảng kết quả NES2Net/NES2Net-X gộp nhiều cấu hình | Tách single-model, checkpoint averaging, tập đánh giá và Arena; không chọn số thấp nhất để gán cho weights local |
| LVFace **97,70 / 96,51** | Ghi đủ **TAR@FAR=10⁻⁴**, đúng B/Glint360K |
| PAD/ASR theo đề xuất cũ | Đối chiếu FS-VFM-L/Qwen0.6B trong gói mới, không giữ nhãn MiniFASNet/PhoWhisper cho pipeline không dùng chúng |

## Tách khỏi kết quả thực nghiệm của nhóm

Số paper/model card ở trên đặt trong mục **“Cơ sở lựa chọn mô hình và kết quả
công bố”**. Mục **“Kết quả thực nghiệm VeriClue”** chỉ dùng phép đo của nhóm có
source commit, phiên bản, bộ dữ liệu/split, số mẫu và giao thức thực tế.

[Preflight](../status/results/APP-01-phone-demo-preflight-2026-11-01.json) chỉ
chứng minh suy luận/IPC và các chốt API chạy được, không phải đánh giá accuracy.
Ngưỡng demo vẫn chưa hiệu chỉnh; không thay dữ liệu hiệu chỉnh/LTT bằng số
paper, không fit trên VIVOS parity và không biến degraded/error thành đạt.
Ba luồng điện thoại của gói này chưa được nghiệm thu tại thời điểm lập tài liệu.

Không gọi EER, HTER, WER, AUC, TAR và AP chung là một cột “accuracy”. Không tự
quy đổi EER thành accuracy hoặc cộng/trung bình chỉ số khác nhiệm vụ thành một
“độ chính xác VeriClue”. Độ trễ/RAM cũng phải đo trên máy demo, không lấy số GPU
paper cho CPU và không lấy một lượt smoke làm p50/p95.

## Tài liệu tham khảo gốc

- **P1.** *Scalable Face Security Vision Foundation Model for Deepfake, Diffusion,
  and Spoofing Detection*. arXiv **2510.10663v1**,2025.
  [Paper](https://arxiv.org/abs/2510.10663v1).
- **P2.** *Deepfake Detection that Generalizes Across Benchmarks*. WACV2026;
  bản đối chiếu arXiv **2508.06248v4**,2026.
  [Paper](https://arxiv.org/abs/2508.06248v4).
- **P3.** *LVFace: Progressive Cluster Optimization for Large Vision Models in
  Face Recognition*. ICCV2025; arXiv **2501.13420v3**.
  [Paper](https://arxiv.org/abs/2501.13420v3).
- **P4.** *Post-training for Deepfake Speech Detection*. arXiv **2506.21090v2**,2025.
  [Paper](https://arxiv.org/abs/2506.21090v2).
- **P5.** *Qwen3-ASR Technical Report*. arXiv **2601.21337v1**,2026.
  [Paper](https://arxiv.org/abs/2601.21337v1). Dùng PDF vì bảng phụ lục cần thiết.
- **P6.** *LatentSync: Taming Audio-Conditioned Latent Diffusion Models for Lip
  Sync with SyncNet Supervision*. arXiv **2412.09262v2**,2025.
  [Paper](https://arxiv.org/abs/2412.09262v2).
- **P7.** *Nes2Net: A Lightweight Nested Architecture for Foundation Model Driven
  Speech Anti-spoofing*. arXiv **2504.05657v2**,2025.
  [Paper](https://arxiv.org/abs/2504.05657v2).
- **P8.** *Speech DF Arena: A Leaderboard for Speech DeepFake Detection Models*.
  arXiv **2509.02859v1**,2025. [Paper](https://arxiv.org/abs/2509.02859v1).
- **P9.** *Sample and Computation Redistribution for Efficient Face Detection*.
  arXiv **2105.04714v1**,2021; ICLR2022.
  [Paper](https://arxiv.org/abs/2105.04714v1).
- **P10.** *Scaling Speech Technology to 1,000+ Languages*. arXiv **2305.13516**,2023.
  [Paper](https://arxiv.org/abs/2305.13516). Nguồn nền MMS, không phải benchmark
  timestamp tiếng Việt của bản aligner tích hợp.

Nguồn model card Google, repository và checkpoint được đặt ngay cạnh từng
chỉ số/ánh xạ ở trên để phân biệt với số của paper. Không có phép fit hoặc đo
chất lượng mới nào được thực hiện trong lần tổng hợp tài liệu này.
