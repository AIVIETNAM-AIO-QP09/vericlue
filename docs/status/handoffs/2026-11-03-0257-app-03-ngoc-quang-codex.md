# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-03 02:57

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái:** `doing` — đã triển khai bản sửa, chưa nghiệm thu khôi phục thật.

Đây là trạng thái cuối đợt làm qua đêm, thay các mục “đang chờ” trong bàn giao
00:01, 01:28 và 02:23. Không tuyên bố toàn bộ demo hoặc mọi lỗi đã hoàn tất.

## Đã xong
- Hòa giải main `7cb73ba`, review chéo toàn nhánh và chốt mã chạy
  `fb8c2bf2ad13c45461caeb4d58c85024b66e0e8c`. Draft
  [PR135](https://github.com/AIVIETNAM-AIO-QP09/vericlue/pull/135) đã push;
  **10/10 kiểm tra CI thành công trên commit này**, chưa merge hoặc đóng PR134.
- Sửa chờ phản hồi AI, ACK/phản hồi thiếu, thao tác ghi âm native 10 giây và
  bấm “Đọc xong”, FIT preview, JPEG freshness và mốc trace quay đầu. Giữ
  protocol3 adaptive, binding phiên/artifact/tài khoản và chốt error/degraded.
- Qwen1.7B opt-in chỉ cho manual full demo, pin model xuyên worker, phiên,
  quyết định và quyền ghi danh có giọng. DNU calib_fit18 mẫu/18 người là phép
  so sánh lựa chọn đã khóa trước; không dùng điện thoại, heldout hoặc VIVOS32.
  Số đo và giới hạn ở bàn giao01:28; mặc định sản phẩm vẫn Qwen0.6B.
- Native preload trên **đúng 607 file Git archive** của commitfb8c2bf:
  11 mô-đun nạp được, 0 lỗi, watchdog/child exit0, 59,5 giây, không còn
  tiến trình con sau cleanup. RAM trống thấp nhất1.1927 GiB; peak commit của
  cây tiến trình24.1127 GiB. Đây là bằng chứng nạp/chạy cùng runtime,
  **không phải độ chính xác, độ trễ suy luận hoặc nghiệm thu điện thoại**.
- Đã kích hoạt API snapshotfb8c2bf, bật selectorQwen1.7B trong bundle demo;
  sáu ngưỡng không đổi. Đã sao lưu cấu hình/APK/SQLite nhất quán, kiểm toàn
  bộ hàng DB và byte khóa/media giữ nguyên khi kích hoạt.
- Server thực tế đã khởi động thành công, health `ok`, không failed module.
  Health vẫn có `mock_models=true` vì trường này đọc cờ mặc định toàn API;
  không dùng cờ đó để suy ra detector phiên. Native proof riêng kiểm các
  detector phiên thật và hello/version worker. OTP vẫn mô phỏng.
- **02:57 ngày03/11**: cài đè APK nguồn
  `c64686868a698842cb20d7394b36a97e00bcb67f` lên S24 FE, cùng cây Android
  vớifb8c2bf. Kiểm hash APK trên máy, signer cũ, reverse8421; không mở app.
  Tài khoản và hàng khôi phục khớp bản sao lưu trước triển khai; SQLite
  quick_check đạt. Không gỡ app, reset, đổi khóa hoặc xóa media.
- Đã dừng server do phiên này sở hữu sau kiểm chứng, chuẩn bị tắt máy theo
  yêu cầu người dùng. Bản cài và bundle được giữ để mở lại sáng hôm sau.

## Đang dở
- **Khôi phục/giọng thật chưa đạt nghiệm thu.** Lượt có giọng gần nhất trước
  đợt này không đạt nội dung câu và lipsync. Hai lượt sau preview chỉ tới bước
  yêu cầu giọng trên server rồi APK cũ hết thời gian chờ; không có bản thu mới.
  Chưa có lượt người thật trên APK vừa cài hoặc backend1.7B.
- Frontend landmark106 vẫn chỉ là công cụ đối chứng ngoại tuyến. Đã sửa lỗi
  roundoff FP32 tại biên đổi byte và chạy native lại thành công; một bản ghi
  cố định cho4 cửa sổ/232 khung căn/64 khung chọn. Audio, mel và media gốc
  không đổi. Khác biệt input/model response chưa giải quyết được timing;
  không đủ căn cứ bật frontend này, dịch clock hoặc nới ngưỡng.
- Ngưỡng demo còn tạm, OTP mô phỏng; chưa có bộ giọng thật + TTS/VC đủ quyền,
  mã người/nguồn và chia tập để hiệu chỉnh/đánh giá độc lập. Không dùng kết
  quả trên paper hoặc18 mẫu calib_fit làm số accuracy của hệ thống.

## Bước tiếp theo
1. Sau mở máy, chạy `D:/vericlue/tmp/phone-demo-2026-11-02/START-DEMO.cmd`,
   đợi READY (cold start cho phép tối đa5 phút). Không chạy server checkout cũ.
2. Bật gỡ lỗi Wi-Fi/USB và nối S24 FE. Người dùng chạy `CONNECT-PHONE.cmd`
   để cài giữ dữ liệu/kết nối reverse/mở app, hoặc agent chỉ xác nhận ADB và
   reverse rồi để người dùng tự mở. Địa chỉ/cổng Wi-Fi có thể đổi sau reboot.
3. Người dùng thử khôi phục từ đầu, đọc đủ câu sau “Đang ghi âm”, bấm
   “Đọc xong”, giữ màn kết quả. Đối chiếu đúng APK/API/model/session mới,
   không quy kết lỗi micro khi chưa có log. Không nghiệm thu bằng test tự động.
4. Nếu lipsync còn chặn, tiếp tục đối chứng recipe/clock bằng bằng chứng A/V
   có thời gian tham chiếu. Không chọn offset/crop/ngưỡng theo điểm bản ghi.
   Frontend mới phải có version/calibrator phù hợp trước đề xuất triển khai.
5. Chỉ đưa PR khỏi draft/merge khi nghiệm thu còn thiếu đã được xem xét rõ;
   nhóm chốt dữ liệu có quyền dùng, chia theo người/nguồn trước fit/LTT/test.

## Quyết định, lưu ý, bẫy
- Bundle: `D:/vericlue/tmp/phone-demo-2026-11-02`; API
  `source-fb8c2bf2ad13`, APK `apk/VeriClue.apk`.
- Backup: `revision-backups/before-reviewed-fb8c2bf2ad13`. Không khôi phục
  DB vô cớ; bản hiện hành đã kiểm toàn vẹn và tài khoản giữ nguyên.
- Bằng chứng riêng: `diagnostics/reviewed-bundle-phone-install.json`,
  `diagnostics/reviewed-bundle-final-health.json`, backup`activation.json`;
  preload`D:/vericlue/tmp/asr-comparison-2026-11-03/fullstack-preload-20261103-025030-3452`.
  Không đưa `.env`, DB, video/audio, transcript, ID, điểm cá nhân hoặc trọng
  số vào Git. Báo cáo công khai chỉ ghi count/version/kết luận có giới hạn.
- Qwen1.7B nặng hơn0.6B; preload thành công không đảm bảo mọi tải suy luận
  đều đủ RAM/thời gian. Giữ deadline, không fallback model âm thầm.
- Đăng ký/đăng nhập lại từng có lượt đạt trước đây; không thay nghiệm thu
  bản mới. TaskAPP-03 vẫndoing, APP-11 vẫnreview; STATUS.md không sửa.

## Câu hỏi cho nhóm
- Thu xếp một lượt S24 FE khi người dùng thức; không cần chạy lại nhiều lượt
  liên tục trước khi đối chiếu nguyên nhân theo log.
- Ai cung cấp/duyệt dữ liệu giọng thật + tấn công và nguồn A/V đồng bộ chuẩn
  để kiểm lipsync? Thiếu dữ liệu thì giữ trạng thái chưa hiệu chỉnh/nghiệm thu.

## Test đã chạy
- Python đầy đủ khôngslow tạifb8c2bf: **5329 passed,92 skipped,25 deselected**,
  0 failure/error,397,26 giây. Dùng PYTHONPATH tuyệt đối. Báo cáo riêng
  `diagnostics/overnight-final-python.xml` vàlog.
- Android `recordPaparazziDebug lintDebug assembleDebug assembleDebugAndroidTest`:
  **445 ca,0 failure/error,1 export skip,89 lớp**; lint0 lỗi/44 cảnh báo/5 thông
  tin; APK build thành công, signedMedia/liveByDefault=true,presenceTrace=false.
- RuntimeTorch/Kornia:115 ca frontend/file/RAM sau sửa roundoff đạt. Các nhóm
  hẹp khác chồng lặp với tổng, không cộng số kiểm thử.
- Ruffcheck/format sạch, TypeScript typecheck đạt, OpenAPI sinh không khác;
  plan_check0 lỗi/10 cảnh báo tải và phụ thuộc có sẵn. Guard không có file cấm.
- Review độc lập toàn nhánh không tìm thấy blocker trong runtimeAndroid/API/ML;
  đây là review mã, không chứng nhận mô hình. Native frontend và fullstack được
  kiểm riêng như trên; kiểm triển khai/cài máy không thay lượt người dùng.
