# Bàn giao · LEAD · Lead+Claude · 2026-10-17 21:58

**Nhánh:** `docs/LEAD-decisions-1017` (phiên điều phối, chỉ sửa tài liệu)
**Trạng thái task sau phiên này:** doing — điều phối liên tục. **Phiên mới: gõ `/lead`, đọc file này trước.**

## Đã xong
- Gộp PR #20 (DATA-03 âm thanh), #22 (bàn giao 16/10), #23 (dọn ROUT-02), #24 (Zalo tải nguyên ZIP + test ZIP độc hại). Không còn PR mở. `main` = `4a5bf03`.
- Dữ liệu: **11/13 bộ** trong `D:\Projects\vericlue-store\data` (21,9 GB). Âm thanh đã chia tập (`data/splits/`, quota đủ: fit 116 thật/103 giả, LTT 80 replay/60 TTS, 0 rò rỉ — trưởng nhóm tự kiểm bằng script đọc CSV).
- Mô hình: 9/11 trong `D:\Projects\vericlue-store\models` (8,1 GB). Chỉ **PhoWhisper** đã cắm vào hệ thống (`registry._REAL_FACTORIES`); MiniFASNet, SCRFD, GenD, AntiDeepfake, AudioSeal… chưa có phần bọc.
- Duyệt kế hoạch DATA-03 ảnh (xem "Quyết định").
- Nhánh này: ghi quyết định 17/10 vào thẻ PRES-01, PRES-04, CAP-03, CAP-04, FACE-04, VOICE-03, VOICE-05, DATA-04; backlog CAP-03 → done, PRES-01 → done (quyết định hạ cấp); STATUS 17/10.
- Demo chạy được trên máy người dùng: API (`uvicorn`, người dùng tự bật) + DB (`data4life-db-1`) + web `npm run dev` (phiên này bật nền). `/verify?scenario=…` đi được 4 nhánh với AI giả lập; `/review`, `/forensic` chỉ là trang trống.

## Đang dở
- **DATA-03 phần ảnh** — Codex `vericlue-data`, nhánh `feat/DATA-03-image-splits`: kế hoạch đã duyệt, chờ PR. Khi duyệt PR kiểm: Zalo gộp bằng ArcFace với **ngưỡng lỏng** + union-find, không rà tay, có báo phân bố kích thước component, siết nếu component > ~30%; không lưu embedding lâu dài; subject_id để trống; liên kết Zalo↔FAS buộc về test; FAS-VN/RTFS-10k/WildDeepfake test-only; 16 file FAS mâu thuẫn bị cách ly; ViCocktail ∪ vn_celeb thành nhóm nguồn cho DATA-04; ArcFace được ghim trong manifest (nghiên cứu phi thương mại).
- **Lượt nghiệm thu DATA-01**: người dùng chạy `download_data.py --subset small` (không `--only`, có HF_TOKEN + KAGGLE_*) trên `main` mới nhất; mong đợi 11 complete, 2 skipped, gần như không tải thêm → DATA-01 done (Codex đổi dòng backlog + đánh dấu thẻ).
- PR tài liệu của nhánh này: chưa commit (chờ người dùng đồng ý).

## Bước tiếp theo
1. Commit + PR nhánh `docs/LEAD-decisions-1017` khi người dùng đồng ý.
2. Duyệt PR DATA-03 ảnh bằng `reviewer` (theo các điểm ở "Đang dở"), tự kiểm CSV bằng script đọc (mẫu: kiểm subject/source/reference không ở 2 tập, đường dẫn tương đối, quota).
3. Người dùng họp nhóm → nhận tên M1–M5 → điền `team.md`, `CODEOWNERS`, cột Người trong backlog → soạn tin nhắn nhận việc cho từng người (đọc gì, task đầu, prompt có bước subagent). Bảng việc S1 theo ngày đã soạn trong chat 17/10, tóm tắt:
   - M1: đo ≥ 15 fps CAP-02 trên Android → CAP-05 → CAP-06 (CAP-04 hạ ưu tiên).
   - M2: hỏi BTC (Q1) + xin 4 bộ dữ liệu → REDT-01 → DATA-04 (≥ 200 video ghép mặt + ≥ 100 lip-sync, chỉ người nổi tiếng công khai) → REV-02 → PLAT-07.
   - M3: duyệt DATA-03 ảnh → FACE-01 (R1 gốc) → FACE-02 (R2 gốc).
   - M4: VOICE-01 (R3 gốc, làm ngay) → DATA-05 → VOICE-02 → chạy thử VOICE-03 trên máy.
   - M5: tiếp nhận ROUT-02 → PLAT-06 (chuyển từ M2 để cân tải) → chủ trì tích hợp 21/10 → notebook mẫu Kaggle.
4. Người dùng đã hỏi có muốn để AI cắm sẵn MiniFASNet (FACE-01) để demo có AI thật — **chưa trả lời**. Nếu đồng ý: giao một phiên AI rảnh làm phần bọc FACE-01 (chưa cần dữ liệu đã chia).
5. Tắt demo khi người dùng yêu cầu: web dev server (nền của phiên cũ có thể đã dừng khi phiên kết thúc), `docker compose down`, đóng cửa sổ uvicorn.

## Quyết định, lưu ý, bẫy
- **17/10: không thu dữ liệu thiết bị/người thật nữa** (người dùng quá tải). ChromaPulse = tín hiệu phụ, không tuyên bố hiệu quả trong báo cáo. Không dùng mặt/giọng thành viên.
- **Nguyên tắc gộp nhóm danh tính:** gộp nhầm khác người = vô hại; bỏ sót cùng người = rò rỉ → luôn thiên về gộp.
- **Bộ có bằng chứng chung nguồn người → cùng tập; bộ độc lập → chia trong bộ, ghi là giả định.**
- Máy người dùng: RTX 4050 Laptop 6 GB, 16 GB RAM — đủ suy luận cả bộ não và tinh chỉnh PAD; AntiDeepfake tinh chỉnh phải lên Kaggle. Có thể là máy demo (chờ chốt Q5).
- Người dùng không chuyên: trả lời tiếng Việt đơn giản, có bảng, nói rõ "bạn cần làm gì tiếp". Gọi các phiên theo thư mục: Claude `vericlue-claude`, Codex `vericlue-codex`, Codex `vericlue-data`. Người dùng mở cả 3 phiên từ thư mục `Data4Life` — prompt luôn ghi rõ worktree, kiểm `pwd` + nhánh trước commit.
- `python -I` bỏ qua `PYTHONIOENCODING`: dùng `python -I -X utf8` khi script in tiếng Việt.
- Lệnh `du`/đếm file trong `vericlue-store` chậm (> 2 phút): chạy nền.

## Câu hỏi cho nhóm
- Q4 (tên M1–M5), Q5 (máy demo GPU, máy red-team), Q7 (kênh liên lạc) — chốt trong buổi họp.
- Q8–Q11 trong STATUS (giấy phép proposal, màn đồng ý, giữ media giám định, mã lý do).
- Có muốn tải bản lớn hơn của ViMD/VSASV trước khi chốt R3 không (ổ D: còn ~100 GB)?

## Test đã chạy
```
uv run python scripts/plan_check.py → 0 lỗi, 0 cảnh báo (nhánh docs/LEAD-decisions-1017)
Script đọc CSV splits (scratchpad/audit_splits.py) → 0 rò rỉ, 0 đường dẫn tuyệt đối, quota đủ
curl /verify, /verify?scenario={low_quality,voice_clone,print}, /lab/chromapulse → 200; POST /v1/sessions → 200
```
