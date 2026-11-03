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

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Lượt 08:39: nhóm mặt dùng khoảng 83,879 giây, bước match chỉ còn khoảng
  6,209 giây trong ngân sách chung rồi timeout; GenD cũng không đạt ngưỡng.
  Thiếu dữ liệu hiệu chỉnh vẫn là giới hạn riêng, không lấy lượt này để chọn ngưỡng.
- Đang chuẩn bị phép đo CPU với lịch chạy 9 → 1 → 9 worker, cùng input/mô hình/
  cutoff/ngân sách. Chỉ đo thời gian và lỗi; không chọn cấu hình theo việc
  người thử được chấp nhận. Chạy riêng phần mặt nên không thay nghiệm thu
  bộ server có cả worker giọng hoặc điện thoại thật.
- Server hiện dừng để đo ngoại tuyến; chỉ bật lại sau triển khai/kiểm chứng.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Chốt CI và triển khai bản sửa mã lỗi bằng snapshot bất biến, giữ DB/khóa/media/APK/profile.
2. Review rồi thực hiện phép đo lịch chạy; chỉ đổi cấu hình khi có bằng chứng.
3. Khởi động kiểm server và ADB; báo rõ phần nào đã kiểm, phần nào còn chờ người thử.
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
