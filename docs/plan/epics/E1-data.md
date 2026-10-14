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
- [ ] `--subset small` chạy xong < 30 phút, tổng < 30 GB.
- [ ] Bộ cần đăng ký (HF gated) báo rõ cách lấy token nếu thiếu `HF_TOKEN`.
- [ ] Mỗi bộ có `SOURCE.md`.

**Lưu ý:** gửi ngay hôm nay các yêu cầu cần chờ duyệt: SEA-Spoof (email tác giả), FaceForensics++, DeepSpeak v1, Deepfake-Eval-2024. Không chặn việc khác nếu chưa được duyệt.

---

### DATA-02 · Script tải mô hình

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S0 | P0 | PLAT-01 |

**Mục tiêu:** `scripts/download_models.py` tải mọi mô hình trong `models/manifest.yaml`, ghi và kiểm SHA-256.

**Tiêu chí hoàn thành:**
- [ ] Tải đủ GenD, AntiDeepfake, PhoWhisper, SyncNet (`stable_syncnet`), MiniFASNet (qua uniface), SBI, SCRFD.
- [ ] Lần đầu điền `sha256` vào manifest; các lần sau kiểm tra và báo sai lệch.
- [ ] Chép link Google Drive của SBI sang Hugging Face riêng của nhóm (để private) để tránh hết lượt tải.

---

### DATA-03 · Chia tập theo người

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M3 + M4 | 1 | S1 | P0 | DATA-01 |

**Mục tiêu:** mỗi bộ có danh sách train / calib / test, **không trùng người** giữa các tập.
**Đầu ra:** `scripts/make_splits.py` → `data/splits/<bộ>/{train,calib,test}.csv` (cột: path, label, attack_type, subject_id, source, region nếu có). Thống kê số mẫu theo nhãn và loại tấn công → `data/splits/SUMMARY.md`.

**Quy tắc chia:**
- Zalo 2022 chỉ tập train có nhãn → chia 60/20/20 theo người.
- MLAAD-vi chia theo câu và hệ TTS.
- **ViSpoofDB giữ nguyên làm test** (công cụ chưa từng thấy).
- RTFS-10k chia theo video gốc (cặp thật–giả nằm cùng tập).
- ViMD chia theo người, giữ cân bằng 3 miền.

**Tiêu chí hoàn thành:**
- [ ] Test tự động: không có `subject_id` xuất hiện ở 2 tập.
- [ ] Mỗi loại tấn công chính có ≥ 60 mẫu trong tập calib (để chứng nhận α = 5%); nếu thiếu thì ghi rõ trong SUMMARY.
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
