# Ổn định bước mắt và quay đầu cho demo Android

Ngày rà soát: 30/10/2026. Baseline code: `dab9f6f246180834466290fc08f54b16cf597149`.
Đây là thiết kế bàn giao để người dùng xem và chuyển Gemini thực hiện; chưa phải
bằng chứng đã sửa lỗi hoặc đã nghiệm thu demo.

## Mục tiêu

Tìm và sửa sai lệch có thể tái hiện giữa hướng dẫn Android, video và phép đo
server. Kết thúc bằng APK truy được phiên bản, server dùng đúng mã, báo cáo
theo từng bước và nghiệm thu điện thoại. Không lấy việc unit test xanh làm
bằng chứng lượt thật đã đạt. OTP tiếp tục mô phỏng theo yêu cầu.

## Những gì đã kiểm tra

Nguồn: kết quả DB được giải mã qua SessionPrivacy, đúng runtime local;
không lấy nội dung CCCD/token ra báo cáo. Bốn lượt gần nhất có gaze/head
version lần lượt `gaze-rules@0.2+face-landmarker-f16-1` và
`head-turn-rules@0.1+face-landmarker-f16-1`.

| Lượt tạo, giờ Việt Nam | Mắt | Quay đầu |
|---|---|---|
| 21:17:02 | matched | pose_out_of_range |
| 21:21:00 | trajectory_mismatch | incomplete_time_window |
| 21:38:09 | trajectory_mismatch | incomplete_time_window |
| 21:39:35 | trajectory_mismatch | incomplete_time_window |

- Hai lượt 21:38/21:39: đều có 70 mẫu mắt hợp lệ, coverage khoảng 0,986.
  Correlation x lần lượt 0,443/0,409; y 0,774/0,855. Biến thiên tư thế đầu
  khoảng 2,06°/1,28°. Hỏng trục ngang không đồng nghĩa không có mắt hoặc đầu
  quay nhiều. Không chọn ngưỡng mới từ những lượt này.
- Lượt 21:39: đoạn đầu có 125 quan sát, 105 quan sát pose hợp lệ, 20 no_face;
  khoảng trống 2098 ms từ head+1720 tới head+3818 ms; yaw trước/sau
  -55,5°/-60,8°. Max abs pitch 4,5°, roll 12,3°.
- Lượt 21:17: max abs yaw 60,9°, roll 16,1°. Không gán nguyên nhân của lượt
  này cho mọi lượt sau.
- Chất lượng hình và CamProbe đều pass ở bốn lượt. PAD/GenD/match cùng
  E_LOW_QUALITY; `session_views` từ chối khi head_turn chưa pass. Chưa có
  bằng chứng ba bộ đó đã suy luận thành công ở những lượt này.
- Kiểm load bằng CalibrationStore trong môi trường server: calibrator fitted
  đúng full version video v2 của face_pad và face_deepfake đều unavailable.
  identity_face_calibration và identity_consistency_calibration chưa cấu hình;
  account_enrollment=false. Các chốt này độc lập với sửa UI.

Báo cáo số local: `D:/vericlue/tmp/full-demo-setup/head-assist-comfort/handoff-audit.json`
và `handoff-artifact-audit.json`. Chỉ để chẩn đoán, không phải tập hiệu chỉnh
hay đánh giá độ chính xác/chống tấn công.

## Chưa thể kết luận

1. Góc ML Kit lệch MediaPipe bao nhiêu trên cùng thời điểm của cùng lượt.
   Chưa có trace client đồng bộ; không được tự đặt hệ số nhân/offset.
2. Lỗi mắt ngang do hình học, dấu, đường vẽ thực tế, đồng hồ, ước lượng iris
   hay thao tác/đặc tính quan sát. Correlation hiện có không chứng minh lỗi dấu.
3. Callback CameraX Status được suy ra t0 có sai lệch đủ gây lỗi không.
   Video dài đủ và một mốc luma đổi không chứng minh toàn lịch khớp.
4. Baseline nhìn thẳng, ba ảnh session_views, ngưỡng danh tính và các bước sau
   có đạt hay không khi head_turn đã pass.

## Thiết kế thực hiện

Làm một chuỗi việc có điểm kiểm tra: (1) xác nhận phiên bản và readiness toàn
luồng; (2) chẩn đoán đồng bộ client/video/server; (3) sửa đúng biến đổi/hướng dẫn
có bằng chứng; (4) kiểm chuỗi phía sau; (5) đóng gói và nghiệm thu có giới hạn.
Ưu tiên sửa trong pipeline có sẵn. Chỉ thay provider đo góc trên Android nếu
chứng minh provider hiện tại không đáp ứng và viết bổ sung thiết kế trước.

Trace debug opt-in chỉ gồm thời gian tương đối, phase/segment, tọa độ chấm
được vẽ, pose và tuổi kết quả analyzer. Tắt mặc định, không vào API Signals,
không làm bằng chứng đạt. Phân tích trong RAM; chỉ giữ tổng hợp đã lọc ở tmp
private, không log token/CCCD/ảnh/video/vector. Không dùng dữ liệu diagnostic
làm calib_fit/calib_ltt/test nếu chưa có quyền và protocol riêng.

## Giới hạn bắt buộc

- Không đổi thresholds.yaml, API/contracts, lịch v1/v2 hoặc chốt tài khoản để
  ép pass. Muốn đổi protocol/provider/thiết kế phải đưa bằng chứng và phạm vi
  riêng, không làm âm thầm trong bản sửa số học.
- Không đổi degraded/error thành đạt, không abs(correlation), chọn trục/đoạn
  có lợi, nới góc/gap/lag hay dùng điểm client thay phép đo server.
- Giữ UI A/Be Vietnam Pro, giảm chuyển động, âm báo dịu, CCCD thủ công,
  không sửa iOS/OTP/flow ngoài phạm vi.
- Giữ video liên tục, gốc thời gian và ký media. Không rebind camera theo phase.
- Không sửa `.env`, khóa, DB, xóa dữ liệu app; cài `adb install -r` cùng signer.
- Không push/mở PR. Không sửa STATUS.md. Commit có [APP-01]/[LIVE-02].

## Nghiệm thu

- Test hồi quy tái hiện lỗi trước sửa; positive và negative controls vẫn đúng;
  Android unit/build/snapshot và ML/API liên quan xanh.
- Phiên bản APK/server/manifest model được ghi rõ. Nếu hash cài đặt không
  kiểm được thì ghi chưa kiểm; không lách policy hoặc suy từ tên APK.
- Tối đa ba lượt kiểm có hướng dẫn sau sửa, mỗi lượt ghi kết quả từng module;
  đạt prefix mắt+đầu khi cả hai ok/pass. Không gọi đó là đạt toàn eKYC.
- Đạt toàn luồng chỉ khi API trả pass thực tế trong profile đã công bố và có
  đầy đủ artifact/bằng chứng cho các module bắt buộc. Ghi danh thật là tiêu chí
  riêng; profile OTP demo/account_enrollment=false không chứng minh điều đó.
- Nếu artifact/dữ liệu vẫn thiếu hoặc lỗi chưa có bằng chứng sửa đúng, kết
  thúc với danh sách thiếu chính xác và bản code đã kiểm, không ghi DONE thật.
