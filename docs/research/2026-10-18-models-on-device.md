# Nghiên cứu: mô hình chạy trên điện thoại (on-device) cho VeriClue

Ngày: 18/10/2026. Chỉ nghiên cứu, không sửa repo.

**Cách đọc:** [XM] = đã xác minh từ nguồn trong phiên này (có link ở mục Nguồn). [SĐ] = suy đoán hoặc kiến thức chung, chưa kiểm lại. "Chưa có số công bố" = không tìm thấy số đo trên điện thoại.

---

## 0. Kết luận nhanh

1. **Không nên chuyển quyết định giả/thật xuống điện thoại.** Kẻ tấn công nắm thiết bị (camera ảo, hook API camera, sửa JS). Kết quả từ client chỉ là "gợi ý", server phải tính lại. Đây cũng là điều ADR-0003 và luật §6.3 đang làm.
2. **Nên chạy ở client** (đa phần đã làm): dò mặt + mốc mặt (MediaPipe), kiểm chất lượng ảnh, hướng dẫn chụp, VAD (phát hiện có tiếng nói), có thể thêm tiền lọc PAD rất nhẹ để báo "chụp lại" sớm. Tất cả **chỉ cải thiện trải nghiệm**, không dùng để cho "đạt".
3. **Bắt buộc ở server:** deepfake mặt (GenD), giọng giả (AntiDeepfake), ASR kiểm câu đọc, căn câu, khớp môi, thủy vân, và PAD quyết định cuối.
4. **Mô hình "trên điện thoại" tốt nhất hiện có cho từng việc** (nếu sau này cần): BlazeFace/YuNet (dò mặt), MiniFASNet-V2-SE ONNX 600 KB (PAD tiền lọc), Moonshine-tiny-vi 27M hoặc Zipformer-vi 30M (ASR) — nhưng **giấy phép** của hai mô hình ASR này không dùng được cho sản phẩm thương mại / chưa rõ; PhoWhisper-tiny/base (BSD-3) là lựa chọn an toàn giấy phép nhưng WER kém hơn. Deepfake mặt và giọng giả **chưa có** mô hình nhỏ nào vừa tổng quát hóa tốt vừa có giấy phép rõ.

---

## 1. Bảng tổng hợp theo module

| Module | Hiện tại (server) | Khuyến nghị | Ứng viên on-device tốt nhất | Giấy phép | Mức chắc chắn |
|---|---|---|---|---|---|
| Dò mặt + mốc mặt | SCRFD det_10g | **Hybrid** (đã làm): client MediaPipe để hướng dẫn; server dò lại | MediaPipe BlazeFace / Face Landmarker; YuNet (75k tham số) | MediaPipe: Apache-2.0 (gói npm; model card cần kiểm lại). YuNet: MIT. SCRFD/insightface: **chỉ nghiên cứu phi thương mại** | Cao |
| Chất lượng ảnh | luật trên SCRFD | **Client** (gợi ý) + server kiểm lại | Luật trên mốc MediaPipe (độ sáng, mờ Laplacian, kích cỡ mặt, góc) — không cần mô hình | — | Cao |
| PAD (in/màn hình) | MiniFASNet V2 | **Hybrid**: tiền lọc nhẹ ở client (chỉ để báo "chụp lại"); quyết định ở server | MiniFASNet V2-SE ONNX (suriAI, 600 KB INT8); MobileNetV3 (kprokofi fork); server nâng cấp: DINOv2-reg ViT-B | MiniFASNet: Apache-2.0; suriAI: Apache-2.0; DINOv2: Apache-2.0 (code/trọng số Meta) [SĐ cho DINOv2] | Trung bình (chưa có số cross-dataset/người Việt) |
| Deepfake mặt | GenD CLIP-L/14 (304M) | **Giữ server** | Không có ứng viên đủ tốt. Tham khảo: Tiny-LaDeDa (chưa có code), DeFakeQ (chưa có code), MobileCLIP-S2 + linear probe kiểu GenD (phải tự huấn luyện) | GenD code + trọng số: MIT (theo manifest repo). MobileCLIP trọng số: Apple ML Research Model Terms | Cao (giữ server) |
| Giọng giả | AntiDeepfake MMS-300M | **Giữ server** | Wav2Vec2-Small-AntiDeepfake (95M); AASIST-L (85k tham số, nhưng tổng quát hóa kém); XLS-R cắt còn 7 lớp (~101M) chạy trong trình duyệt | AntiDeepfake trọng số: CC BY-NC-SA 4.0; AASIST: MIT; Nes2Net: Apache-2.0 | Cao (giữ server) |
| ASR kiểm câu đọc | PhoWhisper (small) | **Giữ server**; tùy chọn client cho phản hồi tức thời | Moonshine-tiny-vi (27M); sherpa-onnx Zipformer-vi-30M (32 MB INT8); PhoWhisper-tiny/base | Moonshine-vi: "other" (chưa rõ); Zipformer-30M: **CC BY-NC-ND 4.0**; PhoWhisper: BSD-3 | Trung bình |
| Căn câu (forced alignment) | ctc-forced-aligner (MMS) | **Giữ server** | Lấy dấu thời gian từ Zipformer/Moonshine (không cần mô hình riêng) [SĐ] | — | Trung bình |
| Khớp môi | SyncNet (LatentSync) | **Giữ server**; client chỉ thu mốc môi | Đặc trưng mốc môi MediaPipe + bộ phân loại nhỏ (BioLip, KLASSify-TCN 124k) — để nghiên cứu, chưa dùng | LatentSync code Apache-2.0, trọng số OpenRAIL++ (theo third_party) | Trung bình-thấp |
| Thủy vân âm thanh | AudioSeal | **Giữ server** (vô nghĩa nếu kiểm ở client) | — | AudioSeal code + trọng số: MIT | Cao |

---

## 2. Chi tiết từng module

### 2.1 Dò mặt và mốc mặt

| Ứng viên | Kích thước | Định dạng | Độ trễ điện thoại | Benchmark | Giấy phép | Ghi chú |
|---|---|---|---|---|---|---|
| MediaPipe BlazeFace short-range | đầu vào 128×128, float16; không công bố dung lượng | TFLite (.task), chạy Web/Android/iOS | **2,94 ms CPU / 7,41 ms GPU, Pixel 6** [XM] | không ghi trên trang | Mã: Apache-2.0; model: cần kiểm model card | Web của nhóm đã dùng Face Landmarker (CAP-03) |
| MediaPipe Face Landmarker (float16 v1) | 3,76 MB (theo `third_party/README.md`) | .task | chưa có số trong phiên này | — | Apache-2.0 theo Google, **cần kiểm lại** (đã ghi trong repo) | Cho 478 mốc → dùng cho chất lượng, ChromaPulse, môi |
| YuNet (OpenCV Zoo) | ~75k tham số [XM, nguồn Luxonis] | ONNX | chưa có số công bố | WIDER Face AP easy/medium/hard ≈ 0,83–0,88 / 0,82–0,87 / 0,71–0,75 (số khác nhau giữa các phiên bản) [XM] | **MIT** [XM] | Thay thế SCRFD khi cần giấy phép sạch |
| SCRFD-500M / 2.5G (insightface) | nhỏ | ONNX | chưa có số | — | **"ALL models ... non-commercial research purposes only"** [XM] | Chỉ dùng cho demo nghiên cứu; nếu thương mại hóa phải thay |

**Khuyến nghị:** giữ như hiện tại (client MediaPipe, server SCRFD). Ghi rủi ro giấy phép SCRFD (đã ghi trong repo); phương án thay là YuNet (MIT) hoặc MediaPipe ở server.

### 2.2 Chất lượng ảnh
Không cần mô hình học sâu. Luật trên mốc MediaPipe (độ sáng vùng mặt, độ nét Laplacian, mặt chiếm bao nhiêu khung, góc yaw/pitch, mắt mở) chạy tốt trên mọi điện thoại. Client làm để hướng dẫn ngay; server tính lại để chống client gian lận. [SĐ: thực hành chung, không cần số]

### 2.3 PAD (ảnh in / màn hình)

| Ứng viên | Kích thước | Định dạng | Độ trễ điện thoại | Benchmark | Giấy phép |
|---|---|---|---|---|---|
| MiniFASNetV2 (minivision) | 0,435M tham số, 0,081 GFLOPs [XM] | PyTorch (cộng đồng có ONNX) | **~19 ms Kirin 990 5G, 24 ms Snapdragon 845, 90 ms RK3288** [XM] | Nhà phát triển tự báo TPR 97,8% @ FPR 1e-5 (bộ dữ liệu nội bộ, không công khai) [XM] | Apache-2.0 [XM] |
| suriAI/face-antispoof-onnx (MiniFASNet V2-SE huấn luyện trên CelebA-Spoof) | 1,82 MB ONNX; **~600 KB INT8** [XM] | ONNX (chạy được ONNX Runtime Web [SĐ]) | chưa có số công bố | CelebA-Spoof: acc 98,2%, AUC 0,9984 (cùng bộ, **không có cross-dataset**) [XM] | Apache-2.0 [XM] |
| Custom-Lightweight-FAS (MobileNetV3, CelebA-Spoof) | nhỏ [SĐ] | ONNX | chưa có số | — | chưa kiểm |
| DINOv2-with-registers ViT-B/14 (Tohoku, CVPRW 2026) | ~86–87M | PyTorch | không phải mô hình điện thoại | MICO trung bình AUC 96,25% (DINOv2-reg) so với MobileViT 91,36%, EfficientFormer 88,35%, DeiT-tiny 76,56% [XM] | Bài báo không ghi code/trọng số; DINOv2 gốc Apache-2.0 [SĐ] |

**Nhận xét:**
- Bài benchmark Tohoku cho thấy rõ: **mô hình nhỏ tổng quát hóa kém hơn** (DeiT-tiny 76,6% vs DINOv2-reg 96,3% AUC). Đây là lý do khách quan để PAD quyết định nằm ở server.
- MiniFASNet đã yếu với ảnh giả Zalo khi nhóm thử tay → hướng nâng cấp server: DINOv2-reg ViT-B (hoặc CLIP ViT-B kiểu FLIP — nhưng **repo FLIP không có file LICENSE** [XM], nên chỉ tham khảo ý tưởng).
- Không có ứng viên nào báo kết quả trên người Việt / châu Á. CelebA-Spoof chủ yếu là người nổi tiếng. **Phải tự đo trên dữ liệu nhóm.**

**Khuyến nghị:** Hybrid. Client chạy MiniFASNet INT8 (≈600 KB) chỉ để nói "ảnh chưa rõ, chụp lại" (đúng luật §6.3, không nói "giả mạo"); server chạy lại PAD và quyết định. Có thể bỏ qua nếu thời gian ít — lợi ích chủ yếu là UX.

### 2.4 Deepfake khuôn mặt

| Ứng viên | Kích thước | Định dạng | Độ trễ điện thoại | Benchmark | Giấy phép |
|---|---|---|---|---|---|
| GenD CLIP-L/14 (hiện tại) | ~304M (encoder ViT-L); chỉ tinh chỉnh LayerNorm 0,03% | PyTorch | không hợp điện thoại; ~120 khung/s trên A100, ~2 GB VRAM [XM] | **AUROC trung bình 91,2% trên 14 bộ cross-dataset** [XM] | Code MIT [XM]; trọng số MIT (theo manifest repo) |
| GenD bản backbone nhỏ | — | — | — | **Không tồn tại**: bài báo chỉ có 3 encoder cỡ ViT-L (CLIP-L, PE-L, DINOv3-L) [XM] | — |
| MobileCLIP / MobileCLIP2 (Apple) + đầu GenD tự huấn luyện | S0: 11,4M (ảnh); S2: 35,7M; B: 86,3M [XM] | PyTorch; Apple có CoreML [SĐ] | S0 1,5 ms; S2 3,6 ms; B 10,4 ms (bảng không nêu thiết bị; iPhone 12 Pro Max chỉ nêu cho S4) [XM] | Chỉ ImageNet zero-shot; **chưa ai báo deepfake** | Code MIT; **trọng số: Apple ML Research Model Terms** (cần đọc kỹ) [XM] |
| SBI (EfficientNet-B4, dự phòng hiện tại) | ~19M [SĐ] | PyTorch | chưa có số | CDF 93,8%, DFDC 73,0%, FFIW 84,5% (AUC, FF-raw) [XM] | **Chỉ nghiên cứu; thương mại phải xin phép** [XM] |
| DeFakeQ (lượng tử hóa DeiT/ViT/Swin) | Swin-B 334,8 MB → 31,8 MB [XM] | — | 25 ms/khung, 87 mW "Android" (không nêu máy; bài có số 35–50 ms ở chỗ khác) [XM] | Độ chính xác cross-dataset giảm rõ (vd. DFD 86,7% → 78,1% với ViT-B) [XM] | **Không thấy code/trọng số** |
| Tiny-LaDeDa | 4 lớp conv; ít hơn LaDeDa 10.000× tham số [XM] | — | "chạy được edge" (không có số) | WildRF mAP 93,7% (LaDeDa); ảnh do AI tạo, không phải hoán mặt video [XM] | Code "coming soon" — chưa có |

**Nhận xét:** Chưa có mô hình deepfake mặt nhỏ nào vừa (a) có trọng số + giấy phép dùng được, (b) có số cross-dataset gần GenD. Lượng tử hóa làm tụt độ chính xác rõ (DeFakeQ). Hơn nữa, đưa detector xuống client giúp kẻ tấn công **có sẵn oracle** để tối ưu deepfake vượt qua (xem §3).

**Khuyến nghị:** **Giữ server.** Nếu muốn có phương án nhẹ cho server (CPU), thử GenD-style (chỉ tinh chỉnh LayerNorm + chuẩn hóa L2) trên CLIP ViT-B/16 (OpenAI CLIP, MIT) — đây là việc thử nghiệm, chưa có số công bố.

### 2.5 Giọng giả (anti-spoofing)

| Ứng viên | Kích thước | Định dạng | Độ trễ | Benchmark (EER, thấp là tốt) | Giấy phép |
|---|---|---|---|---|---|
| AntiDeepfake MMS-300M (hiện tại) | 0,3B | PyTorch | server | In-the-Wild 2,90%, FakeOrReal 1,40%, ADD2023 7,93%, Deepfake-Eval-2024 32,84% [XM] | Trọng số **CC BY-NC-SA 4.0** [XM]; code BSD-3 (theo repo) |
| AntiDeepfake Wav2Vec2-Small | 95M (F32 ≈ 380 MB [SĐ: 95M×4 byte]) | PyTorch (HF) | chưa có số | model card nhỏ không có bảng so sánh tôi đọc được | CC BY-NC-SA 4.0 (theo bên thứ ba, chưa kiểm trực tiếp) |
| XLS-R-300M cắt ở lớp 7 + 1 lớp tuyến tính, **chạy trong trình duyệt** (ONNX Runtime Web, 1 nhân CPU) | ~101M | ONNX | **5 s âm thanh mất ~3,4 s (Ryzen 7 7800X3D), ~4,2 s (i3-1215U)**; ~1 GB RAM — **máy tính, không phải điện thoại** [XM] | Ngoài miền trung bình 8,4%; In-the-Wild 6,6% [XM] | Code công khai trên GitHub; trọng số/giấy phép không nêu [XM]; XLS-R gốc Apache-2.0 [SĐ] |
| AASIST / AASIST-L | AASIST-L: **85.306 tham số** [XM] | PyTorch | chưa có số | ASVspoof2019 LA: AASIST 0,83%, AASIST-L 0,99% [XM]. Nhưng mô hình huấn luyện trên ASVspoof2019 **tổng quát hóa rất kém** ra dữ liệu thật (EER tăng tới ~1000%, Müller 2022) [XM] | MIT [XM] |
| Nes2Net / Nes2Net-X (back-end) + XLS-R-300M | back-end **511k** tham số; front-end vẫn ~300M [XM] | PyTorch | — | ASVspoof21 DF 1,49–1,89%; In-the-Wild 5,15–5,80% [XM] | Apache-2.0 [XM] |

**Nhận xét:** Phần nặng là front-end SSL (wav2vec2/XLS-R ≥ 95M). Bản nhỏ thật sự (AASIST-L) không tổng quát hóa. Bản trình duyệt tốt nhất (XLS-R cắt 7 lớp) cần ~1 GB RAM và gần 1 giây xử lý cho mỗi giây âm thanh **trên máy tính để bàn** → trên điện thoại tầm trung chắc chắn chậm hơn [SĐ]. Không mô hình nào huấn luyện trên tiếng Việt (AntiDeepfake không có tiếng Việt trong dữ liệu huấn luyện [XM]).

**Khuyến nghị:** **Giữ server.** Nếu muốn nhẹ server: thử Nes2Net-X (Apache-2.0) làm đối chứng; Wav2Vec2-Small-AntiDeepfake nếu GPU thiếu (vẫn NC).

### 2.6 ASR tiếng Việt (kiểm câu đọc)

| Ứng viên | Tham số / dung lượng | Định dạng | Độ trễ | WER tiếng Việt | Giấy phép |
|---|---|---|---|---|---|
| PhoWhisper-tiny | 39M | HF Transformers (có thể xuất ONNX [SĐ]) | chưa có số điện thoại | CMV-Vi 19,05; VIVOS 10,41; VLSP2020-T1 20,74 [XM] | **BSD-3** [XM] |
| PhoWhisper-base | 74M | như trên | chưa có số | CMV-Vi 16,19; VIVOS 8,46; VLSP2020-T1 19,70 [XM] | BSD-3 |
| PhoWhisper-small (hiện tại) | 244M | — | server | CMV-Vi 11,08; VIVOS 6,33; VLSP2020-T1 15,93 [XM] | BSD-3 |
| Moonshine-tiny-vi | **27,1M** | safetensors F32; có 6 bản lượng tử [XM]; Moonshine có runtime ONNX [SĐ] | "nhanh hơn Whisper 5–15×" (không nêu máy) [XM] | CV17 18,83; Fleurs 13,01 (Whisper-medium: 23,54 / 13,45) [XM] | **"other" — chưa rõ** (model card) [XM]; Moonshine có "community license" hạn chế thương mại [SĐ, cần kiểm] |
| sherpa-onnx Zipformer-vi-30M (hynt) | ~30M; **~32 MB INT8** [XM] | ONNX, sherpa-onnx (Android/iOS; có WASM [SĐ]) | CPU 0,3 s cho 12 s âm thanh (CPU máy chủ HF, không phải điện thoại) [XM] | VLSP2020-T1 12,29; VLSP2023-Private 11,10; GigaSpeech2 7,56 [XM] | **CC BY-NC-ND 4.0** [XM] — cấm phái sinh, không thương mại |
| sherpa-onnx Zipformer-vi (2025-04-20, ~70k giờ) | 74 MB INT8 / 259 MB F32 [XM] | ONNX | chưa có số | không ghi trên trang sherpa | **chưa rõ** |
| Whisper-base qua transformers.js (onnx-community) | 74M | ONNX cho trình duyệt [XM] | chưa có số | Whisper gốc tiếng Việt rất kém ở cỡ nhỏ (base: CV17 59,5%) [XM] | MIT (Whisper gốc) [SĐ] |

**Nhận xét:** Về chất lượng/kích thước, **Moonshine-tiny-vi và Zipformer-vi-30M vượt PhoWhisper-tiny/base** và gần PhoWhisper-small. Nhưng: giấy phép Zipformer-30M là NC-ND; Moonshine-vi giấy phép chưa rõ. PhoWhisper-tiny/base là lựa chọn giấy phép sạch duy nhất. Lưu ý quan trọng: ASR ở client **không chống được tấn công** (kẻ tấn công sửa JS để báo "đọc đúng"); chỉ dùng để báo người dùng "đọc lại" sớm.

**Khuyến nghị:** Giữ PhoWhisper ở server làm quyết định. Tùy chọn (nếu dư thời gian, sau demo): client chạy ASR nhỏ chỉ để phản hồi tức thì. Có thể thử Zipformer-vi-30M ở server làm đối chứng nghiên cứu (nhanh hơn nhiều) — chú ý NC-ND.

### 2.7 Căn câu (forced alignment)
MMS-300M aligner nặng. On-device thì lấy dấu thời gian từng từ từ ASR transducer (Zipformer có token timestamps) [SĐ]. Không có lý do chuyển xuống client. **Giữ server.**

### 2.8 Khớp môi (lip-sync)
- Hướng nhẹ có trong tài liệu: **BioLip** (2026) dùng 64 mốc quanh môi MediaPipe, ~4,4 ms MediaPipe + 0,39 ms bộ phân loại / cửa sổ trên CPU, không dùng âm thanh [XM]; **KLASSify** dùng đặc trưng hình học miệng (MAR, vận tốc…) + TCN 124k tham số, ghép với đặc trưng âm thanh SSL [XM]. Chưa kiểm code/giấy phép.
- Client có thể **gửi chuỗi mốc môi** (đã có MediaPipe) cùng video; server vẫn tính SyncNet trên video thật và so khớp với mốc client (giống cờ `client_server_mismatch` của ChromaPulse).
- **Giữ server.** Không đưa SyncNet xuống điện thoại.

### 2.9 Thủy vân âm thanh (AudioSeal)
Code + trọng số MIT; có detector streaming; không có ONNX/mobile chính thức [XM]. Kiểm thủy vân ở client vô nghĩa về an ninh (kẻ tấn công xóa kết quả). **Giữ server.**

---

## 3. Phân tích an ninh: chạy phát hiện giả ở client có an toàn không?

**Mô hình đe dọa eKYC:** kẻ tấn công kiểm soát hoàn toàn thiết bị: camera ảo, hook API camera (Frida), giả lập/root, sửa JS trong trình duyệt, chặn và sửa request API. Đây là **tấn công tiêm (injection)**, khác với tấn công trình diện (PAD). ISO/IEC 30107-3 chỉ đo PAD; tiêm được chuẩn hóa riêng ở **CEN/TS 18099** (CEN phê duyệt 13/10/2024) [XM].

**Hệ quả khi chạy detector ở client:**
1. **Kết quả có thể bị sửa.** Mọi "đạt" tính ở client đều giả được bằng một dòng JS. → Client không bao giờ được quyết định. [XM: Signzy báo Frida hook camera vượt cả liveness thụ động và chủ động — nguồn nhà cung cấp, chưa kiểm độc lập]
2. **Lộ mô hình = cho kẻ tấn công oracle.** Mô hình tải về trình duyệt có thể trích ra và dùng để tối ưu deepfake/tấn công đối kháng cho tới khi qua. Với server, kẻ tấn công chỉ thấy `pass/retry/review` và bị giới hạn số lần. [SĐ — lập luận chuẩn về adversarial ML, chưa có nguồn cụ thể trong phiên]
3. **Detector ở client không thấy được tiêm.** Nếu khung hình đã bị thay ở tầng camera, mô hình client chỉ đang chấm điểm khung giả.

**Chạy ở client thì phù hợp cho:** dò mặt, mốc mặt, chất lượng ảnh, hướng dẫn chụp, VAD, đo ChromaPulse (đang làm, và server tính lại), tiền lọc PAD để báo "chụp lại". Lợi ích: phản hồi tức thì, giảm upload ảnh xấu, giảm tải server. Điều kiện: server **luôn tính lại** và coi lệch client/server là tín hiệu nghi ngờ.

**Hướng hybrid ngành dùng:**
- **App native + chứng thực thiết bị:** Android **Play Integrity** (`PLAY_RECOGNIZED` = app không bị sửa; `MEETS_DEVICE/STRONG_INTEGRITY` = thiết bị thật; chống replay bằng nonce/requestHash, **server** phải xác minh; Google nói không nên là cơ chế duy nhất; mặc định 10.000 request/ngày) [XM]. iOS **App Attest**: khóa trong Secure Enclave, server gửi challenge, xác minh assertion; Apple nói **không thể chắc chắn phát hiện OS bị chiếm** [XM].
- **Trình duyệt thì không có chứng thực tương đương:** Google **bỏ Web Environment Integrity** (02/11/2023); chỉ còn Media Integrity API cho **WebView trong app Android** [XM]. → Với kiến trúc web (ADR-0003), không có cách mật mã nào chứng minh khung hình đến từ camera thật. Phải dựa vào: thử thách ngẫu nhiên do server sinh (ChromaPulse màu ngẫu nhiên, câu đọc ngẫu nhiên — đúng thiết kế hiện tại), ràng buộc phiên + thời gian, dấu hiệu môi trường (CreepJS "lies" — repo đã có CAP-05), phát hiện camera ảo theo tên thiết bị/độ trễ khung hình, giới hạn số lần thử.
- **Lớp phân tách theo nhà cung cấp:** xác minh danh tính, liveness/PAD, deepfake, và **IAD (injection attack detection)** là bốn lớp khác nhau [XM — nguồn nhà cung cấp CyberLink].

**Hệ quả cho VeriClue:** giữ kiến trúc hiện tại là đúng. Nếu ban giám khảo hỏi "sao không chạy trên điện thoại", câu trả lời: (1) web không có chứng thực thiết bị sau khi WEI bị bỏ; (2) mô hình nhỏ tổng quát hóa kém (PAD: DeiT-tiny 76,6% vs DINOv2-B 96,3% AUC); (3) lộ mô hình tạo oracle cho kẻ tấn công. Hướng tương lai (ngoài phạm vi demo): SDK native ký dữ liệu chụp + Play Integrity/App Attest.

---

## 4. Rủi ro lớn nhất

1. **Giấy phép:** gần như mọi mô hình tốt đều NC: SCRFD (nghiên cứu), SBI (nghiên cứu), Effort (NC), AntiDeepfake (CC BY-NC-SA), Zipformer-vi-30M (CC BY-NC-ND), Moonshine-vi (chưa rõ), MobileCLIP (điều khoản riêng của Apple). Ổn cho demo cuộc thi, nhưng phải ghi rõ trong báo cáo và có phương án thay (YuNet MIT, PhoWhisper BSD-3, Nes2Net Apache, GenD MIT).
2. **Chưa có số trên người Việt / điện thoại Việt** cho bất kỳ ứng viên nào. Mọi số trong bảng là trên bộ dữ liệu nước ngoài. Nhóm phải tự đo (đúng luật §6.9).
3. **Tổng quát hóa của mô hình nhỏ kém** (PAD, giọng nói AASIST, DeFakeQ). Chuyển xuống điện thoại sẽ làm tụt chất lượng rõ.
4. **Tấn công tiêm** là lỗ hổng chính của kiến trúc web, không giải được bằng mô hình ở client. Phải dựa vào thử thách ngẫu nhiên từ server và kiểm tra chéo client/server.
5. **Hiệu năng trình duyệt điện thoại:** WebGPU có trên Chrome Android 121+ (Android 12+, GPU Qualcomm/ARM) và iOS 26 [XM]; máy cũ hơn chỉ có WASM CPU → mô hình > ~30M tham số sẽ chậm [SĐ].

---

## 5. Nguồn

Mặt / PAD / deepfake
- GenD repo: https://github.com/yermandy/GenD — bài báo: https://arxiv.org/html/2508.06248v3 — WACV 2026: https://openaccess.thecvf.com/content/WACV2026/html/Yermakov_Deepfake_Detection_that_Generalizes_Across_Benchmarks_WACV_2026_paper.html
- MediaPipe Face Detector: https://developers.google.com/edge/mediapipe/solutions/vision/face_detector
- insightface model zoo (giấy phép): https://github.com/deepinsight/insightface/tree/master/model_zoo
- YuNet: https://huggingface.co/opencv/face_detection_yunet/blob/main/README.md ; https://models.luxonis.com/luxonis/yunet/aim_8TPr5pvDyoe5cAvrPbzNxc
- Silent-Face-Anti-Spoofing (MiniFASNet): https://github.com/minivision-ai/Silent-Face-Anti-Spoofing
- suriAI face-antispoof-onnx: https://github.com/suriAI/face-antispoof-onnx
- Custom-Lightweight-FAS: https://github.com/lluevano/Custom-Lightweight-Face-Anti-Spoofing
- Benchmark VFM cho FAS (Tohoku, CVPRW 2026): https://arxiv.org/html/2604.19196
- DINOv2-reg cho FAS: https://arxiv.org/html/2510.17201v1
- FLIP: https://github.com/koushiksrivats/FLIP
- MobileCLIP: https://github.com/apple/ml-mobileclip
- SBI: https://github.com/mapooon/SelfBlendedImages
- DeFakeQ: https://arxiv.org/html/2604.08847v1
- LaDeDa / Tiny-LaDeDa: https://arxiv.org/abs/2406.09398 ; https://vision.huji.ac.il/ladeda

Giọng nói / âm thanh
- AntiDeepfake MMS-300M: https://huggingface.co/nii-yamagishilab/mms-300m-anti-deepfake
- Wav2Vec2-Small-AntiDeepfake (bản sao): https://huggingface.co/SpeechAntiSpoofingBenchmarks/Wav2Vec2-Small-AntiDeepfake
- Audio deepfake trong trình duyệt: https://arxiv.org/html/2606.30780v1
- AASIST: https://github.com/clovaai/aasist
- Nes2Net: https://github.com/Liu-Tianchi/Nes2Net ; https://github.com/Liu-Tianchi/Nes2Net_ASVspoof_ITW ; https://arxiv.org/abs/2504.05657
- Müller et al. 2022 "Does Audio Deepfake Detection Generalize?": https://arxiv.org/abs/2203.16263
- AudioSeal: https://github.com/facebookresearch/audioseal
- PhoWhisper: https://github.com/VinAIResearch/PhoWhisper ; https://huggingface.co/vinai/PhoWhisper-tiny
- Moonshine-tiny-vi: https://huggingface.co/moonshine-ai/moonshine-tiny-vi ; bài báo: https://arxiv.org/html/2509.02523v1
- Zipformer-vi-30M: https://huggingface.co/hynt/Zipformer-30M-RNNT-6000h
- sherpa-onnx danh sách mô hình: https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.html
- Whisper ONNX cho transformers.js: https://huggingface.co/onnx-community/whisper-base

Khớp môi
- BioLip: https://arxiv.org/pdf/2604.16808
- KLASSify: https://arxiv.org/pdf/2508.07337

Trình duyệt / an ninh
- WebGPU trên trình duyệt chính: https://web.dev/blog/webgpu-supported-major-browsers
- ONNX Runtime Web: https://npmjs.com/package/onnxruntime-web
- Play Integrity: https://developer.android.com/google/play/integrity/overview
- App Attest: https://developer.apple.com/documentation/devicecheck/establishing-your-app-s-integrity
- Google bỏ WEI: https://www.theregister.com/2023/11/02/google_abandons_web_environment_integrity ; https://en.wikipedia.org/wiki/Web_Environment_Integrity
- CEN/TS 18099: https://www.evs.ee/en/cen-ts-18099-2024 ; https://withpersona.com/blog/what-is-cen-ts-18099-a-guide-to-the-injection-attack-detection-standard
- Tấn công tiêm (nguồn nhà cung cấp, coi là tham khảo): https://docs-vision.fpt.ai/en/ekyc/IV-guides/Methods%20for%20verifying%20and%20preventing%20eKYC%20frauds ; https://www.signzy.com/blogs/liveness-detection-bypass-deepfake-injection ; https://www.cyberlink.com/faceme/insights/articles/2061/what-is-IAD
