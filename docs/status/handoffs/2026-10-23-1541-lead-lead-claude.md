# Bàn giao · LEAD · Lead+Claude · 2026-10-23 15:41

**Nhánh:** `docs/LEAD-liveness-order` (chỉ tài liệu). **Phiên mới: gõ `/lead`, đọc file này trước.** Bàn giao LEAD trước đó: `2026-10-21-1449`.

## Đã xong (21/10 → 23/10)
- **Đã gộp:** PR #43 (STATUS 21/10), PR #44 (ADR-0016 Dynamic Liveness, task LIVE-01…05, ADR-0014 mục "Cập nhật 21/10").
- **PAD:** chạy `combine_pad.py` trên 2 zip Kaggle. `splits.csv` SHA `22b0d16f…0534a` khớp. Trên calib_fit (1.627 ảnh, 557 tấn công), APCER @ BPCER ≤ 1 %: MiniFASNet gốc 0,80 · MiniFASNet tinh chỉnh 0,42 · **DINOv2 tinh chỉnh 0,25** · gộp max 0,37. **Chọn một mình DINOv2.** Yếu với ảnh in, mặt nạ (Axon phụ, ít mẫu) và ảnh chụp tại quầy (nguồn A). Báo cáo: `vericlue-store/models/finetuned/pad/combine-20261021/`.
- **GenD hiệu chỉnh** (Kaggle, `SMOKE=False`, commit `42c4bfc`, zip SHA `07565b65…85ee`): isotonic, log-loss 0,463 → 0,401. AUC thô trên calib_fit: RTFS thật vs giả 0,82 (con số trung thực); FAS-VN vs RTFS 0,95 bị **lộ đề nguồn** (độ nét), không dùng. Ngưỡng tạm B = 0,15 thì khoảng 50 % người Việt thật phải đọc câu, khoảng 11 % vượt A.
- **Lỗi notebook GenD:** Kaggle có `transformers` 5.x, khóa state_dict CLIP đổi (bỏ tiền tố `vision_model.`). Chạy được nhờ thêm ô `!pip install -q "transformers>=4.57.1,<5"`. **Chưa sửa template notebook** (cần giao một phiên AI; kiểm cả notebook PAD).
- **Tải và cất mô hình** vào `D:\Projects\vericlue-store\models\`:
  - `finetuned/pad/` (DINOv2, MiniFASNet tinh chỉnh) và `finetuned/gend-calibration/20261021_1310/`;
  - `_pending/` (AdaFace IR101 WebFace4M, SFace, MediaPipe Face Landmarker), có `SOURCE.md` ghi nguồn ghim, SHA-256 và giấy phép. **Chưa vào `models/manifest.yaml`**: task tích hợp phải thêm.
- **Cài FFmpeg 9.0.2** (winget) trên laptop.
- **Thiết kế luồng người dùng mới**, có artifact:
  - hai cột song song: https://claude.ai/artifact/6DxJiDet7shzekmYqUJHLv (bản 23/10, 13 bước);
  - sơ đồ hệ thống: https://claude.ai/artifact/5vg1kBcsh1F99pUxZZJPxh (chưa đồng bộ với bản 23/10: vẫn ghi "ngân hàng", chưa có tải lên dần);
  - bản mẫu bấm thử: https://claude.ai/artifact/HrdSMVHbBjzdN7wQRwRtd4;
  - slide mentoring: https://claude.ai/artifact/NhS82abgkg1v9wPS5wLQGW.
- **Giai đoạn B gộp còn 2 việc** (~18 giây): (1) giữ đầu yên: nền xám chụp góc 1 → đổi màu → mắt theo chấm sáng; (2) quay trái, quay phải. Đọc câu chạy song song với chấm giai đoạn B. Ghi ở ADR-0016 mục "Cập nhật 22/10" và ghi chú trong ADR-0013.
- **ADR-0017** (mới): thông báo làm lại hai loại (chất lượng báo cụ thể, thử thách chỉ hướng dẫn); xử lý gián đoạn (giai đoạn A tự gia hạn, giai đoạn B/C làm lại riêng phần khuôn mặt, giới hạn tổng đề xuất 15 phút); tải media lên dần, ảnh tĩnh 3 góc, không nén mạnh; **ký số không chống chèn luồng camera**. ADR-0011 ghi "thay một phần".
- **Kế hoạch:** thêm LIVE-06 (gia hạn phiên, `[contract]`) và LIVE-07 (thông báo làm lại); thẻ LIVE-03 thêm tải lên dần và ký từng đoạn. `plan_check`: 0 lỗi.
- **`docs/pitch/y-nghia-tung-thanh-phan.md`:** vấn đề → làm gì → giá trị của từng bước, dùng cho báo cáo và hỏi đáp. Kịch bản mentoring đã xóa theo yêu cầu.
- **Đã trình bày mentoring (23/10).** Góp ý của mentor **chưa nhận**.

## Đang dở
1. Chưa có notebook tinh chỉnh AntiDeepfake. Đây là việc lớn nhất về mô hình; kế hoạch đã trình bày cho người dùng (nhân bản giọng thật, khử lộ đề, giữ công cụ chưa thấy làm tập kiểm). Common Voice cần người dùng đồng ý điều khoản.
2. Chưa gắn DINOv2, calibrator GenD, AdaFace, MediaPipe vào server.
3. Chưa chốt cách làm app. Người dùng đã có UI/UX trên Figma. Đề xuất: web app + bọc Capacitor. ADR-0014 vẫn ghi Kotlin.
4. Sơ đồ hệ thống chưa đồng bộ bản 23/10.

## Bước tiếp theo
1. Hỏi người dùng **góp ý của mentor**; gom vào STATUS (STATUS vẫn ghi ngày 21/10).
2. Chốt **web + Capacitor hay Kotlin**, rồi sửa ADR-0014.
3. Soạn prompt (có phần subagent):
   - **(a)** notebook AntiDeepfake;
   - **(b)** gắn DINOv2 + calibrator GenD + sửa pin `transformers<5` trong template notebook;
   - **(c)** AdaFace + MediaPipe (FLOW-05, LIVE-02);
   - **(d)** dựng giao diện theo Figma.
4. Duyệt UI Figma theo luật 3 và ADR-0017 khi người dùng gửi.

## Quyết định, lưu ý, bẫy
- **Phạm vi:** chỉ luồng người dùng; không làm thêm giám định hay tính năng phụ (memory `scope-citizen-flow-only`). Mọi bước phải nói **vấn đề trước, giá trị sau** (memory `problem-first-motivation`).
- **VeriClue dành cho "bên tích hợp"** (ngân hàng, ví, sàn, dịch vụ công), không riêng ngân hàng. VeriClue báo "xác minh thành công"; bên tích hợp mới báo "mở tài khoản thành công".
- **Không nói quá:** không có rPPG, không dựng 3D (chỉ kiểm thị sai), ZKP chỉ là giấy chứng nhận tùy chọn gửi bên tích hợp, không phải "không gửi video". Kháng lượng tử = PQC (ML-KEM, ML-DSA), không dùng máy lượng tử. Tên mô hình không nêu khi trình bày.
- **Sửa nguồn của người dùng:** dự báo "2026 deepfake tăng" là của NCA, không phải Bộ Công an; Thanh Hóa: hơn 2.000 tài khoản là tổng hai vụ, thủ đoạn chèn ảnh ở vụ 1; không nói "Telegram rao bán công khai".
- **Host:** 3 dịch vụ (web, API chứa toàn bộ mô hình, PostgreSQL) + đường hầm Cloudflare. Kaggle/Colab không dùng để host. Làm app thì cần **tên miền cố định** (đường hầm có tên). Thuê cloud GPU theo giờ quanh ngày chấm, ưu tiên trong nước.
- Ổ D còn khoảng 55 GB.

## Câu hỏi cho nhóm
- Góp ý mentor: vòng 2 chấm nặng phần nào? Bỏ giám định có ổn? Dữ liệu deepfake người Việt?
- Web + Capacitor hay Kotlin?
- Có cần hệ thống chạy 24/7 cho giám khảo tự thử không (quyết định thuê cloud)?
- Luật 91/2025 và quy định đặt máy chủ xử lý sinh trắc (Q17) vẫn chưa kiểm.

## Test đã chạy
```
uv run python scripts/plan_check.py → 0 lỗi, 9 cảnh báo (quá tải vai trò, chuỗi gần găng chưa ★)
combine_pad.py (2 zip Kaggle) → khuyến nghị DINOv2 một mình
sha256sum -c trên 3 gói Kaggle → OK
```
