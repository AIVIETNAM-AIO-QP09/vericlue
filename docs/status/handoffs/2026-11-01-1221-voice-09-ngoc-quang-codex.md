# Bàn giao · VOICE-09 · Ngoc Quang+Codex · 2026-11-01 12:21

**Nhánh:** codex/APP-01-demo-integration; nền bdea478.
**Trạng thái task sau phiên này:** review; parity/gộp offline có code, chưa có
calibrator và nghiệm thu AI thật toàn luồng.

## Đã xong
- Người dùng cho phép bấm Đồng ý Điều khoản Colab; đã bấm và chạy CPU trên
  notebook private, không đổi chia sẻ/mount Drive/GPU/token.
- Cell main khớp notebook sinh sạch, source commit
  140beb55d27e7c4ae2f4bf8883117c7c2a1553e6; script SHA
  52c7a43c04f67893fb109f693a77e27805d07db2e1fbee1465dde7525a1baac5.
- Job đầu tải517/520, ba HTTPError. Colab còn lỗi tải JavaScript hiển thị kết
  quả; reload đã khôi phục được output. Không sửa source hoặc bỏ mẫu lỗi.
  Chạy lại cùng cell, reuse517/tải3, errors=[] và PCM duplicate check passed.
- Đã nhận ZIP114802930byte/527tệp. SHA ZIP
  972aaae1fa8a1da1b1bdf2efed56aa4668e6dce9eb2c8d56ceb9b50463677d74;
  manifest c4fc4b3498c210410a79bd00cc0ba11109cd88784260be18ccc9f43f0584a16b.
  Kiểm allowlist/containment/symlink/SHA mọi tệp trước giải nén vào thư mục mới.
- Bundle: D:/vericlue/data/prepared/vericlue-dnu-bonafide-30ff4361.zip.
  Root: D:/vericlue/data/prepared/nes2net-dnu-bonafide-2026-11-01-30ff4361/.
- Chạy eval prepare độc lập bằng native decoder:520WAV,26nhóm, calib_fit360/
  18người,calib_ltt80/4người,test80/4người; không trùng byte/PCM/người/nguồn.
  Báo attack=0 cả ba phần, calibration_fitted=false. Chưa inference/fit.
- Đã cập nhật research, task card/backlog và notebook README theo kết quả thật.

## Đang dở
- Nguồn MLAAD cần đăng nhập/cấp quyền. Chrome hiện chưa đăng nhập HF, chưa có
  cached CLI auth. Đã mở trang login và hỏi chủ tài khoản tự đăng nhập; chưa
  chấp thuận điều kiện hay chia sẻ thông tin. Không tìm mirror/bỏ gate.
- Chưa có mẫu tấn công/crosswalk người/nguồn/phạm vi clone-VC, chưa fit/LTT/test.
- Android ba luồng not_run do người dùng chưa thể trực tiếp thử; không phải
  lý do dừng phần tự động hóa độc lập. APK/server/migration giữ checkpoint trước.

## Bước tiếp theo
1. Khi chủ tài khoản đăng nhập HF: đọc điều kiện MLAAD, chỉ hỏi xác nhận ở bước
   chấp thuận mới/chia sẻ thông tin cụ thể; quyền Colab không bao gồm bước này.
   Revision30c3dec763fa4803f11c2df1557d3b0828395366. Đọc metadata thực để kiểm
   reference_speaker/original_file; không lấy hệ TTS làm người. Chia nhóm trước đo.
2. Chuẩn bị lớp tấn công trên Colab/Kaggle có quyền/nguồn rõ, cùng protocol xử lý
   hai lớp; chỉ collect/fit khi audit đạt điều kiện, giữ test cho đánh giá cuối.
3. Khi có artifact thật và được kiểm: tiếp tục integration/API theo task; giữ
   error/degraded không đạt cho tới khi đủ bằng chứng. Không thay thresholds,
   contracts hay ADR nếu chưa có task rõ.
4. Khi người dùng cầm máy được: nghiệm thu CCCD/quay mặt/đọc câu cho đăng ký →
   đăng nhập lại → khôi phục. Không gọi ADB/install/health là đã nghiệm thu.

## Quyết định, lưu ý, bẫy
- DNU publisher33b2a469901cb71b243403254d3cfef25170526c, seed42/20mẫu/người,
  native mono16kPCM16. Không đổi mẫu theo điểm hoặc chuyển người test.
- Luôn bonafide_only/calibration_ready=false; không tạo clone hay fit từ bộ này.
  VIVOS32mẫu/9người parity tuyệt đối ngoài hiệu chỉnh.
- Receipt, provenance, audit, notebook lần đầu và screenshot nằm ngoài Git:
  D:/vericlue/tmp/finish-2026-11-01/cloud-data/.
  audit SHA90bf22825b68854472acc34dbbfcc2d27b6cf85668dbe1394126ff37791d4052;
  verification commit bdea478c5ebe95aa912b03f4a3f3c2cfe48064d9,Python3.12.15.
- Colab notebook: https://colab.research.google.com/drive/158imAsNmuj0Eg7O6IoD1-OttUSgOh2IM
  Có thêm cell chỉ in tóm tắt report để xem; không thay main/selection/protocol.
  Đã giữ tab deliverable. HF login đã giữ handoff.
- Download event của browser timeout nhưng ipynb tải thật vào Downloads; đã
  sao lưu ngoài Git. ZIP tải qua files.download thành công, hash khớp phía cloud.
- Không push/PR/xóa account/model/media/tắt máy. Không sửa STATUS. OTP mô phỏng.

## Câu hỏi cho nhóm
- Chờ chủ tài khoản đăng nhập HF để xem điều kiện cấp quyền MLAAD. Chưa có
  bộ attack đủ quyền/mã người, nên không fit/đánh giá hoặc mở chốt AI thật.

## Test đã chạy
- Cloud source đã có full regression ở checkpoint bdea478:4704passed99skipped,
  2warning; WSL17passed,Windows15passed2skip symlink. Lượt này chỉ sửa docs.
- Job Colab CPU thực:520verified,PCM check passed,errors=[] sau resume.
- Kiểm ZIP/all527file hashes/allowlist/containment trước giải nén: đạt.
- `PYTHONPATH=ml/src;services/api/src` rồi native Python chạy:

```text
python -m vericlue_ml.eval.nes2net_utterance prepare --manifest D:/vericlue/data/prepared/nes2net-dnu-bonafide-2026-11-01-30ff4361/manifest.json --data-root D:/vericlue/data/prepared/nes2net-dnu-bonafide-2026-11-01-30ff4361 --output D:/vericlue/tmp/finish-2026-11-01/cloud-data/local-utterance-audit.json
```

Exit0;520mẫu/26nhóm, thiếu attack cả3phần, chưa fit. Không có chỉ số model mới.
Kiểm lại trước commit tài liệu: Ruff sạch, notebook --check và git diff --check
exit0; plan_check0lỗi/10cảnh báo tải công việc/đường găng đã có trước. Không chạy
lại full regression cho các thay đổi chỉ tài liệu của lượt này.
