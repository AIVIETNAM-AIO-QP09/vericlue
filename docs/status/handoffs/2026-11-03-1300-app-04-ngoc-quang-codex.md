# Bàn giao · APP-04 · Ngoc Quang+Codex · 2026-11-03 13:00

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** doing (APP-02/03/04)

Theo yêu cầu người dùng: preset ngưỡng demo cố định, quét CCCD một màn, oval
gọn và thống nhất, giảm việc bắt thu mặt lại không cần thiết. Không thay
contracts/thresholds.yaml/ADR, không tự xóa tài khoản hoặc nới error/degraded.

## Đã xong
- Thêm `MANUAL_DEMO_PRESET=phone-demo-fixed-v1`: PAD 0.70, GenD front 0.95,
  AntiDeepfake 0.70, SyncNet 0.60; cosine danh tính/nhất quán 0.30. Đây là
  lựa chọn kỹ thuật tạm cho demo theo yêu cầu, không fit hoặc báo thành ngưỡng
  đã hiệu chỉnh. Preset bất biến, chỉ chấp nhận explicit full manual; override
  khác preset bị từ chối. Legacy/custom chưa bật preset giữ nguyên.
- Policy mới `ebe8835e33f9e0cdc187bf450a0793b105084d7258509455e71be0923294fed9`;
  worker, phiên và tài khoản tiếp tục dùng cùng cơ chế binding. Review độc lập
  không phát hiện lỗi cần sửa. Chưa áp dụng trên server.
- CCCD: một màn camera chụp và kiểm tra, không điều hướng sang QR-only. Chỉ
  ảnh chụp mới có QR hợp lệ và đúng một chân dung mới được gửi. QR lưu tạm chỉ
  là quan sát UI, không ghép với ảnh mới. Vùng nghi QR có thể kích hoạt ảnh
  độ phân giải cao nhưng không đủ để duyệt hoặc báo đã trích xuất.
- Crop theo CameraX cropRect/rotation và tỷ lệ preview cho live/still; đo độ
  nét/lóa trên chân dung, QR phải giải mã thực. Thử lại crop QR có lề thay zoom
  toàn camera; giữ các cutoff chất lượng. Tự chụp tối đa ba lần/20 giây rồi
  nút chụp ngay cùng màn. Server retry dừng gửi tự động, hiện hướng dẫn tại chỗ.
- Câu chữ: “Đang trích xuất thông tin”, “Đang trích xuất chân dung”. Chỉ đánh
  dấu hoàn tất khi ảnh mới thực sự trích xuất được.
- Tách source guide (camera coordinates) khỏi oval hiển thị; fontsize không
  còn làm đổi vùng tối đa nhận mặt. Oval hiển thị gọn hơn, preview được biến
  đổi cùng oval. Màn đọc dùng cùng source guide và giữ preview trong lúc chuẩn
  bị/ghi âm; vẫn một native camera host, không đổi zoom/output video.
- Tracking ID đã thiết lập nhưng tạm thiếu metadata: coi như thiếu bằng chứng
  thay vì đổi người ngay. Giữ grace 450 ms ngoài adaptive-head, giữ correction
  deadline trong adaptive-head; lọc trước cả controller và hold gate nên không
  cộng tiến độ từ khung thiếu ID. ID khác/multiple faces vẫn bị chặn, không
  hoàn tất khi ID đã thiết lập đang thiếu. Trạng thái ban đầu chưa có ID giữ
  hành vi cũ. Review độc lập không có blocker.

## Đang dở
- Đã tích hợp, review, kiểm render, test/lint, build và cài APK giữ dữ liệu.
  Nghiệm thu những thay đổi UI này trên S24 FE còn chờ người dùng.
- Đã thêm mức lấp đầy tối thiểu hai chiều 65% khi vào / 60% khi giữ vị trí,
  vẫn giữ giới hạn tối đa/toàn mặt và kiểm server. Chưa công bố khoảng cách cm
  hoặc mức giảm cảnh báo giả khi chưa đo máy thật.
- P2 review CCCD đã sửa: dọn/cancel deferred cả khi CameraX từ chối takePicture
  đồng bộ; reviewer đã kiểm lại và xác nhận giải quyết.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Người dùng thử CCCD, framing và preview giọng thật trên APK mới; giữ
   API/policy hiện tại. Không yêu cầu xóa tài khoản để thử đăng ký cùng CCCD.
2. Preset mới chỉ áp dụng sau khi tài khoản cũ hết hạn: đọc lại số account còn
   hiệu lực ngay trước activation, không chỉ dựa vào mốc giờ cũ. Kiểm manifest,
   source, worker handshake/policy; không đổi receipt hoặc account để lách.

## Quyết định, lưu ý, bẫy
- Người dùng đã chọn **giữ tài khoản để thử; áp dụng preset sau khi hết hạn**.
  Read-only DB có một account đang hiệu lực, expires_at 04/11 04:12:57 UTC
  (11:12:57 UTC+7). Giữ API 11df và policy demo GenD 0.90 đang chạy hiện tại.
- Tài khoản gắn policy cũ không dùng được ở policy mới; cùng CCCD còn UNIQUE
  đến natural expiry, nên không hứa chỉ cần đăng ký lại ngay. Không tự xóa,
  backfill, migrate hoặc clear app data.
- Đăng ký/đăng nhập từng đạt; lượt recovery 12:20 qua sáu kiểm tra mặt, riêng
  GenD không đạt. Không coi preset mới hoặc UI test là nghiệm thu khôi phục.
- Giữ OTP mô phỏng; không dùng VIVOS parity/heldout/điểm điện thoại để fit.

## Câu hỏi cho nhóm
- Hiệu chỉnh/đánh giá độc lập và nghiệm thu máy thật vẫn còn; không có số liệu
  chứng minh false alarm giảm hoặc bảo đảm mọi lần quét đều nhận ngay.

## Test đã chạy
- Preset: RED quan sát trước triển khai; **392/392 test liên quan đạt**, gồm
  30 ca mới. Ruff/check-format sạch. Full Python non-slow: **5419 đạt,
  92 bỏ qua, 25 deselected**, exit 0.
- CCCD: **5/5 regression RED** tái hiện portrait-only, QR-only và dữ liệu cũ;
  GREEN tích hợp đã đạt.
- Geometry/voice/tracking: **23 test, 4 RED đúng dự kiến** trước sửa, gồm hai
  tracking-metadata, oval còn lớn và preview giọng biến mất khi chuẩn bị.
- Log kiểm thử ngoài repo trong thư mục scratch của phiên; không commit media,
  dữ liệu, trọng số, cấu hình riêng hoặc ảnh chụp giấy tờ.
- Android cuối: **473 test, 0 failures/errors, 1 skipped** (472 đạt);
  `testDebugUnitTest lintDebug assembleDebug` BUILD SUCCESSFUL. Lint 0 lỗi,
  44 warnings và 6 information. Đã sửa assertion snapshot dùng nhầm tọa độ
  source/display và sai số float; không nới logic sản phẩm để làm test đạt.
- Render face/voice cỡ chữ thường và 200% đã review; đây là ảnh tổng hợp,
  không thay nghiệm thu camera thật. `plan_check`: 0 lỗi, 10 cảnh báo có sẵn.

## Biên nhận triển khai 13:30 UTC+7
- APK nguồn `1f0fc6069765fb7234766cc9f61b2cc63b1e2e3f`, cây Android
  `8ceac4c856eefd0e21e01ae0415371da81252c21`; SHA-256
  `9178eb03de0713302d5201669bfbaf33f09e252a085cb544536664949ec39c87`.
- `adb install -r` Success; hash `base.apk` trên S24 FE khớp. Version 0.3.0
  code 2; lastUpdateTime 03/11 13:29:53, firstInstallTime vẫn 02/11 09:01:50.
  Không uninstall/clear data/mở app hoặc camera tự động.
- Signer/v2 và flags live/signed/trace=false đã kiểm; APK cũ + build-info được
  sao lưu trong bundle riêng trước thay. API vẫn `11dfc7e`, profile SHA giữ
  `c8177427f499c112d9a0290a6906f99e37f6b48c9f11f5a311b6b461be7e02a2`.
- `demo.py check` integrity OK; status ready=true, owned_process=true,
  failed_modules=[]; ADB reverse tcp:8421 hoạt động. Status có tạo một phiên
  tổng hợp ký HMAC để xác nhận server, không phải lượt người dùng nghiệm thu.
- Chưa tạo lịch tự động đổi preset; bước activation còn chờ xác nhận tài
  khoản thực sự hết hạn và kiểm tra lại server/source/binding tại thời điểm đó.
