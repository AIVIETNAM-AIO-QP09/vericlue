# Bàn giao · FOR-01 (kèm FOR-03 lõi) · AIVIETNAM-AIO-QP09+Claude · 2026-10-18 13:43

**Nhánh:** feat/FOR-01-forensic-real-mvp (tạo từ `origin/main` 3ff07cb; chưa mở PR tại thời điểm ghi)
**Trạng thái task sau phiên này:** doing — đây là **lõi MVP** (ADR-0012 đợt 2). Theo yêu cầu, `backlog.md` **không đổi** (FOR-01, FOR-03 vẫn `todo`). Đã tick trong thẻ E7 chỉ các tiêu chí thật sự có test hoặc thử tay.

## Đã xong
- **Chia đoạn** (`ml/src/vericlue_ml/forensic/segment.py`): đoạn 3 s chồng 50% (bước 1,5 s), đoạn đuôi neo vào cuối file, file ngắn hơn 3 s là một đoạn. **Gộp khoảng**: đoạn liền kề vượt ngưỡng thành một khoảng, mở rộng ±1 s, cắt vào [0, thời lượng], không bao giờ chồng nhau.
- **Đọc media** (`media.py`): metadata và khung hình bằng `cv2` (đã có trong extra `face`); tiếng của file âm thanh bằng `soundfile`, **hoặc `wave` chuẩn cho WAV PCM (không cần thư viện)**; tiếng của video (mp4/webm) bằng PyAV nếu máy đã có, rồi `ffmpeg`/`ffprobe` trên PATH (hoặc `FFMPEG_BINARY`/`FFPROBE_BINARY`), gọi bằng subprocess, tham số dạng danh sách, `-protocol_whitelist file,pipe`. **Lý do chọn:** `ffprobe` không có trên PATH máy dev Windows; wheel PyAV đóng gói FFmpeg mà giấy phép (LGPL hay GPL) chưa xác nhận được nên **không khai báo `av` làm dependency** (AGENTS §6 luật 6). Không có công cụ thì tiếng của video là `unavailable` (không đoán, không giả lập).
- **Pipeline** (`pipeline.py`): mỗi đoạn chạy `face_deepfake` (4 khung PNG), `voice_spoof` (WAV 16 kHz); `lipsync` luôn `unavailable` (cần video đoạn + câu đề bài của VOICE-05); `provenance` chạy trên cả file. Điểm thô → xác suất qua `CalibrationStore.apply` (identity theo ADR-0012); thiếu calibrator thì đoạn đó `error`, **không dùng điểm thô**. Ngưỡng `face.b/face.a`, `voice.spoof_threshold` lấy từ `thresholds.yaml` (không sửa). Đoạn không mặt/im lặng → `not_applicable`.
- **Kết luận một chiều**: có đoạn vượt ngưỡng hoặc thủy vân AI → `suspect`; thiếu/lỗi/`unavailable` ở bước **bắt buộc** (video: `face_deepfake`; có hoặc chưa biết có tiếng: `voice_spoof`), hoặc bước bắt buộc chỉ phân tích được < `MIN_COVERAGE_FRACTION` (50%) số đoạn, hoặc điểm mặt nằm giữa b và a → `inconclusive`; chỉ khi mọi bước bắt buộc chạy ổn mới `authentic` (kèm câu "không phải chứng nhận là thật"). Detector giả (`mock@…`) không bao giờ được dùng làm bằng chứng.
- **Provenance** (`provenance.py`, FOR-03): AudioSeal nạp OFFLINE từ `MODELS_DIR/audioseal-detector/detector_base.pth` bằng đường dẫn file, kiểm SHA-256 theo manifest trước `torch.load`, `nbits=16`, không mạng; xác suất theo mẫu → cửa sổ 0,5 s → khoảng thủy vân (≥ 1 s). C2PA bằng `c2pa-python` (đọc manifest, tắt tải từ xa và OCSP; chỉ tin `validation_status`). **Perth: chưa hỗ trợ** (manifest `blocked`), ghi rõ trong bằng chứng, không giả lập. `prob_attack=None` luôn; `score` = p cửa sổ lớn nhất (chỉ tham khảo, không vào hợp nhất). Không có thủy vân → "Không có tín hiệu nguồn gốc" + ghi chú không có nghĩa là thật. Đăng ký factory `provenance` trong `registry.py` (chỉ thêm factory + một dòng), `models.yaml`.
- **API/dịch vụ**: `USE_MOCK_MODELS=true` giữ nguyên bản mock; còn lại → `POST /v1/forensic/jobs` trả `queued`, `forensic_runner.run_forensic_job` chạy nền (BackgroundTasks, transaction riêng mỗi bước ghi, khóa tiến trình một phân tích một lúc, dùng lại detector đã preload của orchestrator), `GET /jobs/{id}` trả `progress`, lỗi → `failed` (verdict trống, `error`). Hàng đợi tối đa 8 job (429 `forensic_busy`); job dở dang được đánh `failed` (`interrupted`) khi API khởi động lại; báo cáo của job chưa `done` trả 409 `job_not_ready`. SHA-256 tính trên **byte gốc** trước mọi việc khác, file lưu nguyên vẹn (có test). Báo cáo HTML: khung mock hiện dữ liệu thật + mục Giới hạn; **chữ ký vẫn MOCK** (PLAT-06/FOR-04).
- **Hợp đồng** (`[contract]`, chỉ THÊM trường tùy chọn): `forensic.schema.json` + Pydantic + `openapi.json` + `apps/web/src/lib/api/schema.d.ts` sinh lại. ForensicJob thêm `progress, error, media, suspect_intervals, unavailable_modules, provenance, verdict_reason`; signal thêm `status, reason`. Không phá client cũ.
- Test mới: `ml/tests/test_forensic_{segment,media,pipeline,provenance}.py`, `services/api/tests/test_forensic_real.py` (và `test_forensic_schema.py` nếu có); chạy được cả khi CI chỉ cài extra `face` (đã giả lập bằng stub chặn soundfile/torch/c2pa/audioseal).

## Đang dở
- **`face_deepfake` (GenD, FACE-02) chưa có trên `main`** (nhánh `feat/FACE-02-gend-mvp`, chưa merge). Trên nhánh này mọi video ra `inconclusive` (đúng thiết kế), giọng/âm thanh vẫn chạy thật. Khi FACE-02 vào `main`: đăng ký factory là đủ; cần thêm calibrator identity cho `face_deepfake` (đúng `model_version` của GenD) nếu chưa có, vì thiếu calibrator thì mọi đoạn mặt là `error`.
- **`lipsync`** vẫn `unavailable` ở giám định (VOICE-05 cần câu đề bài; chưa có bản không prompt).
- **Calibrator `forensic`** riêng (thẻ FOR-01, cần tập calib có cả bản nén DATA-05) **chưa làm** — hôm nay không làm gì về dữ liệu.
- **Perth** chưa hỗ trợ (manifest `blocked`, chờ xác minh quyền trọng số; sha256 trống).
- Chưa ký báo cáo Ed25519 (FOR-04/PLAT-06); chưa có thang ENFSI / tỷ số khả năng.
- Giao diện `/forensic` (FOR-02) không thuộc phiên này (trang vẫn 6 dòng); type web đã sinh lại.

## Bước tiếp theo
1. Sau khi FACE-02 vào `main`: chạy lại thử tay (bên dưới) với GenD thật; đo thời gian video 60 s (GenD ≈ 6,5 s cho 3 khung trên CPU theo bàn giao FACE-02 → ước ~4 phút cho 39 đoạn, **chưa đo**). Tăng/giảm `FRAMES_PER_SEGMENT` (hiện 4) theo thời gian.
2. Thêm calibrator identity `face_deepfake` nếu chưa có; sau đó tạo calibrator `forensic` thật khi có DATA-05.
3. Cài `ffmpeg` (và `ffprobe`) trên máy chạy API nếu muốn phân tích tiếng của mp4/webm; hoặc quyết cho phép dependency `av` sau khi xác nhận giấy phép FFmpeg đi kèm. Đặt `FFMPEG_BINARY`/`FFPROBE_BINARY` nếu không nằm trên PATH.
4. Hàng đợi một worker thật sự (hiện giới hạn 8 job chờ, mỗi job chờ giữ một luồng) và khôi phục job khi chạy nhiều worker (hiện chỉ đúng cho một tiến trình).
5. Đưa `generator_base.pth` của AudioSeal (sha256 `7a845b5fbe9364a63a3909d8ab3fe064d13a76ae4c2e983573e08c69b7b51748`, cùng revision `3c19eba…`) vào `models/manifest.yaml` nếu muốn test/red-team tự tạo file thủy vân trong repo (hôm nay dùng bản tải riêng để thử tay).

## Quyết định, lưu ý, bẫy
- **Không chạy qua orchestrator**: trần 4 s mỗi lần gọi (`detector_timeout_seconds` ≤ 4) không đủ cho phân tích từng đoạn; nên giám định gọi trực tiếp từng detector, nhưng vẫn dùng detector đã preload của orchestrator (`Orchestrator.loaded_detector`, thêm mới) và calibrator của router. Hệ quả: hồ sơ `ROUTER_PROFILE=mvp` (tắt `lipsync`, `provenance` cho eKYC) **không** ảnh hưởng giám định; `provenance` được tự nạp (một lần) ngay cả khi hồ sơ không có nó.
- Ở `USE_MOCK_MODELS=mixed`, orchestrator trả mock cho `face_deepfake`; pipeline **bỏ** detector có version `mock@` (coi là `unavailable`). Đừng đổi điều này.
- Kết quả luôn là **điểm tạm**: calibrator identity (ADR-0012), ngưỡng `thresholds.yaml` đang `provisional`; các hằng số mới (`FRAMES_PER_SEGMENT=4`, `MIN_COVERAGE_FRACTION=0.5`, `MAX_DURATION_SECONDS=600`, cửa sổ/ngưỡng thủy vân, `MAX_PENDING_JOBS=8`) là hằng số có tên, chưa đo trên dữ liệu thật (AGENTS §6 luật 9).
- Thủy vân AudioSeal: chưa đo tỉ lệ báo nhầm trên giọng thật, độ bền sau nén (MP3/AAC/Opus), đổi sample rate. Thông điệp 16 bit không cho biết "công cụ nào" — kết luận ghi "thủy vân AI của AudioSeal".
- `torch.load(weights_only=False)` của thư viện `audioseal` chạy sau khi đã kiểm SHA-256 file; có khe hở TOCTOU rất nhỏ giữa lúc băm và lúc nạp (file được đọc hai lần).
- C2PA: cần cài extra `c2pa` (wheel Windows ~88 MB, ~300 MB trên đĩa); thiếu thì C2PA ghi `unavailable`, không đổ. Chưa thử trên WAV/MP3 có manifest thật (chỉ có fixture JPG/MP4 ở c2pa-rs); chứng chỉ thử cho `Valid` nhưng `untrusted`.
- `uv.lock` đổi (thêm `audioseal`, `c2pa-python`, `einops`, `omegaconf`, `toml`, `cryptography`); extra mới: `forensic`, `c2pa` (`ml/pyproject.toml`). CI chỉ cài `--extra face`, các test cần thư viện khác đã `importorskip`.
- Đã sửa theo review: `null` vi phạm schema (nới schema, thêm test), báo cáo cho job chưa xong (409), ngưỡng bao phủ cho `authentic`, trần thời lượng, hàng đợi, khôi phục job, `-protocol_whitelist`, thông báo timeout ffmpeg, ảnh tĩnh → `unsupported_media`.
- ADR-0012 nằm ở `docs/adr/0012-mvp-chay-that.md` (đã vào `main`).

## Câu hỏi cho nhóm
- Có cho phép thêm dependency `av` (PyAV) để giải mã tiếng của video không? Cần ai đó xác nhận FFmpeg đi kèm wheel là LGPL (không GPL) trước khi khai báo. Hiện dựa vào `ffmpeg` do người vận hành tự cài.
- Calibrator `forensic` (thẻ FOR-01): có chấp nhận dùng identity cho MVP rồi thay khi có DATA-05 không (hiện đang làm vậy)?
- `lipsync` ở giám định: cần bản SyncNet không phụ thuộc câu đề bài (VOICE-05); hoặc bỏ lipsync khỏi giám định MVP?
- Thang ENFSI/tỷ số khả năng (ADR-0008) phụ thuộc calibrator thật; ghi nhận là chưa làm.

## Test đã chạy
Chạy trên `feat/FOR-01-forensic-real-mvp` sau tất cả sửa đổi cuối:
```
uv run ruff check . && uv run ruff format --check .       -> sạch (286 file)
uv run python scripts/gen_openapi.py --check              -> openapi.json khớp code
uv run python scripts/plan_check.py                       -> 0 lỗi, 0 cảnh báo
uv run pytest                                             -> 2319 passed, 28 skipped (đủ extra face, voice, forensic, c2pa)
giả lập CI (stub chặn soundfile, torch, c2pa, audioseal, ...; PYTHONPATH):
  pytest ml/tests services/api/tests                      -> 2020 passed, 18 skipped
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
| ViCocktail `0000142565.mp4` (96×96 h264, 4,8 s, có tiếng) | 2 đoạn, 5,6 s; `voice_spoof` ≈ 0,001 (ok); không thủy vân, không C2PA; **inconclusive** vì `face_deepfake` chưa có |
| ViCocktail `0000142566.mp4` (14,96 s) | 9 đoạn, 16,4 s; `voice_spoof` ≈ 0–0,001; **inconclusive** (cùng lý do) |
| Video lặp từ clip trên tới 60 s (`ffmpeg -stream_loop`, chỉ để đo thời gian) | **39 đoạn, 68,9 s** trên CPU, chỉ giọng + provenance (chưa có GenD) |
| Giọng thật VIVOS (VIVOSDEV08_002) lặp tới 12 s | 7 đoạn, 12,1 s; `voice_spoof` ≈ 0–0,001; không thủy vân → **"Không có tín hiệu nguồn gốc"**, verdict `authentic` kèm cảnh báo không phải chứng nhận thật |
| Cùng giọng đó, gắn thủy vân AudioSeal ở giây 4–8 (generator tải riêng) | **Phát hiện khoảng 4,0–8,0 s**, p ≈ 0,987, 16 bit thông điệp đọc được; `voice_spoof` vẫn thấp (đúng: giọng người thật gắn thủy vân) → verdict `suspect` do thủy vân |
Chưa thử: GenD (chưa có), âm thanh AI thật có thủy vân, file sau nén MP3/AAC, C2PA trên file có manifest thật, GPU, Perth (Chatterbox).
