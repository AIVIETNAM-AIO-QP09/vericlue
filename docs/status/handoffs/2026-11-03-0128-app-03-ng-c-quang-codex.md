# Bàn giao · APP-03 · Ngọc Quang+Codex · 2026-11-03 01:28

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** `doing` — chưa nghiệm thu khôi phục thật.

## Đã xong
- Android: sửa FIT preview, giới hạn chờ phản hồi AI riêng và kiểm phản hồi trước
  giải phóng bản thu; APK `03b4abc03b43b1dbc511423f610ac37596f09287` đã build.
  Chi tiết RED/GREEN và lượt S24 FE nằm trong bàn giao `2026-11-03-0001`.
- Thêm `eval.dnu_asr_fit` và hướng dẫn cùng thư mục: 18 WAV/18 người calib_fit
  được khóa bằng protocol trước suy luận, chọn cố định theo hash ID. Kiểm
  crosswalk đủ 360 mẫu fit, nhãn train, checksum, revision, giấy phép/approval.
- Giữ toàn bộ lỗi trong mẫu số 18, WER thiếu là null; báo nguồn/config/model/
  runtime và thời gian nạp. Không transcript, ID người hay đường dẫn media
  trong báo cáo. Nhãn chỉ tới matcher/bộ đếm âm tiết, không đưa vào ASR context.
- PhoWhisper tải riêng theo manifest đã pin và kiểm hash; runtime riêng
  Transformers 4.57.6 đã chuẩn bị. Qwen dùng runtime 5.13.0 có sẵn. Chưa đổi API.

## Đang dở
- Chưa có số đo suy luận của phép so sánh này tại thời điểm commit adapter.
- Nhận dạng câu/khớp môi đã không đạt trên lượt thật trước. Không suy ra đạt
  từ kiểm thử tự động hoặc việc tải đủ mô hình.

## Bước tiếp theo
1. Xác nhận cài APK, giữ tài khoản/khóa/cấu hình. Người dùng đã đi ngủ, không
   tự mở camera hay tự đánh dấu nghiệm thu.
2. Chạy hai candidate tuần tự theo `ml/src/vericlue_ml/eval/DNU_ASR_FIT.md`,
   dùng output mới trong vùng riêng; ghi đầy đủ lỗi và giới hạn 18 mẫu.
3. Tiếp tục kiểm chứng frontend SyncNet bằng artifact nguồn hợp lệ và phép
   biến đổi độc lập; không chọn crop/ngưỡng theo điểm bản ghi điện thoại.

## Quyết định, lưu ý, bẫy
- Người dùng đã cho phép làm tiếp trong đêm và tắt máy sau khi kết thúc; lưu
  đầy đủ bàn giao trước khi tắt. Không force đóng tài liệu chưa lưu.
- OTP mô phỏng và ngưỡng demo tạm giữ nguyên. Error/degraded không thành pass.
- Không dùng điện thoại nghiệm thu, 32 VIVOS parity, calib_ltt hoặc test để
  chọn mô hình/ngưỡng. DNU fit chỉ là chẩn đoán nội dung, không phải đánh giá
  spoof, lipsync, LTT hay mức độ hoàn thiện xác thực.

## Câu hỏi cho nhóm
- Còn cần nghiệm thu người thật và dữ liệu/artifact đúng phiên bản để đánh
  giá ngoài phép chẩn đoán fit. Không lấy số paper thay số hệ thống chạy thật.

## Test đã chạy
- Root chạy `pytest ml/tests/test_dnu_asr_fit.py ml/tests/test_eval_voice_challenge.py`:
  42 ca đạt. Agent có RED khi module chưa tồn tại và review độc lập không còn
  blocker; riêng adapter 13 ca đạt. Ruff check + format check sạch.
- Protocol thật `--check-only`: 18 mẫu/18 người, `inference_performed=false`.
- Android mới nhất: 441 ca, 0 failure, 0 error, 1 export skip; lint 0 lỗi,
  44 cảnh báo/5 thông tin; hai APK build đạt. Plan check 0 lỗi/10 cảnh báo.
