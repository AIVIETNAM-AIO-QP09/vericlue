# Nghiệm thu eKYC sau bản tích hợp 01/11/2026

Phạm vi Android, API và mô hình; OTP vẫn mô phỏng. Không coi test phần mềm,
parity số học hoặc màn thành công là số liệu chống giả mạo.

## Đã có trên máy

- Code consent lưu mẫu tách biệt, biên nhận/migration0011 và nhãn `manual_full_demo`.
- Hai môi trường WSL: `/home/ngocquang/nes2net-hf-parity` (Python3.12, HF4.57.6,
  torch2.2.2CPU) và `/home/ngocquang/nes2net-fairseq-ref` (Python3.10, Fairseq0.12.2,
  torch2.2.2CPU). Không dùng Python3.10 import `vericlue_ml`.
- XLS-R gốc và checkpoint NES2Net trong `D:/vericlue/models/selected-2026-10-24`.
- VIVOS publisher revision `3cbfb2502e5e84776b4b778b020a09759f723f52`, tải bằng
  downloader repo; 32 PCM duy nhất/9 speaker chọn cho parity tại
  `D:/vericlue/data/diagnostics/nes2net-parity-vivos/`. Chỉ kiểm tra hai cách
  triển khai trên cùng đầu vào. VIVOS vẫn test-only cho việc chọn model/ngưỡng;
  không biến dữ liệu này thành calib_fit.
- Log/test/screenshot và báo cáo parity tại `D:/vericlue/tmp/finish-2026-11-01/`.

Lệnh parity và cách dựng môi trường: [README parity](../../ml/scripts/README-parity-nes2net.md).
Đọc báo cáo thực tế; không suy kết quả PASS từ việc có đủ file trên ổ đĩa.
Lượt source `52cebaf` trên32 WAV/9 speaker với Torch2.2.2/cùng4 threads đã PASS
(max margin diff `2.47955322265625e-05`,32/32 cùng dấu). Hai lượt trước khác
số threads không đạt vẫn được giữ để truy vết. Không suy kết quả này thành
chất lượng chống giả giọng hoặc giấy phép mở chốt khi thiếu hiệu chỉnh.
Runtime Windows Torch2.14.1CPU/HF4.57.6 cũng đã đo trên cùng32 PCM/hash và logits
Fairseq4threads: PASS, max margin diff `7.271766662597656e-05`,32/32 cùng dấu;
xem `nes2net-parity-windows.json`. Đã nối bằng chứng có binding runtime/config/
source (01/11) và công cụ gộp offline riêng; vẫn cần dữ liệu/hiệu chỉnh trước
khi thay đổi đường quyết định. Marker parity không nâng trạng thái diagnostic.

## Phần dữ liệu vẫn cần

Đã có công cụ offline đo/gộp max margin toàn câu có version riêng và kiểm
manifest/split/CV theo người/nguồn: [runbook](nes2net-utterance-calibration.md).
Người giao việc xác nhận dữ liệu chưa được chuẩn bị; chưa có artifact fit thật.
Nguồn publisher/revision và phần cần nhận/tải: [ghi chú](../research/2026-11-01-voice-calibration-prep.md).

| Mô-đun/giao thức | Dữ liệu và bằng chứng cần giữ |
|---|---|
| PAD/GenD phiên video | Video thật/tấn công có nhãn, đúng lịch challenge thực sự đã phát (dynamicv2/12giây), `subject_id` và liên kết nguồn; không dựng lịch để hợp thức hóa video cũ |
| Đối chiếu CCCD/mẫu ghi danh | Cặp cùng người/khác người có quyền sử dụng; đúng preprocessing LVFace, khung chính diện và protocol tương ứng |
| Nhất quán nhiều góc/continuity | Video mặt/giọng cùng phiên, nhãn đổi danh tính nếu có, lịch và offset AV thực tế; tách người/nguồn giữa các split |
| NES2Net | Giọng thật và TTS/VC có quyền sử dụng, nhãn/nguồn/người; quy tắc gộp cửa sổ được kiểm chứng trước fit calibrator |
| SyncNet | Video nói khớp và không khớp có quyền sử dụng, offset AV/PTS và câu đề bài; giữ protocol `session-offset-v1` |

Tách theo người/nhóm nguồn liên quan thành `calib_fit`, `calib_ltt`, `test`.
Fit/chọn phương pháp trên calib_fit, chọn ngưỡng theo quy trình LTT trên
calib_ltt; khóa trước đánh giá test. Ghi mẫu lỗi/loại trừ, không chỉ giữ lượt đạt.
Không đủ cỡ mẫu để kết luận thì ghi rõ, không tự ghi số accuracy.

Đo PAD/GenD và fit: [session-face-calibration.md](session-face-calibration.md).
Các entry point có thật trong repo (đọc `--help` trước khi dùng):

```powershell
$py = 'D:\vericlue\tmp\session-api-runtime\Scripts\python.exe'
$env:PYTHONPATH = 'ml/src;services/api/src'
& $py -m vericlue_ml.eval.session_calibration --help
& $py -m vericlue_ml.eval.video_face_match --help
& $py -m vericlue_ml.eval.face_continuity --help
```

Hai entry point đối chiếu/continuity là **diagnostic**, không tự sinh ngưỡng LTT
cho mọi giao thức tài khoản. Không dùng các tên script `measure_video_face_match.py`
hoặc `fit_identity_thresholds.py` không tồn tại được ghi trong báo cáo cũ.
Artifact phải khớp version thực từ detector; không dùng MiniFASNet thay FS-VFM,
artifact ảnh thay video, hay gắn lại version vào ngưỡng của giao thức khác.
`ml/configs/thresholds.yaml` vẫn provisional; chốt chính sách ROUT-03 trên dữ liệu
phù hợp trước khi gọi hệ thống đã hiệu chỉnh. Không đổi file này trong phiên này.

## Điều kiện nghiệm thu thiết bị

1. Backup DB/khóa bằng quy trình vận hành, áp migration0011 trước server mới.
   Tài khoản cũ thiếu biên nhận không được tự gán đồng ý; không xóa/đăng ký đè.
2. Dùng APK/server cùng phiên bản, đúng alias ký; cài đè, không gỡ/xóa dữ liệu.
   Môi trường thử nghiệm đặt `SECURITY_PROFILE=synthetic`, `SIMULATED_OTP=true`.
   Mã OTP là mã được hiển thị cho lượt gửi, không mặc định `123456`.
3. Đăng ký: hai lựa chọn đồng ý bỏ chọn ban đầu; thiếu quyền lưu mẫu không tạo
   tài khoản. Kiểm CCCD/mặt, receipt lưu bền, rồi đăng xuất/mở lại/đăng nhập.
4. Recovery: dùng binding tài khoản, OTP, mặt và giọng đúng chốt; không đổi khóa
   trước khi đủ điều kiện. Thử sai người, sai câu, không khớp môi và hết hạn.
5. Thử trùng CCCD, rút đồng ý, mất mạng, tắt/mở app và khôi phục tiến trình.
   Giữ tài khoản cũ khi lượt mới lỗi; không hiện thành công nếu receipt chưa lưu.

Chỉ ghi luồng nào đã thực sự nghiệm thu; không dùng detector giả hoặc hạ chốt
để quay đủ màn. Bản ngưỡng thủ công luôn mang nhãn thử nghiệm và không thay
thế các artifact/đánh giá còn thiếu.
