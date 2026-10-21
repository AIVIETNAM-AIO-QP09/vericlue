# Kiểm toán dữ liệu GIỌNG — VeriClue (chỉ đọc)

Ngày đo: 18–19/10/2026. Không sửa file nào trong repo hay `vericlue-store`.
Mọi số dưới đây chạy ra từ các script trong thư mục này:

| File | Nội dung |
|---|---|
| `features.py` → `features.csv` | 7.861 file: toàn bộ MLAAD-vi (1.198), VSASV (1.223), ViMD (19), VIVOS (1.521); ViSpoofDB lấy mẫu seed 42 gồm 1.500 thật + 400 mỗi hệ TTS (giữ đủ 154 file MP3 ElevenLabs) |
| `analyze.py` → `measure.md` | bảng đặc tính và AUC đơn biến cho từng cặp thật/giả (bảng đầy đủ) |
| `extra.py` → `extra.txt` | tỉ lệ file dài đúng 5,000 s; năng lượng theo dải tần ở tần số lấy mẫu gốc (30 file mỗi nhóm) |
| `text_meta.py` → `text_meta.txt` | thống kê văn bản và manifest; đối chiếu `corpus.txt` với `prompts.txt` của VIVOS |
| `asr_probe.py` → `asr.json` | PhoWhisper-small (bản local, CPU) chạy trên 128 mẫu: 20 MLAAD, 20 VSASV, 10 ViMD, 20 VIVOS, 20 ViSpoofDB thật, 24 ViSpoofDB giả |
| quét header (`sf.info`) | quét toàn bộ file .wav/.mp3 trong 5 bộ |

Cách đo: VAD dùng webrtcvad mode 2, khung 20 ms, ở 16 kHz. LUFS xấp xỉ theo BS.1770: lọc K, khối 400 ms, có gating. Nhiễu nền = phân vị 5 % RMS của khung 20 ms. `bw50` = tần số cao nhất mà phổ còn trong khoảng 50 dB dưới đỉnh. Các con số này là đo đạc thay cho việc nghe; tôi không nghe được âm thanh.

---

## 1. Kiểm kê và đặc tính kỹ thuật

| Bộ / nhóm | File | Giờ | Người | SR gốc · định dạng | Thời lượng median [p10–p90] | Im lặng đầu/cuối median | LUFS | Nhiễu nền p5 (dBFS) |
|---|---:|---:|---:|---|---|---|---:|---:|
| VSASV bonafide | 743 | 0,82 | 16 | 16 kHz WAV **float32** mono | 3,31 s [2,0–6,4] | 0,08 / 0,14 s | −21,2 | −56 |
| VSASV replay | 480 | 0,45 | 12 | 16 kHz float32 | 3,20 s | 0,02 / 0,14 s | −15,0 | −52 |
| MLAAD-vi (5 hệ TTS) | 1.198 | 2,42 | 0 người thật | **22,05 kHz** PCM16 mono | 7,0 s [3,2–14] | ≈0 / ≈0,05 s | −25,8 | −84 (OmniVoice, VoxCPM2: −94 = im lặng số) |
| ViMD | **19** | **0,10** | **12** | 44,1 kHz (14 file) / 48 kHz (5); 16 file **stereo** (2 kênh gần như giống hệt, L−R −62 dB); 1 file float | 20,3 s [13–27] | 0,02 / 0,04 s | −23,7 | −51 |
| VIVOS (phần đã tải) | 1.521 | 2,14 | 9 | 16 kHz PCM16 | 4,44 s [2,7–8,4] | **0,32 / 0,30 s** | −19,3 | −63 |
| ViSpoofDB thật | 5.500 | 6,29 | không có ID | **24 kHz** PCM16 | 3,33 s [1,4–8,0] | 0 / 0 s | −20,0 | −74 |
| ViSpoofDB edgetts / fptai / gtts / mmstts / zaloai | 1.200 / 1.199 / 1.200 / 1.200 / 1.199 | 1,67 mỗi hệ | – | **16 kHz** PCM16 | **đúng 5,000 s ở 100 % file** | 0 / **1,5–2,5 s** | −19…−21 | **−120 (số 0 tuyệt đối)** |
| ViSpoofDB elevenlabs | 1.197 (1.039 WAV 16 kHz + **154 MP3 44,1 kHz** + 4 WAV 44,1 kHz) | 1,69 | – | hỗn hợp | 5,000 s ở 60,5 % file | 0 / 1,5 s | −17,0 | −120 |

Đặc tính phổ, đo ở tần số lấy mẫu gốc (`extra.txt`), tính bằng dB so với tổng năng lượng:

- **ViSpoofDB thật** có năng lượng ở dải 8,1–11 kHz ≈ −31 dB. Đây là nội dung thật trên 8 kHz, nên **không thể là VIVOS 16 kHz được upsample**.
- **VIVOS** gần như không có năng lượng trên 7 kHz (dải 7–7,9 kHz: −49,5 dB).
- **MLAAD** có năng lượng đến 11 kHz.
- **ViMD** có năng lượng đến hơn 11 kHz (dải 11–24 kHz: −52 dB).
- **VSASV replay**: 7–7,9 kHz ở −24 dB (VSASV thật: −44 dB). Peak median = 1,0, tức bản replay đã bị chuẩn hóa hoặc bão hòa.

Chuẩn hóa về 16 kHz xóa được lộ đề về tần số lấy mẫu và băng thông (sau resample, `bw50_16k` có AUC 0,50 ở mọi cặp). Nhưng nó **không** xóa được lộ đề về im lặng, nhiễu nền, độ to và thời lượng (xem §3).

## 2. Nội dung thực tế (PhoWhisper, `asr.json`)

| Bộ | Kiểu nói (đọc từ transcript) | Khớp văn bản tham chiếu |
|---|---|---|
| **MLAAD-vi** | Tiếng Việt **dịch máy từ truyện tiếng Anh** (Jane Eyre, Oz…). Câu dài: median 27 âm tiết (2–70). | CER median theo hệ: OmniVoice 0,00, VoxCPM2 0,02, LEMAS 0,04, VieNeu 0,15, **vixTTS 0,27** (WER 0,38; 4 mẫu mỗi hệ). PhoWhisper nghe ra tiếng Việt rõ ở 3 hệ; VieNeu và vixTTS sai nhiều tên riêng và từ. |
| **VSASV** | Tự do, **giọng YouTube/vlog/quảng cáo** ("đến với nhà hàng của chúng tôi…"), có cả câu đọc ngắn; replay cũng vậy. | Không có transcript gốc. 2/20 mẫu bị PhoWhisper sinh "a. a. a." do nhiễu. |
| **ViMD** | **Phỏng vấn trên đài truyền hình tỉnh**, nói tự nhiên có từ đệm ("cái", "thì"), 35–84 âm tiết mỗi câu. | WER median 0,12 (10 mẫu). |
| **VIVOS** | Đọc từng câu báo/văn ngắn (median 12 âm tiết), phòng yên tĩnh. | CER median 0,00 (20 mẫu). Nhưng **5/20 mẫu PhoWhisper bịa thêm "chị ngã ngửa em em thương em…" hoặc "a. a."** sau câu: đây là lỗi ảo giác ở đuôi im lặng, liên quan VOICE-04. |
| **ViSpoofDB thật** | Lẫn nhiều kiểu: thời sự ("đồng chí Trương Thị Mai…"), hội thoại, **văn dịch**, câu ngắn. | **0/20 mẫu khớp `prompts.txt` của VIVOS** (CER tốt nhất median 0,64 trên 12.420 câu). |
| ViSpoofDB edgetts / gtts / mmstts | Đọc câu trong `corpus.txt` (câu ngắn đời sống/tin tức, median 10 âm tiết). | CER 0,00–0,09: khớp `corpus.txt`. |
| ViSpoofDB **fptai / zaloai / elevenlabs** | Câu tự nhiên, **không có trong `corpus.txt`** ("đừng quên nhấn like và subscribe…", "trên thực tế ta khó đạt đến sự hoàn hảo…"). | CER tốt nhất so với corpus 0,71–0,85: văn bản nguồn **khác** với nhóm trên. Có 1 mẫu ElevenLabs đọc dòng corpus sai rất nặng. |

Về văn bản: `corpus.txt` có 1.202 dòng, nhưng **0 dòng trùng chính xác** với 12.420 câu VIVOS, và chỉ 2.130/10.533 trigram (20 %) xuất hiện trong VIVOS. Như vậy thật và giả trong ViSpoofDB đọc **văn bản khác nhau**. Đây là một lộ đề theo nội dung (chủ đề, độ dài câu).

## 3. Lộ đề: AUC đơn biến (bảng đầy đủ trong `measure.md`)

AUC tách = max(AUC, 1−AUC). Ngưỡng > 0,8 nghĩa là chỉ một con số đơn giản đã tách gần hết thật/giả.

| Cặp dự định dạy chung | Đặc trưng lộ (AUC) | Còn lộ sau khi chuẩn hóa 16 kHz? |
|---|---|---|
| VSASV thật vs MLAAD (743 vs 1.198) | SR gốc **1,00**, float32 vs PCM16 **1,00**, bw50 gốc 1,00; nhiễu nền nonspeech 0,90; độ to (LUFS) 0,84; nhiễu p5 0,84; số 0 0,84; **thời lượng 0,84** (3,3 s vs 7,0 s) | **Còn**: LUFS, nhiễu, thời lượng. Riêng OmniVoice/VoxCPM2 có nhiễu p5 **0,99**; vixTTS có LUFS **0,94** |
| ViMD vs MLAAD (19 vs 1.198) | SR 1,00, **thời lượng 0,97** (20 s vs 7 s), nhiễu 0,93, hf4k 0,85 | Còn. ViMD quá nhỏ để dạy được gì |
| VSASV + ViMD vs MLAAD | float 0,99, SR 0,98, nhiễu 0,90, LUFS 0,84, thời lượng 0,82 | Còn |
| VSASV thật vs VSASV replay | peak 0,91, **LUFS 0,90**, độ to lúc nói 0,88 | Còn (replay to hơn khoảng 6 dB) |
| VIVOS vs ViSpoofDB giả | nhiễu p5 **0,94** (−63 vs −120 dB), số 0 0,91, im lặng đầu 0,86, im lặng cuối 0,84 | Còn |
| ViSpoofDB thật vs giả (theo cách bộ này gán nhãn) | bw50 gốc 0,98, SR 0,93, **im lặng cuối 0,92**, tỉ lệ có tiếng 0,92, nhiễu 0,85; **"dài đúng 5,000 s"**: thật 0 % so với giả 93 % → AUC nhị phân ≈ 0,97 | Còn (đệm số 0 đến 5 s). Riêng edgetts: im lặng cuối **1,00** |
| ↳ ElevenLabs | MP3 44,1 kHz chỉ có ở lớp giả (154 file, 13 %; thật 0 MP3): is_mp3 0,70; im lặng cuối 0,85 | Còn |
| VIVOS vs ViSpoofDB thật (kiểm chéo: cả hai đều là giọng thật) | SR 1,00, im lặng cuối 0,86, im lặng đầu 0,83 | Cả hai đều là giọng thật nhưng vẫn tách được: đây là khác biệt kênh, không phải dấu hiệu giả |

Ngoài AUC còn hai lộ đề **danh tính giọng**:

- **MLAAD-vi**: giả chỉ có **4 giọng tham chiếu** là người đọc tiếng Anh của M-AILABS (elizabeth_klett 397, elliot_miller 321, judy_bieber 269, mary_ann 211 mẫu). Riêng vixTTS **không có reference** (246 mẫu, có thể chỉ dùng một giọng mặc định). Mô hình có thể học "5 âm sắc này = giả".
- **ViSpoofDB mmstts** và mô hình `mms-tts-vie` chỉ có **1 giọng** (xem §5).

## 4. Từng bộ: kết luận

### MLAAD-vi

Gồm 1.198 file giả của 5 hệ, dựa trên 1.163 câu nguồn:

| Hệ | Kiến trúc | Speaker similarity median |
|---|---|---:|
| LEMAS-TTS | F5-TTS | 0,69 |
| OmniVoice | – | 0,57 |
| VieNeu-TTS | – | 0,35 |
| VoxCPM2 | – | 0,57 |
| vixTTS | XTTS | không có |

Cả 5 hệ đều là hệ mã nguồn mở. Trong bộ **không có** FPT.AI, Viettel hay ElevenLabs.

MLAAD không có giọng thật tiếng Việt. Trang gốc khuyên ghép với M-AILABS, mà M-AILABS là tiếng Anh, nên không ghép được cho tiếng Việt.

Có hai vấn đề:
- Văn bản là truyện dịch, câu dài (median 7 s). Câu thử thách của VeriClue chỉ 8–12 âm tiết.
- Theo SUMMARY, tập test MLAAD chỉ có vixTTS.

Giấy phép CC BY-NC 4.0, khớp trang HF.

### VSASV

Đã tải 1.223 file của 16 người (id00046 chiếm 196 mẫu, lệch nhiều). Có bonafide và replay; **không có TTS/VC**, vì nhóm đã loại theo quyết định ngày 16/10.

Bản đầy đủ theo paper Interspeech 2024 có **1.382 người**, khoảng 164 nghìn câu thật và hơn 174 nghìn câu giả. Trang HF ghi 69,2 GB và lưu ý "bản công bố không đầy đủ như paper".

Giấy phép CC BY-NC 4.0. Phải đồng ý chia sẻ thông tin liên hệ mới tải được.

### ViMD

Chỉ có **19 file / 0,10 giờ / 12 người**, gồm nữ 17 và nam 2 (theo cột gender). Đây là phỏng vấn trên đài truyền hình tỉnh. Âm thanh ở 44,1/48 kHz, nhiều file stereo.

Bản đầy đủ có 12.955 người, 102,56 giờ, 63 tỉnh.

Giấy phép **CC BY-NC-ND 4.0**. Hướng dẫn của Creative Commons về huấn luyện AI ("Using CC-licensed works for AI training") theo cách tiếp cận thận trọng nói rõ: *"CC-licensed work subject to the NoDerivatives restriction should not be used as training data."* Ngay cả khi mô hình chưa chắc là "tác phẩm phái sinh", cũng không được phát hành bản biến đổi của dữ liệu, ví dụ bản nén hay tăng cường (DATA-05).

→ **Không dùng để dạy.** Chỉ dùng để thử theo miền (Bắc/Trung/Nam), và hiện 19 file là quá ít.

### VIVOS

Đã tải 1.521 file / 2,14 giờ / 9 người. Bản gốc có 65 người, khoảng 15 giờ, đọc từng câu trong phòng yên tĩnh với micro tốt. Giấy phép **CC BY-NC-SA 4.0**, cấm tìm cách nhận dạng người nói; khớp trang HF.

Âm thanh rất sạch (nhiễu −63 dB), có khoảng 0,3 s im lặng hai đầu, gần như không có năng lượng trên 7 kHz. Khác xa micro điện thoại.

### ViSpoofDB (studie-e/Vietnamese-Audio-Deepfake-Detection)

**Nguồn giọng thật không phải VIVOS như đã ghi**, hoặc ít nhất phần lớn không phải. Có 3 bằng chứng:
- 24 kHz, có nội dung trên 8 kHz;
- 0/20 transcript khớp câu VIVOS;
- 0 file trùng byte (theo SUMMARY).

README gốc ghi nguồn là "VIVOS và VLSP". Đặc điểm 24 kHz và nội dung kiểu YouTube giống các bộ crawl 24 kHz (ví dụ viVoice). **Đây chỉ là giả thuyết, chưa xác minh.**

Hệ giả thực tế gồm: **edgetts, elevenlabs, fptai, gtts, mmstts, zaloai**. **Không có Viettel, không có Coqui**, trong khi README ghi FPT.AI, Viettel, ElevenLabs, Coqui (đã thấy khi train) và gTTS (chưa thấy). Số lượng cũng lệch: thật 5.500 so với khoảng 7.000 theo README; giả 7.195.

Nhãn chỉ suy ra từ thư mục `real/` và `fake/<hệ>/`. Không có ID người, không có transcript cho từng file.

**Định dạng**: MP3 chỉ có ở ElevenLabs (154 file); mọi file giả khác là WAV 16 kHz; mọi file thật là WAV 24 kHz.

**Trùng câu**: không trùng câu nào với VIVOS. Thật và giả đọc văn bản khác nhau.

**Giấy phép**: README có badge MIT nhưng không thấy file LICENSE. Code MIT cũng không có nghĩa là giọng người và âm thanh TTS thương mại (FPT, Zalo, ElevenLabs) được phép dùng. → Coi là **giấy phép chưa rõ**.

### Ảnh hưởng đến cách chia tập hiện tại (SUMMARY.md)

Luật "VIVOS + ViSpoofDB cùng test do chung nguồn người" dựa trên giả định ViSpoofDB thật lấy từ VIVOS. Đo đạc không ủng hộ giả định này: đổi luật thì vô hại, nhưng **lý do thì sai**.

Câu hỏi cho nhóm: có tách lại không, hay giữ nguyên test cho an toàn?

## 5. mms-tts-vie

| Mục | Giá trị |
|---|---|
| Kiến trúc | VITS (`VitsModel`) |
| Số giọng | **1** (`num_speakers: 1`, `speaker_embedding_size: 0`) |
| Tần số lấy mẫu | 16 kHz |
| Giấy phép | **CC BY-NC 4.0** (README và SOURCE.md) |
| Phiên bản | facebook/mms-tts-vie@b58928d |

Đánh giá:
- Sinh hàng loạt giọng giả từ mô hình này nghĩa là hàng nghìn mẫu **cùng một âm sắc**. Mô hình phát hiện sẽ học "giọng này = giả": đó là lộ đề nhận dạng người nói, và nó không khái quát sang FPT/Viettel/ElevenLabs.
- ViSpoofDB **đã có 1.200 mẫu `mmstts`**, nhiều khả năng cùng mô hình này. Dùng mms-tts-vie để dạy mà lại thử trên ViSpoofDB mmstts thì không còn là hệ "chưa thấy".
- Kết luận: chỉ dùng làm **một trong nhiều** hệ, giới hạn số mẫu (ví dụ ≤ 10 % lớp giả), câu 8–12 âm tiết **cùng phân bố với câu thật**, và đánh giá theo kiểu bỏ ra một hệ TTS (leave-one-TTS-out).
- Đầu ra cũng mang giấy phép NC; không tuyên bố là public domain.

## 6. Giấy phép: đối chiếu với trang gốc

| Bộ | SOURCE.md | Trang gốc (đã mở) | Khớp? | Hệ quả |
|---|---|---|---|---|
| MLAAD | CC BY-NC 4.0 | CC BY-NC 4.0, "strictly non-commercial academic research" | ✔ | Dạy được cho demo nghiên cứu |
| VSASV | CC BY-NC 4.0 | CC BY-NC 4.0 (có cổng chia sẻ liên hệ) | ✔ | Dạy được |
| ViMD | CC BY-NC-ND 4.0 | CC BY-NC-ND 4.0 | ✔ | **Không dạy**; chỉ đánh giá nội bộ; không phát hành bản biến đổi |
| VIVOS | CC BY-NC-SA 4.0 | CC BY-NC-SA 4.0 | ✔ | Dạy được; dữ liệu phái sinh phải giữ SA |
| ViSpoofDB | không rõ | README ghi MIT (code), không thấy LICENSE; mô tả nguồn và hệ **không khớp** dữ liệu thực tế | ✘ (mô tả) | Chỉ test nội bộ, có ghi chú |
| mms-tts-vie | CC BY-NC 4.0 | CC BY-NC 4.0 | ✔ | Sinh dữ liệu nội bộ được |

## 7. Vai trò đề xuất cho VeriClue

| Bộ | Vai trò | Điều kiện bắt buộc |
|---|---|---|
| **MLAAD-vi** | **Dạy (lớp giả)**, chỉ khi có điều kiện | Resample 16 kHz mono PCM16; cắt lặng bằng VAD rồi đệm lặng **ngẫu nhiên giống nhau cho cả hai lớp**; chuẩn hóa độ to (ví dụ −23 LUFS ± ngẫu nhiên); thêm nhiễu nền thấp cho mẫu có im lặng số; **cắt đoạn 2–4 s** để xóa lộ đề thời lượng; chia theo giọng tham chiếu (4 reader + vixTTS) **và** theo hệ TTS; báo kết quả bỏ ra một hệ (leave-one-TTS-out). Không có giọng thật để ghép, phải ghép với nguồn thật khác |
| **VSASV** bonafide | **Dạy (lớp thật)**, chính, vì gần kênh thực tế nhất | 16 người là quá ít, nên tải thêm người (bản đầy đủ có 1.382); float32 → PCM16; cân độ to. Replay: chỉ dùng cho calib/test kênh, **không gộp vào nhãn "giả TTS"**, vì replay to hơn 6 dB (lộ LUFS 0,90) và câu ngẫu nhiên đã chặn replay |
| **ViMD** | **Không dạy** (ND, chỉ 19 file) | Nếu dùng thì chỉ thử độ bền theo miền, nội bộ, sau khi tải thêm |
| **VIVOS** | Dạy (lớp thật) **bổ sung** hoặc test | Thêm nhiễu và mô phỏng kênh điện thoại để không thành "sạch = thật"; cắt bớt lặng 0,3 s; chia theo người |
| **ViSpoofDB** | **Chỉ test ngoài miền**, đọc kết quả thận trọng | Trước khi chấm: resample 16 kHz, **cắt mọi im lặng/đệm số 0 rồi cắt cùng độ dài**, giải mã MP3 rồi đánh giá riêng; báo theo từng hệ. Không dùng để chọn ngưỡng. Kết quả "thật vs giả" trên bộ này khi chưa xử lý là **vô nghĩa** (riêng thời lượng 5 s đã cho AUC ≈ 0,97) |
| **mms-tts-vie** | Sinh giả bổ sung, giới hạn | 1 giọng → giới hạn số mẫu; câu cùng kiểu câu thử thách; không thử trên ViSpoofDB mmstts như "hệ chưa thấy" |

### Nguồn giọng thật tiếng Việt tốt hơn (công khai, giấy phép rõ)

1. **Mozilla Common Voice – Tiếng Việt** (CC0): người dân đọc câu ngắn qua micro điện thoại hoặc trình duyệt, nhiều người, có ID ẩn danh. Đây là nguồn **khớp kênh eKYC nhất**.
2. **Google FLEURS `vi_vn`** (CC BY 4.0): câu đọc, nhiều người, có transcript; dùng tốt cho cả ASR lẫn lớp thật.
3. **Tự thu bằng app Android của nhóm**, có văn bản đồng ý, đọc đúng câu thử thách 8–12 âm tiết. Đây là nguồn duy nhất trùng hoàn toàn kênh và kịch bản. Nên dùng tối thiểu cho calib và test.
4. **VSASV bản đầy đủ** (1.382 người, CC BY-NC): lấy thêm bonafide.

Số giờ và phiên bản của (1) và (2) cần xác nhận khi tải.

### Câu hỏi cho nhóm

1. Cách chia hiện tại xếp ViSpoofDB + VIVOS chung test với lý do "cùng người". Bằng chứng cho thấy ViSpoofDB thật không phải VIVOS. Có giữ nguyên không?
2. Có cho phép tiền xử lý chung (resample, cắt lặng, cân LUFS, cắt cùng độ dài) **trước** khi dạy và chấm không? Nếu không, mọi AUC báo cáo trên các cặp ở §3 đều có thể là AUC của lộ đề.
3. Có tải Common Voice vi / FLEURS vi để thay ViMD làm nguồn thật không?
