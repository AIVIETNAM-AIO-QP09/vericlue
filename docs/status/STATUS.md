# STATUS — Tình trạng dự án

> **Cập nhật:** 21/10/2026 · **Sprint:** S1 · **Mốc kế tiếp:** demo M1 25/10 · **Hạn nộp:** trước 06/11 (còn 16 ngày)
> **Chỉ trưởng nhóm sửa file này** (tránh xung đột git). Người khác ghi vào file bàn giao, trưởng nhóm gom lại.
> Số liệu task luôn mới nhất: `uv run python scripts/plan_check.py --board`.

## Tổng quan

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Proposal | ✅ Chốt bản 3 · ⚠ cần sửa | Đổi sang app Android (ADR-0014) và bản chốt dữ liệu (ADR-0015) chưa vào proposal — cần task riêng (luật 7) |
| Kiến trúc | 🟡 Cần cập nhật | `architecture.md` chưa có 3 luồng eKYC (ADR-0013) và app (ADR-0014) |
| Kế hoạch | ✅ 68 task | **14 done · 3 review · 4 doing** (`plan_check.py`, 0 lỗi). Thêm epic E9 (FLOW, SEC, APP) và DATA-06 |
| Nền tảng (web, API, DB, Docker) | ✅ Chạy được | `docker compose up` → web :3000, API :8000, PostgreSQL |
| **MVP chạy toàn mô hình thật** | ✅ 18/10 (ADR-0012) | `ROUTER_PROFILE=mvp USE_MOCK_MODELS=false`: MiniFASNet, GenD, AntiDeepfake, PhoWhisper, quality, CamProbe; lipsync chỉ tham khảo. Calibrator **identity (tạm)**. RTX 4050: bước mặt 0,9–2,2 s, bước giọng 1–1,7 s, VRAM 3,5–4,4 GB (thử tay, không phải số R) |
| Luồng người dân | 🟡 Web `/verify` chạy được; **app Android chưa bắt đầu** | ADR-0014: demo bằng app Kotlin native, web làm dự phòng. 3 luồng (đăng ký, đăng nhập lại, khôi phục — ADR-0013): FLOW-01…05, SEC-01/02, APP-01…04 đều `todo` |
| Bộ quyết định | ✅ Chính sách đủ, ngưỡng **tạm** | ROUT-02 xong, hồ sơ `mvp`; ROUT-01 `review` (identity MVP); ngưỡng thật chờ ROUT-03 |
| Bàn duyệt | 🟡 API xong | REV-01. Giao diện REV-02 chưa làm |
| Giám định | 🟡 API theo đoạn xong | PR #33: chia đoạn, AudioSeal, C2PA. Giao diện FOR-02 chưa làm. Máy demo cần FFmpeg |
| Giọng nói | 🟡 Chạy thật, **chưa tinh chỉnh** | **Lỗi đã biết:** AntiDeepfake gốc cho giọng mms-tts-vie qua (0,115 → pass). Sửa bằng VOICE-03 (notebook Kaggle giọng — chưa bắt đầu) |
| Mô hình | ✅ 8 mô hình + CLIP | Đã chọn thêm AdaFace (so mặt 1:1) và DINOv2-reg (PAD tầng 2) — ADR-0015 |
| Dữ liệu | ✅ Đã rà soát có bằng chứng, **bản chốt mới** | `docs/research/2026-10-19-data-audit/`, ADR-0015 mục "Cập nhật 19–20/10". Dữ liệu dạy/hiệu chỉnh chỉ lấy trên Kaggle/Colab |
| Tinh chỉnh PAD | 🟡 Đang chạy | Prep trên Kaggle xong (`splits.csv` SHA-256 `22b0d16f…0534a`); 2 thành viên chạy MiniFASNet và DINOv2 |
| Hiệu chỉnh GenD | ⬜ Notebook sẵn, chưa ai chạy | `ml/notebooks/calibrate_gend.ipynb` |
| Kết quả R1–R7 | ⬜ Chưa có | Chờ tinh chỉnh + calibrator thật + ROUT-03 |

## Đang làm

| Mã | Người · nơi chạy | Ghi chú |
|---|---|---|
| FACE-04 (prep PAD) | Trưởng nhóm · Kaggle "pre-pad" | Chạy lại bằng **Save & Run All (Commit)** để có Output; kiểm SHA rồi báo 2 thành viên dùng bản mới nhất |
| FACE-04 (PAD) | Quang Lê (MiniFASNet), Ducky06 (DINOv2) · Kaggle | Chạy SMOKE rồi chạy thật → gửi zip qua Drive nhóm → trưởng nhóm chạy `combine_pad.py` |
| FACE-04 (GenD) | **chưa có người** | Notebook hiệu chỉnh sẵn sàng (GPU T4) |
| DATA-03 (ảnh) | Codex `vericlue-data` | **Lỗi thời** so với bản chốt dữ liệu (FAS-VN/RTFS chia trong notebook) — chờ quyết dừng hay sửa |
| DATA-01 · CAP-02 · ROUT-01 | — | `review` lâu: DATA-01 chờ lượt nghiệm thu; CAP-02 chờ đo fps Android (có thể chuyển sang app); ROUT-01 chờ calibrator thật |
| FACE-02 · VOICE-05 | — | `doing` trên bảng nhưng code MVP đã gộp (PR #31, #32); còn phần kết quả R2 / hiệu chỉnh lipsync |

Các worktree `vericlue-claude`, `vericlue-codex`, `vericlue-lab`, `vericlue-nb-gend`, `vericlue-nb-pad` đang rảnh (nhánh đã gộp). Giao task mới: `git switch -c … origin/main`.

## Bị chặn

| Mã | Lý do | Cần ai giải quyết |
|---|---|---|
| VOICE-03 (tinh chỉnh giọng) | Chưa có notebook; Common Voice cần bấm đồng ý điều khoản trên Mozilla Data Collective | Trưởng nhóm đồng ý bắt đầu + bấm đồng ý |
| ROUT-03, R1–R4 | Chờ PAD/GenD/giọng có calibrator thật | FACE-04, VOICE-03 |
| Tinh chỉnh GenD (sau này) | Không tự tạo deepfake người thật; cần đơn DeepSpeak / Celeb-DF++ (email trường) | Ai có email trường |

## Câu hỏi mở

| # | Câu hỏi | Ai hỏi / trả lời | Hạn |
|---|---|---|---|
| Q1 | Vòng 2 phải nộp những gì (bản chạy, báo cáo, video, slide, link repo)? | M2 hỏi BTC/mentor | 16/10 |
| Q2 | Có được nêu Đề 62 và DA940-02 là đề liên quan ngoài BTL86-16 không? | M2 hỏi BTC | 16/10 |
| Q3 | Điều khoản gốc của Zalo AI 2022 về việc dùng dữ liệu? | M3 | 17/10 |
| Q4 | Gán tên thật cho M1–M5 (đã có 2 thành viên chạy notebook: Quang Lê, Ducky06); chọn tech lead; điền `team.md` và `CODEOWNERS` | Cả nhóm | quá hạn |
| Q5 | Máy nào làm máy demo (có GPU)? Máy nào làm máy red-team? | Cả nhóm | 17/10 |
| Q6 | Tra lại Google Scholar cho tuyên bố "lần đầu áp dụng Learn-then-Test" | M5 | trước khi nộp |
| Q7 | Kênh liên lạc chính của nhóm (Zalo/Discord/…)? Giờ họp nhanh 21:00 có hợp không? | Cả nhóm | 16/10 |
| Q8 | **Bảng giấy phép proposal §3.1 lệch thực tế** (DATA-02): SyncNet là OpenRAIL++ (proposal ghi Apache-2.0); trọng số CTC aligner CC-BY-NC (proposal ghi BSD-2); SCRFD `det_10g` phi thương mại và CLIP (trọng số không khai giấy phép) chưa có trong bảng; câu "thương mại hóa dùng GenD (MIT)" chưa tính SCRFD/CLIP. Bản thi không ảnh hưởng. Có sửa proposal không? | Tech lead | trước khi nộp |
| Q9 | **Màn đồng ý** (CAP-01): còn để trống quyền rút lại đồng ý/xóa sớm, bên kiểm soát dữ liệu, hạn lưu giọng nói, nơi lưu bản ghi đồng ý. Demo chỉ dùng mặt/giọng thành viên nhóm, nhưng nên có câu chữ trước khi nộp | M2 | 01/11 |
| Q10 | **Media giám định** hiện không tự xóa (`FORENSIC_TTL_DAYS` trống). Chính sách giữ chứng cứ cho điều tra viên? | M2 + M5 | 01/11 |
| Q11 | Danh sách **mã lý do** bàn duyệt (9 mã tạm, REV-01) — M2 chốt khi làm REV-02 | M2 | 25/10 |
| Q12 | Ai chạy notebook hiệu chỉnh GenD? | Trưởng nhóm | 22/10 |
| Q13 | Bắt đầu notebook giọng (VOICE-03, ưu tiên số 1) chưa? Giao phiên AI nào? | Trưởng nhóm | 22/10 |
| Q14 | Giao E9 (APP-01, FLOW-01/02, SEC-01) cho phiên AI nào? Ai trong nhóm biết Kotlin? | Trưởng nhóm | 22/10 |
| Q15 | `vericlue-data` (DATA-03 ảnh): dừng hay sửa theo bản chốt mới? | Trưởng nhóm | 22/10 |
| Q16 | Sửa `vispoofdb/SOURCE.md` (giọng thật không phải VIVOS) và chia lại audio — làm cùng notebook giọng | Phiên làm VOICE-03 | cùng VOICE-03 |
| Q17 | Kiểm văn bản gốc: Luật 91/2025/QH15 về dữ liệu cá nhân có thể đã thay NĐ 13/2023 | M2 | 01/11 |
| Q18 | Giấy phép PhoWhisper: manifest ghi BSD-3, một nguồn ghi Apache-2.0 | M2 | trước khi nộp |

## Rủi ro cần theo dõi

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Hạn 4 giây mỗi bộ phát hiện **tính cả thời gian xếp hàng** (PLAT-08); mô hình thật vài giây/lần → người xếp sau quá giờ → `review` oan | Thử FACE-01/02 trên máy demo | Đo trên máy demo có GPU; chỉnh `INFERENCE_BUDGET_SECONDS`, `DETECTOR_QUEUE_SIZE`; ghi giới hạn số người cùng lúc vào kịch bản demo |
| Bài thử trình duyệt (`npm run test:e2e`) chưa vào CI | PR web chưa ai chạy e2e | Chạy tay trước PR chạm `/verify`; PLAT-09 đưa vào CI |
| Dữ liệu small rất nhỏ (ViMD 3 người/tập, quota calib chưa đủ) | SUMMARY.md của DATA-03 | Ghi rõ giới hạn trong R3; tải bản đầy đủ nếu ổ đĩa cho phép |
| Ổ D còn ~62 GB; RAM 16 GB căng khi nhiều phiên AI | Lỗi cấp phát bộ nhớ khi 2 API chạy cùng lúc | Dữ liệu dạy chỉ trên Kaggle/Colab; phiên AI thử ở cổng 8200, không đụng :8000 |
| **Giọng AI lọt** (AntiDeepfake chưa tinh chỉnh) | e2e 18/10: mms-tts-vie ra 0,115 → pass | VOICE-03; **không hạ ngưỡng tay** |
| App Android chưa bắt đầu, còn 16 ngày | APP-01 vẫn `todo` | Giao ngay; web `/verify` làm dự phòng |
| Lộ đề trong dữ liệu (FAS-VN, RTFS, ViSpoofDB) | Mô hình chỉ dùng siêu dữ liệu đạt AUC cao | Khử lộ đề trong notebook; kiểm AUC ≤ 0,65 trước khi dạy |
| Kaggle Quick Save không lưu Output | Version có Output = 0 file | Luôn dùng "Save & Run All (Commit)"; output có ảnh mặt → luôn Private |

## Quyết định gần đây

| Ngày | Quyết định | Tham chiếu |
|---|---|---|
| 21/10 | Gộp PR #41 (Kaggle: chỉ "Save & Run All (Commit)" mới lưu Output) và #42 (bàn giao LEAD, báo cáo rà soát dữ liệu) | PR #41, #42 |
| 19–20/10 | **Bản chốt dữ liệu mới** sau rà soát có bằng chứng: PAD dạy trên FAS-VN đã làm sạch và chia lại theo người; GenD **không tinh chỉnh, chỉ hiệu chỉnh** (thật = FAS-VN live + RTFS gốc; giả = RTFS); giọng: thật từ Common Voice/DNU-ViSpeech/Speech-MASSIVE/FLEURS, giả nhân bản chính những người đó; `splits.csv` của notebook là cách chia chuẩn duy nhất cho FAS-VN và RTFS | ADR-0015 "Cập nhật 19–20/10", `docs/research/2026-10-19-data-audit/` |
| 19–20/10 | **Không tự tạo deepfake người thật** — DATA-04 cũ hủy; loại ForgeryNet (cần tài khoản OpenDataLab/115), DFDC (điều khoản cấm sinh trắc), bản sao FF++ trên Kaggle | ADR-0015 |
| 19–20/10 | PAD kết hợp max(p_MiniFASNet, p_DINOv2), chỉ dùng cả hai nếu thắng mô hình đơn ở BPCER ≤ 1% trên calib_fit | ADR-0015, PR #38 |
| 19–20/10 | Notebook nhúng code bằng script build (`scripts/build_*`, có `--check`); không sửa tay notebook | PR #38, #39, #40 |
| 18/10 | **MVP chạy toàn mô hình thật** (`ROUTER_PROFILE=mvp`), calibrator identity tạm, lipsync chỉ tham khảo; không lấy số R từ MVP | ADR-0012, PR #25–#36 |
| 18/10 | Ba luồng eKYC (đăng ký, đăng nhập lại, khôi phục), 6 câu hỏi theo thứ tự cố định | ADR-0013 |
| 18/10 | **Demo bằng app Android Kotlin native**; bàn duyệt và giám định vẫn web; web `/verify` dự phòng; HTTPS từ đầu | ADR-0014 (thay một phần ADR-0003) |
| 18/10 | Chọn mô hình: giữ GenD, AntiDeepfake MMS-300M, MiniFASNet; thêm DINOv2-reg (PAD) và AdaFace (so mặt); tinh chỉnh chỉ trên Colab/Kaggle | ADR-0015 |
| 14/10 | Chốt proposal v3: 1 bộ não + 2 chế độ; chỉ dữ liệu công khai; GenD, AntiDeepfake, MAPIE, mã nháy màu AWS Amplify, quét thủy vân | `docs/adr/0001`–`0009` |
| 14/10 | Monorepo, mock trước, AGENTS.md làm luật chung cho mọi AI | ADR-0001 |
| 14/10 | Cân lại kế hoạch theo tải từng sprint: SBI và tinh chỉnh GenD sang S2; PLAT-06/07 → M2; FOR-01 → M5; FOR-03 → M3; thêm PLAT-09 (kiểm thử đầu–cuối) và EVAL-03 (đánh giá giám định, R7) | `docs/plan/roadmap.md` |
| 14/10 | Tách tập calib theo người thành `calib_fit` (hiệu chỉnh, hợp nhất, chọn mô hình) và `calib_ltt` (chỉ chọn ngưỡng); calibrator lưu trong `ml/configs/calibrators/` | ADR-0010 |
| 14/10 | Token theo phiên (~5 phút), mỗi bước nhận một lần (409), thử thách sống 120 giây; nhịp nháy màu ≥ 550 ms/bước | ADR-0011 |
| 14/10 | Chạy song song 2 AI bằng git worktree: Claude ở `D:\Projects\vericlue-claude` (PLAT-02 → PLAT-04), Codex ở `D:\Projects\vericlue-codex` (ROUT-01 → EVAL-01) | `docs/ai/working-with-ai.md` |
| 14/10 | Gộp PR #2 (ADR-0010, ADR-0011) và PR #3 (ROUT-01: hiệu chỉnh xác suất, GroupKFold theo người, thiếu calibrator thì báo lỗi) | PR #2, #3 |
| 15/10 | PLAT-04: phiên đã ra `review` là trạng thái cuối (gọi lại → 409); xác thực nhân viên cho `/review`, `/forensic` giao PLAT-06 | Bàn giao LEAD 15/10, thẻ PLAT-06 |
| 15/10 | Nên mở phiên AI tại thư mục worktree của nó (nếu mở từ `Data4Life` thì prompt ghi rõ worktree, kiểm `pwd`/nhánh trước commit); dữ liệu và mô hình để chung ngoài worktree (`DATA_DIR`, `MODELS_DIR`) | `docs/ai/working-with-ai.md` |
| 15/10 | Gộp PR #5 (EVAL-01) và PR #6 (bộ công cụ trưởng nhóm) | PR #5, #6 |
| 14/10 | Gộp PR #4 (PLAT-02). `npm audit`: 5 lỗi mức cao chỉ nằm trong công cụ lint (`eslint-config-next`); bản chạy thật báo 0. Không chạy `audit fix --force` | PR #4 |
| 14/10 | EVAL-01: BPCER@APCER 5% chính lấy ngưỡng từ `calib_fit` rồi khóa, kèm dòng "mô tả" theo đường cong; cột `status` bắt buộc, không âm thầm bỏ mẫu lỗi | Bàn giao LEAD, bàn giao EVAL-01 |
| 14/10 | Phiên điều phối riêng (`/lead`); luật subagent: mỗi task một phiên chính, chỉ phiên chính commit, không hai bên sửa cùng file, duyệt chéo Claude ↔ Codex | `docs/ai/lead-playbook.md`, `docs/ai/working-with-ai.md` |
| 17/10 | **Không thu dữ liệu thiết bị/người thật** (quá tải): ChromaPulse **hạ xuống tín hiệu phụ** (PRES-01 đóng, CAP-03 đóng ở mức code); không dùng mặt/giọng thành viên (DATA-04 chỉ dùng người nổi tiếng công khai); PRES-04 (R5) bỏ hoặc thay bằng dữ liệu tổng hợp | Bàn giao LEAD 17/10, thẻ PRES-01/04, CAP-03/04, DATA-04 |
| 17/10 | DATA-03 ảnh: FAS-VN, RTFS-10k, WildDeepfake **chỉ test**; Zalo gộp video theo embedding ArcFace (ngưỡng lỏng, thà gộp nhầm còn hơn bỏ sót); GenD tinh chỉnh trên DATA-04 + ViCocktail; PAD chỉ trên Zalo | Thẻ FACE-04 |
| 17/10 | Tinh chỉnh **hai bước**: chạy thử nhỏ trên máy (RTX 4050 6 GB), chạy thật trên Kaggle; cùng script, ghi commit; VOICE-03 dùng VSASV thay VIVOS | Thẻ FACE-04, VOICE-03 |
| 16/10 | ROUT-02: thứ tự cổng theo thẻ (chất lượng trước mặt); ngưỡng giọng `voice.spoof_threshold` riêng, không dùng chung B; cờ cắt ghép vắng giữ `absent` | PR #21 |
| 16/10 | REV-01: chuỗi băm bảo đảm ở tầng DB (`UNIQUE(case_id, prev_hash)`, migration 0002); xung đột ghi → 409 | PR #19 |
| 16/10 | DATA-03 âm thanh: bộ có bằng chứng chung nguồn người buộc cùng tập (ViSpoofDB + VIVOS → test); bộ thu thập độc lập (VSASV, ViMD) chia theo người trong bộ, ghi là giả định; thiếu quota thì dồn nhóm từ train | PR #20 |
| 16/10 | MLAAD-vi bỏ 159 file thiếu metadata; VSASV chỉ lấy thật + phát lại (không xác minh được người nguồn của mẫu đổi giọng/nhiễu) | PR #17 |
| 16/10 | PLAT-08: hàng đợi 3 tác vụ/module; nhả chỗ trước khi trả kết quả (sửa lỗi chập chờn) | PR #16, #18 |
| 16/10 | CAP-02: chụp lại phải qua cổng chất lượng lại; quá sáng chỉ dẫn cục bộ ở web, không đổi hợp đồng; FPS < 15 là màn riêng | PR #15 |
| 15/10 | PLAT-05: ca review chưa đóng thì giữ media; 30 ngày tính từ lúc đóng ca; giám định không tự xóa | PR #13 |
| 15/10 | CAP-01: tạo phiên ngay trước bước nháy màu; hết hạn tính bằng đồng hồ đơn điệu của trình duyệt | PR #12, `architecture.md` §6 |
| 15/10 | DATA-01/02: không mirror SBI (điều khoản hạn chế chia sẻ); tiêu chí tải đổi thành "chạy hết qua một đêm"; ViCocktail/WildDeepfake chọn theo shard có chỉ mục video | PR #9, #11 |
| 14/10 | Bàn giao mỗi lần một file (`docs/status/handoffs/`) để tránh xung đột git | `docs/status/handoffs/README.md` |

## Kết quả đã có

Chưa có R1–R7. MVP 18/10 chỉ là thử tay (bàn giao LEAD 18/10), không đưa vào báo cáo. Thử nghiệm nhỏ: `docs/status/results/VOICE-04.md` (kiểm câu đọc trên 19 câu ViMD — chỉ chứng minh chạy được, **không** đưa vào báo cáo như số liệu theo miền).

## Liên kết nhanh

- Sơ đồ kiến trúc (artifact): https://claude.ai/artifact/EmX1EhHPH6DrKeLxCHDmuo — nguồn: `docs/architecture/architecture.html`
- Repo GitHub: https://github.com/AIVIETNAM-AIO-QP09/vericlue (private)
