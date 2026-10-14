# Học hỏi từ GitHub: các hệ thống tương tự VeriClue

> Rà soát ngày 14/10/2026 qua GitHub API và README của từng repo. Số sao, ngày cập nhật và giấy phép lấy từ API. Mục ghi [chưa kiểm chứng] là chưa xác nhận được.

## 1. Kết luận chính

1. **Chưa có repo mã nguồn mở nào làm trọn phạm vi VeriClue**, tức là cùng lúc có: thu nhận trên web, thử thách liveness, phát hiện camera ảo, quyết định cho qua / chụp lại / duyệt, và bàn duyệt.
2. **Chưa có hệ thống mã nguồn mở nào làm giám định theo từng đoạn, có biểu đồ thời gian và báo cáo.** TrueMedia, DeepSafe, FakeFinder chỉ đưa một kết luận cho cả file. Chế độ giám định của VeriClue vì vậy là điểm khác biệt thật.
3. **Không có thư viện JS mã nguồn mở nào phát hiện camera ảo một cách nghiêm túc.** Ngay cả AWS Amplify cũng chỉ kiểm tra tên thiết bị có chữ "virtual" hay không.
4. **Ba phần khó nhất đã có code tham khảo:**
   - **Nháy màu:** AWS Amplify, giấy phép Apache-2.0.
   - **Learn-then-Test:** thư viện MAPIE, giấy phép BSD-3.
   - **Mô hình PAD chạy trên trình duyệt:** face-antispoof-onnx, giấy phép Apache-2.0.

## 2. Repo dùng lại được code (giấy phép cho phép)

| Repo | Giấy phép | Lấy gì cho VeriClue |
|---|---|---|
| [aws-amplify/amplify-ui](https://github.com/aws-amplify/amplify-ui) — `packages/react-liveness` (1.145★) | Apache-2.0 | **ChromaPulse:**<br>• `ColorSequenceDisplay.ts` phát chuỗi màu do server cấp.<br>• Tô màu vùng quanh khung oval khuôn mặt.<br>• Ghi thời điểm đổi từng màu để server đối chiếu.<br>• Ước lượng độ sáng bằng histogram 8 mức (tối / bình thường / sáng); kiểm tra khuôn mặt nằm đúng khung oval; yêu cầu ≥ 15 khung hình/giây.<br>Phải giữ file NOTICE và ghi nguồn. |
| [scikit-learn-contrib/MAPIE](https://github.com/scikit-learn-contrib/MAPIE) (1.602★, v1.5.0) | BSD-3 | **TrustRouter:**<br>• `BinaryClassificationController` hỗ trợ **hai ngưỡng có vùng "chuyển người duyệt"**, kiểm soát nhiều rủi ro cùng lúc (mỗi loại tấn công một rủi ro), p-value Hoeffding–Bentkus, hiệu chỉnh đa kiểm định Holm / Bonferroni.<br>• Có ví dụ `plot_risk_control_multi_parameter_binary_classification.py` gần như trùng thiết kế VeriClue.<br>→ **Không cần tự viết Learn-then-Test.** |
| [facenox/face-antispoof-onnx](https://github.com/facenox/face-antispoof-onnx) (273★) | Apache-2.0 | PAD 600 KB chạy được trên trình duyệt. Báo cáo AUC 0,998 trên CelebA-Spoof; nhóm phải tự kiểm tra lại trên dữ liệu người Việt |
| [minivision-ai/Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) (1.829★) | Apache-2.0 | MiniFASNet và code huấn luyện |
| [asalazarvaldiviaocg/biometrical-verify](https://github.com/asalazarvaldiviaocg/biometrical-verify) (7★) | MIT | **Thiết kế gần VeriClue nhất:**<br>• `GET /verify/challenge` trả mã dùng một lần kèm chỉ dẫn.<br>• Quyết định APPROVE / REVIEW / REJECT.<br>• Biên nhận quyết định có chữ ký Ed25519; tự xóa dữ liệu theo hạn; nhật ký chỉ ghi thêm. |
| [truemediaorg/deepfake-app](https://github.com/truemediaorg/deepfake-app) (MIT, đã lưu trữ) | MIT | **Cách ra kết luận cho chế độ giám định:**<br>• Mỗi mô hình cho một mức: cao / chưa rõ / thấp / **không áp dụng** (ví dụ không thấy mặt).<br>• Gom thành kết luận "bằng chứng mạnh / chưa rõ / ít bằng chứng".<br>• Nhãn **"ngoài phạm vi"** khi không có mặt, có quá nhiều mặt, hoặc nhiều chữ — tránh kết luận chắc chắn sai. |
| [siddharthksah/DeepSafe](https://github.com/siddharthksah/DeepSafe) (122★) | MIT | Mỗi mô hình có `/health` và `/predict`; một gateway FastAPI gom kết quả |
| [zlin0/wedefense](https://github.com/zlin0/wedefense) | Apache-2.0 | Bộ công cụ chống giả giọng: SSL-AASIST, tăng cường dữ liệu (codec, nhiễu, vang), **định vị đoạn giả trong audio** |
| [TakHemlata/SSL_Anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing) | MIT | XLS-R + AASIST + RawBoost, baseline mạnh cho giọng giả |
| [nii-yamagishilab/PartialSpoof](https://github.com/nii-yamagishilab/PartialSpoof) | BSD-3 | Chỉ số **SegmentEER / RangeEER** để đánh giá phát hiện theo đoạn |
| [ymhzyj/UMMAFormer](https://github.com/ymhzyj/UMMAFormer) | MIT | Định vị đoạn giả trong video, cả hình lẫn tiếng |
| [hllj/ZaloAIChallenge-2022](https://github.com/hllj/ZaloAIChallenge-2022) | MIT | Lời giải **top 2** Zalo AI 2022 Liveness: lấy 1 khung hình/giây, ghép nhiều mô hình |
| [vladmandic/human](https://github.com/vladmandic/human) | MIT | Landmark, nháy mắt, quay đầu, mô hình chống giả mạo chạy trên trình duyệt |
| [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) (46k★) | MIT | Khung dự án: FastAPI, PostgreSQL, Alembic, Docker Compose |
| [google-ai-edge/mediapipe-samples](https://github.com/google-ai-edge/mediapipe-samples) | Apache-2.0 | Ví dụ Face Landmarker trên web |
| [zhu-j-faceonlive/kyc-review-dashboard-vue](https://github.com/zhu-j-faceonlive/kyc-review-dashboard-vue) | MIT | Khung giao diện bàn duyệt: lọc ca, so sánh song song, nút duyệt kèm ghi chú |

**Thư viện khác nên dùng:**
- `netcal` (Apache-2.0) và `betacal` (MIT): hiệu chỉnh xác suất.
- `pyeer` (MIT): kiểm tra chéo EER.
- `pytorch-ood` (Apache-2.0): phát hiện mẫu ngoài phạm vi.
- `react-webcam` (MIT): thu hình trên web.

## 3. Chỉ học ý tưởng, không chép code

| Repo | Lý do |
|---|---|
| Ballerine (2.440★) | Giấy phép gốc là Elastic-2.0, và repo đang được xây lại. Chỉ học **luồng bàn duyệt**: hàng đợi → nhận ca → bảng bằng chứng → quyết định kèm mã lý do → nhật ký |
| Marble | Elastic-2.0. Học bộ công cụ điều tra và nhật ký không sửa được |
| DeepfakeBench, AV-Deepfake1M, LAV-DF | CC BY-NC. Dùng được cho nghiên cứu và đánh giá |
| Các repo không có giấy phép (VTCC Zalo, LipFD, Viet-Guard…) | Chỉ tham khảo ý tưởng và số liệu |

## 4. Bài học nên đưa vào VeriClue (xếp theo giá trị và công sức)

1. **Chép bộ phát chuỗi màu của AWS Amplify** cho ChromaPulse, thay vì tự viết. Có sẵn cách tô màu quanh khung oval, chuyển màu mượt, và ghi thời điểm từng màu.
2. **Dùng MAPIE cho Learn-then-Test.** Tạo một rủi ro cho mỗi loại tấn công, dùng Holm để kiểm soát đa kiểm định. Báo cáo cỡ mẫu và mức α thực sự đạt được.
3. **Cổng chất lượng theo kiểu Amplify:** mặt nằm đúng khung oval, đo độ sáng bằng histogram, ≥ 15 khung hình/giây. Mỗi lần không đạt đi kèm một lý do "chụp lại" cụ thể.
4. **Thêm nhãn "ngoài phạm vi / không áp dụng"** theo kiểu TrueMedia cho chế độ giám định và cho từng mô hình (không thấy mặt, nhiều mặt, đoạn quá ngắn). Khi đó kết luận tối đa chỉ là "chưa rõ".
5. **Tăng cường dữ liệu giọng nói là bắt buộc.** Repo đo trên SEA-Spoof tiếng Việt cho thấy: không tăng cường thì EER từ khoảng 1% vọt lên hơn 30% khi có nhiễu hoặc vang; có tăng cường thì chỉ còn 6%.
6. **Khóa giao thức đánh giá và giữ riêng một công cụ giả giọng để kiểm tra.** Bài học từ Viet-Guard: tập "chưa từng thấy" của họ lại dễ hơn tập "đã thấy", nên kết quả bị đẹp giả.
7. **Đoạn nghi giả trong báo cáo giám định nên ghi thành khoảng thời gian**, không ghi mốc chính xác từng khung hình. Mô hình tốt nhất (BA-TFD+) chỉ đạt AP@0.95 khoảng 4%, nên ranh giới đoạn không chính xác tới từng khung. Thêm biên ±0,5–1 giây.
8. **Coi chừng lượng tử hóa INT8.** Repo verilens đo được INT8 làm MiniFASNet phân biệt giả kém hẳn: xác suất "thật" của ảnh giả tăng từ 0,06 lên 0,65. Phải so FP32 và INT8 trên dữ liệu giả trước khi dùng bản nhẹ.
9. **Biên nhận quyết định có chữ ký và mã thử thách dùng một lần** (biometrical-verify): bằng chứng chống chối bỏ, chống phát lại.
10. **Thêm luật cho thử thách:** thứ tự ngẫu nhiên, phải đạt nhiều khung hình liên tiếp, quay về tư thế trung tính giữa các bước, có thời gian chờ tối đa (AlanJuker, face-biometrics-api).

## 5. Công cụ tấn công dùng để tự kiểm thử (red-team)

| Công cụ | Dùng để thử |
|---|---|
| DeepFaceLive, Deep-Live-Cam | Ghép mặt thời gian thực |
| OBS Virtual Camera | Camera ảo |
| [android-v4l2-kernel-camera-injection-bypass](https://github.com/android-kyc-lab/android-v4l2-kernel-camera-injection-bypass) | Chèn luồng ở mức driver Android. Cho thấy kiểm tra tên thiết bị không đủ |
| invisible_playwright | Trình duyệt chống bị phát hiện tự động hóa |
| [GOTCHA](https://github.com/mittalgovind/GOTCHA-Deepfakes) | Danh mục 13 kiểu thử thách chống deepfake thời gian thực |

Chỉ dùng để thử trên hệ thống của chính nhóm.

## 6. Tham khảo từ Việt Nam

- **Zalo AI 2022 Liveness:**
  - Lời giải top 2 (hllj, MIT) ghép nhiều mô hình trên khuôn mặt cắt từ nhiều khung hình.
  - Lời giải VTCC báo EER 0,0086 trên tập public, nhưng lên 0,059–0,064 trên tập private. Khoảng cách này nhắc rằng phải đánh giá trên dữ liệu khác hẳn dữ liệu huấn luyện.
- **Giọng nói:**
  - Viet-Guard dùng ViSpoofDB.
  - KhanhDo4804 dùng SEA-Spoof tiếng Việt, kết quả về độ bền tốt nhất tìm được.
  - Cả hai repo **không có giấy phép**, nên chỉ học số liệu và phương pháp.
- **Không có repo tiếng Việt nào làm trọn eKYC chống deepfake trên web.**

---

# ĐỢT 2 — Đào sâu (14/10/2026)

> Rà 6 hướng, khoảng 270 repo. Đọc **mã nguồn thật** của khoảng 40 repo, không chỉ README. Số sao, ngày cập nhật và giấy phép lấy từ GitHub API. Mục ghi [chưa kiểm chứng] là chưa xác nhận được.

## 7. Phát hiện làm thay đổi thiết kế

### 7.1 Kẻ tấn công đã nhắm thẳng vào KYC trên web

**Đã có công cụ sẵn trên GitHub:**

- **Extension Chrome nhắm vào trang KYC** — ví dụ `Daze2772/camera-intercept-extension`:
  - Thay `getUserMedia` bằng video phát qua `canvas.captureStream`.
  - Giả tên camera thành "Integrated Camera".
  - `applyConstraints` trả về ngay mà không làm gì.
  - Sửa CSP của trang KYC.
  - Kèm sẵn trang `kyc-simulation.html` để tự thử.
- **`xViada/VCam-Bypass` tinh vi hơn:** giả trọn bộ thông số của camera thật (lấy nét, phơi sáng, cân bằng trắng). Mục đích là vượt qua cách kiểm tra kiểu "camera ảo thì thiếu thông số".

→ Chỉ kiểm tra tên thiết bị hoặc danh sách thông số là **không đủ**.

**Điểm yếu đọc được từ code:** các extension này gán đè hàm bằng JavaScript thường và **không giả được dấu hiệu `[native code]`**. Vì vậy có thể phát hiện bằng bộ "lie detector" của **CreepJS** (MIT, `src/lies/index.ts`):
- so sánh `Function.prototype.toString`;
- kiểm tra `'prototype' in fn`;
- kiểm tra descriptor;
- đối chiếu với một `<iframe>` sạch.

Đây là lỗ hổng của **các công cụ hiện tại**, kẻ tấn công có thể vá sau. Chỉ coi đây là **một lớp** phòng thủ, không phải bảo đảm.

**Tấn công cấp nhân Android** (kprobe vào `VIDIOC_DQBUF`, chép nguyên dấu thời gian và số thứ tự khung thật) vượt qua mọi kiểm tra JavaScript, kể cả Play Integrity. **Chỉ thử thách nháy màu bắt được loại này.** Đó là lý do ChromaPulse là lớp quan trọng nhất.

### 7.2 ChromaPulse phải dựa vào độ trễ tuyệt đối, không chỉ "có phản chiếu hay không"

- **GOTCHA (EuroS&P 2024):** mặt giả thời gian thực vẫn "làm theo" thử thách nháy sáng 52–83% số lần. Đường ống ghép mặt chạy 20–23,5 khung/giây.
- **Code Deep-Live-Cam** có tùy chọn hòa trộn Poisson. Mặt ghép vì thế mượn được ánh sáng thật ở viền: **vẫn có phản chiếu, chỉ trễ hơn và yếu hơn**.
- Toàn bộ khung hình bị trễ như nhau, nên so sánh mặt với cổ **không** làm lộ độ trễ. Chỉ đo trễ tuyệt đối trên cùng một đồng hồ mới lộ ra.
- **Không có mã nguồn mở nào làm phân tích tương quan màu và độ trễ ở phía server** (AWS cũng giữ kín phần này). ChromaPulse vì vậy là phần tự xây có giá trị thật.

### 7.3 Đổi mô hình deepfake khuôn mặt sang GenD

- **`yermandy/GenD`** (WACV 2026):
  - Giấy phép **MIT** cho cả code lẫn trọng số trên Hugging Face.
  - AUC trung bình trên 14 bộ dữ liệu cao nhất: 91,2–91,6%.
  - Chỉ cần tinh chỉnh LayerNorm và lớp cuối (0,03% tham số).
- **Effort** chỉ cho dùng phi thương mại → chuyển xuống làm dự phòng.

### 7.4 Giọng nói: có mô hình nền đa ngôn ngữ rất mạnh

- **NII AntiDeepfake** (`nii-yamagishilab/mms-300m-anti-deepfake`) đã được huấn luyện thêm trên **18 nghìn giờ giọng giả + 56 nghìn giờ giọng thật, hơn 100 ngôn ngữ**. Trọng số: CC BY-NC-SA.
- EER 2,9% trên In-the-Wild nhưng **32,8% trên Deepfake-Eval-2024** → khoảng cách giữa thí nghiệm và thực tế rất lớn.

### 7.5 Khoảng trống được xác nhận lần nữa

Không tìm thấy:
- hệ thống mã nguồn mở nào làm **giám định theo đoạn** cho video có cả hình và tiếng;
- **thông số nén của Zalo** được công bố;
- bộ phát hiện mã nguồn mở đáng tin cho **ghép mặt thời gian thực**.

## 8. Repo theo từng thành phần (đợt 2)

### 8.1 ChromaPulse và cổng chất lượng

| Repo | Giấy phép | Lấy gì |
|---|---|---|
| aws-amplify/amplify-ui `react-liveness` (đã đọc trọn luồng) | Apache-2.0 | **Màu và thời gian do server gửi:** 8 màu, cuốn 300 ms rồi giữ 100 ms; tick 10 ms; tô toàn màn hình, alpha 0,9 ngoài oval và 0,75 trong oval.<br>**Sự kiện `ColorDisplayed`** (màu hiện tại, màu trước, số thứ tự, thời điểm) gửi trên cùng luồng với video.<br>**Kéo mặt lại gần** để tăng ánh sáng phản chiếu; giữ yên 1 giây trước khi nháy.<br>IoU > 0,6; hộp mặt dựng từ landmark; tối thiểu 15 khung/giây.<br>⚠️ **Không chép `estimateIllumination`**: có lỗi, không bao giờ trả về "BRIGHT".<br>⚠️ **Không dùng MediaRecorder để đo thời gian**: AWS phải chỉnh bằng hệ số 0,73. |
| raghavenderreddygrudhanti/faceflash | MIT | Bản dựng lại duy nhất của Face Flashing: 5 vùng mặt, điểm nhất quán giữa các vùng. Chưa đo độ trễ, chưa trừ nền. |
| SamProell/yarppg | MIT | Trung bình vùng da có trừ nền; mặt nạ nửa dưới mặt theo index MediaPipe; bộ lọc IIR. |
| remotebiosensing/rppg | Apache-2.0 | POS/CHROM và hàm khử xu hướng (detrend). |
| jeeliz ExposureController | MIT | Khóa phơi sáng rồi **đọc lại `getSettings()` để xác nhận đã khóa thật**. |
| yakhyo/face-image-quality-assessment + uniface | MIT | **eDifFIQA-T ONNX** (1,7M tham số) chấm chất lượng mặt ở server: ảnh gốc 0,76; mờ nặng 0,14. |
| BSI-OFIQ/OFIQ-Project | MIT | Định nghĩa phép đo theo ISO/IEC 29794-5 kèm tham số sigmoid. |
| ❌ rPPG-Toolbox (RAIL), pyVHR, heartbeat-js (GPL) | — | Không chép code, chỉ dựng lại công thức từ paper. |

### 8.2 CamProbe (camera ảo, chèn luồng)

| Repo | Giấy phép | Lấy gì |
|---|---|---|
| abrahamjuliot/creepjs `src/lies/` | MIT | Bộ phát hiện hàm bị can thiệp. Áp vào `getUserMedia`, `enumerateDevices`, `getSettings`, `getCapabilities`, `applyConstraints`. |
| fingerprintjs/BotD | MIT | Thêm các phép dò can thiệp: `function_bind`, `error_trace`, `eval_length`. |
| VCam-Bypass `profiles.js` | MIT | Cho biết **chính xác thông số nào kẻ tấn công sẽ giả**. Từ đó đối chiếu thông số với **hành vi thật**: `applyConstraints` có làm `getSettings()` thay đổi không. |
| v4l2loopback, OBS virtualcam (đã đọc code) | GPL | Dấu vết: tên "Dummy video device", "OBS Virtual Camera"; **lặp khung** để giữ tốc độ khung hình. |
| android_virtual_cam (Xposed, đã đọc code) | MIT | Phát video theo đồng hồ phần mềm (`Thread.sleep`) nên **nhịp khung đều bất thường**; video lặp lại. |

### 8.3 Deepfake khuôn mặt và PAD

| Repo | Giấy phép | Vai trò |
|---|---|---|
| **yermandy/GenD** (`GenD_CLIP_L_14`) | MIT | **Mô hình chính.** SCRFD + căn chỉnh 5 điểm, tỷ lệ 1,3, 224 px, 32 khung, trung bình softmax. |
| mapooon/SelfBlendedImages (`FFc23`) | Chỉ nghiên cứu | **Dự phòng và nguồn bằng chứng:** chuyên bắt đường hòa trộn, đúng kiểu dán mặt của Deep-Live-Cam; có Grad-CAM cho người duyệt. |
| yakhyo/uniface (MiniFASNet ONNX) | MIT | PAD dùng ngay (1,2 MB). Mô hình này chỉ trả lời "camera đang nhìn màn hình hay ảnh in?", **không** trả lời "mặt có bị ghép không?". |
| Zalo 2022 top (hllj, VTCC) | MIT / không có | Cả hai **phân loại cả khung hình** (bắt được viền màn hình, vân moiré). Tốt cho liveness, kém cho phát hiện ghép mặt. |

**Dấu vết của Deep-Live-Cam** (đọc `face_swapper.py`):
- Mặt ghép ở **128 px** rồi phóng to.
- Dán lại bằng mặt nạ elip làm mờ (GaussianBlur 31, σ 12) hoặc hòa trộn Poisson.
- Chỉ dò mặt khoảng mỗi 12 khung, nên **rung khi chuyển động nhanh**.

Các tín hiệu phụ giải thích được rút ra từ đó:
- tỷ lệ độ nét trong elip so với má, tóc, cổ;
- đường viền elip;
- độ dao động của embedding danh tính giữa các khung.

⚠️ `inswapper-512-live` (11/2025) ghép ở 512 px, nên dấu vết độ phân giải thấp sẽ mờ dần.

### 8.4 Giọng nói tiếng Việt

| Repo / mô hình | Giấy phép | Vai trò |
|---|---|---|
| **nii-yamagishilab/AntiDeepfake** (`mms-300m-anti-deepfake`) | Code BSD-3; trọng số CC BY-NC-SA | **Mô hình nền chính**, tinh chỉnh với lr 1e-6. |
| **zlin0/wedefense** | Apache-2.0 | Công thức tăng cường (codec, RawBoost, MUSAN+RIR); `logits_to_llr.py`; **định vị đoạn giả** (SSL-MHFA, độ phân giải 0,02 s); RangeEER. |
| ItzJuny/CFPRF | MIT | Định vị đoạn giả 2 bước, có checkpoint. |
| PhoWhisper-large-ct2 + faster-whisper | BSD-3 / MIT | Nhận dạng câu đọc, bật lọc VAD. |
| MahmoudAshraf97/ctc-forced-aligner | BSD-2 | **Căn chỉnh chính câu đề bài** theo thời gian; token `<star>` bắt phần nói thừa. |
| vinhdq842/soe-vinorm | MIT | Chuẩn hóa văn bản tiếng Việt. |
| ByteDance/LatentSync (`stable_syncnet.pt`) | Apache-2.0 | SyncNet mới, độ chính xác đồng bộ khoảng 94%. |
| nguyenvulebinh/AVSRCocktail | — | **Đọc môi tiếng Việt**: tùy chọn kiểm tra câu đọc bằng hình. |
| **pnnbao97/VieNeu-TTS** (2,85k★) | Apache-2.0 | Công cụ tấn công mạnh nhất: clone giọng tiếng Việt từ 3–5 giây, chạy trên CPU. |

### 8.5 Giám định, bàn duyệt và giải thích

| Repo | Giấy phép | Lấy gì |
|---|---|---|
| AFP-Medialab/verification-plugin (InVID) | MIT | Biểu đồ điểm theo cảnh, dải ảnh thu nhỏ, bấm vào cảnh để xem mặt; câu cảnh báo "không phát hiện ≠ chắc chắn thật". |
| truemediaorg/deepfake-app | MIT | Nhãn theo bằng chứng; **giải thích bằng chữ chỉ hiện khi khớp kết luận**; nhân viên được ghi đè kết luận. |
| Ballerine back office (đã đọc code) | Học ý tưởng | Không cho duyệt khi còn mục cần chụp lại; nút chỉ hiện khi ca đã được nhận và trạng thái cho phép; mã lý do khai báo trong schema. |
| Marble (đã đọc code) | Học ý tưởng | Bảng `CaseEvent` chỉ ghi thêm; **hộp thư leo thang** cho người thứ hai duyệt (nguyên tắc bốn mắt). |
| wavesurfer.js 8 | BSD-3 | Dạng sóng, vùng đánh dấu, phổ âm cho chế độ giám định âm thanh. |
| WeasyPrint / Playwright `page.pdf()` | BSD-3 / Apache-2.0 | Xuất báo cáo PDF. |
| `cryptography` (Ed25519), minisign | Apache/BSD / ISC | Ký báo cáo. |
| c2pa-python / c2pa-js | Apache-2.0 / MIT | Đọc và ký chứng nhận nguồn gốc. |
| ⚠️ InVID, TrueMedia | — | **Không học cách đổi xác suất thô thành chữ** (kiểu "≥ 70% = mạnh"): không theo chuẩn ENFSI. |

### 8.6 Ý tưởng mới

| Repo | Giấy phép | Ý tưởng |
|---|---|---|
| **facebookresearch/audioseal** | MIT | Dò thủy vân AI trong âm thanh, cho điểm **theo từng mẫu** nên khớp với biểu đồ đoạn. |
| **resemble-ai/Perth** | MIT | Dò thủy vân PerTh. **Chatterbox (26,9k★) gắn thủy vân này vào mọi giọng nó tạo ra.** |
| facebookresearch/videoseal | MIT | Gắn và dò thủy vân ảnh, video. |
| zfr00/ForenAgent; suncore946/AgentFoX | Không có / Apache-2.0 | Agent giám định: 12 công cụ có schema gọi hàm, LLM viết báo cáo. |
| truebees-ai/social_emulator | CC BY-4.0 | Ước lượng thông số nén của mạng xã hội rồi mô phỏng lại. |
| SantanderAI/gen-fraud-graph | Apache-2.0 | Sinh đồ thị gian lận tổng hợp cho Ring Radar sau này. |

## 9. Đề xuất đưa vào VeriClue (xếp theo giá trị × công sức)

| # | Đề xuất | Thành phần | Công sức | Giá trị |
|---|---|---|---|---|
| 1 | **Lớp kiểm tra API bị can thiệp** theo CreepJS (toString, iframe sạch) | CamProbe | ~1 ngày | Rất cao |
| 2 | **Đo độ trễ tuyệt đối trên cùng một đồng hồ**: thời điểm vẽ màu (rAF) so với `captureTime` của từng khung (rVFC). Không dùng MediaRecorder. | ChromaPulse | ~1 ngày | Rất cao |
| 3 | **Mô hình 3×3 nhiều kênh** `y = M·x(t−τ) + b`, quét τ từ 0–300 ms, tính trong miền log có trừ nền; dùng R² và τ làm điểm. Kèm kiểm tra **tỷ lệ phản chiếu giữa các vùng**. | ChromaPulse | 2–3 ngày | Cao |
| 4 | **Chép bộ phát màu và cách kéo mặt lại gần của AWS Amplify.** Cân nhắc màu đậm hơn nhưng vẫn gần đẳng sáng, ≤ 2,5 lần đổi/giây. | ChromaPulse | 1–2 ngày | Cao |
| 5 | **Đổi mô hình deepfake chính sang GenD**, SBI làm dự phòng và nguồn heatmap. Gộp điểm = trung bình + trung bình top 25%. | Bộ não | ~1 ngày | Cao |
| 6 | **Đổi mô hình nền giọng nói sang NII AntiDeepfake**, tăng cường dữ liệu theo wedefense. **Chống học vẹt:** cắt khoảng lặng, cân âm lượng. | Bộ não | 2–3 ngày | Cao |
| 7 | **Kiểm tra câu đọc 8 bước:** câu phủ đủ 6 thanh; **không** đưa câu đề bài làm gợi ý cho ASR; so khớp hai lớp (có dấu và bỏ dấu); căn chỉnh câu đề bài để phát hiện chỗ cắt ghép. | VoiceGate | ~2 ngày | Cao |
| 8 | **Báo cáo giám định 11 mục:** chuỗi lưu giữ có hash; hai giả thuyết; thang lời ENFSI suy từ tỷ số khả năng đã hiệu chỉnh; mục giới hạn; chữ ký Ed25519. | Giám định | ~2 ngày | Cao |
| 9 | **Bàn duyệt 3 giai đoạn:** duyệt mù → mở kết quả AI → nếu bất đồng thì nêu lý do và chuyển người thứ hai. Chèn khoảng 5% ca chuẩn để kiểm tra người duyệt. | Bàn duyệt | ~2 ngày | Trung bình–cao |
| 10 | **"Quét nguồn gốc":** AudioSeal, Perth, C2PA. Chỉ là **bằng chứng một chiều**: thiếu thủy vân không có nghĩa là thật. | Giám định | ~1 ngày | Cao (demo ấn tượng) |
| 11 | **Hồ sơ nén Zalo/Messenger:** gửi 50–100 video và tin nhắn thoại qua app rồi tải về, ước lượng thông số nén, dùng để tăng cường dữ liệu và vẽ đường "độ chính xác sau Zalo". | Bộ não / báo cáo | 2–3 ngày | Cao (chưa ai công bố) |
| 12 | Nhãn "ngoài phạm vi"; giải thích bằng chữ chỉ hiện khi khớp kết luận | Giám định | < 1 ngày | Trung bình |

**Nên tránh:**
- Tự fine-tune MLLM giám định: quá nặng.
- Coi việc thiếu thủy vân là bằng chứng thật.
- SynthID: không có API công khai.
- Dùng rPPG làm luật cứng.
- FHE và học liên kết (federated learning).
- Đưa code GPL/AGPL vào sản phẩm.
