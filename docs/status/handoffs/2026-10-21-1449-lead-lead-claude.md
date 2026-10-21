# Bàn giao · LEAD · Lead+Claude · 2026-10-21 14:49

**Nhánh:** `docs/LEAD-handoff-1021` (chỉ tài liệu).
**Trạng thái:** doing — điều phối liên tục. **Phiên mới: gõ `/lead`, đọc file này trước.** Bàn giao LEAD trước đó: `2026-10-18-1852`.

## Đã xong (18/10 tối → 21/10)
- **Đã gộp các PR:**
  - #37: ADR-0013 (ba luồng eKYC: đăng ký, xác thực lại, khôi phục), ADR-0014 (demo bằng app Android Kotlin native), ADR-0015 (chọn mô hình, tinh chỉnh trên Colab/Kaggle, có mục **"Cập nhật 19–20/10 — dữ liệu"**), epic E9 (FLOW, SEC, APP), DATA-06.
  - #38: 2 notebook PAD (MiniFASNet, DINOv2).
  - #39: notebook hiệu chỉnh GenD.
  - #40: sửa lỗi gom người trong bước prep.
- **Đang mở:** **PR #41** (sửa hướng dẫn Kaggle: phải dùng "Save & Run All (Commit)", không dùng Quick Save) → **chờ người dùng gộp**.
- **Rà soát dữ liệu có bằng chứng** (xem ảnh, đo, nghe qua ASR). Báo cáo đã chép vào `docs/research/2026-10-19-data-audit/` (7 file). Phát hiện chính:
  - **Zalo 2022:** toàn người đeo khẩu trang.
  - **FAS-VN:**
    - lộ đề qua chiều rộng ảnh và EXIF (AUC 0,99);
    - ảnh trùng mang 2 nhãn;
    - cặp ảnh gốc/chụp lại bị tách giữa train và test.
  - **ViSpoofDB:**
    - giọng giả dài đúng 5,000 s, 16 kHz; giọng thật 24 kHz;
    - giọng thật **không phải** VIVOS (`SOURCE.md` ghi sai, chưa sửa).
  - **ViCocktail:** chỉ có vùng miệng.
  - **WildDeepfake:** mặt cắt sát, SCRFD không dò được.
  - **RTFS-10k:** lộ đề qua bitrate.
  - **vn_celeb (bản HF):** nhãn sai.
  - **mms-tts-vie:** chỉ có 1 giọng.
- **Bản chốt dữ liệu:** ghi trong ADR-0015 mục "Cập nhật 19–20/10" (đã trên `main`).
- **Notebook trên Kaggle (dữ liệu chỉ lấy trên Kaggle/Colab, không tải về laptop):**
  - PAD: `ml/notebooks/prep_pad.ipynb` (người dùng chạy) → `finetune_pad_minifasnet.ipynb` (Người 1) và `finetune_pad_dinov2.ipynb` (Người 2) → trưởng nhóm gộp 2 zip bằng `uv run --no-sync python ml/notebooks/combine_pad.py --minifasnet <zip> --dinov2 <zip>`. Đề xuất kết hợp: max(p₁, p₂), chỉ dùng cả hai nếu thắng ở BPCER ≤ 1%.
  - GenD: `ml/notebooks/calibrate_gend.ipynb` — **chỉ hiệu chỉnh, không tinh chỉnh**. Lớp thật = FAS-VN live + video gốc RTFS; lớp giả = RTFS; VLR tắt.
  - Mỗi bộ có `README-*.md` (cách chạy) và `HANDBOOK-*.md` (sổ tay sửa lỗi, vùng cấm sửa).
- **Prep PAD chạy thật trên Kaggle (tài khoản người dùng, notebook "pre-pad"):**
  - qua đủ các chốt an toàn;
  - **SHA-256 splits.csv = `22b0d16f60de8afbfd7a8bc2ca09b9dc6745984676ca3e8c7c1a0e00bdc0534a`**;
  - thời gian: bước 2 mất 23 phút, bước 3 mất 81 phút.
  - **Version 1 là Quick Save nên Output = 0 file.** Người dùng đang chạy lại bằng **Save & Run All (Commit)** (khoảng 1 giờ 45 phút) → version mới phải có Output khoảng 13 file / 3,9 GB.
  - Notebook đã **chia sẻ Private** cho 2 member: **Quang Lê** và **Ducky06** (Viewer).

## Đang dở
1. **Prep version 2** (commit) đang chạy trên Kaggle. Khi xong:
   - kiểm tab Output và SHA (bình thường vẫn là `22b0d16f…`);
   - báo 2 member Add Input **version mới nhất**.
2. **2 member chạy notebook PAD**:
   - Người 1 (MiniFASNet) và Người 2 (DINOv2) đã nhận file và tin nhắn;
   - chạy SMOKE trước, rồi chạy thật;
   - gửi zip qua Drive nhóm;
   - trưởng nhóm chạy `combine_pad.py`.
3. **Notebook GenD chưa có người chạy.** Đã đề xuất người dùng tự chạy (GPU T4, Add Input `stplusplus/rtfs-10k` + `maihongtng/face-anti-spoofing`).
4. **Phần giọng (AntiDeepfake, ưu tiên số 1) chưa bắt đầu.** Đang chờ người dùng đồng ý giao agent làm notebook Kaggle cùng kiểu:
   - giọng thật: Common Voice vi, DNU-ViSpeech, Speech-MASSIVE, FLEURS;
   - giọng giả: nhân bản chính những người đó bằng VieNeu v3 (đã thử chạy được trên CPU) / F5-vi / OmniVoice, cộng MLAAD-vi;
   - khử lộ đề: 16 kHz, bỏ đệm số 0, cắt cửa sổ, cân độ to, AUC ≤ 0,65;
   - test: ViSpoofDB (đã khử lộ đề).
   - Common Voice cần người dùng bấm đồng ý điều khoản trên Mozilla Data Collective.
5. **App và luồng (E9: APP, FLOW, SEC) chưa giao.** Chưa soạn prompt.

## Bước tiếp theo
1. Nhắc người dùng gộp **PR #41**.
2. Kiểm Output prep version 2 → báo member.
3. Hỏi lại người dùng: (a) ai chạy notebook GenD; (b) có bắt đầu notebook phần giọng không.
4. Nhận 2 zip PAD → chạy `combine_pad.py` → báo người dùng chọn MiniFASNet / DINOv2 / kết hợp.
   - Nếu kết hợp thắng: giao việc thêm DINOv2 làm mô-đun mặt ở server.
   - Nếu MiniFASNet tinh chỉnh thắng: cần mục manifest + `model_version` mới trong `pad.py`.
5. Nhận zip GenD → đưa calibrator vào (qua PR, ROUT-01).
6. Giao việc app/luồng (E9) cho các phiên AI. Prompt luôn có phần subagent.

## Quyết định, lưu ý, bẫy
- **Không tự tạo deepfake người thật.**
  - Hệ thống an toàn của AI đã chặn khi định ghép mặt người trong VLR; trưởng nhóm đồng ý bỏ.
  - DATA-04 cũ bị hủy.
  - ForgeryNet bị loại: phần dạy cần tài khoản OpenDataLab hoặc 115.
  - DFDC bị loại: luật cuộc thi chỉ cho dùng trong cuộc thi; Meta §6G cấm dùng cho sinh trắc học.
  - Muốn có deepfake để tinh chỉnh GenD thì gửi đơn DeepSpeak / Celeb-DF++, cần email trường.
- **Trước khi giao vai trò cho bộ dữ liệu, phải mở mẫu ra xem/đo** (memory `inspect-data-visually`). Mọi thứ báo là "xong" phải đi được trọn luồng của người dùng (memory `usable-end-to-end-first`).
- **Kaggle:**
  - chỉ "Save & Run All (Commit)" mới lưu file Output;
  - output prep chứa ảnh mặt người thật → **luôn Private** (người dùng từng định để Public, đã khuyên không và người dùng đã để Private).
- Repo `vericlue` là **private**, nên notebook nhúng code bằng script build (`scripts/build_pad_notebook.py`, `scripts/build_gend_notebooks.py`, có `--check` và test đồng bộ). **Không sửa tay notebook trong repo — sửa template rồi sinh lại.**
- **Worktree:**

  | Thư mục | Ghi chú |
  |---|---|
  | `vericlue-nb-pad` | nhánh `docs/FACE-04-kaggle-save-version` (PR #41) |
  | `vericlue-nb-gend` | đã gộp |
  | `vericlue-claude`, `vericlue-codex`, `vericlue-lab` | nhánh cũ đã gộp |
  | `vericlue-data` | DATA-03 ảnh: **đã lỗi thời** so với bản chốt dữ liệu, cần quyết dừng hay sửa |

  Giao task mới thì phiên AI chạy `git switch -c … origin/main`.
- Laptop: ổ D còn khoảng 62 GB; RAM 16 GB rất căng khi nhiều phiên AI chạy cùng lúc.
- Agent nền có thể dừng vì hạn mức tuần (reset 6 giờ sáng giờ Việt Nam) hoặc mất mạng → gửi tin nhắn cho agent để chạy tiếp, không tạo agent mới.
- Báo cáo nghiên cứu mô hình: `docs/research/2026-10-18-models-*.md`. Báo cáo dữ liệu: `docs/research/2026-10-19-data-audit/`.

## Câu hỏi cho nhóm
- Ai chạy notebook GenD? Có bắt đầu notebook giọng không?
- Có email trường để gửi đơn DeepSpeak / Celeb-DF++ (tinh chỉnh GenD sau này) không?
- `vericlue-data` (DATA-03 ảnh): dừng hay sửa theo bản chốt mới?
- Sửa `vispoofdb/SOURCE.md` (nguồn giọng thật không phải VIVOS) và chia lại audio (VIVOS/ViSpoofDB) — làm cùng notebook giọng.
- Kiểm văn bản gốc: Luật 91/2025/QH15 về dữ liệu cá nhân có thể đã thay NĐ 13/2023.

## Test đã chạy
```
plan_check: 0 lỗi (cảnh báo quá tải M1/M2/M3 — dự kiến)
PR #38–#41: CI xanh (Guard, Python, Web); reviewer duyệt #38 #39 (đạt sau khi sửa, đã sửa)
prep_pad chạy thật trên Kaggle: XONG, splits.csv 22b0d16f…0534a
```
