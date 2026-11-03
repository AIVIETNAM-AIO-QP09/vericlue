# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-03 09:24

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái:** `doing` — người dùng yêu cầu tiếp tục sau tạm dừng; khôi phục chưa nghiệm thu.

## Đã xong
- Đọc lại bàn giao và giữ nguyên hai file sửa dở. Sửa `session_views`: lỗi
  timeout/decode/internal từ kiểm tra quay đầu bên trong giữ đúng mã/trạng thái,
  không bị đổi thành `degraded/E_LOW_QUALITY`. `ERROR` thiếu mã thành
  `E_INTERNAL`; `OK` kèm mã lỗi bị từ chối. Không đổi nhánh thành công hoặc
  fallback chất lượng khi chuyển động thực sự không đạt.
- Test kiểm cả PAD/GenD: lỗi trước chọn khung không gọi backend, không sinh
  score/probability và không thành pass. Vì API chỉ cho thử lại với lỗi chất
  lượng cụ thể, timeout không còn bị hiểu nhầm thành trường hợp đó.
- Review độc lập và nhóm kiểm thử liên quan đạt. Không sửa ngưỡng, model,
  contracts, mặc định TTL hoặc APK. GenD alignment sửa trước vẫn giữ nguyên.
- Đọc phép đối chứng riêng đã hoàn tất trước lúc tạm dừng: trên đúng video
  08:37, head và hai lần `session_views` tuần tự đều chạy được; lease đã thu
  hồi, media gốc giữ nguyên. Chưa chứng minh nguyên nhân ở lúc chạy đồng thời.
- Hoàn tất phép đo v2 **chỉ phần mặt**, trên API `f3305b2`, một đầu vào cố định,
  ba lượt theo thứ tự 9 → 1 → 9 worker. Thời gian nhóm mặt lần lượt
  **20,753 / 25,703 / 21,461 giây**; thời gian trả kết quả gồm bước match
  **28,192 / 33,504 / 31,219 giây**. Các mô-đun trả `status=ok`, `error=null`;
  đây là trạng thái thực thi, không phải kết luận chấp nhận người thử.
  Phần face-only của bản JSON công khai đã được root review:
  [`APP-03-face-scheduling-2026-11-03.json`](../results/APP-03-face-scheduling-2026-11-03.json).
- V2 có một lần preload **12,151 giây**, không warmup thêm. Thứ tự cố định
  chưa loại ảnh hưởng cache/warmup; ba lượt dùng lại cùng một đầu vào, không
  phải ba mẫu accuracy độc lập. Voice/Qwen, lipsync và continuity không được
  nạp nên chưa tái hiện áp lực RAM/luồng của server đầy đủ. **Giữ 9 worker**;
  chưa đổi cấu hình theo phép đo này.
- Đã hoàn tất phép đo **full preload** trên cùng API `f3305b2` và cùng một
  đầu vào: nạp đủ **11 mô-đun**, hai nhóm worker giọng thực resident. Preload
  **51,378 giây**; một lượt **9 worker** có nhóm mặt **22,672 giây**, trả kết quả
  gồm match **31,558 giây**. Bảy mô-đun được suy luận đều `status=ok`, `error=null`;
  lease được nhả, tiến trình sở hữu đã thu hồi, nguồn/đầu vào giữ nguyên.
  **Không suy luận giọng**: các worker đó chỉ được nạp và giữ resident.
- Timeout cũ **không tái hiện trong điều kiện của lượt full-preload này**;
  chưa xác định nguyên nhân hoặc chứng minh sự cố đã được sửa. Chỉ có một lượt
  full-preload, không loại ảnh hưởng cache/thứ tự/tải nền khi so với face-only,
  không phải thử tải đồng thời hoặc đánh giá accuracy. Giữ **9 worker**.
  Cả hai phần của JSON đã được root đối chiếu với bằng chứng riêng và review.
  Không công bố tổng RAM từ counter trong tiến trình con: kiểm lại cho thấy
  counter chỉ quan sát một tiến trình, không bao phủ toàn bộ worker.
- Bản sửa mã lỗi `11dfc7e` đã có đủ 10 CI thành công; receipt đã được root duyệt,
  snapshot bất biến đã kích hoạt. Mọi hàng DB, khóa/media, profile và APK giữ
  nguyên qua activation; backup tại `revision-backups/before-api-only-session-views-11dfc7ec6a85`.
  Các phép đo phía trên thuộc `f3305b2`, không phải bản sửa mới.
- Server API `11dfc7e` READY lại; kiểm HTTP lúc **09:55 ngày 03/11** xác nhận
  health không module lỗi, đúng instance/policy ký, challenge180/token300.
  S24 FE còn kết nối ADB, reverse8421 đã kiểm; không cài APK hay tự mở app.
  Receipt riêng: `diagnostics/session-views-live-safe-20261103.json`.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Lượt 08:39: nhóm mặt dùng khoảng 83,879 giây, bước match chỉ còn khoảng
  6,209 giây trong ngân sách chung rồi timeout; GenD cũng không đạt ngưỡng.
  Thiếu dữ liệu hiệu chỉnh vẫn là giới hạn riêng, không lấy lượt này để chọn ngưỡng.
- Các phép đo face-only/full-preload đã xong; vẫn chưa tái hiện được timeout
  cũ hoặc chứng minh nguyên nhân. Còn nghiệm thu thực tế phần giọng/khôi phục;
  kết quả đo ngoại tuyến và health sau activation không thay bước này.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Khi người dùng thử lượt mới, đối chiếu đúng phiên và mã lỗi; không yêu cầu
   quay lặp chỉ để tìm lượt đạt. Nếu timeout lặp, lấy thời gian hàng đợi/native
   và tải máy ở chính lượt đó trước khi đổi cấu hình.
2. Giữ 9 worker và các ngưỡng; GenD fail vẫn là chốt độc lập, cần dữ liệu hiệu chỉnh.
3. Giữ server/máy bật cho người dùng thử; không chạy lệnh tắt máy cũ.
4. Giữ PR135 draft/chưa merge và APP-03 doing khi recovery chưa đạt.

## Quyết định, lưu ý, bẫy
- Mã đang chạy trước phiên này: API `f3305b2`, APK `c646868`, profile riêng
  challenge180/token300/max900. Thay đổi profile trước chỉ áp dụng challenge
  mới; không hồi sinh phiên đã hết hạn. OTP vẫn mô phỏng.
- Không suy từ `E_LOW_QUALITY` cũ rằng người dùng quay sai: lớp bọc cũ có
  thể che lỗi hạ tầng. Gaze mismatch và GenD fail là chốt độc lập, không được bỏ qua.
- Không dùng phone/VIVOS32/heldout để fit hoặc chọn model/crop/ngưỡng.
- Bằng chứng riêng nằm ở `D:/vericlue/tmp/gend-parity-2026-11-03` và
  `D:/vericlue/tmp/landmark-repeatability-2026-11-03`; không commit media,
  điểm cá nhân, template, khóa hoặc profile.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Vẫn cần dữ liệu có quyền dùng, mã người/nguồn, tách tập và hiệu chỉnh đúng
  phiên bản. Mã chạy đúng upstream không đồng nghĩa đủ độ chính xác cho eKYC.

## Test đã chạy
- RED trước sửa: 14 lỗi/10 đạt; GREEN sau sửa: 106 đạt (bằng chứng JUnit ở vùng riêng).
- Kiểm lại lúc tiếp tục: 261 đạt ở nhóm ML selection/head/landmarks và API
  capture retry/session guards/manual demo/deadline; 45 đạt ở các caller match/
  calibration. Tổng 306 ca không lỗi, không bỏ qua; không cộng với các lượt
  test trước vì chồng lặp. JUnit khóa hash nguồn trong receipt riêng.
- Ruff check sạch, format 934 file không cần đổi; review độc lập không blocker.
- Helper triển khai API mới: 30 test đạt; benchmark JSON/containment: 10 test
  đạt qua các lượt riêng, gồm chấm dứt cây tiến trình normal/failure/timeout
  và giữ lease khi chưa xác minh đã thu hồi tiến trình. Không cộng vào 306 test sản phẩm.
- Kiểm lần cập nhật tài liệu: `plan_check` 0 lỗi, 10 cảnh báo có sẵn.
