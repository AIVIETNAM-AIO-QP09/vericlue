# Bàn giao · APP-01 / LIVE-02 · Ngoc-Quang+Codex · 2026-10-30 23:25

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Người dùng yêu cầu Codex làm trực tiếp thay Gemini; tiếp tục plan presence stabilization, giữ các commit trước.
- Sửa lỗi đã tái hiện bằng test: chuỗi analyzer frame đến trễ nhưng timestamp vẫn liên tục có thể báo giữ đủ. Giờ tuổi frame >300ms/future/đoạn cũ bị loại, giao diện kiểm lại tuổi mỗi100ms và nhắc giữ yên khi kết quả cũ, không thúc quay thêm.
- Nối một trace dùng chung CameraSession → App → FaceTimelineScreen → TurnHeadContent; ghi raw pose ở capture/receive clock, phase đúng frame, hướng dẫn thật và chấm lúc draw. Build flag vericlue.presenceTrace tắt mặc định/release; chỉ bản diagnostic bật.
- Gắn SHA256 challenge_id để ghép đúng attempt, không xuất identifier nguyên bản hoặc dùng trace làm input quyết định. Thêm CLI compare_presence_trace.py: giữ retention guard trước decrypt, nạp model theo settings, lease luôn release, so capture time, kiểm cả Hold/Completed. Report chỉ số tổng hợp kèm commit/version/hash.
- Cache JSON private có giới hạn, không media/CCCD/token/key/vector. Xóa khi bỏ lượt/rút đồng ý/lượt mới, timer prune15phút và prune khi khởi tạo. Media ACK giữ lại file để chẩn đoán; explicit callbacks được kiểm lại.
- Review độc lập xác nhận sửa retention, model root, đủ trạng thái xanh và vòng đời cache; không còn phát hiện cần sửa trong phạm vi review.
- Sửa test ChromaPulse cũ: version2 đã hợp lệ nên invalid-case dùng3; thêm positive1/2. Không thay protocol hoặc logic sản phẩm ML.

## Lượt thật và giới hạn kết luận
- Lượt tạo23:25:55 ngày30/10 (UTC+7), chạy APK diagnostic đầu: gaze0.3 ok/pass; head125/125 pose hợp lệ, không mất mặt, max abs yaw47,0°, pitch11,7°, roll16,2°. Tám mẫu roll>15° tại head+6356..7055ms, head_turn pose_out_of_range.
- Có tiến triển so lượt cũ nhưng prefix vẫn chưa pass đầy đủ. Không hứa xác minh toàn luồng.
- File trace lượt này bị xóa khi media ACK do hai method reference camera::deleteVideo bị bỏ sót. Đã thừa nhận với người dùng, tái hiện cache regression đỏ, sửa hai ACK callback thành preserveDiagnostics=true; drop/withdraw vẫn xóa. Không khôi phục được trace đã mất, chưa chứng minh lệch ML Kit/MediaPipe.
- Người dùng mệt; không yêu cầu thử lặp tiếp. Bản cuối đã cài Success, chờ một lượt paired khi người dùng sẵn sàng. Không ghi đã nghiệm thu cache/pairing trên điện thoại.

## Đang dở
- Nguyên nhân cảnh báo roll trên app chưa giúp tránh roll>15 của server: chưa đủ cặp số đo đúng thời điểm để kết luận. Không tự nhân hệ số hoặc hạ ngưỡng.
- Artifact fitted video v2 PAD/GenD và match/consistency còn thiếu; ACCOUNT_ENROLLMENT=false. Mắt/đầu pass không tự hoàn tất toàn eKYC. SEC-09 lưu mẫu và đánh giá độc lập chưa hoàn tất.

## Bước tiếp theo
1. Khi người dùng sẵn sàng, một lượt mới bằng bản cuối và giữ nguyên màn kết quả; lấy private cache/presence-debug.json trước khi thoát/lượt mới/hết15phút.
2. Theo docs/runbooks/presence-phone-diagnostics.md, ghép attempt bằng digest và chạy compare CLI. Chỉ sửa phép đo/feedback tiếp khi có bằng chứng; không chọn ngưỡng trên mẫu chẩn đoán.
3. Kiểm artifact/dữ liệu hợp lệ độc lập nếu mục tiêu pass toàn luồng. Không ép pass/error/degraded hoặc tạo calibrator giả.

## Quyết định, lưu ý, bẫy
- Không đổi thuật toán mắt0.3, ngưỡng server, contracts, ADR, OTP, data/api hoặc flow. Các thay đổi capture chỉ là freshness/diagnostic/cleanup.
- Không mở app hoặc quét/chụp thay người dùng. Không uninstall/clear dữ liệu. Server không cần restart vì không đổi runtime ML/API.
- Không push/PR. Trace/model/ảnh/video/.env/khóa chỉ local ignored; tuyệt đối không commit.

## Test đã chạy
- TDD delayedAnalyzerFramesCannotCompleteAHold:14test/1fail trước sửa; sau sửa suite xanh.
- Bốn regression Python review đỏ rồi xanh; cache ACK regression2test/1fail trước sửa rồi xanh.
- testDebugUnitTest assembleDebug -Pvericlue.presenceTrace=true:182tests,0fail/error/skip; CitizenCopyTest, ThemeAccessibilityTest qua. BUILD SUCCESSFUL.
- recordPaparazziDebug --tests '*FaceChallengeSnapshotTest*' cùng flag:BUILD SUCCESSFUL;54 ảnh trước/54 ảnh sau,0 khác. UI không đổi giữa snapshot và bản cleanup cuối.
- Full Python lần đầu:4537pass/80skip/1fail do test version2 cũ. Sau sửa test:4544pass/80skip,2warning dependency/fixture cũ; log/JUnit local.
- Ruff3file Python thay đổi: sạch. plan_check:0lỗi,10cảnh báo cũ. git diff --check sạch.
- APK signer SHA256822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75; adb install -r Success trên SM_A526B. APK bản cuối SHA256d8140b9101807913cd2d5a8e1745ea90ea30ba528fbcf2d28e7e33d38c79b83f.
- Evidence local D:/vericlue/tmp/full-demo-setup/presence-stabilization/codex-*; bản đầu bf03766c... khác bản cuối, không nhập nhằng nghiệm thu. Không kiểm hash base.apk trên điện thoại.

## Câu hỏi cho nhóm
- Chưa có dữ liệu/artifact để cam kết full demo thật trong phiên này. Cần cung cấp nguồn có quyền, đúng protocol/chia theo người; không dùng clip chẩn đoán để fit/chọn ngưỡng.
