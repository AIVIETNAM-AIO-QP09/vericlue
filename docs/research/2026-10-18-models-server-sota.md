# Nghiên cứu mô hình SOTA cho VeriClue (server) — 18/10/2026

Phạm vi: chọn mô hình cho từng module, chạy ở server (RTX 4050 Laptop 6 GB, đang dùng ~4,4 GB → còn ~1,6 GB), mỗi bước ~4 giây, tinh chỉnh trên Kaggle, phải xong trước 06/11/2026.

Ký hiệu: **[XM]** = số đã kiểm ở nguồn (link ở cuối). **[SĐ]** = suy đoán/ước tính của người nghiên cứu, chưa chạy thử.
VRAM là ước tính từ số tham số (fp16 ≈ 2 byte/tham số, cộng phần kích hoạt) → luôn là [SĐ] trừ khi ghi khác.

Nguyên tắc: chỉ đổi khi có bằng chứng tốt hơn **rõ rệt** trên dữ liệu ngoài miền. Còn lại: giữ, và dồn công sức vào tinh chỉnh/hiệu chỉnh ngưỡng trên dữ liệu Việt Nam.

---

## 0. Bảng tổng hợp

| Module | Quyết định | Mô hình đề xuất | Giấy phép (trọng số) | VRAM ước tính | Mức chắc chắn |
|---|---|---|---|---|---|
| Face recognition 1:1 (MỚI) | Thêm | **AdaFace IR101 (WebFace4M hoặc 12M)** qua CVLFace; dự phòng sạch: **SFace (OpenCV Zoo)** | Code MIT; trọng số "theo giấy phép bộ dữ liệu huấn luyện" = WebFace → phi thương mại [SĐ]. SFace: Apache-2.0 [XM] | ~0,2–0,3 GB fp16 [SĐ] (65,2 M tham số [XM]); SFace ~0,05 GB, chạy CPU được | Cao |
| PAD (chống giả mạo trình diện) | Giữ MiniFASNet làm cổng nhanh + **thêm** bộ 2 tự tinh chỉnh | **DINOv2-reg ViT-B/14** (hoặc CLIP ViT-B/16) tinh chỉnh khối cuối trên CelebA-Spoof + Zalo 2022 + ảnh tự thu | DINOv2: Apache-2.0 [SĐ]; CelebA-Spoof: chỉ nghiên cứu phi thương mại [XM] | ~0,3 GB fp16 [SĐ] | Trung bình |
| Deepfake mặt | **Giữ** | GenD CLIP ViT-L/14 (giữ); không đổi sang PE/DINOv3 | MIT [XM] | ~2 GB (bài báo) [XM] | Cao |
| Giọng giả / anti-spoofing | **Giữ backbone, tinh chỉnh tiếng Việt** | AntiDeepfake MMS-300M + tinh chỉnh trên dữ liệu TTS tiếng Việt (SEA-Spoof, VietPrism, TTS tự sinh) | CC BY-NC-SA 4.0 [XM] | ~0,7 GB fp16 [SĐ] | Cao (về hướng), Trung bình (về kết quả) |
| ASR tiếng Việt (kiểm câu đọc) | **Giữ** | PhoWhisper-small (đã sửa lỗi lặp, VOICE-04); tùy chọn ChunkFormer-CTC-large-vie làm ý kiến thứ hai | Apache-2.0 [XM]; ChunkFormer CC BY-NC 4.0 [XM] | ~0,5 GB fp16 [SĐ]; ChunkFormer ~0,25 GB [SĐ] | Cao |
| Khớp môi / AV | **Giữ** | stable_syncnet (LatentSync 1.6) | OpenRAIL++ [XM] (không phải GPL, có điều khoản cấm dùng sai) | nhỏ [SĐ] | Trung bình–Cao |
| Dò mặt | **Giữ cho demo, ghi rõ giấy phép**; dự phòng sạch YuNet | SCRFD det_10g | insightface: "chỉ nghiên cứu phi thương mại" [XM]; YuNet: MIT [XM] | rất nhỏ | Cao |
| Căn chỉnh câu | **Giữ** | ctc-forced-aligner + mms-300m-1130-forced-aligner | Code BSD-2 [XM]; mô hình CC-BY-NC 4.0 [XM] | ~0,7 GB fp16 [SĐ] | Cao |
| Thủy vân âm thanh | **Giữ** | AudioSeal 0.2 | MIT (cả trọng số) [XM] | nhỏ [SĐ] | Cao |

---

## 1. Face recognition 1:1 (chưa có — cần thêm)

### Ứng viên

| Mô hình | Benchmark công bố | Tham số | Giấy phép | Ghi chú |
|---|---|---|---|---|
| **AdaFace IR101 – WebFace4M** (CVLFace, HF `minchul/cvlface_adaface_ir101_webface4m`) | IJB-B 96,10; IJB-C 97,46 (TAR@FAR=1e-4); TinyFace R1 72,13 [XM] | 65,2 M [XM] | Code MIT [XM]; model card: "follow the license of the training dataset" [XM] → WebFace260M phi thương mại (bản port Keras ghi rõ không dùng thương mại) [SĐ, chưa đọc được văn bản gốc của WebFace] | Đầu vào 112×112 RGB, chuẩn hóa 0,5/0,5 [XM]. Có code HF `from_pretrained` sẵn. TinyFace tốt → hợp ảnh chất lượng thấp (selfie điện thoại, ảnh CCCD). |
| AdaFace IR101 – WebFace12M | IJB-B 96,46; IJB-C 97,72 [XM] | ~65 M [SĐ] | như trên | Hơn bản 4M ~0,3 điểm IJB-C — không đáng kể. |
| AdaFace ViT-KPRPE – WebFace12M | IJB-B 96,55; IJB-C 97,82; TinyFace R1 76,10 [XM] | ~ViT-B [SĐ] | như trên | Cần landmark đầu vào (KP-RPE) → tích hợp phức tạp hơn. |
| **LVFace-B (ICCV 2025, ByteDance)** – Glint360K | IJB-C 97,70 @1e-4; IJB-B 96,51 [XM] | ~ViT-B [SĐ] | Code MIT nhưng **model: "non-commercial research purposes only"** [XM] | Có ONNX. Glint360K có tỉ lệ người châu Á cao [SĐ]. Hạng 1 MFR-Ongoing 2021 (academic) [XM]. |
| TransFace-L (ICCV 2023) – Glint360K | IJB-C 97,61 @1e-4 [XM] | — | **Không thấy LICENSE** trên trang repo [XM] → loại | |
| **SFace (OpenCV Zoo, MobileFaceNet)** | 0,9940 trên công cụ eval của OpenCV Zoo (README không ghi rõ bộ dữ liệu; khả năng là LFW) [XM số, SĐ bộ dữ liệu] | rất nhỏ | **Apache-2.0** [XM] | Phương án "giấy phép sạch" nếu ban giám khảo hỏi; yếu hơn nhiều so với AdaFace trên ảnh khó [SĐ]. |
| facenet-pytorch (InceptionResnetV1, VGGFace2) | LFW 99,65 [XM] | ~23 M [SĐ] | Code MIT [XM]; điều khoản dữ liệu VGGFace2 không ghi [XM] | Cũ (2018). |

**SOTA nhưng không dùng được / không nên:**
- insightface buffalo_l / antelopev2 (ArcFace R50@WebFace600K, R100@Glint360K): "ALL models are available for non-commercial research purposes only" [XM] — dùng được cho cuộc thi nếu ghi rõ, nhưng không hơn AdaFace và đúng là thứ nhóm muốn tránh.
- EdgeFace (Idiap): CC BY-NC-SA 4.0 [XM]; EdgeFace-XS: IJB-C 94,85 [XM] — yếu hơn AdaFace, giấy phép không sạch hơn.
- TransFace: không có LICENSE → loại theo ràng buộc 2.

**Số trên tập châu Á:** chưa tìm thấy số RFW-Asian công bố cho AdaFace/LVFace/TransFace (chưa có số công bố). Số cũ: ArcFace (CASIA, R34) RFW-Asian ~84,0% so với Caucasian ~92,2% [XM, bài 2018–2020] → khoảng cách chủng tộc có thật, phải **tự hiệu chỉnh ngưỡng** trên cặp ảnh người Việt (dev set chia theo người).

**Đề xuất:** AdaFace IR101-WebFace4M (hoặc 12M) làm mô hình chính, ghi rõ "trọng số phi thương mại do bộ dữ liệu WebFace". Đóng gói SFace (Apache-2.0) làm dự phòng sạch giấy phép. Chọn ngưỡng cosine trên tập dev người Việt (selfie ↔ ảnh CCCD), không trên tập test.

---

## 2. PAD (chống giả mạo trình diện)

Hiện tại: MiniFASNet V2 (Silent-Face, 0,43 M tham số [XM]) — yếu trên ảnh giả Zalo 2022 (theo nhóm).

### Tình hình 2025–2026
- Mô hình FAS khái quát hóa tốt nhất gần đây đều dựa trên **mô hình nền (foundation model)**: FLIP (CLIP, ICCV 2023), I-FAS/InstructFLIP (VLM, 2025), DADM (ICCV 2025).
- Benchmark 15 mô hình nền (CVPRW 2026, Tohoku): **DINOv2-with-registers** AUC trung bình cao nhất 96,25% (DINOv3 95,14%, CLIP 95,41%) [XM]. Baseline của họ (DINOv2-reg + augment): MICO HTER trung bình 7,63%, AUC 97,66% [XM]. **Code "Coming soon", không có trọng số** [XM].
- arXiv 2510.17201: DINOv2-reg ViT-B/14, chỉ huấn luyện khối encoder cuối [XM] — công thức đơn giản, hợp tinh chỉnh trên Kaggle.

### Ứng viên
| Mô hình | Trọng số công khai | Giấy phép | Ghi chú |
|---|---|---|---|
| MiniFASNet V1SE/V2 (yakhyo/face-anti-spoofing, ONNX) | Có [XM] | Apache-2.0 [XM] | Giữ làm cổng nhanh (CPU được). Không có số benchmark công bố trong repo [XM]. |
| **DINOv2-reg ViT-B/14, tinh chỉnh khối cuối (tự huấn luyện)** | Backbone có; head phải tự train | DINOv2 Apache-2.0 [SĐ – cần kiểm lại]; dữ liệu CelebA-Spoof chỉ nghiên cứu phi thương mại [XM]; Zalo 2022: chưa tìm được điều khoản [XM] | Đề xuất chính. ~86 M tham số → ~0,2–0,3 GB fp16 [SĐ]. |
| FLIP (CLIP ViT-B/16) | README trỏ tới model_zoo.md nhưng link 404 khi kiểm [XM] | **Không thấy LICENSE** [XM] → loại | |
| DADM (ICCV 2025) | Không có checkpoint, không có LICENSE [XM] → loại | | |
| LipFD/InstructFLIP/I-FAS | Không xác nhận được trọng số + giấy phép → loại | | |

**Đề xuất:** Giữ MiniFASNet ở bước đầu (lọc nhanh), **thêm** bộ phân loại DINOv2-reg ViT-B/14 tinh chỉnh khối cuối trên CelebA-Spoof + Zalo 2022 + ảnh tự thu bằng điện thoại (in giấy, màn hình, ảnh chụp lại màn hình Zalo). Đánh giá chéo bộ dữ liệu (train CelebA-Spoof → test Zalo) để chứng minh khái quát hóa. Kỳ vọng tốt hơn MiniFASNet rõ rệt trên ảnh Zalo [SĐ — phải đo].
Lựa chọn rẻ hơn [SĐ]: dùng chung CLIP ViT-L/14 đã nạp sẵn cho GenD? Không được — GenD đã chỉnh LayerNorm nên đặc trưng đã khác; cần backbone riêng.

---

## 3. Deepfake mặt

Hiện tại: GenD CLIP ViT-L/14 (WACV 2026, MIT).

Số từ bài GenD (huấn luyện FF++, AUROC video trung bình 14 bộ dữ liệu, bảng tái chạy cùng điều kiện) [XM]:

| Phương pháp | AUROC TB 14 bộ | CDFv2 | DFDC |
|---|---|---|---|
| ForAda (CLIP L/14) | 88,4 | 95,7 | 87,3 |
| Effort (CLIP L/14, ICML 2025) | 88,5 | 93,2 | 85,4 |
| **GenD CLIP** | **91,2** | 94,6 | 86,4 |
| GenD PE-L | 91,4 | 95,0 | 82,2 |
| GenD DINOv3-L | 91,6 | 92,5 | 85,6 |

- ViT-L ~304 M tham số, ~2 GB VRAM, ~120 khung/giây trên A100 [XM].
- Ba biến thể GenD chênh nhau ≤0,4 điểm trung bình — **không đáng đổi**. DINOv3 có giấy phép riêng của Meta [SĐ], PE-L thua rõ ở DFDC.
- Thực tế ngoài đời: Deepfake-Eval-2024 cho thấy mô hình mã nguồn mở giảm AUC ~50% (video), ~45% (ảnh); AUC tốt nhất của mô hình mở ~0,58 [XM]. Không có số GenD trên Deepfake-Eval-2024 (chưa có số công bố).
- Các bài 2025–2026 khác (FSFM + metric learning 2508.19730 — **đã rút bài** [XM]; hệ thống động 2607.13234 tự báo AUC 0,915 trên ảnh Deepfake-Eval-2024 [XM, tự báo cáo]) không có trọng số xác nhận.

**Đề xuất:** Giữ GenD CLIP. Việc đáng làm hơn đổi mô hình: tinh chỉnh LayerNorm thêm trên dữ liệu face-swap/reenactment kiểu eKYC (DF40 + video tự tạo bằng công cụ swap phổ biến trên người Việt) và hiệu chỉnh ngưỡng trên dev set người Việt. Effort giữ làm đối chứng.

---

## 4. Giọng giả / anti-spoofing

Hiện tại: AntiDeepfake MMS-300M (NII) — chấm giọng TTS tiếng Việt thất thường.

### Số công bố
Speech DF Arena (2025, 14 bộ dữ liệu, chỉ tiếng Anh + tiếng Trung) [XM]:

| Hệ thống mở | Tham số | EER TB (%) | EER gộp (%) |
|---|---|---|---|
| XLSR+SLS | 340 M | 13,84 | 15,68 |
| XLSR-Mamba | 319 M | 14,21 | 20,12 |
| TCM | 319 M | 15,77 | 16,35 |
| Nes2NetX | 318 M | 16,11 | 17,04 |
| Wav2Vec2-AASIST | 318 M | 18,02 | 19,47 |

AntiDeepfake (bài 2506.21090, zero-shot, có RawBoost) [XM]:

| Backbone | Tham số | ITW EER | Deepfake-Eval-2024 EER | TB 6 cột* |
|---|---|---|---|---|
| MMS-300M (đang dùng) | 317 M | 2,90 | 32,84 | 8,89 |
| MMS-1B | 965 M | 1,82 | 27,70 | 7,34 |
| XLS-R-1B | 965 M | 1,35 | 26,76 | 8,98 |
| XLS-R-2B | 2,2 B | 1,23 | 27,76 | 6,69 |

*trung bình do công cụ tóm tắt tính từ bảng, không phải bài báo công bố.
MMS-300M tinh chỉnh trên Deepfake-Eval-2024: EER 17,15% (4 s) → 10,79% (50 s) [XM].

### Tiếng Việt — bằng chứng then chốt
- **SEA-Spoof** (2025, 6 ngôn ngữ ĐNA gồm tiếng Việt): MoLEx zero-shot trên giả tiếng Việt từ hệ thương mại EER **48,50%** (≈ đoán mò), sau tinh chỉnh trên SEA-Spoof **0,01%** [XM]. Dữ liệu "phát hành cho nghiên cứu", link HF `Jack-ppkdczgx/SEA-Spoof` cần kiểm còn sống [XM].
- **VietPrism** (arXiv 2609.30005, 2026): 5 bộ phát hiện đa ngôn ngữ zero-shot; DFA-1B EER tăng 16,3% → 33,6% khi giọng giả càng giống người thật [XM]. Giấy phép dữ liệu chưa công bố [XM].
- **VSASV/VLSP 2025**: hệ thống tốt nhất EER 17,78% trên private test [XM] (bài toán xác minh người nói có chống giả, không hoàn toàn giống).
- Dataset HF `vietkemmai/Data_voice_AI_human_scam`: giọng thật + giả tiếng Việt, phi thương mại [XM].

→ Kết luận: vấn đề **không phải backbone** mà là **khác miền ngôn ngữ/TTS**. Đổi sang backbone lớn hơn chỉ giảm EER vài điểm trên dữ liệu khó (32,8 → ~27), trong khi tinh chỉnh trong miền tiếng Việt giảm hàng chục điểm (48,5 → 0,01 ở SEA-Spoof, dù con số này là trong miền).

### Ứng viên
| Mô hình | Giấy phép | VRAM fp16 | Đánh giá |
|---|---|---|---|
| **AntiDeepfake MMS-300M + tinh chỉnh tiếng Việt** | CC BY-NC-SA 4.0 [XM] | ~0,7 GB [SĐ] | Đề xuất. Repo có sẵn lệnh tinh chỉnh (lr 1e-6, RawBoost) [XM]; chạy được trên T4. |
| AntiDeepfake MMS-1B | CC BY-NC-SA 4.0 | ~2 GB [SĐ] → thêm ~1,3 GB so với 300M | Tốt hơn ~5 điểm EER trên DE-2024 zero-shot. **Không vừa** ngân sách VRAM khi còn ~1,6 GB và cần thêm FR + PAD. Chỉ cân nhắc nếu nạp theo yêu cầu (lazy load) cho chế độ giám định. |
| XLS-R-2B | CC BY-NC-SA 4.0 | ~4,5 GB [SĐ] | Không vừa VRAM. |
| XLSR+SLS | Repo gốc: chưa kiểm được LICENSE; bản HF tái hiện không chính thức ghi MIT [XM] | ~0,7 GB | Tốt nhất Arena (EN/ZH) nhưng nguồn trọng số không chính thức → không đổi. |

**Đề xuất:** Giữ MMS-300M; tinh chỉnh trên Kaggle với: (a) SEA-Spoof phần tiếng Việt, (b) giọng thật tiếng Việt (Common Voice vi, VIVOS, FLEURS vi), (c) giọng giả tự sinh bằng các TTS tiếng Việt mở mà kẻ gian có thể dùng; chia theo người nói; giữ một bộ TTS "chưa thấy" làm test ngoài miền.

---

## 5. ASR tiếng Việt (kiểm câu đọc)

Vietnamese Open ASR Leaderboard (HF, N-WER đã chuẩn hóa, trung bình các bộ "Natural") [XM, bảng do công cụ dựng lại từ trang]:

| Mô hình | N-WER Natural TB | Ghi chú |
|---|---|---|
| hynt/Zipformer-30M-RNNT-6000h | 6,77 | CC BY-NC-ND 4.0 [XM] |
| vinai/PhoWhisper-medium | 7,61 | Apache-2.0 [XM] |
| **vinai/PhoWhisper-small (đang dùng)** | 8,77 | Apache-2.0 [XM] |
| Qwen3-ASR-1.7B | 9,84 | |
| nvidia/parakeet-ctc-0.6b-Vietnamese | 12,81 | |

- PhoWhisper-large: WER 4,67 VIVOS, 8,14 CommonVoice-vi (bài báo) [XM].
- ChunkFormer-CTC-large-vie: 110 M, WER VIVOS 4,18 / CV 6,66 / VLSP T1 14,09; CC BY-NC 4.0 [XM].
- Lưu ý: PhoWhisper được huấn luyện có VIVOS/CV → số trên các bộ này có thể là trong miền [SĐ].

**Đề xuất:** Giữ PhoWhisper-small. Với bài toán "đọc đúng câu được giao", sai số 1–2 điểm WER không đổi kết quả nếu so khớp có dung sai. Điểm yếu thật của Whisper là **ảo giác/lặp** (đã xử lý ở VOICE-04). Nếu còn ảo giác: thêm ChunkFormer-CTC (CTC không sinh ảo giác kiểu tự hồi quy [SĐ]) làm ý kiến thứ hai — chỉ khi còn thời gian. Zipformer tốt nhất bảng nhưng CC BY-NC-ND (cấm phái sinh → không được tinh chỉnh) và cần k2/sherpa → không đáng.

---

## 6. Khớp môi / AV deepfake

- stable_syncnet (LatentSync 1.6): trang HF ghi giấy phép **openrail++** [XM] (cho phép dùng, kèm điều khoản cấm sử dụng sai; không phải copyleft). Không có số độ chính xác SyncNet trên model card [XM].
- AV-Deepfake1M++ challenge 2025: đội đứng đầu AUC 0,9783 phân loại video [XM]; dữ liệu giấy phép chỉ nghiên cứu [XM]; không xác nhận được trọng số mở của đội thắng.
- AVH-Align (CVPR 2025, huấn luyện chỉ trên video thật, dùng AV-HuBERT): không tìm thấy repo/trọng số/giấy phép chính thức [XM]; AV-HuBERT có giấy phép riêng phi thương mại của Meta [SĐ].
- LipFD (NeurIPS 2024): **không có LICENSE** [XM] → loại.

**Đề xuất:** Giữ stable_syncnet. Điểm khớp môi là tín hiệu bổ trợ cho thử thách đọc câu, không cần SOTA. Ghi "OpenRAIL++" trong third_party/README.

---

## 7. Dò mặt

| Mô hình | WIDER val (Easy/Med/Hard) | Giấy phép |
|---|---|---|
| SCRFD-10GF (đang dùng) | 95,16 / 93,87 / 83,05; 3,86 M tham số; 4,9 ms [XM] | insightface: **"ALL models … non-commercial research purposes only"** [XM] |
| YuNet (OpenCV Zoo) | 0,834/0,824/0,708 (phần giới thiệu) hoặc 0,884/0,866/0,750 (bảng eval) — README tự mâu thuẫn [XM] | MIT [XM]; bản 2026may có kích thước đầu vào động [XM] |

Với eKYC (một mặt to, chính diện), độ chính xác "Hard" ít quan trọng [SĐ].
**Đề xuất:** Giữ SCRFD cho demo, ghi rõ giấy phép phi thương mại. Chuẩn bị YuNet làm phương án sạch (đổi được trong 1 ngày [SĐ]).

---

## 8. Căn chỉnh câu

- ctc-forced-aligner: code BSD-2-Clause [XM]; mô hình mặc định `MahmoudAshraf/mms-300m-1130-forced-aligner` **CC-BY-NC 4.0** [XM], ~1130 ngôn ngữ, cần `--romanize` với mô hình đa ngôn ngữ [XM] (tiếng Việt sẽ mất dấu khi romanize → vẫn đủ cho mốc thời gian [SĐ]).
- Phương án [SĐ]: dùng ChunkFormer-CTC tiếng Việt (nếu đã thêm cho ASR) để căn chỉnh trực tiếp có dấu — chỉ khi đã tích hợp ChunkFormer.

**Đề xuất:** Giữ.

---

## 9. Thủy vân âm thanh

- AudioSeal: MIT cho cả code và trọng số (cập nhật 2024-04-02) [XM]; bản 0.2 (12/2024) hỗ trợ streaming [XM].
- Thay thế mới (DuraMark 2026, benchmark VoxWatermark 06/2026) chưa xác nhận trọng số/giấy phép [XM].

**Đề xuất:** Giữ AudioSeal.

---

## 10. Ngân sách VRAM [SĐ]

Đang dùng ~4,4 GB. Thêm: AdaFace IR101 fp16 ~0,2–0,3 GB + DINOv2-B PAD ~0,2–0,3 GB → ~5,0 GB. Còn ~1 GB đệm. **Không** còn chỗ cho MMS-1B (+1,3 GB) hay PhoWhisper-medium (+1 GB). Nếu thiếu: chạy SFace/MiniFASNet/YuNet trên CPU (ONNX), hoặc nạp mô hình giám định theo yêu cầu.

---

## 11. Rủi ro lớn nhất

1. **Giấy phép:** gần như mọi trọng số tốt nhất đều phi thương mại (insightface/SCRFD, AdaFace-WebFace, LVFace, EdgeFace, AntiDeepfake, MMS aligner, CelebA-Spoof, SEA-Spoof). Chấp nhận cho cuộc thi nhưng phải liệt kê trong third_party/README và báo cáo; chuẩn bị bộ "sạch" (SFace, YuNet, MiniFASNet Apache, AudioSeal MIT, PhoWhisper Apache, GenD MIT).
2. **Khác biệt miền Việt Nam:** giọng giả TTS tiếng Việt zero-shot ≈ đoán mò (EER 48,5% ở SEA-Spoof); FR có chênh lệch chủng tộc (RFW-Asian thấp hơn Caucasian ~8 điểm với ArcFace cũ); PAD MiniFASNet yếu trên Zalo. Bắt buộc có dev set người Việt chia theo người để chọn ngưỡng.
3. **Thời gian (19 ngày):** chỉ đủ cho 1 tích hợp mới (FR) + 2 lần tinh chỉnh (giọng giả tiếng Việt, PAD). Không đổi GenD/ASR/SyncNet/AudioSeal.
4. **VRAM 6 GB:** thêm FR + PAD đưa tổng lên ~5 GB [SĐ]; phải đo thực tế, dùng fp16, đẩy mô hình nhỏ sang CPU khi cần.
5. **Dữ liệu tinh chỉnh chưa chắc tải được:** SEA-Spoof ghi "will be available", VietPrism chưa có giấy phép, điều khoản Zalo 2022 chưa rõ → cần phương án tự sinh dữ liệu TTS tiếng Việt và tự thu ảnh tấn công.

---

## Nguồn

Face recognition
- AdaFace repo (MIT, bảng IJB): https://github.com/mk-minchul/AdaFace
- CVLFace (bảng IR101/ViT, link HF): https://github.com/mk-minchul/CVLface
- Model card AdaFace IR101 WebFace4M: https://huggingface.co/minchul/cvlface_adaface_ir101_webface4m
- AdaFace paper: https://arxiv.org/abs/2204.00964
- Keras_insightface (ghi chú WebFace phi thương mại): https://github.com/leondgarse/Keras_insightface
- LVFace: https://github.com/bytedance/LVFace , https://arxiv.org/abs/2501.13420
- TransFace: https://github.com/DanJun6737/TransFace
- EdgeFace: https://huggingface.co/Idiap/EdgeFace-Base
- SFace OpenCV Zoo: https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/README.md
- facenet-pytorch: https://github.com/timesler/facenet-pytorch
- insightface model zoo (giấy phép): https://github.com/deepinsight/insightface/tree/master/model_zoo
- RFW: https://arxiv.org/abs/1812.00194

PAD
- FAS VFM benchmark CVPRW 2026: https://gsisaoki.github.io/FAS-VFMbenchmark-CVPRW2026/
- DINOv2-reg cho FAS: https://arxiv.org/abs/2510.17201
- FLIP: https://github.com/koushiksrivats/FLIP
- DADM: https://github.com/yjyddq/DADM
- InstructFLIP: https://arxiv.org/abs/2507.12060
- MiniFASNet ONNX: https://github.com/yakhyo/face-anti-spoofing
- CelebA-Spoof: https://github.com/Davidzhangyuanhan/CelebA-Spoof , https://mmlab.ie.cuhk.edu.hk/projects/CelebA/CelebA_Spoof.html

Deepfake mặt
- GenD: https://github.com/yermandy/GenD , https://arxiv.org/abs/2508.06248 , https://huggingface.co/collections/yermandy/gend
- Deepfake-Eval-2024: https://arxiv.org/abs/2503.02857
- DF40: https://github.com/YZY-stack/DF40
- 2508.19730 (đã rút): https://arxiv.org/abs/2508.19730
- 2607.13234: https://arxiv.org/abs/2607.13234

Giọng giả
- AntiDeepfake: https://github.com/nii-yamagishilab/AntiDeepfake , https://huggingface.co/nii-yamagishilab/mms-300m-anti-deepfake , https://arxiv.org/abs/2506.21090
- Speech DF Arena: https://arxiv.org/abs/2509.02859
- SEA-Spoof: https://arxiv.org/abs/2509.19865 , https://huggingface.co/datasets/Jack-ppkdczgx/SEA-Spoof
- VietPrism: https://arxiv.org/abs/2609.30005
- VSASV/VLSP 2025: https://preview.aclanthology.org/anlp-naacl/2025.vlsp-1.12.pdf , https://jcsce.vnu.edu.vn/index.php/jcsce/article/view/6492
- Dataset giọng giả VN: https://huggingface.co/datasets/vietkemmai/Data_voice_AI_human_scam
- XLSR-SLS (bản HF không chính thức): https://huggingface.co/sukhdeveyash/XLS-R-SLS-Deepfake-Detection

ASR / căn chỉnh
- PhoWhisper: https://github.com/VinAIResearch/PhoWhisper , https://arxiv.org/abs/2406.02555
- Vietnamese Open ASR Leaderboard: https://vietaudio-team-vietnamese-asr-leaderboard.hf.space/
- ChunkFormer: https://huggingface.co/khanhld/chunkformer-ctc-large-vie
- Zipformer-30M: https://huggingface.co/hynt/Zipformer-30M-RNNT-6000h
- ctc-forced-aligner: https://github.com/MahmoudAshraf97/ctc-forced-aligner

Khớp môi / AV
- LatentSync 1.6: https://huggingface.co/ByteDance/LatentSync-1.6
- AV-Deepfake1M++: https://arxiv.org/abs/2507.20579
- AVH-Align: https://arxiv.org/abs/2412.00175
- LipFD: https://github.com/AaronComo/LipFD

Dò mặt / thủy vân
- SCRFD: https://github.com/deepinsight/insightface/tree/master/detection/scrfd
- YuNet: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- AudioSeal: https://github.com/facebookresearch/audioseal
- AudioMarkBench: https://arxiv.org/abs/2406.06979
