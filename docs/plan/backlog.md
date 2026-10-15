# Backlog — bảng tất cả task

> **Nguồn sự thật về phạm vi, người phụ trách, ước lượng, phụ thuộc và trạng thái.** Chi tiết từng task: `docs/plan/epics/`.
>
> **Sprint:** **S0** 15–17/10 · **S1** 18–25/10 · **S2** 26/10–01/11 · **S3** 02–04/11 · **DP** (dự phòng) 05/11.
> **Trạng thái:** `todo` · `doing` · `review` · `done` · `blocked` · `cut`.
> **Ưu tiên:** **P0** bắt buộc · **P1** nên có.
> **★** = trên đường găng.
>
> **Kiểm tra tự động sau mỗi lần sửa:** `uv run python scripts/plan_check.py` (phụ thuộc, vòng lặp, thứ tự sprint, tải từng người, đường găng). CI cũng chạy lệnh này.
>
> **Cách cập nhật để tránh xung đột git:** chỉ sửa **dòng của task mình**, và sửa trong chính PR của task đó.

## E0 — Nền tảng · `epics/E0-platform.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| PLAT-01 ★ | uv workspace, ruff/pytest, script setup | M5 | Claude | 0,5 | S0 | P0 | — | done |
| PLAT-02 | Khởi tạo Next.js (3 khu vực) | M1 | Claude | 0,5 | S0 | P0 | — | done |
| PLAT-03 ★ | FastAPI + vericlue_ml + ModuleResult + mock | M5 | Claude | 1 | S0 | P0 | PLAT-01 | done |
| PLAT-04 ★ | Chốt API v1, hợp đồng, sinh type cho web | M5 (+M1) | Claude | 1 | S0 | P0 | PLAT-02, PLAT-03 | done |
| PLAT-05 ★ | DB, Alembic, Docker Compose | M5 | | 1 | S1 | P0 | PLAT-04 | todo |
| PLAT-06 | Token phiên, giới hạn lượt, khóa Ed25519 | M2 | | 1 | S1 | P0 | PLAT-05 | todo |
| PLAT-07 | CI xanh, branch protection, CODEOWNERS | M2 | | 0,5 | S0 | P0 | PLAT-01, PLAT-02 | todo |
| PLAT-08 ★ | Orchestrator chạy song song detector | M5 | | 1 | S1 | P0 | PLAT-05 | todo |
| PLAT-09 ★ | Kiểm thử đầu–cuối theo kịch bản (mock) | M1 | | 1 | S2 | P0 | PLAT-08, ROUT-02, CAP-06 | todo |

## E1 — Dữ liệu · `epics/E1-data.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| DATA-01 | Script tải dữ liệu công khai | M3 + M4 | Codex | 1 | S0 | P0 | PLAT-01 | review |
| DATA-02 | Script tải mô hình + SHA-256 | M2 | Codex | 0,5 | S0 | P0 | PLAT-01 | done |
| DATA-03 | Chia tập theo người | M3 + M4 | | 1 | S1 | P0 | DATA-01 | todo |
| DATA-04 | Tạo deepfake người Việt | M2 | | 1,5 | S1 | P0 | DATA-01, REDT-01 | todo |
| DATA-05 | Biến thể nén 3 mức | M4 | | 0,5 | S1 | P0 | DATA-01 | todo |

## E2 — Web thu nhận · `epics/E2-capture.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| CAP-01 ★ | Luồng /verify + màn hình đồng ý | M1 | Claude | 1 | S0–S1 | P0 | PLAT-02, PLAT-04 | done |
| CAP-02 ★ | Camera, oval, cổng chất lượng | M1 | | 1,5 | S1 | P0 | CAP-01 | todo |
| CAP-03 | Trang thử ChromaPulse (spike) | M1 (+M3) | Claude | 1 | S0 | P0 | PLAT-02 | review |
| CAP-04 | ChromaPulse chính thức (chép Amplify) | M1 | | 1,5 | S1 | P0 | CAP-03, PRES-01, PLAT-04 | todo |
| CAP-05 ★ | CamProbe phía trình duyệt | M1 | | 1 | S1 | P0 | CAP-02 | todo |
| CAP-06 ★ | Gửi media, xử lý kết quả | M1 | | 1 | S1 | P0 | CAP-04, CAP-05, PLAT-06 | todo |
| CAP-07 ★ | Màn hình đọc câu tiếng Việt | M1 | | 1 | S2 | P0 | CAP-06, VOICE-04 | todo |
| CAP-08 ★ | Hoàn thiện UX, thử nhiều máy | M1 | | 0,5 | S3 | P1 | CAP-07 | todo |

## E3 — Hiện diện phía server · `epics/E3-presence.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| PRES-01 | Spike phân tích độ trễ (cổng quyết định 17/10) | M3 | | 1 | S0 | P0 | CAP-03 | todo |
| PRES-02 | chromapulse.py | M3 | | 2 | S1 | P0 | PRES-01, PLAT-03 | todo |
| PRES-03 | camprobe.py | M3 | | 0,5 | S1 | P0 | CAP-05, PLAT-03 | todo |
| PRES-04 | Chạy thử của nhóm, chỉnh ngưỡng (R5) | M1 (+M3) | | 1 | S2 | P0 | PRES-02, PRES-03, CAP-06, REDT-01 | todo |

## E4 — Khuôn mặt · `epics/E4-face.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| FACE-01 | PAD MiniFASNet + kết quả gốc (R1) | M3 | | 1 | S0–S1 | P0 | PLAT-03, DATA-03, EVAL-01 | todo |
| FACE-02 | GenD + kết quả gốc (R2) | M3 | | 1,5 | S1 | P0 | PLAT-03, DATA-02, DATA-03, EVAL-01 | todo |
| FACE-03 | SBI + heatmap | M3 | | 1 | S2 | P0 | FACE-02 | todo |
| FACE-04 | Tinh chỉnh GenD và PAD trên dữ liệu VN | M3 | | 2 | S2 | P0 | FACE-01, FACE-02, DATA-04, DATA-05 | todo |
| FACE-05 | Tối ưu tốc độ | M3 | | 0,5 | S2 | P1 | FACE-04 | todo |

## E5 — Giọng nói · `epics/E5-voice.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| VOICE-01 | AntiDeepfake + kết quả gốc (R3) | M4 | | 1 | S0–S1 | P0 | PLAT-03, DATA-02, DATA-03, EVAL-01 | todo |
| VOICE-02 | Tăng cường dữ liệu, chống học vẹt | M4 | | 1 | S1 | P0 | PLAT-03, DATA-01 | todo |
| VOICE-03 | Tinh chỉnh AntiDeepfake cho tiếng Việt | M4 | | 2 | S1–S2 | P0 | VOICE-01, VOICE-02, DATA-03, DATA-05 | todo |
| VOICE-04 | Câu thử thách, nhận dạng, so khớp 2 lớp | M4 | | 1,5 | S1–S2 | P0 | PLAT-03 | todo |
| VOICE-05 | Căn chỉnh câu, cắt ghép, SyncNet | M4 | | 1,5 | S2 | P0 | VOICE-04, DATA-02 | todo |
| VOICE-06 | Gộp bước giọng nói vào luồng | M4 | | 0,5 | S2 | P0 | VOICE-03, VOICE-04, VOICE-05, ROUT-02 | todo |

## E6 — TrustRouter · `epics/E6-router.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| ROUT-01 | Hiệu chỉnh xác suất | M5 | Codex | 1 | S1 | P0 | PLAT-03 | done |
| ROUT-02 ★ | Bộ chính sách quyết định | M5 | | 1,5 | S1 | P0 | ROUT-01, PLAT-08 | todo |
| ROUT-03 ★ | Chọn ngưỡng bằng Learn-then-Test (MAPIE) | M5 | | 1,5 | S2 | P0 | ROUT-02, FACE-04, VOICE-03 | todo |
| ROUT-04 | Cổng ngoài phạm vi | M5 | | 1 | S2 | P1 | FACE-02 | todo |
| ROUT-05 ★ | Đánh giá R4 | M5 | | 1 | S3 | P0 | ROUT-03 | todo |

## E7 — Bàn duyệt và giám định · `epics/E7-review-forensic.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| REV-01 | API bàn duyệt + nhật ký chuỗi băm | M2 | | 1 | S1 | P0 | PLAT-05 | todo |
| REV-02 | Giao diện bàn duyệt + hồ sơ bằng chứng | M2 | | 2 | S1–S2 | P0 | REV-01, PLAT-04 | todo |
| FOR-01 | API giám định: chia đoạn, chạy bộ não | M5 | | 1,5 | S2 | P0 | PLAT-05, FACE-02, VOICE-01 | todo |
| FOR-02 | Giao diện giám định | M2 | | 1,5 | S2 | P0 | FOR-01 | todo |
| FOR-03 | Quét nguồn gốc (AudioSeal, Perth, C2PA) | M3 | | 1 | S2 | P0 | PLAT-03 | todo |
| FOR-04 | Báo cáo ENFSI có chữ ký | M2 (+M5) | | 1,5 | S2 | P0 | FOR-01, FOR-03, PLAT-06, ROUT-01 | todo |

## E8 — Red-team, đánh giá, demo · `epics/E8-eval-demo.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| REDT-01 | Máy red-team + kịch bản tấn công | M2 (+M3, M4) | | 1 | S1 | P0 | — | todo |
| EVAL-01 | Khung đánh giá chung (chỉ số, bootstrap) | M5 | Codex | 1 | S1 | P0 | PLAT-03 | done |
| EVAL-02 | Đo độ trễ (R6) | M5 | | 0,5 | S3 | P0 | PLAT-08, VOICE-06 | todo |
| EVAL-03 | Đánh giá chế độ giám định theo đoạn (R7) | M4 | | 1 | S3 | P1 | FOR-01, DATA-04, EVAL-01 | todo |
| DEMO-01 ★ | Kịch bản demo 7 tình huống | M2 | | 1 | S3 | P0 | PLAT-09, CAP-07, REV-02, FOR-02, FOR-04, VOICE-06, PRES-04 | todo |
| DEMO-02 ★ | Video demo + dự phòng | M1 (+cả nhóm) | | 0,5 | S3 | P0 | DEMO-01 | todo |
| DEMO-03 ★ | Báo cáo nộp vòng 2 | M2 (+cả nhóm) | | 1 | S3 | P0 | ROUT-05, EVAL-02, FACE-04, VOICE-03, PRES-04 | todo |
| DEMO-04 ★ | Kiểm tra cuối, đóng gói nộp | M5 | | 0,5 | DP | P0 | DEMO-02, DEMO-03 | todo |

## Tổng hợp tải (chạy `plan_check.py` để có số mới nhất)

| Vai trò | S0 | S1 | S2 | S3 | DP | Tổng |
|---|---|---|---|---|---|---|
| Sức chứa ở 70% | 2,1 | 5,6 | 4,9 | 2,1 | 0,7 | 15,4 |
| M1 | 2,0 | 5,5 | 3,0 | 1,0 | — | 11,5 |
| M2 | 1,0 | 4,5 | 4,0 | 2,0 | — | 11,5 |
| M3 | 2,0 | 5,0 | 4,5 | — | — | 11,5 |
| M4 | 1,0 | 5,2 | 3,8 | 1,0 | — | 11,0 |
| M5 | 2,0 | 5,5 | 4,0 | 1,5 | 0,5 | 13,5 (+0,5 đã xong) |

56 task (53 P0, 3 P1), khoảng 60 ngày công.
