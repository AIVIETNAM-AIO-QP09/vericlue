# Bàn giao · LEAD-DOCS · Claude (phiên điều phối) · 2026-10-14

**Nhánh:** docs/LEAD-calib-split-session-token
**Trạng thái:** PR tài liệu, chờ duyệt

## Đã xong
- **ADR-0010:** tách `calib` thành `calib_fit` / `calib_ltt` theo người; calibrator lưu ở `ml/configs/calibrators/`.
- **ADR-0011:** token theo phiên, mỗi bước nhận một lần (409), thử thách sống 120 giây, nhịp nháy màu ≥ 550 ms/bước.
- Sửa cho khớp:
  - thẻ DATA-03, FACE-01/04, VOICE-03, ROUT-02…05, PLAT-06;
  - proposal §2.7(a), §2.7(c), §2.7(d), Phụ lục A;
  - `architecture.md` §2, §4;
  - glossary, ADR-0006 (trạng thái), STATUS.
- Giải quyết các câu hỏi trong bàn giao PLAT-02 (token) và ROUT-01 (cách chia calib).

## Đang dở
- Không sửa thẻ ROUT-01 (phiên Codex đang sửa đường dẫn calibrator và chữ "tập calib" → `calib_fit` trong PR của nó).
- Không sửa `session.schema.json` (phiên Claude sửa trong PLAT-04, có `[contract]`).

## Bước tiếp theo
1. Gộp PR này. Phiên Claude (PLAT-04) và Codex (ROUT-01) chạy `git fetch && git merge origin/main` trước khi mở PR của mình.
2. PLAT-04 làm theo ADR-0011. ROUT-01 lưu calibrator theo ADR-0010.

## Quyết định, lưu ý, bẫy
- Nếu thẻ ROUT-01 xung đột khi gộp: giữ bản của phiên Codex, chỉ đảm bảo đường dẫn là `ml/configs/calibrators/` và tập là `calib_fit`.

## Câu hỏi cho nhóm
- Không.

## Test đã chạy
```
uv run python scripts/plan_check.py → 0 lỗi, 0 cảnh báo
```
