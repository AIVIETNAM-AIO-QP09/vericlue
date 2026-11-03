# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-02 21:16

**Nhánh:** codex/APP-03-micro-capture-diagnostic, Draft PR134.
**Trạng thái task sau phiên này:** doing, khôi phục chưa được nghiệm thu.

## Đã xong
- Đối chiếu đúng recovery mới sau mốc triển khai v3, không lấy kết quả phiên v2 cũ. Người dùng báo “chưa hoàn tất xác minh”; API đã kết thúc xử lý ở `review`.
- Bản đọc đầu và bản đọc lại đều đến mô hình. Mọi chốt mặt/quay đầu đạt; voice spoof và face continuity đạt. `voice_challenge` trả `ok/fail`, `E_CHALLENGE_MISMATCH`; lipsync trả `ok/fail`. Không phải timeout hoặc model không nạp.
- Xác nhận tài khoản còn nguyên và chưa commit liên kết khôi phục. `completed` trong payload chỉ là đã xử lý xong, không có nghĩa quyết định `pass`.
- Đối chiếu câu server chấm, trạng thái cấp câu đọc lại và code Android cập nhật `voicePrompt`; chưa có bằng chứng gửi lại bản cũ hay đọc lại câu cũ. Kết quả nhận dạng khác cả từ lẫn dấu; không được suy ra người dùng nói sai từ riêng kết quả ASR.
- Kiểm tra độc lập bản WAV/container của lần đọc lại: PCM16 mono16k hợp lệ, có tín hiệu, không clipping; video PTS tăng và mốc đầu có dấu khớp metadata. So waveform theo presentation-time với decoder độc lập lưu riêng; không dùng confidence/offset tối ưu của SyncNet để căn media.
- Cập nhật README/task/backlog/result để bỏ trạng thái “chờ lượt thử đầu trên v3”. Không đổi production code, model, ngưỡng hoặc API đang chạy trong lượt kiểm tra này.

## Đang dở
- Chưa xác định nguyên nhân gốc của hai chốt nhận dạng câu/lipsync. Phân biệt lỗi mô hình/tiền xử lý, chất lượng capture và hành vi đọc cần bằng chứng riêng; không gọi đây là lỗi micro hay coi thiếu calibration là nguyên nhân đã chứng minh.
- Toàn luồng khôi phục vẫn chưa đạt. Sửa bộ đọc đã cho phép gửi giọng trong phiên mới, không chứng minh độ chính xác hoặc clock phần cứng.

## Bước tiếp theo
1. Dùng diagnostics của đúng phiên mới trong bundle riêng; kiểm tra từng giả thuyết trên dữ liệu đã có, không mời người dùng thử lại liên tiếp khi chưa có thay đổi có căn cứ.
2. Nếu tìm được lỗi code/tiền xử lý, tạo regression test rồi sửa nguyên nhân; không bỏ dấu, bỏ nonce, đổi prompt hoặc dịch A/V dựa trên kết quả mẫu này để được đạt.
3. Giữ Draft PR134; tiếp tục nghiệm thu recovery khi có candidate hoặc kế hoạch đo cụ thể. Dữ liệu hiệu chỉnh/eval có quyền dùng, chia theo người vẫn là việc riêng; không dùng VIVOS parity để fit.

## Quyết định, lưu ý, bẫy
- Code APK vẫn `8049d6bbccfb51e22e28e1f47739b3fcf250e305`, policy `muxed-av-pcm-v3-ptsgrid`, normalizer `pcm16-mono16k-pts-sinc-v2`; API frozen `d73dd773485c970aeae70f2f0c01c7fbede07ac2`. OTP mô phỏng/ngưỡng demo tạm không thay đổi.
- Không giữ transaction DB khi giải mã media; lease chỉ dùng cho kiểm tra cục bộ và đã release. Không commit media, transcript, câu thử thách/nonce, IDs, sample hashes hoặc điểm sinh trắc.
- Đối chiếu waveform nominal có thể khác do chính clock mapping; phải đối chiếu trên cùng timeline presentation. Không suy bug từ correlation nominal hoặc suy thành công xác minh từ similarity waveform.

## Câu hỏi cho nhóm
- Chưa đề nghị thay thiết kế/ngưỡng hoặc yêu cầu người dùng quay thêm ở lượt này. Chờ điều tra có căn cứ cho hai chốt còn lại; không ép phiên `review` thành đạt.

## Test đã chạy
- `inspect_current_attempt.py`: đọc DB chế độ chỉ đọc, projection trạng thái chốt đã đối chiếu; healthz `ok`, không module lỗi khởi động.
- Private `inspect_ptsgrid_attempt.py`: lịch sử nhận dạng/đọc lại của đúng phiên sau anchor, báo cáo chỉ hình dạng edit, không xuất transcript.
- Private `run_ptsgrid_media_check.py` + `check_ptsgrid_media.py`: WAV/container và tham chiếu giải mã độc lập; không chạy lại AI, không fit hoặc sửa quyết định. Số liệu chi tiết chỉ là diagnostics riêng, không là số liệu hiệu suất báo cáo.
- `gh pr checks 134`: các check hiện có trên head `114cc1a075f3e93daa978059632a5bbc04158ef2` đều success; đây là CI của code trước bổ sung tài liệu lượt này. Test Android đầy đủ trước đó ghi trong bàn giao 20:29, không chạy lại/không cộng thành số đo mới ở lượt này.
- Kiểm tra thay đổi tài liệu: `python scripts/plan_check.py` trả 0 lỗi, 10 cảnh báo kế hoạch có sẵn; JSON result hợp lệ và `git diff --check` sạch. Lần gọi ban đầu dùng nhầm tùy chọn `--check` không có trong CLI; đã chạy lại đúng lệnh không tham số và kiểm exit code.
