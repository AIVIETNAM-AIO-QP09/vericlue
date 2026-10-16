# E1 — Dữ liệu và mô hình (DATA)

> Mục tiêu epic: mọi người có cùng dữ liệu và mô hình bằng một lệnh; dữ liệu chia đúng cách; có dữ liệu người Việt tự tạo từ nguồn công khai.
> Nguồn: `docs/data/data-plan.md`, `models/manifest.yaml`, ADR-0002.

---

### DATA-01 · Script tải dữ liệu công khai

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 (ảnh) + M4 (âm thanh) | 1 | S0 | P0 | PLAT-01 |

**Mục tiêu:** `scripts/download_data.py` tải đúng phần cần dùng của từng bộ vào `data/raw/<tên>/`.
**Đọc trước:** `docs/data/data-plan.md` (đường dẫn, giấy phép, kích thước).

**Đầu ra:** script có tham số `--only <tên>`, `--subset small|full`. Hỗ trợ:
- **Ảnh:** zalo2022, fas_vn (maihongtng), rtfs10k (bản nhỏ: khoảng 1.000 video giả + video thật ghép cặp), wilddeepfake (một phần), celeba_spoof (một phần), vn_celeb_faces, vicocktail (một phần), lavdf (một phần).
- **Âm thanh:** mlaad_vi (chỉ `fake/vi`), vispoofdb, vsasv (một phần), vimd (lấy đều 3 miền), vivos.
- Ghi `data/raw/<tên>/SOURCE.md`: nguồn, ngày tải, giấy phép, số file.

**Tiêu chí hoàn thành:**
- [ ] `--subset small` chạy hết trong một đêm, tải tiếp được sau khi ngắt, tổng < 30 GB; ghi tốc độ (MB/s) và thời gian thực vào bàn giao — quyết định trưởng nhóm 15/10.
- [x] Bộ cần đăng ký (HF gated) báo rõ cách lấy token nếu thiếu `HF_TOKEN`.
- [ ] Mỗi bộ có `SOURCE.md`.

**Nghiệm thu DATA-01 (15/10/2026):** trưởng nhóm duyệt để `review` sau khi tải
small thật `vn_celeb_faces` và `vivos`. Chưa nghiệm thu chạy đủ một đêm/<30 GB hoặc SOURCE
đủ mọi bộ cho đến khi chạy small đủ danh mục với credentials. CelebA-Spoof/LAV-DF
được phép báo skipped nếu chưa xác minh HTTP Range và metadata nhóm nguồn;
không tự tải full. Dependency tải dữ liệu nằm trong nhóm tùy chọn `data`.

**Ngoại lệ chọn tập con:** ViCocktail, WildDeepfake: chọn theo shard/archive, có chỉ mục video
— quyết định trưởng nhóm 15/10. `index.csv` cạnh SOURCE ghi source_video_id và subject_id
nếu nguồn có; không tạo ID người giả. WildDeepfake kiểm tra video xuất hiện xuyên archive.
FAS-VN small = full, tải nguyên gói dataset một lần. ViSpoofDB small dự phòng 2,6 GB.
Log tách thời gian HTTP/mạng và xử lý/hash/index/giải nén.

**Sửa MLAAD-vi/VSASV — quyết định trưởng nhóm 16/10:**
MLAAD chỉ giữ WAV có metadata và `original_file` hợp lệ, giữ nguyên nhóm câu nguồn
xuyên TTS; bỏ riêng file thiếu metadata (pin khảo sát: 159/5.000 WAV VieNeu-TTS),
ghi số lượng/lý do theo hệ vào SOURCE, không bỏ cả bộ. Giữ đường dẫn
`reference_speaker` nếu có; không tạo ID người từ đường dẫn tham chiếu.
VSASV dùng `label` làm mã người nói công bố, xác minh với thư mục `file`;
small chỉ lấy **bonafide + replay**, nguyên nhóm hợp lệ xuyên shard, ưu tiên người
có replay. Loại **60.949 voice_conversion + 60.949 adversarial_attack** ở pin khảo sát
vì không xác minh được người nguồn; SOURCE phải ghi số lượng thực theo revision.
Adapter cũng giới hạn full ở phần hợp lệ này, không tự mở lại loại tấn công bị loại.
Audio Parquet dạng mảng được xuất **WAV float32, giữ nguyên sampling_rate**, không
resample/clipping. DATA-03 phải kiểm trùng người xuyên bộ qua giọng tham chiếu MLAAD
và đối chiếu **VSASV ↔ VIVOS/ViMD**; ID nội bộ bộ dữ liệu không chứng minh danh tính
xuyên bộ. DATA-01 vẫn review cho đến nghiệm thu đủ danh mục.

**Lưu ý:** gửi ngay hôm nay các yêu cầu cần chờ duyệt: SEA-Spoof (email tác giả), FaceForensics++, DeepSpeak v1, Deepfake-Eval-2024. Không chặn việc khác nếu chưa được duyệt.

---

### DATA-02 · Script tải mô hình

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S0 | P0 | PLAT-01 |

**Mục tiêu:** `scripts/download_models.py` tải mọi mô hình trong `models/manifest.yaml`, ghi và kiểm SHA-256.

**Tiêu chí hoàn thành:**
- [x] Tải đủ GenD, AntiDeepfake, PhoWhisper, SyncNet (`stable_syncnet`), MiniFASNet (qua uniface), SCRFD **det_10g**, CTC aligner và AudioSeal, kèm CLIP nền của GenD vào MODELS_DIR; **trừ SBI (FACE-03) và PerTh (FOR-03)**, theo quyết định trưởng nhóm 15/10.
- [x] Lần đầu điền `sha256` vào manifest; các lần sau kiểm tra và báo sai lệch.
- [x] Không mirror SBI (điều khoản hạn chế chia sẻ) — mỗi máy tải từ nguồn gốc; quyết định trưởng nhóm 15/10.

**Quyết định 15/10:** MODELS_DIR từ biến môi trường, mặc định ./models; máy nhóm dùng D:\Projects\vericlue-store\models. SCRFD UniFace phải byte-identical det_10g repo GenD; SyncNet ghi OpenRAIL++; PerTh chờ xác minh quyền trọng số — FOR-03. SBI giữ nguồn gốc/chưa pin, không chặn task.

---

### DATA-03 · Chia tập theo người

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 + M4 | 1 | S1 | P0 | DATA-01 |

**Mục tiêu:** mỗi bộ có danh sách train / calib_fit / calib_ltt / test, **không trùng người** giữa các tập (ADR-0010).
**Đầu ra:** `scripts/make_splits.py` → `data/splits/<bộ>/{train,calib_fit,calib_ltt,test}.csv` (cột: path, label, attack_type, subject_id, source, region nếu có). Thống kê số mẫu theo nhãn và loại tấn công → `data/splits/SUMMARY.md`.

**Quy tắc chia:**
- Phần calib (khoảng 20%) chia tiếp **theo người** thành `calib_fit` và `calib_ltt`, mặc định 50/50:
  - `calib_fit`: chọn mô hình, hiệu chỉnh, trọng số hợp nhất, tham chiếu kNN;
  - `calib_ltt`: **chỉ** để chọn ngưỡng (ROUT-03) và p-value cổng ngoài phạm vi (ROUT-04); không dùng để học gì.
  - Task card nào ghi "tập calib" mà không nói rõ thì hiểu là `calib_fit`.
- Zalo 2022 chỉ tập train có nhãn → chia 60/20/20 theo người.
- MLAAD-vi chia theo câu và hệ TTS.
- **ViSpoofDB giữ nguyên làm test** (công cụ chưa từng thấy).
- RTFS-10k chia theo video gốc (cặp thật–giả nằm cùng tập).
- ViMD chia theo người, giữ cân bằng 3 miền.

**Phạm vi làm trước — âm thanh, quyết định trưởng nhóm 16/10:**
- DATA-03 giữ `doing`; phần ảnh đợi dữ liệu Kaggle, không nghiệm thu toàn task.
- ViSpoofDB và VIVOS cùng `test`: có bằng chứng VIVOS là nguồn giọng thật.
- VSASV chia theo 16 ID người. ViMD small: bốn người/miền, mỗi tập một
  người/miền (rất nhỏ; 25% người mỗi tập). **Giả định** hai bộ thu thập độc lập
  với nhau và với VIVOS/ViSpoofDB; chưa xác minh khác người xuyên bộ.
- MLAAD union `original_file` với nhóm giọng tham chiếu theo thư mục reader;
  thiếu reference chỉ nhóm theo câu nguồn, không gom toàn bộ vixTTS. Không tạo
  subject ID giả. Phân tầng TTS chỉ trong giới hạn nhóm liên kết; không cam kết
  giữ riêng một TTS chưa thấy. Reference chưa đối chiếu xuyên bộ phải ghi rõ;
  có crosswalk xác minh thì nhóm liên kết theo cùng tập (test-only ưu tiên).
- Seed 42; tỷ lệ mục tiêu VSASV/MLAAD 60/10/10/20 **theo nhóm**, không cắt nhóm
  lớn để ép tỷ lệ mẫu. LTT có thể nhận thêm nguyên người replay từ train theo
  quy tắc quota bên dưới. Không dùng kết quả phát hiện để chọn nhóm/ngưỡng.
- CSV và SUMMARY chỉ ở `DATA_DIR/splits/`, không commit. SUMMARY ghi giả định,
  rủi ro, nguồn/revision/commit, số nhóm/người/mẫu và từng số thiếu quota.
- Hash trùng byte bằng 0 là bằng chứng yếu, không phải bằng chứng khác người.
  Crosswalk đã xác minh ưu tiên hơn giả định độc lập và cân bằng miền.

**Tiêu chí hoàn thành:**
- [ ] Test tự động: không có `subject_id` xuất hiện ở 2 trong 4 tập.
- [ ] Mỗi loại tấn công chính có ≥ 60 mẫu trong `calib_ltt` (để chứng nhận α = 5%); thiếu thì dồn thêm người sang `calib_ltt`, vẫn thiếu thì ghi rõ trong SUMMARY.
- [ ] `calib_fit` có ≥ 100 mẫu mỗi lớp (điều kiện để ROUT-01 được chọn isotonic); thiếu thì ghi rõ.
- [ ] Seed cố định, chạy lại ra cùng kết quả.

---

### DATA-04 · Tạo deepfake người Việt từ nguồn công khai

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 (trên máy red-team) | 1,5 | S1 | P0 | DATA-01, REDT-01 |

**Mục tiêu:** có video mặt người Việt bị ghép, và video nói tiếng Việt bị lồng tiếng, để đo "khoảng cách dữ liệu Việt Nam".
**Đọc trước:** `docs/runbooks/red-team.md`, ADR-0002.

**Đầu ra:** `data/synth/vn_faceswap/` (≥ 200 video), `data/synth/vn_lipsync/` (≥ 100 video), `data/synth/MANIFEST.csv` (nguồn mặt, nguồn video, công cụ, tham số).

**Các bước:**
1. **Ghép mặt:** lấy mặt từ Vietnamese Celebrity Faces ghép vào video ViCocktail bằng FaceFusion (inswapper); một phần bật hòa trộn Poisson.
2. **Lồng tiếng:** dùng giọng giả MLAAD-vi hoặc VieNeu-TTS, lip-sync lên ViCocktail bằng Wav2Lip.
3. Ghi manifest đầy đủ.

**Tiêu chí hoàn thành:**
- [ ] Đủ số lượng, có manifest.
- [ ] Chia tập theo video nguồn (cập nhật DATA-03).
- [ ] Không phát tán ra ngoài nhóm.

**Lưu ý:** công cụ tấn công chỉ cài trên máy red-team, không đưa vào repo.

---

### DATA-05 · Biến thể nén kiểu mạng xã hội

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M4 | 0,5 | S1 | P0 | DATA-01 |

**Mục tiêu:** mỗi video và âm thanh trong tập test có 3 mức nén để đo độ bền.
**Đầu ra:** `scripts/compress_variants.py`, cho ra:
- **Video:** `c0` (gốc), `c28` (H.264 CRF 28), `c40` (H.264 CRF 40 + giảm xuống 480p).
- **Âm thanh:** gốc, Opus 16 kbps, AMR-NB 8 kHz.

**Tiêu chí hoàn thành:**
- [ ] Chạy trên toàn bộ tập test của RTFS-10k, WildDeepfake, deepfake VN, MLAAD-vi, ViSpoofDB.
- [ ] Ghi thông số ffmpeg vào manifest.
