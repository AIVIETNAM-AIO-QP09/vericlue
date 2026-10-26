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
| PLAT-05 ★ | DB, Alembic, Docker Compose | M5 | Codex | 1 | S1 | P0 | PLAT-04 | done |
| PLAT-06 | HMAC/Ed25519 kết quả/HTML; quota/body limit, StaffBearer; còn nghiệm thu media | M2 | Codex | 1 | S1 | P0 | PLAT-05 | doing |
| PLAT-07 | CI xanh, branch protection, CODEOWNERS | M2 | | 0,5 | S0 | P0 | PLAT-01, PLAT-02 | todo |
| PLAT-08 ★ | Orchestrator chạy song song detector | M5 | Codex | 1 | S1 | P0 | PLAT-05 | done |
| PLAT-09 ★ | Kiểm thử đầu–cuối theo kịch bản (mock) | M1 | | 1 | S2 | P0 | PLAT-08, ROUT-02, CAP-06 | todo |

## E1 — Dữ liệu · `epics/E1-data.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| DATA-01 | Script tải dữ liệu công khai | M3 + M4 | Codex | 1 | S0 | P0 | PLAT-01 | review |
| DATA-02 | Script tải mô hình + SHA-256 | M2 | Codex | 0,5 | S0 | P0 | PLAT-01 | done |
| DATA-03 | Chia tập theo người | M3 + M4 | Codex | 1 | S1 | P0 | DATA-01 | doing |
| DATA-04 | Tạo deepfake người Việt | M2 | | 1,5 | S1 | P0 | DATA-01, REDT-01 | todo |
| DATA-05 | Biến thể nén 3 mức | M4 | | 0,5 | S1 | P0 | DATA-01 | todo |
| DATA-06 | Tự sinh giọng AI tiếng Việt + tải ViMD bản lớn | M4 | | 0,5 | S1 | P0 | DATA-01 | todo |

## E2 — Web thu nhận · `epics/E2-capture.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| CAP-01 ★ | Luồng /verify + màn hình đồng ý | M1 | Claude | 1 | S0–S1 | P0 | PLAT-02, PLAT-04 | done |
| CAP-02 ★ | Camera, oval, cổng chất lượng | M1 | Claude | 1,5 | S1 | P0 | CAP-01 | review |
| CAP-03 | Trang thử ChromaPulse (spike) | M1 (+M3) | Claude | 1 | S0 | P0 | PLAT-02 | done |
| CAP-04 | ChromaPulse chính thức (chép Amplify) | M1 | | 1,5 | S1 | P0 | CAP-03, PRES-01, PLAT-04 | todo |
| CAP-05 ★ | CamProbe phía trình duyệt | M1 | | 1 | S1 | P0 | CAP-02 | todo |
| CAP-06 ★ | Gửi media, xử lý kết quả | M1 | | 1 | S1 | P0 | CAP-04, CAP-05, PLAT-06 | todo |
| CAP-07 ★ | Màn hình đọc câu tiếng Việt | M1 | | 1 | S2 | P0 | CAP-06, VOICE-04 | todo |
| CAP-08 ★ | Hoàn thiện UX, thử nhiều máy | M1 | | 0,5 | S3 | P1 | CAP-07 | todo |

## E3 — Hiện diện phía server · `epics/E3-presence.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| PRES-01 | Spike phân tích độ trễ (cổng quyết định 17/10) | M3 | Lead | 1 | S0 | P0 | CAP-03 | done |
| PRES-02 | ChromaPulse: video/webcam diagnostic; chờ kiểm chứng cổng | M3 | Codex | 2 | S1 | P0 | PRES-01, PLAT-03 | doing |
| PRES-03 | camprobe.py | M3 | | 0,5 | S1 | P0 | CAP-05, PLAT-03 | todo |
| PRES-04 | Chạy thử của nhóm, chỉnh ngưỡng (R5) | M1 (+M3) | | 1 | S2 | P0 | PRES-02, PRES-03, CAP-06, REDT-01 | todo |
| PRES-05 | Lượt thử mặt local liên tục: màu, mắt, quay đầu | M3 | Codex | 1 | S2 | P0 | PLAT-03 | review |

## E4 — Khuôn mặt · `epics/E4-face.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| FACE-01 | PAD MiniFASNet + kết quả gốc (R1) | M3 | | 1 | S0–S1 | P0 | PLAT-03, DATA-03, EVAL-01 | todo |
| FACE-02 | GenD + kết quả gốc (R2) | M3 | | 1,5 | S1 | P0 | PLAT-03, DATA-02, DATA-03, EVAL-01 | doing |
| FACE-03 | SBI + heatmap | M3 | | 1 | S2 | P0 | FACE-02 | todo |
| FACE-04 | Tinh chỉnh GenD và PAD trên dữ liệu VN | M3 | | 2 | S2 | P0 | FACE-01, FACE-02, DATA-04, DATA-05 | doing |
| FACE-05 | Tối ưu tốc độ | M3 | | 0,5 | S2 | P1 | FACE-04 | todo |

## E5 — Giọng nói · `epics/E5-voice.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| VOICE-01 | AntiDeepfake + kết quả gốc (R3) | M4 | | 1 | S0–S1 | P0 | PLAT-03, DATA-02, DATA-03, EVAL-01 | todo |
| VOICE-02 | Tăng cường dữ liệu, chống học vẹt | M4 | | 1 | S1 | P0 | PLAT-03, DATA-01 | todo |
| VOICE-03 | Tinh chỉnh AntiDeepfake cho tiếng Việt | M4 | | 2 | S1–S2 | P0 | VOICE-01, VOICE-02, DATA-03, DATA-05, DATA-06 | todo |
| VOICE-04 | Câu thử thách, nhận dạng, so khớp 2 lớp (chặn lặp token) | M4 | Codex | 1,5 | S1–S2 | P0 | PLAT-03 | done |
| VOICE-05 | Căn chỉnh câu, cắt ghép, SyncNet (thiết bị riêng, nạp lười) | M4 | Codex | 1,5 | S2 | P0 | VOICE-04, DATA-02 | doing |
| VOICE-06 | Gộp bước giọng nói vào luồng | M4 | | 0,5 | S2 | P0 | VOICE-03, VOICE-04, VOICE-05, ROUT-02 | todo |
| VOICE-07 | Qwen3-ASR: backend + CLI kiểm câu đọc, diagnostic CPU riêng | M4 | Codex | 1 | S2 | P0 | PLAT-03, VOICE-04 | review |
| VOICE-08 | Thử câu đọc bằng microphone, RAM-only và runtime Qwen riêng | M4 | Codex | 0,5 | S2 | P0 | VOICE-07 | review |
| VOICE-09 | NES2Net-X: backend + CLI raw diagnostic CPU riêng | M4 | Codex | 1 | S2 | P0 | PLAT-03 | review |
| VOICE-10 | Ghép NES2Net vào công cụ micro qua worker RAM riêng | M4 | Codex | 1 | S2 | P0 | VOICE-08, VOICE-09 | done |
| VOICE-11 | Nhịp đọc/CTC trong lab micro, mốc âm tiết RAM và CLI | M4 | Codex | 1 | S2 | P0 | VOICE-10 | done |
| VOICE-12 | Lab thu A/V một nguồn và khớp môi SyncNet trong RAM | M4 | Codex | 1,5 | S2 | P0 | VOICE-11 | done |
| VOICE-13 | NES2Net theo đoạn phủ toàn bản thu trong lab | M4 | Codex | 1 | S2 | P0 | VOICE-12 | done |
| VOICE-14 | Qwen/CTC/NES2Net/SyncNet API phiên, worker tách runtime | M4 | Codex | 1 | S2 | P0 | VOICE-13 | review |

## E6 — TrustRouter · `epics/E6-router.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| ROUT-01 | Hiệu chỉnh xác suất + identity MVP | M5 | Codex | 1 | S1 | P0 | PLAT-03 | review |
| ROUT-02 ★ | Bộ chính sách quyết định | M5 | Codex | 1,5 | S1 | P0 | ROUT-01, PLAT-08 | done |
| ROUT-03 ★ | Chọn ngưỡng bằng Learn-then-Test (MAPIE) | M5 | | 1,5 | S2 | P0 | ROUT-02, FACE-04, VOICE-03 | todo |
| ROUT-04 | Cổng ngoài phạm vi | M5 | | 1 | S2 | P1 | FACE-02 | todo |
| ROUT-05 ★ | Đánh giá R4 | M5 | | 1 | S3 | P0 | ROUT-03 | todo |

## E7 — Bàn duyệt và giám định · `epics/E7-review-forensic.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| REV-01 | API bàn duyệt + nhật ký chuỗi băm | M2 | Claude | 1 | S1 | P0 | PLAT-05 | done |
| REV-02 | Giao diện bàn duyệt + hồ sơ bằng chứng | M2 | | 2 | S1–S2 | P0 | REV-01, PLAT-04 | todo |
| REV-03 | Chặn ghi quyết định duyệt lặp do snapshot SQLite cũ | M2 | Codex | 0,5 | S2 | P0 | REV-01 | review |
| FOR-01 | API giám định: chia đoạn, chạy bộ não | M5 | | 1,5 | S2 | P0 | PLAT-05, FACE-02, VOICE-01 | todo |
| FOR-02 | Giao diện giám định | M2 | | 1,5 | S2 | P0 | FOR-01 | todo |
| FOR-03 | Quét nguồn gốc (AudioSeal, Perth, C2PA) | M3 | | 1 | S2 | P0 | PLAT-03 | todo |
| FOR-04 | PDF/JSON ký và ảnh/phổ opt-in; còn neo audit/LR và ENFSI | M2 (+M5) | Codex | 1,5 | S2 | P0 | FOR-01, FOR-03, PLAT-06, ROUT-01 | doing |

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

## E9 — App Android, ba luồng eKYC, riêng tư · `epics/E9-app-flows.md`

| Mã | Task | Vai trò | Người | Ngày công | Sprint | Ưu tiên | Phụ thuộc | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| FLOW-01 | Purpose/luật theo luồng; kết quả Ed25519 opt-in, chờ nghiệm thu thật | M5 | Codex | 1 | S1 | P0 | ROUT-02, PLAT-08 | doing |
| FLOW-02 | OTP mô phỏng | M2 | Ngọc Quang+Claude | 0,5 | S1 | P0 | PLAT-05 | doing |
| FLOW-03 | Chụp CCCD, QR, chân dung, kiểm đã đăng ký; bảo toàn ảnh khi lỗi | M1 | Ngọc Quang+Claude | 1,5 | S1 | P0 | PLAT-05, FACE-01 | doing |
| FLOW-04 | Quay đầu, chọn khung RAM, GenD và FS-VFM-L PAD — diagnostic | M1 (+M3) | Codex | 1 | S1 | P0 | CAP-06 | doing |
| FLOW-05 | LVFace-B/mặt–giọng; ghi danh, receipt, so mẫu đã lưu; giữ chốt luồng thật | M3 | Codex | 1 | S1 | P0 | FLOW-03, FACE-01 | doing |
| SEC-01 | Khóa theo phiên, che dữ liệu, nhật ký truy cập | M2 | Codex | 1,5 | S1 | P0 | REV-01, PLAT-05 | review |
| SEC-02 ★ | Ký media, L0 khóa ghi danh; service khôi phục/thu hồi, chờ nghiệm thu máy thật | M2 (+M1) | Codex | 1 | S2 | P0 | APP-01, PLAT-06 | doing |
| APP-01 ★ | App Kotlin: khung, API qua HTTPS, điều hướng 3 luồng | M1 | Ngọc Quang+Claude | 1,5 | S1 | P0 | PLAT-04 | doing |
| APP-02 ★ | App: chụp mặt, quay 3 s, quay đầu ngẫu nhiên | M1 | Ngọc Quang+Claude | 2 | S1–S2 | P0 | APP-01 | doing |
| APP-03 | App: ghi âm đọc câu (WAV 16 kHz) | M1 | Ngọc Quang+Claude | 1 | S2 | P0 | APP-01 | doing |
| APP-04 | App: OTP, chụp CCCD, xác nhận thông tin | M2 (+M1) | Ngọc Quang+Claude | 1,5 | S1–S2 | P0 | APP-01 | doing |
| IOS-01 | App iOS: khung SwiftUI, theme, toàn bộ màn, điều hướng 3 luồng, chế độ demo | M1 | Lý Anh Quân | 2 | S2 | P1 | APP-01 | todo |
| IOS-02 | App iOS: client API, LiveFlow, FlowRules + test | M1 | Lý Anh Quân | 1,5 | S2 | P1 | FLOW-01 | todo |
| IOS-03 | App iOS: OTP, chụp CCCD (nét, lóa, QR bằng Vision), xác nhận thông tin | M1 | Lý Anh Quân | 1,5 | S2 | P1 | IOS-01, IOS-02, FLOW-02, FLOW-03 | todo |
| IOS-04 | App iOS: camera trước, lịch phần mặt một video (màu, chấm, quay đầu), signals, camprobe | M1 | Lý Anh Quân | 3 | S2 | P1 | IOS-02, LIVE-01 | todo |
| IOS-05 | App iOS: đọc câu, WAV 16 kHz + MP4, audio_offset_ms | M1 | Lý Anh Quân | 1 | S2 | P1 | IOS-04 | todo |
| IOS-06 | App iOS: gián đoạn, thử lại khi mất mạng, xóa file tạm | M1 | Lý Anh Quân | 1 | S2 | P1 | IOS-04 | todo |
| IOS-07 | App iOS: bản Release HTTPS, đo trên máy thật, README, bàn giao | M1 | Lý Anh Quân | 1 | S2 | P1 | IOS-03, IOS-05, IOS-06 | todo |
| LIVE-01 | Gói thử thách động theo phiên (màu, chấm sáng, quay đầu, câu) [contract] | M5 | Codex | 1 | S2 | P0 | FLOW-01 | doing |
| LIVE-02 | Dò mắt, chuỗi kiểm mặt và webcam lab — diagnostic | M3 (+M1) | Codex | 1,5 | S2 | P0 | LIVE-01 | doing |
| LIVE-03 | Ký media theo phiên trên web (WebAuthn), chặn phát lại | M2 (+M1) | | 1 | S2 | P0 | LIVE-01 | todo |
| LIVE-04 | Kháng lượng tử: đường truyền ML-KEM, ký kết quả ML-DSA | M2 | | 1 | S2 | P0 | FLOW-01 | todo |
| LIVE-05 | Giấy chứng nhận ZKP cho bên tích hợp | M5 | | 2,5 | S3 | P1 | LIVE-04 | todo |
| LIVE-06 | Gia hạn phiên khi gián đoạn, làm lại riêng phần khuôn mặt [contract] | M5 | Ngọc Quang+Claude | 0,5 | S2 | P0 | LIVE-01 | doing |
| LIVE-07 | Thông báo làm lại theo hai loại (chất lượng · thử thách) | M1 | | 0,5 | S2 | P0 | LIVE-01 | todo |

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
