# Chuẩn bị dữ liệu giọng toàn câu — 01/11/2026

Người giao việc xác nhận dữ liệu này **chưa từng được chuẩn bị**, không bị xóa
khi dọn dẹp. Chưa có bộ giọng thật + TTS/VC/crosswalk đủ điều kiện fit. Giữ chốt
thiếu artifact; không dùng VIVOS parity, unit hoặc lượt thử điện thoại thay thế.

## Nguồn đã đối chiếu publisher

| Nguồn ghim revision | Quyền/metadata quan sát | Việc cần tiếp |
|---|---|---|
| [DNU-ViSpeech](https://huggingface.co/datasets/TrangLe2108/DNU-ViSpeech/tree/33b2a469901cb71b243403254d3cfef25170526c) | CC-BY-NC4.0, speaker_id/checksum/split; có public-release approval của publisher, card ghi giới hạn consent/phạm vi | Bảo toàn người test gốc; chia calib_fit/calib_ltt theo người từ phần phát triển. Xác nhận riêng phạm vi nếu sinh clone/VC |
| [Speech-MASSIVE vi](https://huggingface.co/datasets/FBK-MT/Speech-MASSIVE/tree/ff792febc16187a21e5bca38fb02a55daf91dc05/vi-VN) | CC-BY-NC-SA4.0, speaker_id, mono16k; train_115/validation trên repo publisher | Kiểm người/nguồn xuyên phần và quyền biến đổi; test ở repo riêng có bước chấp thuận |

Chỉ tải card/license/biên bản/metadata để rà nguồn; chưa tải audio, tạo clone
hay fit. Metadata gốc/pin SHA tại
`D:/vericlue/data/diagnostics/nes2net-calibration-prep-2026-11-01/` ngoài Git.
Đã dựng `DNU-bonafide-proposed-manifest.json` từ metadata publisher, chọn bằng
hash seed42 trước inference và giữ người train/validation/test tương ứng
calib_fit/calib_ltt/test-only. Đây mới là manifest ứng viên lớp thật: chưa có
audio, chưa kiểm trùng PCM, thiếu lớp tấn công và quyền clone/VC chưa chốt.
Không chép code của bộ dữ liệu. Giấy phép dữ liệu không tự xác nhận tác giả
cho mọi ứng dụng định danh hoặc nhân bản giọng.

## Bundle cần chuẩn bị trên Kaggle/Colab

1. Lưu publisher/revision/license/quyền đúng tác vụ và mã nguồn âm thanh.
   Không trộn hai bộ khi chưa có crosswalk người/nguồn.
2. Chốt người/nhóm cho calib_fit/calib_ltt/test trước inference; giữ người test
   gốc, các bản gốc/clone/cắt/nén cùng nhóm. Chốt hệ TTS chỉ-test trước đo.
3. Cần cả thật và từng loại tấn công có quyền; giữ hệ/version/seed và
   reference/donor/target/parent audio. Thiếu một bên thì chưa fit.
4. Thật/giả qua cùng đường xử lý. Nếu resampling thì version hóa bước chuẩn bị,
   giữ hash gốc lẫn file đo, không âm thầm đổi protocol.
5. Xuất manifest theo [runbook](../runbooks/nes2net-utterance-calibration.md),
   chạy prepare kiểm trùng byte/PCM/người/nguồn và báo thiếu quota; không chuyển
   người test hoặc chọn mẫu bằng điểm NES2Net.

Chưa có accuracy/ngưỡng LTT hay nghiệm thu Android từ bước rà nguồn. Nhận/tải
audio hợp lệ, chuẩn bị tấn công và chạy hiệu chỉnh/đánh giá vẫn còn phải làm.
