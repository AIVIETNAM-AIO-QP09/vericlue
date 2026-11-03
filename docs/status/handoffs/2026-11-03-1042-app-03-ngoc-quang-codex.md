# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-03 10:42

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** doing

**Cập nhật tiếp sau lượt 10:57:** người dùng yêu cầu cụ thể đổi ngưỡng demo
GenD từ **0.70 lên 0.90** sau khi xem điểm của lượt thất bại. Chỉ áp dụng ở
profile riêng ngoài Git; đây là điều chỉnh vận hành dựa trên phản hồi demo,
không được coi lượt này hoặc lượt thử tiếp theo là đánh giá độc lập của ngưỡng.
Policy mới `10fa514309e87974436834d1ede342657e2e72d694132038a96c3fa8394ccbb3`.
Helper kiểm Settings chỉ khác `manual_demo_gend_max`, sao lưu cấu hình 0.70;
đối chiếu mọi dòng DB/khóa/media/source/APK đều giữ nguyên khi apply. Ruff sạch,
7 kiểm tra tổng hợp ở biên 0.90 và error/degraded/error_code/NaN/gate fail đạt.
Receipt riêng: `diagnostics/gend-demo090-20261103`; lúc **11:08** server ready,
health không có mô-đun lỗi, phiên HTTP có chữ ký đúng policy mới; ADB reverse
8421 hoạt động. Chưa có lượt người dùng trên policy 0.90. Không sửa
GenD/model/default repo, không đổi kết quả phiên cũ. Plan check: 0 lỗi,
10 cảnh báo hiện có; diff check sạch.
Các mục 0.70 bên dưới là lịch sử, không phải cấu hình mới nhất.

**11:18 — ba lượt trên policy 0.90:** người dùng xác nhận đăng ký và đăng nhập
đạt; DB xác nhận onboarding bắt đầu 11:10:09 `pass`, reauth 11:13:41 `pass`.
Recovery 11:15:15 kết thúc `review`: mọi kiểm tra mặt, nội dung câu đọc,
voice_spoof và face_continuity đạt; **lipsync degraded/unclear**. Đối chiếu
`ManualDemoThresholds._voice_valid` cho thấy điều kiện `splice_flags == 0`
không đạt; version/policy đúng, offset/confidence/score có miền giá trị hợp lệ.
Đây là cờ từ căn chỉnh âm thanh, chưa chứng minh bản thu thực sự bị cắt ghép.
Không nới chốt này. Tài khoản còn tồn tại, recovery chưa commit thay khóa.
Chi tiết lọc: `diagnostics/gend-demo090-20261103/flows-latest-safe.json`.

## Đã xong
- Lượt đăng ký chẩn đoán lúc 10:29–10:31 ngày 03/11 qua 6/7 kiểm tra mặt;
  riêng GenD trả `ok/fail`. Không có lỗi hạ tầng trong lượt này. Không suy ra
  ánh mắt đã sửa dứt điểm hoặc đồng hồ video đã được chứng minh đúng từ một lượt đạt.
- Đã lấy trace riêng tư, kiểm ràng buộc đúng phiên/APK; sau đó cài lại APK thường
  bằng `install -r`, tắt ghi trace. API `11dfc7ec6a85`, APK `c64686868a69` vẫn giữ.
- Theo yêu cầu mới của người dùng, cấu hình demo riêng đổi
  `MANUAL_DEMO_GEND_MAX=0.50` thành `0.70`. Đây là lựa chọn vận hành tạm để thử
  demo, không phải ngưỡng được hiệu chỉnh hoặc kết quả đánh giá. Không đọc điểm
  từng mẫu điện thoại để chọn giá trị và không dùng dữ liệu test/VIVOS parity để fit.
- Policy mới `c85a8aec5b75fd6561573c649153b262b9e2150193c53f870e6ff3d5e1629c4f`;
  profile và build-info đã cập nhật cùng nhau. Settings chỉ khác trường ngưỡng
  GenD. Mã sản phẩm, ngưỡng mặc định trong repo, APK, mô hình, các chốt khác không đổi.
- Có bản sao cấu hình trước đổi; đối chiếu khi server dừng xác nhận mọi dòng DB,
  khóa, media và source/APK giữ nguyên. Không khôi phục tài khoản hết hạn, không
  đổi kết quả phiên cũ. Chi tiết riêng tư ở bundle ngoài Git, thư mục
  `diagnostics/gend-demo070-20261103` và `revision-backups/before-gend-demo070-20261103`.
- **10:54:** server ready, health không có mô-đun lỗi; phiên HTTP mới được kiểm
  chữ ký và đúng policy 0.70. ADB reverse 8421 trên S24 FE hoạt động. Probe tạo
  phiên tổng hợp rỗng, không được nhầm thành lượt người dùng.

## Đang dở
- Lượt điện thoại bắt đầu **10:57:15** đã dùng đúng policy 0.70: 6/7 kiểm tra
  mặt đạt, riêng GenD `ok/fail`, điểm góc thẳng vượt 0.70; đủ ba góc và đúng
  mã policy hiện hành. Không có error_code trong bảy mô-đun. Phiên đăng ký
  kết thúc `review`, chưa yêu cầu giọng. Chưa nghiệm thu ba luồng; không tự tăng
  tiếp ngưỡng từ điểm của lượt này. Báo cáo lọc ở `latest-attempt-safe.json`
  trong thư mục chẩn đoán riêng nêu trên.
- GenD chưa có artifact hiệu chỉnh phù hợp `align-upstream-numpy-v2`. Bàn giao
  21/10 có nhắc gói `gend-calibration/20261021_1310`, nhưng chưa tìm thấy tại máy này.
  Bộ chia RTFS cũ theo video nguồn/ảnh donor chưa chứng minh tách theo người.
- Collector metadata RTFS v2 đã được subagent chuẩn bị riêng, chưa được root
  duyệt/chạy; chưa tải dữ liệu và chưa fit.

## Bước tiếp theo
1. Người dùng bắt đầu lượt đăng ký mới; phiên cũ không đổi policy. Ghi kết quả
   là thử demo, không đưa vào số liệu đánh giá khả năng phát hiện giả mạo.
2. Khôi phục nguồn dữ liệu/gói cũ hoặc chuẩn bị dữ liệu được phép dùng, kiểm
   chia theo người, rồi mới hiệu chỉnh và đánh giá độc lập phiên bản hiện tại.

## Quyết định, lưu ý, bẫy
- Ngưỡng 0.70 có thể làm tăng khả năng bỏ lọt deepfake. Không bảo đảm người thật
  sẽ qua; tuyệt đối không coi error/degraded là pass. Không thay bằng bypass.
- Tài khoản trước đây đã hết thời hạn lưu 24 giờ lúc 09:58 ngày 03/11; việc
  đăng ký lại là do retention, không phải APK cài đè làm mất tài khoản.
- PR135 vẫn draft, chưa merge; task không được đánh dấu done.

## Câu hỏi cho nhóm
- Nhóm còn gói GenD ngày 21/10, splits và nguồn gốc dữ liệu không? Chưa nhận được
  đường dẫn; không coi việc thiếu gói tại máy này là bằng chứng chưa từng hiệu chỉnh.

## Test đã chạy
- `pytest ml/tests/test_manual_demo.py -q` trên source API đang triển khai,
  với PYTHONPATH đúng source: **11 đạt**. Lần gọi đầu dùng môi trường mặc định
  lỗi import do trỏ bản package cũ; đã chạy lại đúng source thành công.
- **7 kiểm tra tổng hợp** trên policy ứng viên: ngưỡng đúng 0.70 chấp nhận,
  vượt 0.70 từ chối; error/degraded/error_code/NaN/gate fail đều từ chối.
- Ruff helper cấu hình sạch; review độc lập không có blocker cho lần chạy
  Python không tối ưu hóa. Hash phụ thuộc dùng assert nên không được chạy `-O`.
- Hai lần apply đầu dừng trước ghi cấu hình: cache pytest thêm vào source, rồi
  lệnh shell chứa tên source bị nhận nhầm là process đang chạy. Cache được chuyển
  ra thư mục chẩn đoán; lần apply riêng thành công, kiểm bảo toàn dữ liệu đạt.
- `plan_check.py`: 0 lỗi, 10 cảnh báo tải/lịch hiện có. `git diff --check`: sạch.
