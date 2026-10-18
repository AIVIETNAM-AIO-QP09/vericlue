# Bàn giao · LEAD · Lead+Claude · 2026-10-18 18:52

**Nhánh:** `docs/LEAD-ekyc-flows` (phiên điều phối, chỉ sửa tài liệu). Tất cả thay đổi trên nhánh này **CHƯA commit**: chờ người dùng nói "ok commit".
**Trạng thái task sau phiên:** doing — điều phối liên tục. Phiên mới: gõ `/lead`, đọc file này trước.

## Đã xong
- **MVP chạy toàn đồ thật:** ADR-0012, hồ sơ `ROUTER_PROFILE=mvp`. Các PR đã gộp:

  | PR | Nội dung |
  |---|---|
  | #25, #30, #34 | Tài liệu, ADR-0012 |
  | #26 | MiniFASNet, chế độ mixed |
  | #27 | AntiDeepfake |
  | #28 | Router MVP, calibrator identity |
  | #29 | Web gửi media thật, CamProbe |
  | #31 | GenD, chất lượng ảnh, extra `cuda` |
  | #32 | Lipsync và aligner; lipsync chỉ tham khảo |
  | #33 | Giám định theo đoạn, AudioSeal, C2PA `[contract]` |
  | #35 | `LIPSYNC_DEVICE` |
  | #36 | Sửa lỗi PhoWhisper lặp token |

  `main` = `aa18843`.
- **Trưởng nhóm tự đi hết luồng trên `main`** (DEVICE=cuda, RTX 4050):
  - VRAM 3,5–4,4 GB. Bước mặt 0,9–2,2 giây. Bước giọng 1–1,7 giây.
  - **Lỗi thật:** AntiDeepfake chưa tinh chỉnh chấm cùng một giọng mms-tts-vie ra 0,84 / 0,38 / **0,115**. Mức 0,115 cho kết quả **pass**, tức giọng AI lọt. Không hạ ngưỡng tay; VOICE-03 sẽ sửa.
  - GenD chấm người thật 0,14–0,25, vượt B = 0,15, nên hầu hết phiên phải đọc câu. Đây là thử tay, không phải số R.
- **Tài liệu trên nhánh này (chưa commit):**
  - **ADR-0013:** 3 luồng (đăng ký, đăng nhập lại, khôi phục), 6 câu hỏi, 8 nguyên tắc, quay đầu, riêng tư và bảo mật (A3, A4, A5, A6, B4, B6), 4 ý học từ repo eKYC-system.
  - **ADR-0014:** demo bằng app Android, thay ADR-0003 cho luồng người dân; ADR-0003 đã đánh dấu "thay một phần".
  - **ADR-0015:** chọn mô hình (giữ GenD, AntiDeepfake, PhoWhisper, SyncNet, AudioSeal, SCRFD; thêm AdaFace và DINOv2); tinh chỉnh trên Colab/Kaggle; không thu dữ liệu tay.
  - **Epic E9** (FLOW-01…05, SEC-01, SEC-02, APP-01) và **DATA-06**; VOICE-03 phụ thuộc DATA-06; ghi chú vào thẻ FACE-04 và VOICE-03.
  - `plan_check`: 0 lỗi, 4 cảnh báo quá tải (M1, M2, M3 ở S1), đúng như dự kiến vì các phiên AI làm song song.
- **Hai báo cáo tra cứu** (có nguồn, gắn nhãn [XM]/[SĐ]) nằm ở scratchpad của phiên. **Nên chép vào `docs/research/` khi commit:**
  - `C:\Users\aqdev\AppData\Local\Temp\claude\d--Projects-Data4Life\691c4873-d6f8-4b9a-a482-f3728a8f0aba\scratchpad\research-sota-server.md`
  - `C:\Users\aqdev\AppData\Local\Temp\claude\d--Projects-Data4Life\691c4873-d6f8-4b9a-a482-f3728a8f0aba\scratchpad\research-on-device.md`

## Đang dở
- **Hệ thống demo trên máy người dùng:**
  - API `:8000` chạy từ `D:\Projects\Data4Life`, nhánh main, với `ROUTER_PROFILE=mvp USE_MOCK_MODELS=false DEVICE=cuda LIPSYNC_DEVICE=cpu MODELS_DIR=D:/Projects/vericlue-store/models`; venv đã `uv sync --all-packages --extra cuda`.
  - Web `npm run dev` ở `:3000`.
  - DB `data4life-db-1`.
  - Các script thử nằm trong scratchpad: `e2e_mvp.py`, `e2e_voice.py`, `xem_ket_qua.py` (xem module chấm gì qua DB).
  - Phiên khởi động lại thì các tiến trình nền này tắt.
- **P3 (`vericlue-data`, DATA-03 ảnh):** WildDeepfake đã chia (calib_fit 1.620 / calib_ltt 1.773 / test 11.834). **Zalo 2022 chưa chia.** Chưa có PR.
- **Máy chưa có FFmpeg**, nên giám định không đọc được tiếng trong video. Người dùng cần chạy `winget install --id Gyan.FFmpeg -e`.

## Bước tiếp theo
1. Người dùng trả lời "ok commit" → commit và mở PR cho nhánh này. Chép kèm 2 báo cáo tra cứu vào `docs/research/`.
2. **Chờ người dùng chốt:**
   - (a) cách làm app: bọc web bằng Capacitor (đề xuất) hay Kotlin native;
   - (b) mặc định của luồng đăng nhập lại: nghi thì chặn và cảnh báo; câu đọc có số tiền; hạn mức 24 giờ chỉ ghi trong báo cáo.
3. Soạn prompt cho các phiên AI làm từ 19/10. Prompt luôn có phần subagent.
   - **Nhóm luồng/app:** FLOW-01, FLOW-03, FLOW-04, FLOW-05, SEC-01, APP-01. FLOW-01 làm trước vì đổi hợp đồng.
   - **Nhóm dữ liệu/tinh chỉnh:** DATA-06, DATA-04 (script tạo deepfake theo lô, chỉ người nổi tiếng công khai, chạy trên máy người dùng), VOICE-02, notebook Kaggle cho VOICE-03; thêm DINOv2 và AdaFace vào manifest.
   - Người dùng đã đồng ý: tải ViMD bản lớn, script tự sinh dữ liệu, thêm AdaFace và DINOv2, tinh chỉnh trên Colab/Kaggle. **Cần hỏi ai có tài khoản Kaggle.**
4. Cập nhật `STATUS.md` (ngày 18/10, sprint S1, còn 19 ngày): ghi MVP xong, các quyết định ADR-0012 đến 0015, rủi ro giọng AI lọt.

## Quyết định, lưu ý, bẫy
- Người dùng đánh giá tiến độ theo việc **người thật có dùng được từ đầu tới cuối không** (memory `usable-end-to-end-first`). Trước khi báo "xong", tự đi hết luồng.
- Trưởng nhóm **không tự hạ ngưỡng** để che lỗi mô hình. Ngưỡng chỉ chọn bằng dữ liệu (ROUT-03).
- Có 4 phiên AI chạy cùng lúc nên RAM 16 GB rất căng. Hai API chạy song song đã gây lỗi cấp phát bộ nhớ. Thử nghiệm của các phiên AI dùng cổng 8200, không đụng `:8000`.
- Gộp nhiều PR cùng sửa `registry.py` thì kiểm `git merge-tree` trước khi bảo người dùng bấm Merge.
- Thư mục `D:\Projects\vericlue-demo` đã xóa. Calibrator tạm trong scratchpad không còn dùng.
- Các worktree hiện có:

  | Thư mục | Nhánh |
  |---|---|
  | `vericlue-claude` | FACE-02, đã gộp |
  | `vericlue-codex` | VOICE-04 fix, đã gộp |
  | `vericlue-data` | DATA-03 ảnh |
  | `vericlue-lab` | FOR-01, đã gộp |

  Giao task mới thì cho phiên `git switch -c … origin/main`.

## Câu hỏi cho nhóm
- Cách làm app (Capacitor hay Kotlin); nhóm SW có ai biết Kotlin?
- Ai có tài khoản Kaggle?
- Mặc định của luồng đăng nhập lại (xem Bước tiếp theo 2b).
- Proposal cần sửa vì đổi từ web sang app (ADR-0014). Theo AGENTS §6 luật 7, việc này cần task riêng.
- Kiểm lại giấy phép PhoWhisper: manifest ghi BSD-3, một nguồn ghi Apache-2.0.

## Test đã chạy
```
uv run python scripts/plan_check.py → 0 lỗi, 4 cảnh báo (quá tải M1/M2/M3 ở S1)
e2e_mvp.py trên main aa18843 (4 mẫu Zalo) → voice_challenge, 0,9–2,2 s; VRAM 3,5–4,4 GB
e2e_voice.py ×2 (giọng mms-tts-vie) → review (0,383) và PASS (0,115) — giọng AI lọt, chờ VOICE-03
```
