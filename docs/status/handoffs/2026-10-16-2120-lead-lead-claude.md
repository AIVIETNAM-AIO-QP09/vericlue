# Bàn giao · LEAD · Lead+Claude · 2026-10-16 21:20

**Nhánh:** `docs/LEAD-handover-1016` (phiên điều phối, chỉ sửa tài liệu)
**Trạng thái task sau phiên này:** doing — chuyển từ "AI làm nền" sang "thành viên nhận việc"

## Đã xong
- Gộp từ PR #9 tới #21 (trừ #20): DATA-01/02, CAP-01/02/03, PLAT-05, PLAT-08 (+ hotfix #18), VOICE-04, ROUT-02, REV-01. `main` = `802628a`. Mọi PR đều qua subagent `reviewer`; các lỗi thật đã bắt và sửa:
  - PLAT-04: đi tắt tới `pass` qua `/voice` sau `review`;
  - EVAL-01: BPCER "mô tả" sai do so sánh số thực;
  - CAP-02: kẹt ở bước xin camera (so danh tính đối tượng) → thêm bài thử trình duyệt Playwright;
  - PLAT-08: nhả slot sau khi trả kết quả → lượt kế tiếp bị busy;
  - REV-01: chuỗi băm gãy khi ghi đồng thời → UNIQUE ở DB;
  - PLAT-05: media ca review chưa đóng bị xóa sau 30 ngày.
- Nhánh này:
  - `architecture.md` §6: tạo phiên ngay trước bước nháy màu; chụp lại qua cổng chất lượng;
  - thẻ PRES-02: quá sáng = `unclear` (không phải giả), tín hiệu giác mạc là tùy chọn;
  - thẻ REV-02: ghi những gì REV-01 đã có, còn thiếu API phục vụ ảnh/video; mã lý do tạm;
  - thẻ FOR-04: neo hash cuối chuỗi `review_events` vào báo cáo ký số;
  - thẻ PLAT-09: e2e Playwright đã có từ CAP-02, PLAT-09 đưa vào CI;
  - `working-with-ai.md`: "nên" mở phiên tại worktree (kèm cách làm an toàn khi mở từ `Data4Life`); `docker compose down` sau khi thử;
  - `onboarding.md`: mục chạy thử toàn hệ thống bằng Docker, dữ liệu/mô hình ngoài repo, dùng AI, chạy e2e;
  - `STATUS.md`: tình hình 16/10, bị chặn, câu hỏi Q8–Q11, rủi ro, quyết định.

## Đang dở
- **PR #20** (DATA-03 âm thanh, Codex `vericlue-data`): đã gửi prompt sửa — dồn quota `calib_ltt` từ train (đúng thẻ), đường dẫn CSV tương đối so với `DATA_DIR`, test âm cho `validate_splits`. Duyệt lại rồi gộp. DATA-03 giữ `doing` (phần ảnh chờ Kaggle).
- **Dọn ROUT-02** (Codex `vericlue-codex`): đã gửi prompt (bỏ property `provisional_threshold_b/_a`, xóa `decide_finalize/decide_voice` cũ, cờ cắt ghép không phải số → review, cờ dương → ưu tiên cao, gate hiện diện rỗng → review). Duyệt rồi gộp.
- **Người dùng chưa làm:** (1) thu JSON ChromaPulse 3 máy (PRES-01, hạn 17/10); (2) chạy `download_data.py` với token Kaggle cho Zalo 2022, FAS-VN, RTFS-10k; (3) họp nhóm chốt tên M1–M5.

## Bước tiếp theo
1. Duyệt và gộp PR #20, PR dọn ROUT-02, PR tài liệu của nhánh này.
2. **Sau khi có tên M1–M5:** cập nhật `docs/context/team.md`, `.github/CODEOWNERS`, cột "Người" trong `backlog.md`; soạn cho từng người gói nhận việc (đọc gì, task đầu tiên, prompt có bước subagent).
3. Từ 18/10, các phiên AI hiện có không nhận task mới; có thể giữ 1 phiên để chữa cháy/ghép nối. Mỗi thành viên dùng AI trên máy mình, gửi kế hoạch + PR cho phiên điều phối duyệt.
4. Việc đầu tiên đề xuất theo vai trò:

   | Vai trò | Việc đầu tiên | Ghi chú |
   |---|---|---|
   | M1 | Đo ≥ 15 fps CAP-02 trên Android; thu JSON CAP-03 → CAP-04 | CAP-04 chờ kết luận PRES-01 |
   | M2 | PLAT-06 (token HMAC, 409, 429, xác thực nhân viên, hash token); REDT-01; hỏi BTC (Q1); xin 4 bộ dữ liệu cần duyệt | Danh sách việc PLAT-06 nằm trong bàn giao PLAT-04, PLAT-05, REV-01 và thẻ PLAT-06 |
   | M3 | **PRES-01 (17/10)** → DATA-03 phần ảnh (khi có Kaggle) → FACE-01 (R1) | |
   | M4 | VOICE-01 (R3 gốc) khi PR #20 gộp → DATA-05 → VOICE-02 | R3 phải ghi rõ giới hạn dữ liệu small |
   | M5 | Tiếp nhận ROUT-02 → ROUT-03 (chọn ngưỡng LTT, chỉ trên `calib_ltt`) | Tech lead: duyệt PR `[contract]` |

## Quyết định, lưu ý, bẫy
- Ngưỡng và fusion vẫn `provisional: true`; **chưa học gì trên dữ liệu thật**. Không đưa số nào vào báo cáo trước khi có R1–R3 chạy thật.
- Bài thử trình duyệt `npm run test:e2e` chưa vào CI: chạy tay trước mỗi PR chạm `/verify`.
- Docker: các worktree dùng chung cổng 3000/8000/5432. Gặp "port is already allocated" thì tìm bộ đang chạy (`docker compose ls`) và tắt. Lần chạy lỗi cổng có thể để lại container `db` nối mạng nửa vời → `docker compose down` rồi `up` lại.
- Hạn 4 giây của bộ phát hiện tính cả thời gian xếp hàng: phải đo lại khi gắn mô hình thật (rủi ro trong STATUS).
- Sửa file bằng Python heredoc: đường dẫn `D:\Projects\vericlue-…` bị `\v` hiểu là ký tự điều khiển. Dùng công cụ Edit hoặc script trong scratchpad.

## Câu hỏi cho nhóm
- Q4 (tên M1–M5), Q5 (máy demo GPU, máy red-team), Q7 (kênh liên lạc) — cần chốt ngay trong buổi họp.
- Q8–Q11 mới trong `STATUS.md`: giấy phép trong proposal, câu chữ màn đồng ý, chính sách giữ media giám định, danh sách mã lý do.

## Test đã chạy
```
uv run python scripts/plan_check.py → 0 lỗi, 0 cảnh báo (nhánh docs/LEAD-handover-1016)
npm run test:e2e (vericlue-claude, PR #15) → 5 passed (1.2m)
pytest orchestrator slot test ×50 (PR #18) → 50/50 đạt
```
