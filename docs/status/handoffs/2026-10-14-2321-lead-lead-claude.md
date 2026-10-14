# Bàn giao · LEAD · Lead+Claude · 2026-10-14 23:21

**Nhánh:** `docs/LEAD-lead-playbook` (phiên điều phối, chỉ sửa tài liệu và script công cụ)
**Trạng thái task sau phiên này:** doing — điều phối liên tục

## Đã xong
- Duyệt PR #3 (ROUT-01, Codex), kết luận đạt:
  - GroupKFold theo người; lưu ở `ml/configs/calibrators/`; cắt xác suất 1e-4; có `n_pos`/`n_neg`;
  - AUC < 0,5 báo lỗi; điều kiện chọn isotonic đúng;
  - thiếu calibrator báo lỗi, không fallback; mock và cổng luật được miễn;
  - `status` khác `ok` thì `prob_attack = None`.
- Người dùng đã gộp PR #2 (ADR-0010, ADR-0011) và PR #3. `main` = `c067609`.
- Thư mục `D:\Projects\Data4Life` đã chuyển sang `main` và đã kéo bản mới.
- Đã gửi prompt EVAL-01 cho Codex (người dùng dán).
- **Bộ công cụ trưởng nhóm** (nhánh `docs/LEAD-lead-playbook`, người dùng đã duyệt):
  - `.claude/commands/lead.md` (lệnh `/lead`), `docs/ai/lead-playbook.md`;
  - `.claude/agents/reviewer.md` (subagent duyệt PR, chỉ đọc);
  - mục "Subagent và nhiều phiên song song" trong `docs/ai/working-with-ai.md`;
  - `CLAUDE.md`, `docs/README.md` trỏ tới lệnh và sổ tay mới;
  - `STATUS.md`: ROUT-01 xong (PR #2, #3 đã gộp), PLAT-02 `review`, EVAL-01 `doing`, thêm 2 quyết định;
  - `scripts/new_handoff.py`, `scripts/plan_check.py`: đặt UTF-8 cho stdout/stderr **trước** `parse_args` → `--help` không còn lỗi `UnicodeEncodeError` trên console cp1252.

## Đang dở
- **PLAT-02** (phiên Claude, worktree `D:\Projects\vericlue-claude`, nhánh `feat/PLAT-02-web-skeleton`):
  - **ĐÃ GỘP** (PR #4, `main` = `2b7cd1f`), đã thử trên điện thoại; `reviewer` kết luận đạt; 4 mục "nên sửa" đã sửa trong `d1e9360`;
  - `npm audit`: 5 lỗi chỉ nằm trong công cụ lint, `--omit=dev` báo 0; không `audit fix --force`.
- **PLAT-04** (phiên Claude, `vericlue-claude`): đã gửi prompt (có phần subagent). Nhắc kèm: `cacheComponents` bắt bọc dữ liệu động trong `<Suspense>`; test chặn chữ "điểm" sẽ chặn oan "địa điểm"; ngưỡng B/A tạm đặt trong config API, không sửa `thresholds.yaml`.
- **EVAL-01** (Codex, worktree `D:\Projects\vericlue-codex`, nhánh `feat/EVAL-01-eval-framework` từ `c067609`): kế hoạch đã duyệt, đang code. Bàn giao của Codex: `docs/status/handoffs/2026-10-14-2334-eval-01-codex.md` (ở worktree Codex). Trưởng nhóm đã chốt:
  - BPCER@APCER 5% **chính**: ngưỡng chọn trên `calib_fit` (APCER max ≤ 5%), khóa rồi đánh giá; thiếu thì "không khả dụng"; báo kèm APCER thực đạt;
  - thêm dòng **"mô tả"** tính theo đường cong trên tập đánh giá (giống EER) để so với số đã công bố; ngưỡng của nó không trả ra, không lưu, không dùng;
  - cột `status` **bắt buộc**; mặc định gặp dòng khác `ok` thì báo lỗi; `exclude_non_ok=True` thì loại nhưng báo cáo phải in số và tỷ lệ bị loại theo nhóm (bona fide, từng `attack_type`);
  - thêm SciPy trực tiếp (Clopper–Pearson); README ghi các cột `predictions.csv`; bootstrap theo `subject_id`; commit lấy từ git (thêm `-dirty`), in seed và số lần bootstrap; cảnh báo nếu < 10 người.
- **Subagent trong prompt:** mọi prompt giao việc phải có bước subagent (mẫu ở `lead-playbook.md` §4; chi tiết ở `working-with-ai.md`, mục "Dùng subagent để làm nhanh hơn"; đã thêm cả vào `start-task.md`).
- **PR bộ công cụ trưởng nhóm:** người dùng bảo **khoan commit**; chờ đồng ý rồi mới commit, push, mở PR.

## Bước tiếp theo
1. Commit (có `[LEAD]`), push, mở PR nhánh `docs/LEAD-lead-playbook` khi người dùng đồng ý; người dùng gộp. Từ phiên sau, mở phiên điều phối bằng `/lead`.
2. Duyệt PR PLAT-02 khi có. Kiểm theo thẻ E0:
   - 3 trang;
   - lint, test, build xanh;
   - README hướng dẫn HTTPS/tunnel cho điện thoại;
   - `.env.local.example`.
3. Sau khi PLAT-02 gộp, cho phiên Claude làm **PLAT-04** theo ADR-0011:
   - siết `hold_ms` 400–650 và `transition_ms` = 150 trong `session.schema.json`, PR có `[contract]`;
   - luật quyết định tạm thời B = 0,15, A = 0,60 trên max `prob_attack` của các mô-đun mặt dùng được.
4. Duyệt PR EVAL-01 khi có (subagent `reviewer`):
   - ECE/Brier phải import từ `vericlue_ml.common.calibration`;
   - không dùng `calib_ltt` hay test để chọn gì;
   - làm đúng các quy ước đã chốt ở mục "Đang dở".
5. **PR #5 (EVAL-01): đạt sau khi sửa.** Phải sửa: BPCER@APCER 5% "mô tả" so sánh số thực `fnr == target` → sai khi số tấn công chia hết cho 20 (đã tự tái hiện: 0,3 thay vì 0,0). Đã gửi prompt sửa cho Codex. Trưởng nhóm chấp nhận tách tiêu chí "R1–R4 sinh bằng khung này" sang FACE-01/VOICE-01/task sinh R4. Việc của trưởng nhóm: thêm tiêu chí "sinh bằng `vericlue_ml.eval.report`" vào thẻ task sinh R4 nếu thẻ đó chưa có.
6. Sau EVAL-01, giao **DATA-02** (script tải mô hình, 0,5 ngày) cho Codex; DATA-01 cần người hoặc phiên thứ ba. Cả hai cần cho M0 (17/10).

## Quyết định, lưu ý, bẫy
- **Luật subagent** (đã ghi vào `docs/ai/working-with-ai.md` trên nhánh này):
  - mỗi task một phiên chính, chỉ phiên chính commit hoặc push;
  - subagent dùng để đọc, tra cứu, chạy test, duyệt, hoặc viết ở file riêng;
  - hai subagent không sửa cùng file;
  - nên duyệt chéo: PR của Codex do Claude duyệt, và ngược lại.
- **Chỉ số "trước hiệu chỉnh"** (`baseline: clipped_raw_score` trong calibrator) chỉ có nghĩa khi điểm thô nằm trong [0,1]. Nếu mô hình trả logit (AntiDeepfake có thể như vậy), không đưa con số này vào báo cáo.
- **Worktree để ngang hàng** với `Data4Life`, không lồng vào trong (tránh pytest/ruff/tìm kiếm quét trùng, tránh `git add .` nhầm). Người dùng đã hỏi và đồng ý.
- **Người dùng không chuyên.** Giải thích đơn giản, ít thuật ngữ, có bảng hoặc sơ đồ. Họ hay không thấy code do code nằm ở worktree khác hoặc chưa kéo `main`.
- **Bẫy:**
  - ~~`--help` lỗi `UnicodeEncodeError` trên console cp1252~~ — đã sửa ở nhánh `docs/LEAD-lead-playbook` (cả `new_handoff.py` và `plan_check.py`). Trước khi PR gộp, vẫn cần `PYTHONIOENCODING=utf-8`.
  - Hook pre-commit dùng chung trỏ tới `.venv` của `Data4Life`. Không xóa `.venv` đó.

## Câu hỏi cho nhóm
- Vẫn còn Q1–Q7 trong `STATUS.md`: sản phẩm BTC yêu cầu nộp, tên và vai trò thành viên, kênh liên lạc, máy demo và máy red-team, rà lại Scholar. Cần bật bảo vệ nhánh và mời thành viên (PLAT-07).

## Test đã chạy
```
uv sync --all-packages                         → OK
uv run pytest -q -p no:warnings                → 155 test: 153 đạt, 2 bỏ qua, 0 lỗi (main c067609)
uv run python scripts/plan_check.py            → 0 lỗi, 0 cảnh báo
```
