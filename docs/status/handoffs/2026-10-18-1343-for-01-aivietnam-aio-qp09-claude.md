# Bàn giao · FOR-01 (kèm FOR-03 lõi) · AIVIETNAM-AIO-QP09+Claude · 2026-10-18 13:43

**Nhánh:** feat/FOR-01-forensic-real-mvp (đã **rebase lên `main`** sau khi PR #31 GenD và #32 lipsync vào; PR #33)
**Trạng thái task sau phiên này:** doing — đây là **lõi MVP** (ADR-0012 đợt 2). Theo yêu cầu, `backlog.md` **không đổi** (FOR-01, FOR-03 vẫn `todo`). Đã tick trong thẻ E7 chỉ các tiêu chí thật sự có test hoặc thử tay.

## Đã xong
- **Chia đoạn** (`ml/src/vericlue_ml/forensic/segment.py`): đoạn 3 s chồng 50% (bước 1,5 s), đoạn đuôi neo vào cuối file, file ngắn hơn 3 s là một đoạn. **Gộp khoảng**: đoạn liền kề vượt ngưỡng thành một khoảng, mở rộng ±1 s, cắt vào [0, thời lượng], không bao giờ chồng nhau.
- **Đọc media** (`media.py`): metadata và khung hình bằng `cv2` (đã có trong extra `face`); tiếng của file âm thanh bằng `soundfile`, **hoặc `wave` chuẩn cho WAV PCM (không cần thư viện)**; tiếng của video (mp4/webm) bằng PyAV nếu máy đã có, rồi `ffmpeg`/`ffprobe` trên PATH (hoặc `FFMPEG_BINARY`/`FFPROBE_BINARY`), gọi bằng subprocess, tham số dạng danh sách, `-protocol_whitelist file,pipe`. **Lý do chọn:** `ffprobe` không có trên PATH máy dev Windows; wheel PyAV đóng gói FFmpeg mà giấy phép (LGPL hay GPL) chưa xác nhận được nên **không khai báo `av` làm dependency** (AGENTS §6 luật 6). Không có công cụ thì tiếng của video là `unavailable` (không đoán, không giả lập).
- **Pipeline** (`pipeline.py`): mỗi đoạn chạy `face_deepfake` (**8 khung PNG**, như eKYC; KHÔNG dùng 32 khung của chế độ giám định vì 39 đoạn × 32 khung quá chậm. Truyền `metadata={"mode":"forensic"}` nhưng **số khung do pipeline quyết** bằng số ảnh đưa vào: GenD lấy tối đa số ảnh có), `voice_spoof` (WAV 16 kHz); `lipsync` luôn `unavailable` (cần video đoạn + câu đề bài của VOICE-05); `provenance` chạy trên cả file. Điểm thô → xác suất qua `CalibrationStore.apply` (identity theo ADR-0012); thiếu calibrator thì đoạn đó `error`, **không dùng điểm thô**. Ngưỡng `face.b/face.a`, `voice.spoof_threshold` lấy từ `thresholds.yaml` (không sửa). Đoạn không mặt/im lặng → `not_applicable`.
- **Kết luận một chiều**: có đoạn vượt ngưỡng hoặc thủy vân AI → `suspect`; **bước bắt buộc** (video: `face_deepfake`; có hoặc chưa biết có tiếng: `voice_spoof`) thiếu mô hình (`unavailable`), có đoạn `error`, hoặc chỉ phân tích được < `MIN_COVERAGE_FRACTION` (50%) số đoạn, hoặc điểm mặt nằm giữa b và a → `inconclusive`; ngược lại → `authentic` (kèm câu "không phải chứng nhận là thật"). **Đoạn `degraded`/`not_applicable` (không mặt, im lặng, đầu vào kém) KHÔNG chặn cả video**: chỉ tính vào tỉ lệ phủ; chỉ `error` mới chặn (quyết định trưởng nhóm khi duyệt PR #33). Detector giả (`mock@…`) không bao giờ được dùng làm bằng chứng.
- **Provenance** (`provenance.py`, FOR-03): AudioSeal nạp OFFLINE từ `MODELS_DIR/audioseal-detector/detector_base.pth` bằng đường dẫn file, kiểm SHA-256 theo manifest trước `torch.load`, `nbits=16`, không mạng; xác suất theo mẫu → cửa sổ 0,5 s → khoảng thủy vân (≥ 1 s). C2PA bằng `c2pa-python` (đọc manifest, tắt tải từ xa và OCSP; chỉ tin `validation_status`). **Perth: chưa hỗ trợ** (manifest `blocked`), ghi rõ trong bằng chứng, không giả lập. `prob_attack=None` luôn; `score` = p cửa sổ lớn nhất (chỉ tham khảo, không vào hợp nhất). Không có thủy vân → "Không có tín hiệu nguồn gốc" + ghi chú không có nghĩa là thật. Đăng ký factory `provenance` trong `registry.py` (chỉ thêm factory + một dòng), `models.yaml`. Nếu có âm thanh mà AudioSeal không chạy được (thiếu trọng số/thư viện, lỗi) thì `status=degraded` kèm ghi chú "Quét chưa đầy đủ" (không để `ok` + "Không có tín hiệu nguồn gốc").
- **API/dịch vụ**: `USE_MOCK_MODELS=true` giữ nguyên bản mock; còn lại → `POST /v1/forensic/jobs` trả `queued`, `forensic_runner.run_forensic_job` chạy nền (BackgroundTasks, transaction riêng mỗi bước ghi, khóa tiến trình một phân tích một lúc, dùng lại detector đã preload của orchestrator), `GET /jobs/{id}` trả `progress`, lỗi → `failed` (verdict trống, `error`). Hàng đợi tối đa 8 job (429 `forensic_busy`); job dở dang được đánh `failed` (`interrupted`) khi API khởi động lại; báo cáo của job chưa `done` trả 409 `job_not_ready`. SHA-256 tính trên **byte gốc** trước mọi việc khác, file lưu nguyên vẹn (có test). Báo cáo HTML: khung mock hiện dữ liệu thật + mục Giới hạn; **chữ ký vẫn MOCK** (PLAT-06/FOR-04).
- **Hợp đồng** (`[contract]`, chỉ THÊM trường tùy chọn): `forensic.schema.json` + Pydantic + `openapi.json` + `apps/web/src/lib/api/schema.d.ts` sinh lại. ForensicJob thêm `progress, error, media, suspect_intervals, unavailable_modules, provenance, verdict_reason`; signal thêm `status, reason`. Không phá client cũ.
- Test mới: `ml/tests/test_forensic_{segment,media,pipeline,provenance}.py`, `services/api/tests/test_forensic_real.py` (và `test_forensic_schema.py` nếu có); chạy được cả khi CI chỉ cài extra `face` (đã giả lập bằng stub chặn soundfile/torch/c2pa/audioseal).

## Đang dở
- **`face_deepfake` (GenD)** đã vào `main` (PR #31) và đăng ký trong `registry.py`; calibrator identity của GenD đã có trong `ml/configs/calibrators/face_deepfake/`. Giám định dùng được GenD thật (xem thử tay). Việc còn lại: thời gian CPU lớn (xem dưới) và ngưỡng tạm làm video thật rơi vào khoảng giữa b và a.
- **`lipsync`** vẫn `unavailable` ở giám định (VOICE-05 cần câu đề bài; chưa có bản không prompt).
- **Calibrator `forensic`** riêng (thẻ FOR-01, cần tập calib có cả bản nén DATA-05) **chưa làm** — hôm nay không làm gì về dữ liệu.
- **Perth** chưa hỗ trợ (manifest `blocked`, chờ xác minh quyền trọng số; sha256 trống).
- Chưa ký báo cáo Ed25519 (FOR-04/PLAT-06); chưa có thang ENFSI / tỷ số khả năng.
- Giao diện `/forensic` (FOR-02) không thuộc phiên này (trang vẫn 6 dòng); type web đã sinh lại.

## Bước tiếp theo
1. Đo thời gian video 60 s **có mặt** với GenD thật trên máy GPU demo (`--extra cuda`): CPU ≈ 10 s/đoạn 1080p (8 khung) → 39 đoạn ≈ 6–7 phút (ngoại suy, **chưa đo**). Tăng/giảm `FRAMES_PER_SEGMENT` (hiện 8) nếu cần.
2. Tạo calibrator `forensic` thật (DATA-05, có bản nén) rồi chỉnh ngưỡng; hiện video thật 1080p ra p ≈ 0,15–0,26, nằm giữa b = 0,15 và a = 0,60 nên `inconclusive` (ngưỡng/calibrator đều tạm).
3. Cài `ffmpeg` (và `ffprobe`) trên máy chạy API nếu muốn phân tích tiếng của mp4/webm; hoặc quyết cho phép dependency `av` sau khi xác nhận giấy phép FFmpeg đi kèm. Đặt `FFMPEG_BINARY`/`FFPROBE_BINARY` nếu không nằm trên PATH.
4. Hàng đợi một worker thật sự (hiện giới hạn 8 job chờ, mỗi job chờ giữ một luồng) và khôi phục job khi chạy nhiều worker (hiện chỉ đúng cho một tiến trình).
5. Đưa `generator_base.pth` của AudioSeal (sha256 `7a845b5fbe9364a63a3909d8ab3fe064d13a76ae4c2e983573e08c69b7b51748`, cùng revision `3c19eba…`) vào `models/manifest.yaml` nếu muốn test/red-team tự tạo file thủy vân trong repo (hôm nay dùng bản tải riêng để thử tay).

## Quyết định, lưu ý, bẫy
- **Không chạy qua orchestrator**: trần 4 s mỗi lần gọi (`detector_timeout_seconds` ≤ 4) không đủ cho phân tích từng đoạn; nên giám định gọi trực tiếp từng detector, nhưng vẫn dùng detector đã preload của orchestrator (`Orchestrator.loaded_detector`, thêm mới) và calibrator của router. Hệ quả: hồ sơ `ROUTER_PROFILE=mvp` (tắt `lipsync`, `provenance` cho eKYC) **không** ảnh hưởng giám định; `provenance` được tự nạp (một lần) ngay cả khi hồ sơ không có nó.
- Ở `USE_MOCK_MODELS=mixed`, orchestrator trả mock cho `face_deepfake`; pipeline **bỏ** detector có version `mock@` (coi là `unavailable`). Đừng đổi điều này.
- **Video không có luồng tiếng** (RTFS-10k): khi giải mã biết chắc không có tiếng, `has_audio=False`, `voice_spoof` là `not_applicable` và **không bắt buộc** (nếu không thì video câm luôn `inconclusive` oan). Chỉ khi không giải mã được (thiếu `ffmpeg`/PyAV) thì `voice_spoof` mới là `unavailable` và chặn `authentic`. Lỗi này lộ ra khi thử tay trên video thật.
- Kết quả luôn là **điểm tạm**: calibrator identity (ADR-0012), ngưỡng `thresholds.yaml` đang `provisional`; các hằng số mới (`FRAMES_PER_SEGMENT=8`, `MIN_COVERAGE_FRACTION=0.5`, `MAX_DURATION_SECONDS=600`, cửa sổ/ngưỡng thủy vân, `MAX_PENDING_JOBS=8`) là hằng số có tên, chưa đo trên dữ liệu thật (AGENTS §6 luật 9).
- Thủy vân AudioSeal: chưa đo tỉ lệ báo nhầm trên giọng thật, độ bền sau nén (MP3/AAC/Opus), đổi sample rate. Thông điệp 16 bit không cho biết "công cụ nào" — kết luận ghi "thủy vân AI của AudioSeal".
- `torch.load(weights_only=False)` của thư viện `audioseal` chạy sau khi đã kiểm SHA-256 file; có khe hở TOCTOU rất nhỏ giữa lúc băm và lúc nạp (file được đọc hai lần).
- C2PA: cần cài extra `c2pa` (wheel Windows ~88 MB, ~300 MB trên đĩa); thiếu thì C2PA ghi `unavailable`, không đổ. Chưa thử trên WAV/MP3 có manifest thật (chỉ có fixture JPG/MP4 ở c2pa-rs); chứng chỉ thử cho `Valid` nhưng `untrusted`.
- `uv.lock` đổi (thêm `audioseal`, `c2pa-python`, `einops`, `omegaconf`, `toml`, `cryptography`); extra mới: `forensic`, `c2pa` (`ml/pyproject.toml`). CI chỉ cài `--extra face`, các test cần thư viện khác đã `importorskip`.
- **Sau rebase:** `registry.py` giữ đủ mọi factory (provenance, face_deepfake, quality, lipsync, camprobe, voice_*, face_pad); `models.yaml` giữ `lipsync: syncnet`, `provenance: audioseal-detector`. `ml/pyproject.toml` giữ đủ extra face, gend, voice, forensic, c2pa, eval, cuda; `audioseal` thêm vào `cuda` và `forensic` khai báo xung đột với `cuda` (pyproject gốc) để audioseal không kéo torch cu130 ngoài ý muốn; `uv.lock` sinh lại bằng `uv lock` (không gộp tay), `uv lock --check` qua. `test_device` khớp cuda = face + gend + voice + forensic. CI vẫn chỉ `--extra face`.
- Đã sửa theo review: `null` vi phạm schema (nới schema, thêm test), báo cáo cho job chưa xong (409), ngưỡng bao phủ cho `authentic`, trần thời lượng, hàng đợi, khôi phục job, `-protocol_whitelist`, thông báo timeout ffmpeg, ảnh tĩnh → `unsupported_media`.
- ADR-0012 nằm ở `docs/adr/0012-mvp-chay-that.md` (đã vào `main`). Báo cáo HTML có thêm giới hạn: "Ngưỡng eKYC áp cho từng đoạn nên video dài dễ báo nghi ngờ nhầm." ffmpeg giải mã tiếng bị giới hạn `-t 600` (bằng trần thời lượng).

## Câu hỏi cho nhóm
- Có cho phép thêm dependency `av` (PyAV) để giải mã tiếng của video không? Cần ai đó xác nhận FFmpeg đi kèm wheel là LGPL (không GPL) trước khi khai báo. Hiện dựa vào `ffmpeg` do người vận hành tự cài.
- Calibrator `forensic` (thẻ FOR-01): có chấp nhận dùng identity cho MVP rồi thay khi có DATA-05 không (hiện đang làm vậy)?
- `lipsync` ở giám định: cần bản SyncNet không phụ thuộc câu đề bài (VOICE-05); hoặc bỏ lipsync khỏi giám định MVP?
- Thang ENFSI/tỷ số khả năng (ADR-0008) phụ thuộc calibrator thật; ghi nhận là chưa làm.

## Test đã chạy
Chạy trên `feat/FOR-01-forensic-real-mvp` (đã rebase lên `main` 3caa13e) sau tất cả sửa đổi cuối:
```
uv run ruff check . && uv run ruff format --check .       -> sạch (286 file)
uv run python scripts/gen_openapi.py --check              -> openapi.json khớp code
uv run python scripts/plan_check.py                       -> 0 lỗi, 0 cảnh báo
uv lock --check                                           -> Resolved 140 packages
uv run pytest                                             -> 2686 passed, 30 skipped (đủ extra face, gend, voice, forensic, c2pa)
giả lập CI (stub chặn soundfile, torch, c2pa, audioseal, ...; PYTHONPATH):
  pytest ml/tests services/api/tests                      -> 2346 passed; 27 failed chỉ ở test_face_gend.py và test_face02_integration.py (FACE-02) vì stub của tôi chặn cả torch/safetensors mà các test đó cần — không phải mã FOR-01; CI thật là chuẩn
cd apps/web && npm run lint                               -> sạch
cd apps/web && npm run test                               -> 22 file passed, 1 skipped; 1314 test passed, 10 skipped
cd apps/web && npx tsc --noEmit                           -> sạch (sau npm run gen:api)
cd apps/web && npm run build                              -> Compiled successfully
```
Test giám định mới: `ml/tests/test_forensic_{segment,media,pipeline,provenance}.py`, `services/api/tests/test_forensic_{real,schema}.py`; có 1 test `slow` nạp AudioSeal thật (tự skip khi thiếu trọng số). Chưa chạy: Playwright; GPU; GenD (chưa có trên nhánh).

### Thử tay (KHÔNG phải số liệu, không dùng cho báo cáo; detector thật, CPU i7-13620H, torch 2.14.1+cpu)
Chạy bằng script ngoài repo (`scratchpad/trial/trial.py`), `FFMPEG_BINARY` trỏ ffmpeg tạm từ gói `imageio-ffmpeg` (chỉ để thử trên máy này, không phải dependency), `MODELS_DIR=D:\Projects\vericlue-store\models`. Nạp mô hình AntiDeepfake + AudioSeal ≈ 23–25 s (một lần).
| File | Kết quả |
|---|---|
| ViCocktail `0000142566.mp4` (96×96 h264, 14,96 s, có tiếng; khuôn mặt cắt nhỏ) | 9 đoạn, 21,7 s; `voice_spoof` ≈ 0–0,001; `face_deepfake` **not_applicable** (SCRFD không dò được mặt 96×96) → **inconclusive** (đúng: không có đoạn nào phân tích được mặt) |
| Video lặp tới 60 s từ clip ViCocktail (`ffmpeg -stream_loop`, chỉ đo thời gian; chưa có GenD lúc đo) | 39 đoạn, 68,9 s trên CPU, chỉ giọng + provenance |
| RTFS-10k video gốc `0_SSnD8LJo0_00155_00180.mp4` (1920×1080 h264, 25 s, **không có luồng tiếng**) | 16 đoạn, **172,9 s** CPU (≈ 10,8 s/đoạn, 8 khung/đoạn); GenD `face_deepfake` p ≈ 0,15–0,26 mỗi đoạn; voice not_applicable; verdict **inconclusive** (điểm nằm giữa b = 0,15 và a = 0,60) |
| RTFS-10k bản đổi mặt `inswapper_…_2-25_man.mp4` (1080p hevc, 25 s) | 16 đoạn, **158,0 s**; GenD p ≈ 0,99 mọi đoạn; khoảng nghi giả 0–25,0 s; verdict **suspect** |
| Giọng thật VIVOS (VIVOSDEV08_002) lặp tới 12 s | 7 đoạn, 12,1 s; `voice_spoof` ≈ 0–0,001; không thủy vân → **"Không có tín hiệu nguồn gốc"**, verdict `authentic` kèm cảnh báo không phải chứng nhận thật |
| Cùng giọng đó, gắn thủy vân AudioSeal ở giây 4–8 (generator tải riêng) | **Phát hiện khoảng 4,0–8,0 s**, p ≈ 0,987, 16 bit thông điệp đọc được; `voice_spoof` vẫn thấp (đúng: giọng người thật gắn thủy vân) → verdict `suspect` do thủy vân |
Chưa thử: video có mặt LẪN có tiếng (RTFS không có tiếng; ViCocktail mặt quá nhỏ), GPU, âm thanh AI thật có thủy vân, file sau nén MP3/AAC, C2PA trên file có manifest thật, Perth (Chatterbox). Số trên là thử tay một lần, **không phải số liệu**.
