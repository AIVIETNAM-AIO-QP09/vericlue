# STATUS — Tình trạng dự án

> **Cập nhật:** 16/10/2026 · **Sprint:** S0 (15/10 → 17/10) · **Mốc kế tiếp:** M0 — 17/10 · **Hạn nộp:** trước 06/11 (còn 20 ngày)
> **Chỉ trưởng nhóm sửa file này** (tránh xung đột git). Người khác ghi vào file bàn giao, trưởng nhóm gom lại.
> Số liệu task luôn mới nhất: `uv run python scripts/plan_check.py --board`.

## Tổng quan

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Proposal | ✅ Chốt bản 3 | `docs/proposal/proposal.md` |
| Kiến trúc | ✅ Cập nhật theo code | `docs/architecture/architecture.md` (§5 DB, §6 luồng phiên) |
| Kế hoạch | ✅ 56 task | **13 done · 3 review · 1 doing** (`plan_check.py`, 0 lỗi) |
| Nền tảng (web, API, DB, Docker) | ✅ Khung chạy được | `docker compose up` → web :3000, API :8000, PostgreSQL. AI **giả lập** mặc định. PLAT-01…05, PLAT-08 |
| Luồng người dân `/verify` | 🟡 Khung xong, chờ thử máy thật | CAP-01 (luồng, đồng ý), CAP-02 (camera, oval, cổng chất lượng — chờ đo ≥ 15 fps trên Android), CAP-03 (trang thử ChromaPulse — chờ thu JSON 3 máy) |
| Bộ quyết định | ✅ Chính sách đầy đủ, ngưỡng **tạm** | ROUT-01 (hiệu chỉnh), ROUT-02 (TrustRouter, `ml/configs/thresholds.yaml` `provisional: true`) |
| Bàn duyệt | 🟡 API xong | REV-01 (nhật ký chuỗi băm, UNIQUE ở DB, mã lý do tạm). Giao diện REV-02 chưa làm |
| Giọng nói | 🟡 Kiểm câu đọc xong | VOICE-04 (PhoWhisper offline, so khớp 2 lớp; thử nhỏ trên ViMD) |
| Mô hình | ✅ Tải đủ 8 mô hình + CLIP (8,1 GB, SHA-256) | DATA-02. SBI để FACE-03; PerTh chờ FOR-03 xác minh quyền |
| Dữ liệu | 🟡 8/13 bộ | Đủ **toàn bộ âm thanh** (MLAAD-vi, VSASV, ViMD, VIVOS, ViSpoofDB) + ViCocktail, WildDeepfake, vn_celeb_faces. **Thiếu 3 bộ Kaggle** (Zalo 2022, FAS-VN, RTFS-10k) — cần chạy với token. CelebA-Spoof, LAV-DF bỏ qua có chủ đích. Kho chung `D:\Projects\vericlue-store\` (ngoài repo) |
| Chia tập theo người | 🟡 Âm thanh xong (PR #20 chờ sửa quota) | DATA-03; phần ảnh chờ dữ liệu Kaggle |
| Kết quả R1–R7 | ⬜ Chưa có | Cần mô hình thật chạy trên dữ liệu đã chia (FACE-01/02, VOICE-01) |

## Đang làm

| Mã | Người | Ghi chú |
|---|---|---|
| DATA-03 | M3 + M4 · Codex (`vericlue-data`) | `doing` — PR #20 (âm thanh): sửa dồn quota calib_ltt từ train, đường dẫn tương đối |
| ROUT-02 (dọn) | M5 · Codex (`vericlue-codex`) | Việc dọn nhỏ sau ROUT-02 (bỏ property ngưỡng cũ, cờ cắt ghép ưu tiên cao) |
| CAP-02, CAP-03 | M1 · Claude (`vericlue-claude`) | `review` — code xong, **chờ người thử máy thật** |
| DATA-01 | M3 + M4 · Codex | `review` — chờ chạy tải 3 bộ Kaggle có token |

**Từ 18/10 (S1):** các phiên AI không nhận task mới; giao việc cho thành viên theo vai trò (xem bàn giao LEAD 16/10).

## Bị chặn

| Mã | Lý do | Cần ai giải quyết |
|---|---|---|
| PRES-01 | Chưa có JSON ChromaPulse từ 3 máy thật (Android, iPhone, laptop + OBS) — **cổng quyết định 17/10** | M1 + M3 (người cầm máy) |
| DATA-03 (ảnh), FACE-01, FACE-02 | Thiếu 3 bộ Kaggle | Người có token Kaggle chạy `download_data.py` |
| CAP-02 done | Chưa đo ≥ 15 fps trên Android tầm trung | M1 |

## Câu hỏi mở

| # | Câu hỏi | Ai hỏi / trả lời | Hạn |
|---|---|---|---|
| Q1 | Vòng 2 phải nộp những gì (bản chạy, báo cáo, video, slide, link repo)? | M2 hỏi BTC/mentor | 16/10 |
| Q2 | Có được nêu Đề 62 và DA940-02 là đề liên quan ngoài BTL86-16 không? | M2 hỏi BTC | 16/10 |
| Q3 | Điều khoản gốc của Zalo AI 2022 về việc dùng dữ liệu? | M3 | 17/10 |
| Q4 | Gán tên thật cho M1–M5; chọn trưởng nhóm và tech lead; điền `team.md` và `CODEOWNERS` | Cả nhóm | 16/10 |
| Q5 | Máy nào làm máy demo (có GPU)? Máy nào làm máy red-team? | Cả nhóm | 17/10 |
| Q6 | Tra lại Google Scholar cho tuyên bố "lần đầu áp dụng Learn-then-Test" | M5 | trước khi nộp |
| Q7 | Kênh liên lạc chính của nhóm (Zalo/Discord/…)? Giờ họp nhanh 21:00 có hợp không? | Cả nhóm | 16/10 |
| Q8 | **Bảng giấy phép proposal §3.1 lệch thực tế** (DATA-02): SyncNet là OpenRAIL++ (proposal ghi Apache-2.0); trọng số CTC aligner CC-BY-NC (proposal ghi BSD-2); SCRFD `det_10g` phi thương mại và CLIP (trọng số không khai giấy phép) chưa có trong bảng; câu "thương mại hóa dùng GenD (MIT)" chưa tính SCRFD/CLIP. Bản thi không ảnh hưởng. Có sửa proposal không? | Tech lead | trước khi nộp |
| Q9 | **Màn đồng ý** (CAP-01): còn để trống quyền rút lại đồng ý/xóa sớm, bên kiểm soát dữ liệu, hạn lưu giọng nói, nơi lưu bản ghi đồng ý. Demo chỉ dùng mặt/giọng thành viên nhóm, nhưng nên có câu chữ trước khi nộp | M2 | 01/11 |
| Q10 | **Media giám định** hiện không tự xóa (`FORENSIC_TTL_DAYS` trống). Chính sách giữ chứng cứ cho điều tra viên? | M2 + M5 | 01/11 |
| Q11 | Danh sách **mã lý do** bàn duyệt (9 mã tạm, REV-01) — M2 chốt khi làm REV-02 | M2 | 25/10 |

## Rủi ro cần theo dõi

| Rủi ro | Dấu hiệu | Ứng phó |
|---|---|---|
| Hạn 4 giây mỗi bộ phát hiện **tính cả thời gian xếp hàng** (PLAT-08); mô hình thật vài giây/lần → người xếp sau quá giờ → `review` oan | Thử FACE-01/02 trên máy demo | Đo trên máy demo có GPU; chỉnh `INFERENCE_BUDGET_SECONDS`, `DETECTOR_QUEUE_SIZE`; ghi giới hạn số người cùng lúc vào kịch bản demo |
| Bài thử trình duyệt (`npm run test:e2e`) chưa vào CI | PR web chưa ai chạy e2e | Chạy tay trước PR chạm `/verify`; PLAT-09 đưa vào CI |
| Dữ liệu small rất nhỏ (ViMD 3 người/tập, quota calib chưa đủ) | SUMMARY.md của DATA-03 | Ghi rõ giới hạn trong R3; tải bản đầy đủ nếu ổ đĩa cho phép |
| Ổ D: còn ~105 GB | `download_data.py` báo thiếu chỗ | Chỉ tải `--subset small`; dùng ổ ngoài nếu cần full |

## Quyết định gần đây

| Ngày | Quyết định | Tham chiếu |
|---|---|---|
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

Chưa có R1–R7. Thử nghiệm nhỏ: `docs/status/results/VOICE-04.md` (kiểm câu đọc trên 19 câu ViMD — chỉ chứng minh chạy được, **không** đưa vào báo cáo như số liệu theo miền).

## Liên kết nhanh

- Sơ đồ kiến trúc (artifact): https://claude.ai/artifact/EmX1EhHPH6DrKeLxCHDmuo — nguồn: `docs/architecture/architecture.html`
- Repo GitHub: https://github.com/AIVIETNAM-AIO-QP09/vericlue (private)
