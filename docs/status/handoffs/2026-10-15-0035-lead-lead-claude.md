# Bàn giao · LEAD · Lead+Claude · 2026-10-15 00:35

**Nhánh:** `docs/LEAD-fixes-1015` (phiên điều phối, chỉ sửa tài liệu và cấu hình)
**Trạng thái task sau phiên này:** doing — điều phối liên tục

## Đã xong
- Gộp PR #4 (PLAT-02), PR #5 (EVAL-01), PR #6 (bộ công cụ trưởng nhóm). `main` = `4456711`.
- Duyệt PR #5 hai vòng bằng `reviewer`; lỗi BPCER "mô tả" (so sánh số thực) đã sửa và tự kiểm lại.
- Duyệt kế hoạch PLAT-04; chốt token chỉ làm bản TẠM, đầy đủ để PLAT-06 (ADR-0011 mục "Hệ quả").
- Duyệt PR #7 (PLAT-04): **đạt sau khi sửa**. Đã tự tái hiện lỗi đi tắt tới `pass`: voice_challenge → finalize lại ra review → `/voice` ra pass; và review → finalize lại ra pass. Đã gửi prompt sửa 8 mục.
- Tạo worktree `D:\Projects\vericlue-data` (nhánh `feat/DATA-01-download-datasets`) cho phiên Codex thứ ba; đã soạn prompt DATA-01.
- Nhánh này:
  - `architecture.html`: bỏ chữ "token dùng một lần", ghi theo ADR-0011;
  - thẻ PLAT-06: thêm xác thực nhân viên cho `/v1/review`, `/v1/forensic`, kiểm `Content-Length`, tiêu chí 401;
  - `.claude/settings.json`: chỉ chặn đọc `.env`, `.env.local`, `.env.*.local` (trước đây chặn cả `.env.example`, nên AI phải ghi mù);
  - `working-with-ai.md`, `lead-playbook.md`: mở phiên AI ngay tại thư mục worktree; dữ liệu và mô hình để chung (`DATA_DIR`, `MODELS_DIR`);
  - `STATUS.md` cập nhật tới 15/10.

## Đang dở
- **PLAT-04** (Claude, `vericlue-claude`, PR #7): đang sửa theo review. Khi push xong: duyệt lại nhanh, kiểm đủ test cho 2 lỗi đi tắt (409 `voice_not_requested` sau review; 409 `session_closed`).
- **DATA-02** (Codex, `vericlue-codex`): đang lập kế hoạch + bảng mô hình. Khi duyệt, **gộp kèm phần bổ sung**: đọc `MODELS_DIR` (mặc định `./models`, máy này dùng `D:\Projects\vericlue-store\models`); sửa ít nhất `pyproject.toml`, `uv.lock`, `.env.example`; merge `origin/main` trước PR, `uv.lock` xung đột thì chạy lại `uv lock`. Soi kỹ **giấy phép** từng mô hình.
- **DATA-01** (Codex, `vericlue-data`): đã có prompt, chưa thấy kế hoạch. Soi giấy phép và cách chọn tập con **theo người/video gốc** (luật 8).

## Bước tiếp theo
1. Người dùng duyệt rồi mình commit, push, mở PR nhánh `docs/LEAD-fixes-1015`.
2. Duyệt lại PR #7 → người dùng gộp → PLAT-04 xong: CAP-01 và PLAT-05 mở khóa (đường găng).
3. Duyệt kế hoạch DATA-02, DATA-01 (xem "Đang dở").
4. Giao task tiếp cho phiên Claude sau PLAT-04: ứng viên là CAP-03 (trang thử ChromaPulse, cần cho cổng PRES-01 ngày 17/10) hoặc PLAT-05 (đường găng thứ hai). Xem `plan_check.py`.

## Quyết định, lưu ý, bẫy
- Phiên đã ra `review` là trạng thái cuối (kiểm thứ tự luồng ở PLAT-04, không phải máy trạng thái PLAT-06).
- Mock: print, replay, faceswap đều ra review ưu tiên cao vì chromapulse fail ở cả 4 kịch bản — chốt ở ROUT-02.
- `npm audit` 5 lỗi chỉ ở công cụ lint; không `audit fix --force`.
- Người dùng từng mở mọi phiên AI từ thư mục `Data4Life` rồi để AI tự chuyển sang worktree. Code vẫn vào đúng worktree, nhưng từ nay mở phiên ngay tại worktree.
- Reviewer phải chạy `uv run --all-packages pytest` trong worktree (thiếu `--all-packages` thì `ModuleNotFoundError`).
- Bẫy khi sửa file bằng Python heredoc: chuỗi có `\v` trong đường dẫn Windows (`D:\Projects\vericlue-…`) bị hiểu là ký tự điều khiển. Dùng công cụ Edit hoặc chuỗi raw.
- Ổ D: còn ~119 GB; tải đủ dữ liệu cần 100–150 GB.

## Câu hỏi cho nhóm
- Q1, Q4, Q5, Q7 trong `STATUS.md` vẫn mở. Q4 (tên M1–M5) đang chặn việc giao REDT-01, CAP-03 cho người thật.
- Người dùng cần: Kaggle token, HF token (read; write để chép SBI), đồng ý điều khoản VSASV và LAV-DF trên HF, gửi yêu cầu SEA-Spoof, FaceForensics++, DeepSpeak v1, Deepfake-Eval-2024.

## Test đã chạy
```
uv run python scripts/plan_check.py → 0 lỗi, 0 cảnh báo (nhánh docs/LEAD-fixes-1015)
Script tái hiện của reviewer trên PR #7 (aa966bc) → f2 review, voice pass; g1 review, g2 pass; /voice 409 nhưng vẫn ghi file
```
