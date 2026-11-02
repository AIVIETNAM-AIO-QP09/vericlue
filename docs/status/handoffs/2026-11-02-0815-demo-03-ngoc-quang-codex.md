# Bàn giao · DEMO-03 · Ngoc Quang+Codex · 2026-11-02 08:15

**Nhánh:** `codex/DEMO-03-model-paper-evidence`, base `06c9a7f` của DraftPR126.
**Trạng thái task sau phiên này:** phần tổng hợp literature đã hoàn tất; DEMO-03
vẫn `todo` vì báo cáo cuối và các phụ thuộc thực nghiệm chưa hoàn thành.

## Đã xong
- Đã rà GitHub remote main `7fc2ce9`: có nghiên cứu18/10 về server/on-device,
  bảng GenD/LVFace/AntiDeepfake/Arena và các paper/repo nguồn. Tài khoản đưa lên
  là `AIVIETNAM-AIO-QP09`, commit `baa2034`; không khẳng định danh tính người
  bạn nếu chưa có mapping tài khoản. Phần manual demo mới còn ở DraftPR126.
- Tạo [bảng số liệu để trích báo cáo](../../research/2026-11-02-model-paper-evidence.md):
  paper, version, trang/bảng/hàng/cột, đúng biến thể, dataset/giao thức và
  giới hạn ánh xạ checkpoint. Có đoạn đưa vào mục cơ sở lựa chọn mô hình.
- Bao phủ FS-VFM-L, GenD CLIP-L/14, LVFace-B, AntiDeepfake MMS300M,
  Qwen0.6B, StableSyncNet; tách NES2Net diagnostic/Arena. Thêm SCRFD,
  FaceMeshV2/Face Landmarker, CTC aligner, MLKit và phần luật không có metric
  tương ứng. Không gán mô hình legacy cho gói Android mới.
- Chỉ rõ GenDTable2 khác kết quả mean5seedsTable4; Anti paper32,80/card32,84;
  Qwen0.6B khác1.7B; NESsingle khác gộpcheckpoint; SCRFD KPS khácnonKPS;
  MediaPipeIOD-MAE không phải accuracy liveness. Không lấy số tốt nhất của
  biến thể khác cho weights local.
- Review sub-agent phần mặt, giọng và review độc lập toàn báo cáo đều PASS,
  không có lỗi Important được xác định. Đã bổ sung khác tiền xử lý Anti/NES
  theo góp ý và kiểm trực quan một số bảng PDF, đối chiếu nguồn chính thức.
- Cập nhật mục lục và chú thích vào hai tài liệu18/10, giữ nguyên nội dung
  lịch sử; task card/backlog chỉ ghi phần chuẩn bị, không đánh dấu xong báo cáo.

## Đang dở
- Chưa có báo cáo R1–R6/R7 hoàn chỉnh và chưa nghiệm thu ba luồng điện thoại
  của gói mới. Số paper không lấp các ô số thực nghiệm còn trống.
- Một số ánh xạ exact weights→benchmark chưa chứng minh: FS-VFM là mean5runs
  nhưng giữrun0; QwenHF-native ra sau paper; SyncNet bản phát hành/crop/offset;
  SCRFDhash chưa nối chính xác hàngKPS. Báo cáo đã ghi rõ, không ép thành khớp.

## Bước tiếp theo
1. Dùng phần đầu file nghiên cứu mới trong mục “Cơ sở lựa chọn mô hình và
   kết quả công bố” của báo cáo; giữ dataset/giao thức/đơn vị và link nguồn.
2. Mục “Kết quả thực nghiệm VeriClue” chỉ điền từ report code/eval của nhóm,
   đủ source/model/n/split. Tiếp tục checklist điện thoại và chuẩn bị dữ liệu
   có quyền sử dụng, chia theo người/nguồn trước fit/LTT/test.
3. Nhóm ghép báo cáo cuối qua DEMO-03 khi đủ đầu ra; file proposal/ADR/STATUS
   không bị sửa trong phiên literature này. DraftPR riêng cho tài liệu, không merge main.

## Quyết định, lưu ý, bẫy
- Chỉ đọc paper/PDF/model card/README chính thức cho số liệu; ghi rõ đánh giá
  độc lập Arena so với paper gốc. PDF tải tạm ngoài repo, không commit.
- Code/runtime/model/data/ngưỡng và gói `phone-demo-2026-11-02` không thay đổi.
  Không chạy server/model, không fit hoặc đổi trạng thái degraded/error.
- Không chuyển số literature thành số hiệu suất VeriClue, không dùng số paper
  làm ngưỡng và không đưa VIVOS parity vào hiệu chỉnh.

## Câu hỏi cho nhóm
- Báo cáo cuối cần giữ ranh giới số tác giả và số nhóm đo; các số accuracy/
  FAR/FRR/APCER/BPCER/LTT chưa đo không được suy từ paper hoặc smoke.

## Test đã chạy
- Đối chiếu primary-source PDF/HTML và checkpoint model card; review ba phần
  độc lập về số, metric, table/page, variant và nguồn GitHub đều PASS.
- `plan_check.py`: **0 lỗi,10 cảnh báo** tải/đường găng có sẵn.
- `git diff --check`: sạch. Kiểm Markdown link cục bộ và protected paths trước commit.
- Chỉ thay tài liệu, không chạy lại test model/app hoặc benchmark vì không
  thay code; không ghi các số test của phiên trước thành phép đo nghiên cứu mới.
