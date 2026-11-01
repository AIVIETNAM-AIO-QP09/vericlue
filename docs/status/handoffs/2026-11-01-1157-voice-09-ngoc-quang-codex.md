# Bàn giao · VOICE-09/APP-01 · Ngoc Quang+Codex · 2026-11-01 11:57

**Nhánh:** codex/APP-01-demo-integration; nền194af1d.
**Phạm vi tiếp tục:** người dùng yêu cầu tự hoàn thành phần có thể tự động,
không chờ nghiệm thu điện thoại để dừng các việc dữ liệu độc lập.

## Đã xong ở checkpoint code
- Xác minh Colab đang đăng nhập; Kaggle CLI/browser chưa đăng nhập. Không tạo
  tài khoản/khóa, không tự chấp thuận điều khoản dataset. Không tìm thấy plugin
  Kaggle/Colab trực tiếp; dùng Colab UI hiện có.
- `scripts/prepare_nes2net_data.py`: public DNU revision ghim, chọn seed42 theo
  hash ID trước inference, giữ train/calib_fit,validation/calib_ltt,test/test_only;
  kiểm metadata người/hash/path, file SHA/native WAV, trùng PCM; resume không
  ghi đè file khác. Bundle allowlist và rehash, chặn symlink thoát thư mục.
- Notebook builder nhúng đúng source/commit/SHA, chặn dirty source, CPU mặc định,
  không Drive mount/token/clone/fit. Bundle luôn calibration_ready=false vì chỉ
  có lớp thật; không dùng VIVOS. Chưa gọi đây là dữ liệu hiệu chỉnh đủ hai lớp.
- TDD RED→GREEN: tests mới, gồm lỗi archive xuất file ngoài manifest/đổi bytes;
  hai ca symlink Windows không tạo được nên chạy trên WSL để xác minh thực.
  WSL:17passed; Windows:15passed,2skip quyền tạo symlink. Ruff check/format đạt.
- Review độc lập downloader và builder không có lỗi chặn. P3 đã sửa: containment
  cho source/runs. P3 còn lại: file embedded có sẵn chỉ so read_text nên normalize
  CRLF; Colab mới ghi LF không bị ảnh hưởng. Chưa mở rộng sửa cho case cũ này.

## Đang thực hiện
1. Commit source sạch, sinh notebook và chạy job thật trên Colab CPU.
2. Kiểm output/report/bundle và nhận bundle về laptop để kiểm độc lập.
3. Full Python regression đang chạy; log/XML cloud-data-python.* tại
   D:/vericlue/tmp/finish-2026-11-01/.

## Câu hỏi cho nhóm / phụ thuộc còn thật
- Chưa có dữ liệu tấn công đủ quyền/reference identities. MLAAD publisher hiện
  gated và chưa có HF cached auth. Không lách gate, không tự nhận quyền clone.
- Chưa thể fit hai lớp/chọn LTT/đánh giá hoặc mở chốt API khi thiếu dữ liệu đó.
- Điện thoại: người dùng xác nhận chưa thể thử trực tiếp; chưa nghiệm thu ba luồng.

## Quyết định và giới hạn
- Dạy/hiệu chỉnh chuẩn bị trên Kaggle/Colab theo ADR0015. Laptop chạy test nhỏ,
  nhận bundle cloud đã kiểm, không tự thu người hoặc tải toàn bộ corpus ở laptop.
- Không push/PR,không tắt máy/xóa account/model/media,không sửa STATUS/thresholds/
  contracts/ADR. Không nâng error/degraded thành đạt.
- Đây là checkpoint kỹ thuật trước chạy thật, kết quả cloud bổ sung sau.
