# Chuẩn bị dữ liệu giọng trên Colab — VOICE-09/APP-01

Tiếp tục phạm vi người dùng đã giao; nhánh/worktree hiện có được giữ nguyên.
Không push/PR, không sửa thresholds/contracts/ADR/STATUS, không dùng VIVOS để fit.

## Kết quả cần có

Job chuẩn bị lớp thật từ publisher DNU-ViSpeech đã ghim revision. Chạy trên
Colab CPU đang có phiên đăng nhập, không tạo tài khoản/khóa hoặc chấp thuận
điều khoản thay người dùng. Không tự sinh clone khi quyền đó chưa xác nhận.
Bundle giữ source/license, manifest theo người/nguồn, hash và kết quả kiểm PCM.
Thiếu giọng tấn công phải báo chưa sẵn sàng fit, không sinh calibrator tạm.

## Thực hiện

1. **Chuẩn bị và test downloader độc lập:** thêm
   `scripts/prepare_nes2net_data.py`, chỉ stdlib, DNU revision cố định. Chọn
   metadata accepted/passed mono16k 1–30giây theo hash seed42, giới hạn theo người;
   train→calib_fit, validation→calib_ltt, test→test_only. Không đọc điểm mô hình.
   Kiểm path/hash/subject split/byte và PCM trùng; giữ mọi lỗi, không ghi đè file.
   Viết test trước trong `scripts/tests/test_prepare_nes2net_data.py`: chọn mẫu
   lặp lại, leakage, metadata xấu, đổi bytes, WAV sai định dạng, duplicate PCM,
   output/resume an toàn và không tự đánh dấu calibration_ready.
2. **Đóng gói và chạy Colab:** tạo notebook từ script đã test, nhúng source/hash/
   commit và cấu hình vào cell, lưu notebook private. Dùng CPU, không Drive mount,
   không credential/token hoặc media cá nhân. Chạy job thật; xác minh output,
   tải bundle chuẩn bị về laptop nếu thành công. Không gọi bản chạy smoke là data fit.
3. **Xử lý lớp giả và tích hợp:** rà nguồn fake đã công bố có license/reference
   identities; giữ nguồn gated nếu chưa được cấp quyền. Sau khi có dữ liệu đủ
   hai lớp và nhóm: prepare→collect→fit theo protocol riêng; chưa đủ thì ghi đúng
   blocker và tiếp tục code/kiểm tra độc lập. Không mở chốt hoặc nâng degraded.

## Xác minh và bàn giao

Chạy test mới RED→GREEN, lint/format, regression phù hợp và plan_check. Review
thay đổi trước commit. Ghi commit, cấu hình, số mẫu chạy thật và hash bundle;
không commit audio/metadata dataset/trọng số/khóa. Cập nhật task/bàn giao bằng
bằng chứng đã chạy. Ba luồng vật lý vẫn chờ người dùng trực tiếp thử.
